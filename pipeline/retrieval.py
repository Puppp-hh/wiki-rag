"""Hybrid 检索：BM25 + dense embedding，必要时自动使用 FAISS。"""
from __future__ import annotations

import json
import math
import re
from collections import Counter
from typing import List, Tuple

from core.embedding import embed
from core.utils import (
    FAISS_THRESHOLD,
    HYBRID_DENSE_WEIGHT,
    INDEX_FILE,
    cosine_sim,
    log,
)


TOKEN_RE = re.compile(r"[A-Za-z0-9_]+|[\u4e00-\u9fff]")
ALNUM_PHRASE_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]*[A-Za-z0-9]")
CJK_RE = re.compile(r"[\u4e00-\u9fff]")
CJK_STOP_CHARS = set("的是了和与或在有用么吗什什么一个这个那个以及如何")


def load_index() -> List[dict]:
    if not INDEX_FILE.exists():
        raise FileNotFoundError(
            f"索引文件不存在: {INDEX_FILE}，请先执行 `python main.py index`"
        )
    try:
        with INDEX_FILE.open("r", encoding="utf-8") as f:
            chunks = json.load(f)
    except ValueError as e:
        raise RuntimeError(f"索引文件损坏，无法解析: {e}") from e

    # 兼容旧索引：旧 source 只有文件名，这里统一成 wiki/<name>。
    for i, chunk in enumerate(chunks):
        source = chunk.get("source", "?")
        if source != "?" and not source.startswith("wiki/"):
            chunk["source"] = f"wiki/{source}"
        chunk.setdefault("chunk_id", f"{chunk.get('source', '?')}#{i}")
        chunk.setdefault("position", i)
    return chunks


def retrieve(
    question: str,
    top_k: int,
    mode: str = "hybrid",
) -> Tuple[List[Tuple[float, dict]], List[dict], dict]:
    """召回 top-k 段落。

    mode:
        - dense: 只用 embedding cosine
        - bm25: 只用 BM25
        - hybrid: BM25 + dense 加权融合
    """
    chunks = load_index()
    if not chunks:
        raise RuntimeError("索引为空，先执行 compile + index")

    rewritten = rewrite_query(question)
    search_question = rewritten["expanded_query"]
    query_terms = rewritten["terms"]

    bm25_scores = _bm25_scores(search_question, chunks)

    if mode == "dense":
        dense_scores, dense_backend = _dense_scores(search_question, chunks)
        dense_norm = _minmax(dense_scores)
        bm25_norm = _minmax(bm25_scores)
        final_scores = _minmax(dense_scores)
    elif mode == "bm25":
        dense_scores = [0.0 for _ in chunks]
        dense_backend = "disabled"
        dense_norm = [0.0 for _ in chunks]
        bm25_norm = _minmax(bm25_scores)
        final_scores = _minmax(bm25_scores)
    else:
        dense_scores, dense_backend = _dense_scores(search_question, chunks)
        dense_norm = _minmax(dense_scores)
        bm25_norm = _minmax(bm25_scores)
        final_scores = [
            HYBRID_DENSE_WEIGHT * d + (1.0 - HYBRID_DENSE_WEIGHT) * b
            for d, b in zip(dense_norm, bm25_norm)
        ]

    reranked = _rerank_scores(query_terms, chunks, final_scores, dense_norm, bm25_norm)

    scored: list[tuple[float, dict]] = []
    for score, dense, bm25, chunk, detail in zip(
        reranked["scores"], dense_scores, bm25_scores, chunks, reranked["details"]
    ):
        enriched = dict(chunk)
        enriched["dense_score"] = float(dense)
        enriched["bm25_score"] = float(bm25)
        enriched["retrieval_mode"] = mode
        enriched["retrieval_backend"] = dense_backend
        enriched["rerank"] = detail
        scored.append((float(score), enriched))

    scored.sort(key=lambda x: x[0], reverse=True)
    meta = {
        "mode": mode,
        "dense_backend": dense_backend,
        "chunk_count": len(chunks),
        "query": question,
        "expanded_query": search_question,
        "query_terms": query_terms,
    }
    return scored[:top_k], chunks, meta


