"""FastAPI HTTP 层,专门给 web-frontend 用。

启动:
    uvicorn web.api:app --reload --port 8000

依赖:
    pip install fastapi uvicorn
"""
from __future__ import annotations

import json
import base64
import threading
import time
import uuid
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

from core.embedding import EmbeddingError, embed
from core.llm import LLMError
from core.sessions import append_messages, clear_session, load_session, normalize_session_id
from core.utils import EMBED_MODEL, INDEX_FILE, RAW_DIR, WIKI_DIR, log
from pipeline.index import build_index, sync_raw_markdown_to_wiki
from pipeline.query import _retrieve, answer_question, filter_top, stream_answer
from pipeline.documents import (
    SUPPORTED_EXTS,
    is_editable_text,
    is_supported_file,
    library_kind,
    raw_relative_path,
    wiki_name_for_raw,
)
from pipeline.retrieval import retrieve
from pipeline.sources import sync_sources

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
    answer_mode: str = "expand"
    min_score: float = 0.0
    history: Optional[List[HistoryItem]] = None
    session_id: Optional[str] = None


class DebugReq(BaseModel):
    question: str
    top_k: int = 5
    min_score: float = 0.0


class LibrarySaveReq(BaseModel):
    content: str


class LibraryUploadItem(BaseModel):
    name: str
    content: Optional[str] = None
    data: Optional[str] = None


class LibraryUploadReq(BaseModel):
    files: List[LibraryUploadItem]


# ---------- helpers ----------

def _serialize_hits(top) -> list[dict]:
    return [
        {
            "source": chunk.get("source", "?"),
            "text": chunk.get("text", ""),
            "score": float(score),
            "dense_score": float(chunk.get("dense_score", 0.0)),
            "bm25_score": float(chunk.get("bm25_score", 0.0)),
            "retrieval_backend": chunk.get("retrieval_backend", "numpy"),
            "rerank": chunk.get("rerank", {}),
        }
        for score, chunk in top
    ]


def _sse(event: str, data) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _safe_library_path(name: str) -> Path:
    normalized = name.replace("\\", "/").strip("/")
    rel = Path(normalized)
    if (
        not normalized
        or rel.is_absolute()
        or any(part in {"", ".", ".."} for part in rel.parts)
        or Path(rel.name).suffix.lower() not in SUPPORTED_EXTS
    ):
        raise ValueError("invalid library filename")
    return rel


def _safe_editable_path(name: str) -> Path:
    rel = _safe_library_path(name)
    probe = RAW_DIR / rel
    if not is_editable_text(probe):
        raise ValueError("file type is not editable")
    return rel


REBUILD_TASKS: dict[str, dict] = {}
REBUILD_LOCK = threading.Lock()


def _update_rebuild_task(task_id: str, **patch) -> dict:
    with REBUILD_LOCK:
        task = REBUILD_TASKS.setdefault(task_id, {"task_id": task_id})
        task.update(patch)
        task["updated_at"] = time.time()
        return dict(task)


def _get_rebuild_task(task_id: str) -> dict | None:
    with REBUILD_LOCK:
        task = REBUILD_TASKS.get(task_id)
        return dict(task) if task else None


def _run_rebuild_task(task_id: str) -> None:
    def progress(payload: dict) -> None:
        _update_rebuild_task(task_id, **payload)

    try:
        _update_rebuild_task(
            task_id,
            ok=True,
            status="running",
            stage="prepare",
            message="准备重建索引",
            percent=1,
            synced=0,
            reused=0,
            rebuilt=0,
            chunk_count=0,
        )
        synced = sync_raw_markdown_to_wiki(progress=progress)
        _update_rebuild_task(task_id, synced=synced)
        stats = build_index(incremental=True, progress=progress)
        _update_rebuild_task(
            task_id,
            ok=True,
            status="done",
            stage="done",
            message="索引重建完成",
            percent=100,
            synced=synced,
            **stats,
        )
    except Exception as e:  # noqa: BLE001
        log.exception("rebuild task failed")
        _update_rebuild_task(
            task_id,
            ok=False,
            status="error",
            stage="error",
            message="索引重建失败",
            percent=100,
            error=str(e),
        )


