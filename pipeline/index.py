"""扫描 wiki/，分段并生成 embedding，落盘到 index.json。"""
from __future__ import annotations

import json
from typing import List

from core.embedding import EmbeddingError, embed, save_cache
from core.utils import INDEX_FILE, WIKI_DIR, log


def _split_paragraphs(text: str) -> List[str]:
    """以空行为界做简单分段。足够朴素，够用就好。"""
    return [p.strip() for p in text.split("\n\n") if p.strip()]


def build_index() -> None:
    if not WIKI_DIR.exists():
        log.error(f"wiki 目录不存在: {WIKI_DIR}，请先执行 compile")
        return

    files = sorted(p for p in WIKI_DIR.iterdir() if p.is_file() and p.suffix == ".md")
    if not files:
        log.warning(f"{WIKI_DIR} 下没有 .md 文件，请先执行 compile")
        return

    chunks = []
    for f in files:
        try:
            content = f.read_text(encoding="utf-8")
        except OSError as e:
            log.error(f"读取失败 {f}: {e}")
            continue

        paragraphs = _split_paragraphs(content)
        log.info(f"{f.name}: {len(paragraphs)} 段")

        for para in paragraphs:
            try:
                vec = embed(para)
            except EmbeddingError as e:
                log.error(f"embedding 失败（跳过该段）: {e}")
                continue

            chunks.append({
                "source": f.name,
                "text": para,
                "embedding": vec,
            })

    try:
        INDEX_FILE.parent.mkdir(parents=True, exist_ok=True)
        INDEX_FILE.write_text(
            json.dumps(chunks, ensure_ascii=False), encoding="utf-8"
        )
    except OSError as e:
        log.error(f"写入索引失败: {e}")
        return

    save_cache()
    log.info(f"索引完成: 共 {len(chunks)} 条 → {INDEX_FILE.name}")
