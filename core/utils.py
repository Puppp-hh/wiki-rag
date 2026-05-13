"""公共工具：路径常量、日志、相似度计算。

所有项目内的目录都以这里的常量为准，不要在别处再 hardcode 路径。
"""
from __future__ import annotations

import logging
import os
from pathlib import Path

import numpy as np

# ---------- 路径 ----------
# core/utils.py → 项目根：再上跳两级
ROOT = Path(__file__).resolve().parent.parent

DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
WIKI_DIR = DATA_DIR / "wiki"
INDEX_FILE = DATA_DIR / "index.json"
INDEX_META_FILE = DATA_DIR / "index_meta.json"
SESSIONS_DIR = DATA_DIR / "sessions"

CACHE_DIR = ROOT / "cache"
EMBED_CACHE_FILE = CACHE_DIR / "embedding_cache.json"

# ---------- Ollama ----------
OLLAMA_CHAT_URL = "http://localhost:11434/api/chat"
OLLAMA_EMBED_URL = "http://localhost:11434/api/embeddings"

LLM_MODEL = "deepseek-r1:1.5b"
EMBED_MODEL = "nomic-embed-text"
LLM_BACKEND = os.getenv("WIKI_RAG_LLM_BACKEND", "ollama").strip().lower()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-3-5-haiku-latest")
ANTHROPIC_BASE_URL = os.getenv("ANTHROPIC_BASE_URL", "https://api.anthropic.com")
LLAMA_CPP_BASE_URL = os.getenv("LLAMA_CPP_BASE_URL", "http://localhost:8080")

REQUEST_TIMEOUT = 120  # seconds
FAISS_THRESHOLD = int(os.getenv("WIKI_RAG_FAISS_THRESHOLD", "10000"))
HYBRID_DENSE_WEIGHT = float(os.getenv("WIKI_RAG_DENSE_WEIGHT", "0.7"))


# ---------- 日志 ----------
def setup_logger(name: str = "wiki-rag") -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(
            logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", "%H:%M:%S")
        )
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger


log = setup_logger()


# ---------- 相似度 ----------
def cosine_sim(a, b) -> float:
    a = np.asarray(a, dtype=np.float32)
    b = np.asarray(b, dtype=np.float32)
    na = float(np.linalg.norm(a))
    nb = float(np.linalg.norm(b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return float(np.dot(a, b) / (na * nb))
