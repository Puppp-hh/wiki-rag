"""把 raw/ 下的原始笔记交给 LLM 整理，输出到 wiki/。

注意：文件名为 compiler.py 而非 compile.py，避免与 Python 内置 compile 概念混淆。
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from llm import LLMError, ask
from utils import RAW_DIR, WIKI_DIR, log

_PROMPT = """你是一个知识整理专家，请整理以下内容：

{content}

要求：
1. 分层标题
2. 重点加粗
3. 结构清晰
4. 最后一句总结
"""


def compile_note(src: Path) -> Optional[Path]:
    """整理单个笔记文件，成功返回目标路径，失败返回 None。"""
    try:
        content = src.read_text(encoding="utf-8")
    except OSError as e:
        log.error(f"读取失败 {src}: {e}")
        return None

    log.info(f"整理中: {src.name}")
    try:
        result = ask(_PROMPT.format(content=content))
    except LLMError as e:
        log.error(f"LLM 调用失败 ({src.name}): {e}")
        return None

    WIKI_DIR.mkdir(parents=True, exist_ok=True)
    dst = WIKI_DIR / src.name
    try:
        dst.write_text(result, encoding="utf-8")
    except OSError as e:
        log.error(f"写入失败 {dst}: {e}")
        return None

    log.info(f"已写入: {dst.relative_to(WIKI_DIR.parent)}")
    return dst


def compile_all() -> None:
    if not RAW_DIR.exists():
        log.error(f"raw 目录不存在: {RAW_DIR}")
        return

    files = sorted(p for p in RAW_DIR.iterdir() if p.is_file() and p.suffix == ".md")
    if not files:
        log.warning(f"{RAW_DIR} 下没有 .md 文件")
        return

    log.info(f"共 {len(files)} 个文件待编译")
    ok = 0
    for f in files:
        if compile_note(f) is not None:
            ok += 1
    log.info(f"编译完成: {ok}/{len(files)} 成功")
