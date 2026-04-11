"""本地 OCR：扫描 raw/ 中的图片，识别文本，生成同名 .md。

依赖：
    pip install pytesseract Pillow
    macOS:  brew install tesseract tesseract-lang
    Linux:  sudo apt install tesseract-ocr tesseract-ocr-chi-sim
"""
from __future__ import annotations

import re
from pathlib import Path

from core.utils import RAW_DIR, log

IMAGE_EXTS = {".png", ".jpg", ".jpeg"}
DEFAULT_LANG = "chi_sim+eng"


class OCRError(Exception):
    """OCR 调用失败的统一异常。"""


def _clean_text(text: str) -> str:
    """简单清洗：去空行、合并重复空行、丢掉只剩符号的行。"""
    out = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        # 全是非字母数字汉字的"行"视为噪音
        if not re.search(r"[\w\u4e00-\u9fff]", line):
            continue
        out.append(line)
    return "\n".join(out)


def ocr_image(path: Path, lang: str = DEFAULT_LANG) -> str:
    """对单张图片做 OCR，返回清洗后的文本。"""
    try:
        import pytesseract
        from PIL import Image
    except ImportError as e:
        raise OCRError(
            "缺少依赖，请先执行: pip install pytesseract Pillow"
        ) from e

    try:
        img = Image.open(path)
    except (OSError, FileNotFoundError) as e:
        raise OCRError(f"无法打开图片 {path.name}: {e}") from e

    try:
        text = pytesseract.image_to_string(img, lang=lang)
    except pytesseract.TesseractNotFoundError as e:
        raise OCRError(
            "未找到 tesseract 可执行文件，请先安装："
            "macOS: `brew install tesseract tesseract-lang`"
        ) from e
    except pytesseract.TesseractError as e:
        raise OCRError(f"OCR 失败 ({path.name}): {e}") from e
    except Exception as e:  # 兜底，避免崩溃
        raise OCRError(f"OCR 异常 ({path.name}): {e}") from e

    return _clean_text(text)


def ocr_all(overwrite: bool = False) -> int:
    """扫描 raw/ 下的图片，对每张 OCR 并生成同名 .md。返回成功数量。"""
    if not RAW_DIR.exists():
        log.warning(f"raw 目录不存在: {RAW_DIR}")
        return 0

    images = sorted(
        p for p in RAW_DIR.iterdir()
        if p.is_file() and p.suffix.lower() in IMAGE_EXTS
    )
    if not images:
        log.info("raw/ 中没有图片文件，跳过 OCR")
        return 0

    log.info(f"发现 {len(images)} 张图片，开始 OCR...")
    ok = 0
    for img in images:
        md_path = img.with_suffix(".md")
        if md_path.exists() and not overwrite:
            log.info(f"跳过 (已有 {md_path.name}): {img.name}")
            continue

        log.info(f"OCR 识别: {img.name}")
        try:
            text = ocr_image(img)
        except OCRError as e:
            log.error(str(e))
            continue

        if not text.strip():
            log.warning(f"OCR 结果为空: {img.name}")
            continue

        try:
            md_path.write_text(text, encoding="utf-8")
        except OSError as e:
            log.error(f"写入失败 {md_path.name}: {e}")
            continue

        log.info(f"已从图片生成笔记: {md_path.name}")
        ok += 1

    log.info(f"OCR 完成: {ok}/{len(images)} 成功")
    return ok
