"""扫描 wiki/，分段并生成 embedding，落盘到 index.json。

默认使用增量索引：只有内容 hash 变化的文件会重新切分和 re-embed。
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Callable, List, Optional

from core.embedding import EmbeddingError, embed, save_cache
from core.utils import INDEX_FILE, INDEX_META_FILE, RAW_DIR, WIKI_DIR, log
from pipeline.documents import extract_markdown, is_supported_file, wiki_name_for_raw

ProgressCallback = Optional[Callable[[dict], None]]


def _emit(progress: ProgressCallback, **payload) -> None:
    if not progress:
        return
    try:
        progress(payload)
    except Exception:  # noqa: BLE001
        log.warning("索引进度回调失败", exc_info=True)


def _split_paragraphs(text: str) -> List[str]:
    """以空行为界做简单分段。足够朴素，够用就好。"""
    return [p.strip() for p in text.split("\n\n") if p.strip()]


def _content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _load_json_file(path: Path, fallback):
    if not path.exists():
        return fallback
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        log.warning(f"{path.name} 损坏，已忽略并重建")
        return fallback


def _source_for(path: Path) -> str:
    """统一前端和引用展示的来源格式。"""
    return f"wiki/{path.relative_to(WIKI_DIR).as_posix()}"


def _chunk_id(source: str, pos: int, text: str) -> str:
    short = hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]
    return f"{source}#{pos}:{short}"


def sync_raw_markdown_to_wiki(progress: ProgressCallback = None) -> int:
    """把 raw/ 下的 Markdown 直接同步到 wiki/。

    Library 的 Rebuild 走这个轻量路径，不调用 LLM compile。
    这样新增 raw/*.md 后点击 Rebuild 就会被索引。
    """
    if not RAW_DIR.exists():
        log.warning(f"raw 目录不存在: {RAW_DIR}")
        _emit(progress, stage="sync", message="raw 目录不存在", percent=10, synced=0)
        return 0

    WIKI_DIR.mkdir(parents=True, exist_ok=True)
    files = sorted(p for p in RAW_DIR.rglob("*") if is_supported_file(p))
    _emit(
        progress,
        stage="sync",
        message="同步 raw 文件到 wiki Markdown",
        percent=5,
        file_index=0,
        file_total=len(files),
        synced=0,
    )
    synced = 0
    for idx, src in enumerate(files, start=1):
        _emit(
            progress,
            stage="sync",
            message=f"抽取 {src.name}",
            percent=5 + int(idx / max(len(files), 1) * 10),
            current_file=src.name,
            file_index=idx,
            file_total=len(files),
            synced=synced,
        )
        dst = WIKI_DIR / wiki_name_for_raw(src)
        if src.suffix.lower() != ".md" and dst.exists():
            try:
                if dst.stat().st_mtime >= src.stat().st_mtime:
                    continue
            except OSError:
                pass

        try:
            content = extract_markdown(src)
        except (OSError, UnicodeDecodeError) as e:
            log.error(f"抽取 raw 失败 {src.name}: {e}")
            continue

        if dst.exists():
            try:
                if dst.read_text(encoding="utf-8") == content:
                    continue
            except OSError:
                pass

        try:
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_text(content, encoding="utf-8")
        except OSError as e:
            log.error(f"同步到 wiki 失败 {dst.name}: {e}")
            continue
        synced += 1

    _emit(
        progress,
        stage="sync",
        message=f"同步完成，更新 {synced} 个 wiki Markdown 文件",
        percent=15,
        file_index=len(files),
        file_total=len(files),
        synced=synced,
    )
    log.info(f"raw → wiki 同步完成: {synced} 个 wiki Markdown 文件更新")
    return synced


def build_index(incremental: bool = True, progress: ProgressCallback = None) -> dict:
    _emit(progress, stage="scan", message="扫描 wiki Markdown 文件", percent=18)
    if not WIKI_DIR.exists():
        log.warning(f"wiki 目录不存在: {WIKI_DIR}，将写入空索引")
        WIKI_DIR.mkdir(parents=True, exist_ok=True)

    files = sorted(p for p in WIKI_DIR.rglob("*.md") if p.is_file())
    _emit(
        progress,
        stage="scan",
        message=f"发现 {len(files)} 个 Markdown 文件",
        percent=20,
        file_index=0,
        file_total=len(files),
    )
    if not files:
        log.warning(f"{WIKI_DIR} 下没有 .md 文件，写入空索引")
        INDEX_FILE.parent.mkdir(parents=True, exist_ok=True)
        INDEX_FILE.write_text("[]", encoding="utf-8")
        INDEX_META_FILE.write_text(
            json.dumps(
                {"version": 2, "incremental": incremental, "files": {}, "chunk_count": 0},
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        _emit(
            progress,
            stage="done",
            message="没有可索引文件，已写入空索引",
            percent=100,
            file_index=0,
            file_total=0,
            chunk_count=0,
            reused=0,
            rebuilt=0,
        )
        return {"chunk_count": 0, "reused": 0, "rebuilt": 0}

    existing_chunks = _load_json_file(INDEX_FILE, []) if incremental else []
    old_meta = _load_json_file(INDEX_META_FILE, {}) if incremental else {}
    old_files = old_meta.get("files", {}) if isinstance(old_meta, dict) else {}
    kept_by_source: dict[str, list[dict]] = {}
    for chunk in existing_chunks:
        src = chunk.get("source", "?")
        kept_by_source.setdefault(src, []).append(chunk)

    chunks: list[dict] = []
    new_files: dict[str, dict] = {}
    rebuilt = 0
    reused = 0

    file_total = len(files)
    for file_index, f in enumerate(files, start=1):
        base_percent = 20 + int((file_index - 1) / file_total * 70)
        _emit(
            progress,
            stage="read",
            message=f"读取 {f.name}",
            percent=base_percent,
            current_file=f.name,
            file_index=file_index,
            file_total=file_total,
            chunk_count=len(chunks),
            reused=reused,
            rebuilt=rebuilt,
        )
        try:
            content = f.read_text(encoding="utf-8")
        except OSError as e:
            log.error(f"读取失败 {f}: {e}")
            continue

        source = _source_for(f)
        digest = _content_hash(content)
        stat = f.stat()
        new_files[source] = {
            "hash": digest,
            "mtime": stat.st_mtime,
            "size": stat.st_size,
        }

        if incremental and old_files.get(source, {}).get("hash") == digest:
            reused_chunks = kept_by_source.get(source, [])
            chunks.extend(reused_chunks)
            reused += len(reused_chunks)
            _emit(
                progress,
                stage="reuse",
                message=f"{f.name} 未变化，复用 {len(reused_chunks)} 段",
                percent=20 + int(file_index / file_total * 70),
                current_file=f.name,
                file_index=file_index,
                file_total=file_total,
                chunk_count=len(chunks),
                reused=reused,
                rebuilt=rebuilt,
            )
            log.info(f"{source}: 未变化，复用 {len(reused_chunks)} 段")
            continue

        paragraphs = _split_paragraphs(content)
        paragraph_total = len(paragraphs)
        _emit(
            progress,
            stage="split",
            message=f"{f.name} 切分为 {paragraph_total} 段",
            percent=base_percent,
            current_file=f.name,
            file_index=file_index,
            file_total=file_total,
            chunk_index=0,
            chunk_total=paragraph_total,
            chunk_count=len(chunks),
            reused=reused,
            rebuilt=rebuilt,
        )
        log.info(f"{source}: {len(paragraphs)} 段，重新 embedding")

        for i, para in enumerate(paragraphs):
            chunk_progress = 20 + int(
                ((file_index - 1) + ((i + 1) / max(paragraph_total, 1)))
                / file_total
                * 70
            )
            _emit(
                progress,
                stage="embedding",
                message=f"生成 embedding: {f.name} ({i + 1}/{paragraph_total})",
                percent=min(92, chunk_progress),
                current_file=f.name,
                file_index=file_index,
                file_total=file_total,
                chunk_index=i + 1,
                chunk_total=paragraph_total,
                chunk_count=len(chunks),
                reused=reused,
                rebuilt=rebuilt,
            )
            try:
                vec = embed(para)
            except EmbeddingError as e:
                log.error(f"embedding 失败（跳过该段）: {e}")
                continue

            chunks.append({
                "chunk_id": _chunk_id(source, i, para),
                "source": source,
                "position": i,
                "text": para,
                "embedding": vec,
            })
            rebuilt += 1

    try:
        _emit(
            progress,
            stage="write",
            message="写入 index.json 和 index_meta.json",
            percent=96,
            file_index=file_total,
            file_total=file_total,
            chunk_count=len(chunks),
            reused=reused,
            rebuilt=rebuilt,
        )
        INDEX_FILE.parent.mkdir(parents=True, exist_ok=True)
        INDEX_FILE.write_text(
            json.dumps(chunks, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        INDEX_META_FILE.write_text(
            json.dumps(
                {
                    "version": 2,
                    "incremental": incremental,
                    "files": new_files,
                    "chunk_count": len(chunks),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
    except OSError as e:
        log.error(f"写入索引失败: {e}")
        _emit(progress, stage="error", message=f"写入索引失败: {e}", percent=100)
        return {"chunk_count": len(chunks), "reused": reused, "rebuilt": rebuilt}

    save_cache()
    _emit(
        progress,
        stage="done",
        message=f"索引完成: {len(chunks)} 段，复用 {reused} 段，重建 {rebuilt} 段",
        percent=100,
        file_index=file_total,
        file_total=file_total,
        chunk_count=len(chunks),
        reused=reused,
        rebuilt=rebuilt,
    )
    log.info(
        f"索引完成: 共 {len(chunks)} 条，复用 {reused} 条，重建 {rebuilt} 条 → {INDEX_FILE.name}"
    )
    return {"chunk_count": len(chunks), "reused": reused, "rebuilt": rebuilt}
