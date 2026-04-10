"""LLM 调用封装。当前实现为 Ollama，未来可替换为 OpenAI / Claude。"""
from __future__ import annotations

from typing import Dict, List

import requests

from utils import LLM_MODEL, OLLAMA_CHAT_URL, REQUEST_TIMEOUT, log


class LLMError(Exception):
    """LLM 调用失败的统一异常。"""


def chat(messages: List[Dict[str, str]], model: str = LLM_MODEL) -> str:
    """向 Ollama 发送 chat 请求，返回 assistant 内容。

    要接入其它提供商（OpenAI / Claude），只需重写本函数，保持签名一致即可。
    """
    payload = {
        "model": model,
        "messages": messages,
        "stream": False,  # 关闭流式，避免 NDJSON 解析问题
    }

    try:
        resp = requests.post(OLLAMA_CHAT_URL, json=payload, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
    except requests.Timeout as e:
        raise LLMError(f"LLM 请求超时 (>{REQUEST_TIMEOUT}s)") from e
    except requests.ConnectionError as e:
        raise LLMError("无法连接到 Ollama，确认服务已启动 (ollama serve)") from e
    except requests.HTTPError as e:
        raise LLMError(f"LLM 返回 HTTP 错误: {e}") from e
    except ValueError as e:  # json 解析失败
        raise LLMError("LLM 响应不是合法 JSON") from e

    try:
        return data["message"]["content"]
    except (KeyError, TypeError) as e:
        raise LLMError(f"LLM 响应字段缺失: {data}") from e


def ask(prompt: str, model: str = LLM_MODEL) -> str:
    """单轮问答的便捷入口。"""
    log.info(f"调用 LLM ({model})...")
    return chat([{"role": "user", "content": prompt}], model=model)