def citation_block(top: list[tuple[float, dict]]) -> str:
    """把命中文档转成答案末尾的引用回显。"""
    seen: set[str] = set()
    refs: list[str] = []
    for _, chunk in top:
        source = chunk.get("source", "?")
        if source in seen or source == "?":
            continue
        seen.add(source)
        refs.append(f"[source: {source}]")
    return "\n\n" + " ".join(refs) if refs else ""


def _dense_scores(question: str, chunks: list[dict]) -> tuple[list[float], str]:
    if len(chunks) > FAISS_THRESHOLD:
        try:
            return _faiss_scores(question, chunks), "faiss"
        except Exception as e:  # noqa: BLE001 - faiss 是可选后端
            log.warning(f"FAISS 后端不可用，回退到 numpy dense 检索: {e}")

    q_emb = embed(question)
    return [cosine_sim(q_emb, c["embedding"]) for c in chunks], "numpy"


def _faiss_scores(question: str, chunks: list[dict]) -> list[float]:
    import faiss  # type: ignore
    import numpy as np

    q = np.asarray([embed(question)], dtype="float32")
    matrix = np.asarray([c["embedding"] for c in chunks], dtype="float32")
    faiss.normalize_L2(q)
    faiss.normalize_L2(matrix)
    index = faiss.IndexFlatIP(matrix.shape[1])
    index.add(matrix)
    scores, ids = index.search(q, len(chunks))
    out = [0.0] * len(chunks)
    for score, idx in zip(scores[0], ids[0]):
        if idx >= 0:
            out[int(idx)] = float(score)
    return out


def _bm25_scores(question: str, chunks: list[dict]) -> list[float]:
    docs = [_tokenize(f"{c.get('source', '')}\n{c.get('text', '')}") for c in chunks]
    query_tokens = _tokenize(question)
    if not query_tokens:
        return [0.0 for _ in chunks]

    n_docs = len(docs)
    avgdl = sum(len(d) for d in docs) / max(n_docs, 1)
    df: Counter[str] = Counter()
    for doc in docs:
        df.update(set(doc))

    k1 = 1.5
    b = 0.75
    scores: list[float] = []
    for doc in docs:
        freqs = Counter(doc)
        dl = len(doc)
        score = 0.0
        for term in query_tokens:
            if term not in freqs:
                continue
            idf = math.log(1 + (n_docs - df[term] + 0.5) / (df[term] + 0.5))
            tf = freqs[term]
            denom = tf + k1 * (1 - b + b * dl / max(avgdl, 1e-9))
            score += idf * (tf * (k1 + 1)) / max(denom, 1e-9)
        scores.append(float(score))
    return scores


def _tokenize(text: str) -> list[str]:
    raw_tokens = [m.group(0).lower() for m in TOKEN_RE.finditer(text)]
    has_alnum = any(any(ch.isascii() and ch.isalnum() for ch in t) for t in raw_tokens)
    tokens = [
        token
        for token in raw_tokens
        if not (has_alnum and len(token) == 1 and CJK_RE.fullmatch(token))
        and not (len(token) == 1 and CJK_RE.fullmatch(token) and token in CJK_STOP_CHARS)
    ]

    for match in ALNUM_PHRASE_RE.finditer(text):
        compact = re.sub(r"[^a-z0-9]", "", match.group(0).lower())
        if compact and compact not in tokens:
            tokens.append(compact)
    return tokens


def rewrite_query(question: str) -> dict:
    """查询改写：把 wiki-rag / wikirag 等项目名写法归一并扩展。

    这里使用规则实现，避免为了改写问题再额外调用一次 LLM。
    """
    terms = _compact_query_terms(question)
    variants: list[str] = [question]
    for term in terms:
        variants.append(term)
        if term == "wikirag":
            variants.extend(["wiki-rag", "wiki rag", "Wiki-RAG", "本地知识库", "RAG"])
        elif term.endswith("rag") and len(term) > 3:
            prefix = term[:-3]
            variants.extend([f"{prefix}-rag", f"{prefix} rag"])

    seen: set[str] = set()
    expanded_parts: list[str] = []
    for item in variants:
        normalized = item.strip()
        key = normalized.lower()
        if normalized and key not in seen:
            seen.add(key)
            expanded_parts.append(normalized)

    return {
        "original": question,
        "expanded_query": " ".join(expanded_parts),
        "terms": terms,
    }


