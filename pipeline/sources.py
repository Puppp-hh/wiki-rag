"""可插拔数据源同步。

内置三个轻量 Provider：
    - Obsidian: 从本地 vault 复制 Markdown
    - Notion: 从本地导出的 Markdown 目录复制
    - GitHub Issues: 从本地导出的 issues JSON 转 Markdown

这些 Provider 不强依赖外部 SDK 或网络，方便先在本地课程项目中闭环。
真实 API 同步可以在保持 Provider 接口不变的前提下继续扩展。
"""
from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from core.utils import RAW_DIR, log


@dataclass
class SyncResult:
    source: str
    imported: int = 0
    skipped: int = 0
    message: str = ""


class SourceProvider:
    name = "base"

    def sync(self) -> SyncResult:
        raise NotImplementedError


class ObsidianProvider(SourceProvider):
    name = "obsidian"

    def __init__(self, vault_path: Optional[str]):
        self.vault_path = Path(vault_path).expanduser() if vault_path else None

    def sync(self) -> SyncResult:
        if not self.vault_path or not self.vault_path.exists():
            return SyncResult(self.name, message="未配置 WIKI_RAG_OBSIDIAN_VAULT")
        return _copy_markdown_tree(self.name, self.vault_path)


class NotionProvider(SourceProvider):
    name = "notion"

    def __init__(self, export_path: Optional[str]):
        self.export_path = Path(export_path).expanduser() if export_path else None

    def sync(self) -> SyncResult:
        if not self.export_path or not self.export_path.exists():
            return SyncResult(self.name, message="未配置 WIKI_RAG_NOTION_EXPORT")
        return _copy_markdown_tree(self.name, self.export_path)


class GitHubIssuesProvider(SourceProvider):
    name = "github_issues"

    def __init__(self, issues_json: Optional[str]):
        self.issues_json = Path(issues_json).expanduser() if issues_json else None

    def sync(self) -> SyncResult:
        if not self.issues_json or not self.issues_json.exists():
            return SyncResult(self.name, message="未配置 WIKI_RAG_GITHUB_ISSUES_JSON")

        try:
            issues = json.loads(self.issues_json.read_text(encoding="utf-8"))
        except (OSError, ValueError) as e:
            return SyncResult(self.name, message=f"读取 issues JSON 失败: {e}")

        RAW_DIR.mkdir(parents=True, exist_ok=True)
        imported = 0
        for issue in issues if isinstance(issues, list) else []:
            number = issue.get("number", imported + 1)
            title = _safe_name(issue.get("title", f"issue-{number}"))
            body = issue.get("body") or ""
            url = issue.get("html_url") or issue.get("url") or ""
            text = f"# {title}\n\n- Issue: #{number}\n- URL: {url}\n\n{body}\n"
            (RAW_DIR / f"github-issue-{number}-{title}.md").write_text(
                text, encoding="utf-8"
            )
            imported += 1
        return SyncResult(self.name, imported=imported, message="同步完成")


def sync_sources() -> list[SyncResult]:
    import os

    providers: list[SourceProvider] = [
        ObsidianProvider(os.getenv("WIKI_RAG_OBSIDIAN_VAULT")),
        NotionProvider(os.getenv("WIKI_RAG_NOTION_EXPORT")),
        GitHubIssuesProvider(os.getenv("WIKI_RAG_GITHUB_ISSUES_JSON")),
    ]
    results = []
    for provider in providers:
        result = provider.sync()
        log.info(
            f"数据源 {result.source}: imported={result.imported}, skipped={result.skipped}, {result.message}"
        )
        results.append(result)
    return results


def _copy_markdown_tree(source_name: str, root: Path) -> SyncResult:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    imported = 0
    skipped = 0
    for src in root.rglob("*.md"):
        if ".obsidian" in src.parts:
            skipped += 1
            continue
        rel_name = _safe_name(str(src.relative_to(root).with_suffix("")))
        dst = RAW_DIR / f"{source_name}-{rel_name}.md"
        try:
            shutil.copyfile(src, dst)
            imported += 1
        except OSError:
            skipped += 1
    return SyncResult(source_name, imported=imported, skipped=skipped, message="同步完成")


def _safe_name(value: str) -> str:
    out = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "-" for ch in value)
    return "-".join(part for part in out.split("-") if part)[:120] or "untitled"
