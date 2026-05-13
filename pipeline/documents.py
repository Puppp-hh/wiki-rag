"""Library 文档类型识别与文本抽取。

raw/ 保留用户上传的原文件；wiki/ 保存可被 RAG 索引的 Markdown 文本。
"""
from __future__ import annotations

import html
import zipfile
from pathlib import Path
from xml.etree import ElementTree

from core.utils import RAW_DIR
from pipeline.ocr import OCRError, ocr_image

TEXT_EXTS = {".md", ".txt"}
PDF_EXTS = {".pdf"}
WORD_EXTS = {".docx"}
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp"}
CODE_EXTS = {
    ".java",
    ".py",
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".vue",
    ".html",
    ".css",
    ".scss",
    ".json",
    ".xml",
    ".yml",
    ".yaml",
    ".sql",
    ".sh",
    ".go",
    ".c",
    ".cpp",
    ".h",
    ".hpp",
    ".cs",
    ".php",
    ".rb",
    ".rs",
    ".kt",
    ".swift",
    ".properties",
    ".gradle",
}
CODE_NAMES = {"dockerfile", "makefile"}
SUPPORTED_EXTS = TEXT_EXTS | PDF_EXTS | WORD_EXTS | IMAGE_EXTS | CODE_EXTS
EDITABLE_EXTS = TEXT_EXTS | CODE_EXTS
CODE_LANGS = {
    ".java": "java",
    ".py": "python",
    ".js": "javascript",
    ".jsx": "jsx",
    ".ts": "typescript",
    ".tsx": "tsx",
    ".vue": "vue",
    ".html": "html",
    ".css": "css",
    ".scss": "scss",
    ".json": "json",
    ".xml": "xml",
    ".yml": "yaml",
    ".yaml": "yaml",
    ".sql": "sql",
    ".sh": "bash",
    ".go": "go",
    ".c": "c",
    ".cpp": "cpp",
    ".h": "c",
    ".hpp": "cpp",
    ".cs": "csharp",
    ".php": "php",
    ".rb": "ruby",
    ".rs": "rust",
    ".kt": "kotlin",
    ".swift": "swift",
    ".properties": "properties",
    ".gradle": "gradle",
}


def is_supported_file(path: Path) -> bool:
    return path.is_file() and (
        path.suffix.lower() in SUPPORTED_EXTS
        or path.name.lower() in CODE_NAMES
    )


def library_kind(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".md":
        return "md"
    if suffix == ".txt":
        return "text"
    if suffix == ".pdf":
        return "pdf"
    if suffix == ".docx":
        return "word"
    if suffix in IMAGE_EXTS:
        return "image"
    if suffix in CODE_EXTS or path.name.lower() in CODE_NAMES:
        return "code"
    return "other"


def is_editable_text(path: Path) -> bool:
    return path.suffix.lower() in EDITABLE_EXTS or path.name.lower() in CODE_NAMES


def raw_relative_path(path: Path) -> Path:
    try:
        return path.relative_to(RAW_DIR)
    except ValueError:
        return Path(path.name)


def wiki_name_for_raw(path: Path) -> Path:
    rel = raw_relative_path(path)
    if path.suffix.lower() == ".md":
        return rel
    suffix = path.suffix.lower().lstrip(".")
    if not suffix and path.name.lower() in CODE_NAMES:
        suffix = path.name.lower()
    return rel.with_name(f"{path.stem}-{suffix}.md")


def extract_markdown(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".md":
        return path.read_text(encoding="utf-8")
    if suffix == ".txt":
        return f"# {path.stem}\n\n" + _read_text(path)
    if suffix in CODE_EXTS or path.name.lower() in CODE_NAMES:
        return _code_to_markdown(path)
    if suffix == ".docx":
        return _docx_to_markdown(path)
    if suffix == ".pdf":
        return _pdf_to_markdown(path)
    if suffix in IMAGE_EXTS:
        return _image_to_markdown(path)
    return _unsupported_markdown(path, "暂不支持该文件类型的文本抽取。")


def _docx_to_markdown(path: Path) -> str:
    try:
        with zipfile.ZipFile(path) as zf:
            xml = zf.read("word/document.xml")
    except Exception as e:  # noqa: BLE001
        return _unsupported_markdown(path, f"DOCX 读取失败：{e}")

    try:
        root = ElementTree.fromstring(xml)
    except ElementTree.ParseError as e:
        return _unsupported_markdown(path, f"DOCX XML 解析失败：{e}")

    ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    paragraphs: list[str] = []
    for paragraph in root.findall(".//w:p", ns):
        parts = [
            node.text or ""
            for node in paragraph.findall(".//w:t", ns)
            if node.text
        ]
        text = "".join(parts).strip()
        if text:
            paragraphs.append(text)

    if not paragraphs:
        return _unsupported_markdown(path, "DOCX 中没有抽取到文本。")
    return f"# {path.stem}\n\n" + "\n\n".join(paragraphs)


def _pdf_to_markdown(path: Path) -> str:
    text = _extract_pdf_with_pypdf(path)
    if text is None:
        text = _extract_pdf_with_pdfplumber(path)
    if not text:
        return _unsupported_markdown(
            path,
            "PDF 文本抽取不可用。可以安装 pypdf 或 pdfplumber 后重新 Rebuild。",
        )
    return f"# {path.stem}\n\n{text}"


def _extract_pdf_with_pypdf(path: Path) -> str | None:
    reader_cls = None
    try:
        from pypdf import PdfReader  # type: ignore

        reader_cls = PdfReader
    except ImportError:
        try:
            from PyPDF2 import PdfReader  # type: ignore

            reader_cls = PdfReader
        except ImportError:
            return None

    try:
        reader = reader_cls(str(path))
        pages = [page.extract_text() or "" for page in reader.pages]
        return "\n\n".join(p.strip() for p in pages if p.strip()).strip()
    except Exception:  # noqa: BLE001
        return None


def _extract_pdf_with_pdfplumber(path: Path) -> str | None:
    try:
        import pdfplumber  # type: ignore
    except ImportError:
        return None

    try:
        with pdfplumber.open(path) as pdf:
            pages = [page.extract_text() or "" for page in pdf.pages]
        return "\n\n".join(p.strip() for p in pages if p.strip()).strip()
    except Exception:  # noqa: BLE001
        return None


def _image_to_markdown(path: Path) -> str:
    try:
        text = ocr_image(path)
    except OCRError as e:
        return _unsupported_markdown(path, f"图片 OCR 不可用：{e}")
    if not text.strip():
        return _unsupported_markdown(path, "图片 OCR 没有识别到文本。")
    return f"# {path.stem}\n\n{text}"


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _code_to_markdown(path: Path) -> str:
    rel = raw_relative_path(path).as_posix()
    suffix = path.suffix.lower()
    lang = CODE_LANGS.get(suffix, path.name.lower())
    code = _read_text(path).strip()
    if not code:
        return _unsupported_markdown(path, "代码文件为空。")
    return (
        f"# {path.name}\n\n"
        f"> 原始路径：`{html.escape(rel)}`\n\n"
        f"```{lang}\n{code}\n```\n"
    )


def _unsupported_markdown(path: Path, reason: str) -> str:
    return (
        f"# {path.stem}\n\n"
        f"> 原始文件：`{html.escape(path.name)}`\n\n"
        f"> 抽取状态：{reason}\n"
    )
