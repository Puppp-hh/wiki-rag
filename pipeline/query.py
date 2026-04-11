"""检索 + 生成：读取 index.json → 相似度召回 → LLM 回答 → refine。

对外暴露两个函数：
    - answer_question(...) -> str   返回最终答案字符串（供 chat / Streamlit 使用）
    - query(...) -> None            CLI 风格，直接打印
"""
from __future__ import annotations

import json
from typing import List, Tuple

from core.embedding import EmbeddingError, embed
from core.llm import LLMError, ask
from core.utils import INDEX_FILE, cosine_sim, log
from pipeline.refine import refine_answer

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


def _retrieve(question: str, top_k: int) -> Tuple[List[Tuple[float, dict]], List[dict]]:
    """召回 top-k 段落。返回 (打分后的 top-k, 全部 chunks)。"""
    chunks = _load_index()
    if not chunks:
        raise RuntimeError("索引为空，先执行 compile + index")

    q_emb = embed(question)
    scored = [(cosine_sim(q_emb, c["embedding"]), c) for c in chunks]
    scored.sort(key=lambda x: x[0], reverse=True)
    return scored[:top_k], chunks


def answer_question(
    question: str,
    top_k: int = 3,
    refine: bool = True,
) -> str:
    """完整问答流水线，返回最终答案字符串。

    任何阶段失败都会抛出对应异常，由调用方处理。
    """
    log.info("计算问题 embedding...")
    top, _ = _retrieve(question, top_k)

    for score, chunk in top:
        preview = chunk["text"][:50].replace("\n", " ")
        log.info(f"  hit {score:.4f} | [{chunk.get('source', '?')}] {preview}")

    context = "\n\n".join(c["text"] for _, c in top)
    prompt = _PROMPT.format(context=context, question=question)

    log.info("生成初始回答...")
    initial = ask(prompt)

    if not refine:
        return initial

    try:
        return refine_answer(question, initial)
    except LLMError as e:
        log.warning(f"refine 失败，回退到原始回答: {e}")
        return initial


def query(question: str, top_k: int = 3, refine: bool = True) -> None:
    """CLI 入口：捕获异常，打印结果。"""
    try:
        answer = answer_question(question, top_k=top_k, refine=refine)
    except (FileNotFoundError, RuntimeError) as e:
        log.error(str(e))
        return
    except EmbeddingError as e:
        log.error(f"embedding 失败: {e}")
        return
    except LLMError as e:
        log.error(f"LLM 调用失败: {e}")
        return

    print("\n--- 回答 ---")
    print(answer)