def _rerank_scores(
    terms: list[str],
    chunks: list[dict],
    base_scores: list[float],
    dense_norm: list[float],
    bm25_norm: list[float],
) -> dict:
    details = []
    scores: list[float] = []
    for chunk, base, dense, bm25 in zip(chunks, base_scores, dense_norm, bm25_norm):
        keyword = _keyword_detail(terms, chunk)
        length_score = _length_score(chunk.get("text", ""))
        rerank_score = min(
            1.0,
            keyword["boost"] + keyword["coverage"] * 0.14 + length_score * 0.06,
        )
        final = min(1.0, base * 0.78 + rerank_score * 0.22)
        reasons = []
        if keyword["source_match"]:
            reasons.append("文件名命中查询词")
        if keyword["title_match"]:
            reasons.append("标题/开头命中查询词")
        if keyword["body_match"]:
            reasons.append("正文命中查询词")
        if keyword["coverage"] > 0:
            reasons.append(f"关键词覆盖 {keyword['matched_terms']}/{max(len(terms), 1)}")
        if not reasons:
            reasons.append("主要由向量/BM25 相似度召回")

        detail = {
            "base_score": float(base),
            "final_score": float(final),
            "dense_norm": float(dense),
            "bm25_norm": float(bm25),
            "keyword_boost": float(keyword["boost"]),
            "coverage": float(keyword["coverage"]),
            "length_score": float(length_score),
            "matched_terms": keyword["matched_terms"],
            "reasons": reasons,
        }
        details.append(detail)
        scores.append(float(final))
    return {"scores": scores, "details": details}


def _keyword_detail(terms: list[str], chunk: dict) -> dict:
    if not terms:
        return {
            "boost": 0.0,
            "coverage": 0.0,
            "matched_terms": 0,
            "source_match": False,
            "title_match": False,
            "body_match": False,
        }

    source = _compact_text(chunk.get("source", ""))
    text = chunk.get("text", "")
    title_area = _compact_text("\n".join(text.splitlines()[:8]))
    body = _compact_text(text[:1200])

    source_match = False
    title_match = False
    body_match = False
    matched: set[str] = set()
    boost = 0.0
    for term in terms:
        if term in source:
            source_match = True
            matched.add(term)
            boost = max(boost, 0.55)
        elif term in title_area:
            title_match = True
            matched.add(term)
            boost = max(boost, 0.34)
        elif term in body:
            body_match = True
            matched.add(term)
            boost = max(boost, 0.16)

    return {
        "boost": boost,
        "coverage": len(matched) / max(len(terms), 1),
        "matched_terms": len(matched),
        "source_match": source_match,
        "title_match": title_match,
        "body_match": body_match,
    }


def _length_score(text: str) -> float:
    size = len(text.strip())
    if size <= 0:
        return 0.0
    if 80 <= size <= 900:
        return 1.0
    if size < 80:
        return size / 80
    return max(0.2, 1.0 - (size - 900) / 2000)


def _compact_query_terms(question: str) -> list[str]:
    terms: list[str] = []
    for match in ALNUM_PHRASE_RE.finditer(question):
        compact = re.sub(r"[^a-z0-9]", "", match.group(0).lower())
        if compact and compact not in terms:
            terms.append(compact)
    return terms


def _compact_text(text: str) -> str:
    return re.sub(r"[^a-z0-9\u4e00-\u9fff]", "", text.lower())


def _minmax(values: list[float]) -> list[float]:
    if not values:
        return []
    lo = min(values)
    hi = max(values)
    if abs(hi - lo) < 1e-12:
        return [0.0 for _ in values]
    return [(v - lo) / (hi - lo) for v in values]
