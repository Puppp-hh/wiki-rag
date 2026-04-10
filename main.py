"""wiki-rag 命令行入口。

用法:
    python main.py compile              # raw/ → wiki/
    python main.py index                # wiki/ → index.json
    python main.py query "你的问题"     # 检索 + LLM 回答
"""
from __future__ import annotations

import argparse
import sys

from compiler import compile_all
from index import build_index
from query import query
from utils import log


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="wiki-rag",
        description="本地 RAG：Ollama + nomic-embed-text + 纯 JSON 索引",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("compile", help="把 raw/ 的笔记整理到 wiki/")
    sub.add_parser("index", help="对 wiki/ 构建 embedding 索引")

    q = sub.add_parser("query", help="检索并回答问题")
    q.add_argument("question", help="要问的问题")
    q.add_argument("--top-k", type=int, default=3, help="召回条数 (默认 3)")

    return parser


def main() -> int:
    args = _build_parser().parse_args()

    try:
        if args.cmd == "compile":
            compile_all()
        elif args.cmd == "index":
            build_index()
        elif args.cmd == "query":
            query(args.question, top_k=args.top_k)
    except KeyboardInterrupt:
        log.warning("已中断")
        return 130
    except Exception as e:  # 最后兜底，避免暴露 traceback 给普通用户
        log.exception(f"未处理异常: {e}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