def _start_rebuild_task(message: str = "等待重建索引") -> str:
    task_id = uuid.uuid4().hex
    _update_rebuild_task(
        task_id,
        ok=True,
        status="queued",
        stage="queued",
        message=message,
        percent=0,
    )
    thread = threading.Thread(target=_run_rebuild_task, args=(task_id,), daemon=True)
    thread.start()
    return task_id


# ---------- routes ----------

@app.post("/api/query")
def api_query(req: QueryReq):
    """完整的 RAG 问答:返回最终答案 + 命中段落。"""
    session_id = normalize_session_id(req.session_id)
    try:
        top, _ = _retrieve(req.question, req.top_k)
        top = filter_top(top, req.min_score)
    except (FileNotFoundError, RuntimeError) as e:
        return {"answer": f"[索引未就绪] {e}", "hits": []}
    except EmbeddingError as e:
        return {"answer": f"[embedding 失败] {e}", "hits": []}

    try:
        answer = answer_question(
            req.question,
            top_k=req.top_k,
            refine=req.refine,
            answer_mode=req.answer_mode,
            min_score=req.min_score,
        )
    except LLMError as e:
        answer = f"[LLM 调用失败] {e}"
    except Exception as e:  # noqa: BLE001
        log.exception("answer_question failed")
        answer = f"[未知错误] {e}"

    hits = _serialize_hits(top)
    append_messages(
        session_id,
        [
            {"role": "user", "content": req.question},
            {"role": "assistant", "content": answer, "hits": hits},
        ],
    )
    return {"answer": answer, "hits": hits, "session_id": session_id}


@app.post("/api/search")
def api_search(req: QueryReq):
    """只做检索:返回 Top-1 作为主结果，其余结果由前端折叠展示。"""
    session_id = normalize_session_id(req.session_id)
    try:
        top, _ = _retrieve(req.question, req.top_k)
        top = filter_top(top, req.min_score)
        hits = _serialize_hits(top)
    except (FileNotFoundError, RuntimeError) as e:
        return {
            "answer": f"[索引未就绪] {e}",
            "hits": [],
            "session_id": session_id,
        }
    except EmbeddingError as e:
        return {
            "answer": f"[embedding 失败] {e}",
            "hits": [],
            "session_id": session_id,
        }

    answer = hits[0]["text"] if hits else "没有检索到相关结果。"
    append_messages(
        session_id,
        [
            {"role": "user", "content": req.question},
            {"role": "assistant", "content": answer, "hits": hits},
        ],
    )
    return {
        "answer": answer,
        "best": hits[0] if hits else None,
        "hits": hits,
        "session_id": session_id,
    }


@app.post("/api/query/stream")
def api_query_stream(req: QueryReq):
    """SSE 流式问答:先返回 hits，再持续返回 token。"""
    session_id = normalize_session_id(req.session_id)

    def events():
        answer_parts: list[str] = []
        hits: list[dict] = []
        try:
            top, _ = _retrieve(req.question, req.top_k)
            top = filter_top(top, req.min_score)
            hits = _serialize_hits(top)
            yield _sse("session", {"session_id": session_id})
            yield _sse("hits", hits)
            for part in stream_answer(
                req.question,
                top_k=req.top_k,
                refine=req.refine,
                answer_mode=req.answer_mode,
                min_score=req.min_score,
            ):
                answer_parts.append(part)
                yield _sse("token", part)
            answer = "".join(answer_parts)
            append_messages(
                session_id,
                [
                    {"role": "user", "content": req.question},
                    {"role": "assistant", "content": answer, "hits": hits},
                ],
            )
            yield _sse("done", {"ok": True})
        except (FileNotFoundError, RuntimeError) as e:
            yield _sse("error", f"[索引未就绪] {e}")
        except EmbeddingError as e:
            yield _sse("error", f"[embedding 失败] {e}")
        except LLMError as e:
            yield _sse("error", f"[LLM 调用失败] {e}")
        except Exception as e:  # noqa: BLE001
            log.exception("stream query failed")
            yield _sse("error", f"[未知错误] {e}")

    return StreamingResponse(events(), media_type="text/event-stream")


