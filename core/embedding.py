"""Embedding 调用 + 磁盘缓存（基于 sha256(model + text) 键）。"""
from __future__ import annotations

import hashlib
import json
from typing import Dict, List, Optional

import requests

from core.utils import (
    CACHE_DIR,
    EMBED_CACHE_FILE,
    EMBED_MODEL,
    OLLAMA_EMBED_URL,
    REQUEST_TIMEOUT,
    log,
)


class EmbeddingError(Exception):
    """Embedding 调用失败的统一异常。"""


_cache: Optional[Dict[str, List[float]]] = None


def _load_cache() -> Dict[str, List[float]]:
    global _cache
    if _cache is not None:
        return _cache
    if EMBED_CACHE_FILE.exists():
        try:
            with EMBED_CACHE_FILE.open("r", encoding="utf-8") as f:
                _cache = json.load(f)
        except (OSError, ValueError):
            log.warning("embedding 缓存文件损坏，已忽略")
            _cache = {}
    else:
        _cache = {}
    return _cache


def save_cache() -> None:
    """把内存缓存落盘。仅在索引构建结束后调用一次即可。"""
    if _cache is None:
        return
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        with EMBED_CACHE_FILE.open("w", encoding="utf-8") as f:
            json.dump(_cache, f)
    except OSError as e:
        log.warning(f"保存 embedding 缓存失败: {e}")


def _cache_key(text: str, model: str) -> str:
    h = hashlib.sha256()
    h.update(model.encode("utf-8"))
    h.update(b"\0")
    h.update(text.encode("utf-8"))
    return h.hexdigest()


def embed(text: str, model: str = EMBED_MODEL) -> List[float]:
    """计算单条文本的 embedding，命中缓存则跳过网络调用。

    要更换 embedding 模型：改 core.utils.EMBED_MODEL，或在调用处传 model 参数。
    换到 OpenAI / 其它服务：重写本函数体即可，调用方无感。
    """
    cache = _load_cache()
    key = _cache_key(text, model)
    if key in cache:
        return cache[key]

    payload = {"model": model, "prompt": text}
    try:
        resp = requests.post(OLLAMA_EMBED_URL, json=payload, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
    except requests.Timeout as e:
        raise EmbeddingError(f"embedding 请求超时 (>{REQUEST_TIMEOUT}s)") from e
    except requests.ConnectionError as e:
        raise EmbeddingError("无法连接到 Ollama，确认服务已启动") from e
    except requests.HTTPError as e:
        raise EmbeddingError(f"embedding 返回 HTTP 错误: {e}") from e
    except ValueError as e:
        raise EmbeddingError("embedding 响应不是合法 JSON") from e

    try:
        vec = data["embedding"]
    except (KeyError, TypeError) as e:
        raise EmbeddingError(f"embedding 响应字段缺失: {data}") from e

    cache[key] = vec
    return vec
