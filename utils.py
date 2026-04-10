"""公共工具：配置常量、日志、相似度计算。"""
from __future__ import annotations

import logging
from pathlib import Path

import numpy as np

# ---------- 路径 ----------
ROOT = Path(__file__).resolve().parent
RAW_DIR = ROOT / "raw"
WIKI_DIR = ROOT / "wiki"
INDEX_FILE = ROOT / "index.json"
EMBED_CACHE_FILE = ROOT / ".embedding_cache.json"

# ---------- Ollama ----------
OLLAMA_CHAT_URL = "http://localhost:11434/api/chat"
OLLAMA_EMBED_URL = "http://localhost:11434/api/embeddings"

LLM_MODEL = "deepseek-r1:1.5b"
EMBED_MODEL = "nomic-embed-text"

REQUEST_TIMEOUT = 120  # seconds


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