@app.post("/api/debug")
def api_debug(req: DebugReq):
    """调试用:只做检索 + 暴露 embedding 元信息。"""
    try:
        top, _, meta = retrieve(req.question, req.top_k, mode="hybrid")
        top = filter_top(top, req.min_score)
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
            "minScore": req.min_score,
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
            "minScore": req.min_score,
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
        "minScore": req.min_score,
        "query": meta.get("query", req.question),
        "expandedQuery": meta.get("expanded_query", req.question),
        "queryTerms": meta.get("query_terms", []),
        "retrievalMode": meta.get("mode", "hybrid"),
        "denseBackend": meta.get("dense_backend", "numpy"),
    }


@app.get("/api/library")
def api_library():
    """列出 raw/ 下受支持文件 + 是否已被 wiki/ 索引。"""
    items = []
    if not RAW_DIR.exists():
        return items

    indexed_chunks = _count_chunks_per_source()

    for p in sorted(RAW_DIR.rglob("*")):
        if not is_supported_file(p):
            continue
        wiki_twin = WIKI_DIR / wiki_name_for_raw(p)
        wiki_rel = wiki_twin.relative_to(WIKI_DIR).as_posix()
        source = f"wiki/{wiki_rel}"
        chunks = indexed_chunks.get(source, indexed_chunks.get(wiki_rel))
        indexed = bool(wiki_twin.exists() and chunks)
        rel_name = raw_relative_path(p).as_posix()
        items.append(
            {
                "name": rel_name,
                "kind": library_kind(p),
                "wikiName": wiki_rel,
                "editable": is_editable_text(p),
                "chunks": chunks,
                "indexed": indexed,
                "updatedAt": _format_mtime(p.stat().st_mtime),
            }
        )
    return items


@app.post("/api/library/upload")
def api_library_upload(req: LibraryUploadReq):
    """批量上传受支持文件到 raw/，写入后自动启动索引重建任务。"""
    if not req.files:
        return {"ok": False, "error": "no files"}

    uploaded = []
    try:
        RAW_DIR.mkdir(parents=True, exist_ok=True)
        for item in req.files:
            rel = _safe_library_path(item.name)
            path = RAW_DIR / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            if item.data is not None:
                payload = item.data.split(",", 1)[-1]
                path.write_bytes(base64.b64decode(payload, validate=True))
                size = path.stat().st_size
            elif item.content is not None:
                path.write_text(item.content, encoding="utf-8")
                size = len(item.content.encode("utf-8"))
            else:
                return {
                    "ok": False,
                    "error": f"empty upload payload: {rel.as_posix()}",
                    "uploaded": uploaded,
                }
            uploaded.append(
                {
                    "name": rel.as_posix(),
                    "kind": library_kind(path),
                    "size": size,
                }
            )
    except ValueError:
        return {
            "ok": False,
            "error": f"only supported files are allowed: {', '.join(sorted(SUPPORTED_EXTS))}",
            "uploaded": uploaded,
        }
    except Exception as e:  # noqa: BLE001
        log.exception("upload library files failed")
        return {"ok": False, "error": str(e), "uploaded": uploaded}

    task_id = _start_rebuild_task("文件上传完成，准备重建索引")
    return {"ok": True, "uploaded": uploaded, "task_id": task_id}


@app.get("/api/library/blob/{name:path}")
def api_library_blob(name: str):
    """返回 raw/ 中的原始文件，供图片/PDF 等预览使用。"""
    try:
        rel = _safe_library_path(name)
    except ValueError:
        return {"ok": False, "error": "invalid library filename"}

    path = RAW_DIR / rel
    if not path.exists() or not is_supported_file(path):
        return {"ok": False, "error": "file not found"}
    return FileResponse(path)


