"""FastAPI HTTP 层,专门给 web-frontend 用。

启动:
    uvicorn web.api:app --reload --port 8000

依赖:
    pip install fastapi uvicorn
"""
from __future__ import annotations

from typing import List, Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from core.embedding import EmbeddingError, embed
from core.llm import LLMError
from core.utils import EMBED_MODEL, INDEX_FILE, RAW_DIR, WIKI_DIR, log
from pipeline.index import build_index
from pipeline.query import _retrieve, answer_question

app = FastAPI(title="Wiki-RAG API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------- schemas ----------

class HistoryItem(BaseModel):
    role: str
    content: str


class QueryReq(BaseModel):
    question: str
    top_k: int = 3
    refine: bool = True
    history: Optional[List[HistoryItem]] = None


class DebugReq(BaseModel):
    question: str
    top_k: int = 5


# ---------- helpers ----------

def _serialize_hits(top) -> list[dict]:
    return [
        {
            "source": chunk.get("source", "?"),
            "text": chunk.get("text", ""),
            "score": float(score),
        }
        for score, chunk in top
    ]


# ---------- routes ----------

@app.post("/api/query")
def api_query(req: QueryReq):
    """完整的 RAG 问答:返回最终答案 + 命中段落。"""
    try:
        top, _ = _retrieve(req.question, req.top_k)
    except (FileNotFoundError, RuntimeError) as e:
        return {"answer": f"[索引未就绪] {e}", "hits": []}
    except EmbeddingError as e:
        return {"answer": f"[embedding 失败] {e}", "hits": []}

    try:
        answer = answer_question(
            req.question, top_k=req.top_k, refine=req.refine
        )
    except LLMError as e:
        answer = f"[LLM 调用失败] {e}"
    except Exception as e:  # noqa: BLE001
        log.exception("answer_question failed")
        answer = f"[未知错误] {e}"

    return {"answer": answer, "hits": _serialize_hits(top)}


@app.post("/api/debug")
def api_debug(req: DebugReq):
    """调试用:只做检索 + 暴露 embedding 元信息。"""
    try:
        top, _ = _retrieve(req.question, req.top_k)
        q_emb = embed(req.question)
    except (FileNotFoundError, RuntimeError) as e:
        return {
            "hits": [],
            "embedding": {
                "dim": 0,
                "cached": False,
                "preview": [],
                "model": EMBED_MODEL,
            },
            "topK": req.top_k,
            "error": str(e),
        }
    except EmbeddingError as e:
        return {
            "hits": [],
            "embedding": {
                "dim": 0,
                "cached": False,
                "preview": [],
                "model": EMBED_MODEL,
            },
            "topK": req.top_k,
            "error": f"embedding error: {e}",
        }

    return {
        "hits": _serialize_hits(top),
        "embedding": {
            "dim": len(q_emb),
            "cached": True,
            "preview": [float(x) for x in q_emb[:8]],
            "model": EMBED_MODEL,
        },
        "topK": req.top_k,
    }


@app.get("/api/library")
def api_library():
    """列出 raw/ 下所有文件 + 是否已被 wiki/ 索引。"""
    items = []
    if not RAW_DIR.exists():
        return items

    indexed_chunks = _count_chunks_per_source()

    for p in sorted(RAW_DIR.iterdir()):
        if not p.is_file():
            continue
        suffix = p.suffix.lower()
        kind = (
            "md"
            if suffix == ".md"
            else "image"
            if suffix in {".png", ".jpg", ".jpeg"}
            else "other"
        )
        wiki_twin = WIKI_DIR / p.name if suffix == ".md" else None
        indexed = bool(wiki_twin and wiki_twin.exists())
        chunks = indexed_chunks.get(p.name) if indexed else None
        items.append(
            {
                "name": p.name,
                "kind": kind,
                "chunks": chunks,
                "indexed": indexed,
                "updatedAt": _format_mtime(p.stat().st_mtime),
            }
        )
    return items


@app.post("/api/library/rebuild")
def api_rebuild():
    """重新构建整个索引。"""
    try:
        build_index()
        return {"ok": True}
    except Exception as e:  # noqa: BLE001
        log.exception("rebuild failed")
        return {"ok": False, "error": str(e)}


# ---------- internal ----------

def _count_chunks_per_source() -> dict[str, int]:
    """从 index.json 反推每个 source 有多少段。"""
    import json

    if not INDEX_FILE.exists():
        return {}
    try:
        with INDEX_FILE.open("r", encoding="utf-8") as f:
            chunks = json.load(f)
    except (OSError, ValueError):
        return {}

    counts: dict[str, int] = {}
    for c in chunks:
        src = c.get("source", "?")
        counts[src] = counts.get(src, 0) + 1
    return counts


def _format_mtime(ts: float) -> str:
    from datetime import datetime

    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")
