"""wiki-rag 命令行入口。

仅负责参数解析 + 调度 pipeline 层，不写任何业务逻辑。

用法:
    python main.py ocr                  # raw/ 中的图片 → 同名 .md
    python main.py compile              # raw/ → wiki/
    python main.py index                # wiki/ → index.json
    python main.py query "你的问题"     # 单次问答
    python main.py chat                 # 持续对话模式
"""
from __future__ import annotations

import argparse
import logging
import sys

from core.utils import log
from pipeline.compiler import compile_all
from pipeline.index import build_index
from pipeline.ocr import ocr_all
from pipeline.query import answer_question, query
from pipeline.sources import sync_sources


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="wiki-rag",
        description="本地 RAG：Ollama + nomic-embed-text + 纯 JSON 索引",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("ocr", help="对 raw/ 中的图片做 OCR，生成同名 .md")
    sub.add_parser("compile", help="把 raw/ 的笔记整理到 wiki/")
    idx = sub.add_parser("index", help="对 wiki/ 构建 embedding 索引")
    idx.add_argument(
        "--full",
        action="store_true",
        help="关闭增量索引，强制扫描全部文件",
    )
    sub.add_parser("sources", help="同步可插拔数据源到 data/raw/")

    q = sub.add_parser("query", help="单次检索并回答问题")
    q.add_argument("question", help="要问的问题")
    q.add_argument("--top-k", type=int, default=3, help="召回条数 (默认 3)")
    q.add_argument(
        "--no-refine",
        action="store_true",
        help="跳过答案二次优化（默认开启 refine）",
    )

    c = sub.add_parser("chat", help="进入持续对话模式")
    c.add_argument("--top-k", type=int, default=3, help="召回条数 (默认 3)")
    c.add_argument("--no-refine", action="store_true", help="跳过答案二次优化")

    return parser


def _chat_loop(top_k: int, refine: bool) -> None:
    """简单 REPL：输入问题 → 答案。exit/quit 退出。"""
    # 静默 INFO 日志，保持终端简洁
    logging.getLogger("wiki-rag").setLevel(logging.WARNING)

    print("进入 wiki-rag 对话模式（输入 exit / quit 退出）")
    while True:
        try:
            question = input("\n> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not question:
            continue
        if question.lower() in {"exit", "quit", ":q"}:
            break

        try:
            answer = answer_question(question, top_k=top_k, refine=refine)
        except Exception as e:  # noqa: BLE001 — REPL 中不能让异常打断循环
            print(f"[错误] {e}")
            continue

        print(f"\n{answer}")


def main() -> int:
    args = _build_parser().parse_args()

    try:
        if args.cmd == "ocr":
            ocr_all()
        elif args.cmd == "compile":
            compile_all()
        elif args.cmd == "index":
            build_index(incremental=not args.full)
        elif args.cmd == "sources":
            sync_sources()
        elif args.cmd == "query":
            query(args.question, top_k=args.top_k, refine=not args.no_refine)
        elif args.cmd == "chat":
            _chat_loop(top_k=args.top_k, refine=not args.no_refine)
    except KeyboardInterrupt:
        log.warning("已中断")
        return 130
    except Exception as e:  # 最后兜底
        log.exception(f"未处理异常: {e}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