@app.get("/api/library/file/{name:path}")
def api_library_file(name: str):
    """读取 raw/ 下单个文件，用于 Library 预览。"""
    try:
        rel = _safe_library_path(name)
    except ValueError:
        return {"ok": False, "error": "invalid library filename"}

    path = RAW_DIR / rel
    if not path.exists() or not is_supported_file(path):
        return {"ok": False, "error": "file not found"}

    editable = is_editable_text(path)
    wiki_path = WIKI_DIR / wiki_name_for_raw(path)
    if editable:
        try:
            content = path.read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            return {"ok": False, "error": str(e)}
    elif wiki_path.exists():
        try:
            content = wiki_path.read_text(encoding="utf-8")
        except OSError as e:
            return {"ok": False, "error": str(e)}
    else:
        content = "该文件尚未抽取为可索引文本，请点击 Rebuild Index。"

    return {
        "ok": True,
        "name": rel.as_posix(),
        "kind": library_kind(path),
        "editable": editable,
        "wikiName": wiki_path.relative_to(WIKI_DIR).as_posix(),
        "content": content,
        "previewUrl": f"/api/library/blob/{rel.as_posix()}",
        "updatedAt": _format_mtime(path.stat().st_mtime),
    }


@app.put("/api/library/file/{name:path}")
def api_library_save(name: str, req: LibrarySaveReq):
    """保存 raw/ 下可编辑文本文件，并同步到 wiki 后增量重建索引。"""
    try:
        rel = _safe_editable_path(name)
    except ValueError:
        return {"ok": False, "error": "file type is not editable"}

    try:
        path = RAW_DIR / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(req.content, encoding="utf-8")
        synced = sync_raw_markdown_to_wiki()
        build_index(incremental=True)
    except Exception as e:  # noqa: BLE001
        log.exception("save library file failed")
        return {"ok": False, "error": str(e)}

    path = RAW_DIR / rel
    return {
        "ok": True,
        "name": rel.as_posix(),
        "synced": synced,
        "updatedAt": _format_mtime(path.stat().st_mtime),
    }


@app.delete("/api/library/file/{name:path}")
def api_library_delete(name: str):
    """删除 raw 原文件和对应 wiki Markdown，并增量重建索引。"""
    try:
        rel = _safe_library_path(name)
    except ValueError:
        return {"ok": False, "error": "invalid library filename"}

    removed = []
    raw_path = RAW_DIR / rel
    wiki_path = WIKI_DIR / wiki_name_for_raw(raw_path)
    for path in (raw_path, wiki_path):
        if path.exists() and path.is_file():
            try:
                path.unlink()
                root = RAW_DIR if path.is_relative_to(RAW_DIR) else WIKI_DIR
                removed.append(str(path.relative_to(root)))
            except OSError as e:
                return {"ok": False, "error": str(e)}

    try:
        build_index(incremental=True)
    except Exception as e:  # noqa: BLE001
        log.exception("delete library file rebuild failed")
        return {"ok": False, "error": str(e), "removed": removed}

    return {"ok": True, "name": rel.as_posix(), "removed": removed}


@app.post("/api/library/rebuild")
def api_rebuild():
    """启动索引重建任务，并返回 task_id 供前端轮询进度。"""
    return {"ok": True, "task_id": _start_rebuild_task()}


@app.get("/api/library/rebuild/{task_id}")
def api_rebuild_status(task_id: str):
    """查询索引重建任务进度。"""
    task = _get_rebuild_task(task_id)
    if not task:
        return {"ok": False, "status": "missing", "error": "task not found"}
    return task


@app.post("/api/sources/sync")
def api_sources_sync():
    """同步 Obsidian / Notion export / GitHub Issues JSON 到 raw/。"""
    results = sync_sources()
    return {"ok": True, "results": [r.__dict__ for r in results]}


@app.get("/api/sessions/{session_id}")
def api_session(session_id: str):
    """读取某个用户会话。"""
    sid = normalize_session_id(session_id)
    return load_session(sid)


@app.delete("/api/sessions/{session_id}")
def api_clear_session(session_id: str):
    """清空某个用户会话。"""
    sid = normalize_session_id(session_id)
    clear_session(sid)
    return {"ok": True, "session_id": sid}


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
        if src != "?" and not src.startswith("wiki/"):
            src = f"wiki/{src}"
        counts[src] = counts.get(src, 0) + 1
    return counts


def _format_mtime(ts: float) -> str:
    from datetime import datetime

    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")
