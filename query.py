"""检索 + 生成：读取 index.json → 相似度召回 → LLM 回答。"""
from __future__ import annotations

import json
from typing import List

from embedding import EmbeddingError, embed
from llm import LLMError, ask
from utils import INDEX_FILE, cosine_sim, log

_PROMPT = """基于以下内容回答问题：

{context}

问题：{question}
"""


def _load_index() -> List[dict]:
    if not INDEX_FILE.exists():
        raise FileNotFoundError(
            f"索引文件不存在: {INDEX_FILE}，请先执行 `python main.py index`"
        )
    try:
        with INDEX_FILE.open("r", encoding="utf-8") as f:
            return json.load(f)
    except ValueError as e:
        raise RuntimeError(f"索引文件损坏，无法解析: {e}") from e


def query(question: str, top_k: int = 3) -> None:
    try:
        chunks = _load_index()
    except (FileNotFoundError, RuntimeError) as e:
        log.error(str(e))
        return

    if not chunks:
        log.warning("索引为空，先执行 compile + index")
        return

    log.info("计算问题 embedding...")
    try:
        q_emb = embed(question)
    except EmbeddingError as e:
        log.error(f"embedding 失败: {e}")
        return

    scored = [(cosine_sim(q_emb, c["embedding"]), c) for c in chunks]
    scored.sort(key=lambda x: x[0], reverse=True)
    top = scored[:top_k]

    print("\n--- 匹配段落 ---")
    for score, chunk in top:
        preview = chunk["text"][:50].replace("\n", " ")
        print(f"  {score:.4f} | [{chunk.get('source', '?')}] {preview}")

    context = "\n\n".join(c["text"] for _, c in top)
    prompt = _PROMPT.format(context=context, question=question)

    try:
        answer = ask(prompt)
    except LLMError as e:
        log.error(f"LLM 调用失败: {e}")
        return

    print("\n--- 回答 ---")
    print(answer)
