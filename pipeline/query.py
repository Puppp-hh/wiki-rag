"""检索 + 生成：读取 index.json → hybrid 召回 → LLM 回答 → refine。

对外暴露两个函数：
    - answer_question(...) -> str   返回最终答案字符串（供 chat / Streamlit 使用）
    - query(...) -> None            CLI 风格，直接打印
"""
from __future__ import annotations

from typing import List, Tuple

from core.embedding import EmbeddingError, embed
from core.llm import LLMError, ask, stream_chat
from core.utils import log
from pipeline.refine import refine_answer
from pipeline.retrieval import citation_block, load_index, retrieve

_PROMPT = """请基于以下知识库内容回答用户问题。

回答模式：{mode_name}

规则：
{mode_rules}

通用要求：
1. 优先使用知识库内容。
2. 不要编造具体数据、文件、接口、项目细节。
3. 回答要简洁清晰，适合学习和面试复述。
4. 不要输出无关内容。

{context}

问题：{question}
"""

_ANSWER_MODES = {
    "expand": (
        "知识库 + 适度拓展",
        "可以在知识库内容基础上补充通用背景知识；如果是补充内容，要明确说明它属于通用补充。",
    ),
    "summary": (
        "基于知识库总结",
        "只对知识库命中的内容做归纳、整理和解释；不要引入知识库之外的新事实。",
    ),
    "strict": (
        "严格知识库",
        "只能根据知识库内容回答；如果知识库信息不足，要直接说明“知识库中没有足够信息”。",
    ),
    "extract": (
        "只看原文",
        "不调用大模型，直接返回相似度最高的知识库片段。",
    ),
}


def _load_index() -> List[dict]:
    return load_index()


def _retrieve(question: str, top_k: int) -> Tuple[List[Tuple[float, dict]], List[dict]]:
    """召回 top-k 段落。返回 (打分后的 top-k, 全部 chunks)。"""
    top, chunks, _ = retrieve(question, top_k, mode="hybrid")
    return top, chunks


def filter_top(top: list[tuple[float, dict]], min_score: float = 0.0) -> list[tuple[float, dict]]:
    """按相似度阈值过滤召回结果。"""
    return [(score, chunk) for score, chunk in top if score >= min_score]


def build_prompt(
    question: str,
    top: list[tuple[float, dict]],
    answer_mode: str = "expand",
) -> str:
    context = "\n\n".join(
        f"[source: {c.get('source', '?')}]\n{c['text']}" for _, c in top
    )
    mode_name, mode_rules = _ANSWER_MODES.get(answer_mode, _ANSWER_MODES["expand"])
    return _PROMPT.format(
        context=context,
        question=question,
        mode_name=mode_name,
        mode_rules=mode_rules,
    )


def no_enough_context_message(min_score: float) -> str:
    return (
        f"知识库中没有找到相似度高于 {min_score:.2f} 的相关内容。"
        "可以降低相似度阈值，或先在 Library 中补充并重建索引。"
    )


def answer_question(
    question: str,
    top_k: int = 3,
    refine: bool = True,
    answer_mode: str = "expand",
    min_score: float = 0.0,
) -> str:
    """完整问答流水线，返回最终答案字符串。

    任何阶段失败都会抛出对应异常，由调用方处理。
    """
    log.info("计算问题 embedding...")
    top, _, meta = retrieve(question, top_k, mode="hybrid")
    top = filter_top(top, min_score)
    if not top:
        return no_enough_context_message(min_score)

    for score, chunk in top:
        preview = chunk["text"][:50].replace("\n", " ")
        log.info(
            f"  hit {score:.4f} | dense={chunk.get('dense_score', 0):.4f} "
            f"bm25={chunk.get('bm25_score', 0):.4f} | [{chunk.get('source', '?')}] {preview}"
        )

    if answer_mode == "extract":
        return top[0][1]["text"] + citation_block(top[:1])

    prompt = build_prompt(question, top, answer_mode=answer_mode)

    log.info(f"生成初始回答... retrieval={meta}")
    initial = ask(prompt)

    if not refine:
        return initial + citation_block(top)

    try:
        return refine_answer(question, initial) + citation_block(top)
    except LLMError as e:
        log.warning(f"refine 失败，回退到原始回答: {e}")
        return initial + citation_block(top)


def stream_answer(
    question: str,
    top_k: int = 3,
    refine: bool = True,
    answer_mode: str = "expand",
    min_score: float = 0.0,
):
    """流式返回最终答案文本片段。

    refine 开启时会先生成初始答案，再把 refine 后的最终答案按字符块吐出；
    refine 关闭时直接透传 LLM 的流式输出。
    """
    top, _, meta = retrieve(question, top_k, mode="hybrid")
    top = filter_top(top, min_score)
    if not top:
        yield no_enough_context_message(min_score)
        return

    if answer_mode == "extract":
        yield top[0][1]["text"] + citation_block(top[:1])
        return

    prompt = build_prompt(question, top, answer_mode=answer_mode)
    log.info(f"流式生成回答... retrieval={meta}")

    if refine:
        initial = "".join(stream_chat([{"role": "user", "content": prompt}]))
        try:
            final = refine_answer(question, initial)
        except LLMError as e:
            log.warning(f"refine 失败，回退到原始回答: {e}")
            final = initial
        final += citation_block(top)
        for i in range(0, len(final), 12):
            yield final[i:i + 12]
        return

    for chunk in stream_chat([{"role": "user", "content": prompt}]):
        yield chunk
    yield citation_block(top)


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
