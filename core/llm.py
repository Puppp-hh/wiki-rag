"""LLM 调用封装。

默认后端是 Ollama，也可以通过环境变量切换：
    WIKI_RAG_LLM_BACKEND=ollama | openai | claude | llama.cpp
"""
from __future__ import annotations

import json
from typing import Dict, List, Optional

import requests

from core.utils import (
    ANTHROPIC_API_KEY,
    ANTHROPIC_BASE_URL,
    ANTHROPIC_MODEL,
    LLAMA_CPP_BASE_URL,
    LLM_BACKEND,
    LLM_MODEL,
    OLLAMA_CHAT_URL,
    OPENAI_API_KEY,
    OPENAI_BASE_URL,
    OPENAI_MODEL,
    REQUEST_TIMEOUT,
    log,
)


class LLMError(Exception):
    """LLM 调用失败的统一异常。"""


def chat(
    messages: List[Dict[str, str]],
    model: Optional[str] = None,
    backend: Optional[str] = None,
) -> str:
    """向当前 LLM 后端发送 chat 请求，返回 assistant 内容。"""
    resolved = (backend or LLM_BACKEND or "ollama").lower()
    if resolved == "ollama":
        return _chat_ollama(messages, model or LLM_MODEL)
    if resolved == "openai":
        return _chat_openai(messages, model or OPENAI_MODEL)
    if resolved in {"claude", "anthropic"}:
        return _chat_claude(messages, model or ANTHROPIC_MODEL)
    if resolved in {"llama.cpp", "llamacpp", "llama_cpp"}:
        return _chat_openai_compatible(
            messages,
            model or "local-model",
            f"{LLAMA_CPP_BASE_URL.rstrip('/')}/v1/chat/completions",
            api_key="",
            backend_name="llama.cpp",
        )
    raise LLMError(f"未知 LLM 后端: {resolved}")


def stream_chat(
    messages: List[Dict[str, str]],
    model: Optional[str] = None,
    backend: Optional[str] = None,
):
    """流式返回文本片段。后端不支持时退化为一次性返回。"""
    resolved = (backend or LLM_BACKEND or "ollama").lower()
    if resolved == "ollama":
        yield from _stream_ollama(messages, model or LLM_MODEL)
        return
    if resolved == "openai":
        yield from _stream_openai_compatible(
            messages,
            model or OPENAI_MODEL,
            f"{OPENAI_BASE_URL.rstrip('/')}/chat/completions",
            api_key=OPENAI_API_KEY,
            backend_name="OpenAI",
        )
        return
    if resolved in {"llama.cpp", "llamacpp", "llama_cpp"}:
        yield from _stream_openai_compatible(
            messages,
            model or "local-model",
            f"{LLAMA_CPP_BASE_URL.rstrip('/')}/v1/chat/completions",
            api_key="",
            backend_name="llama.cpp",
        )
        return

    # Anthropic streaming events are more involved; keep it pluggable and safe.
    yield chat(messages, model=model, backend=resolved)


def _chat_ollama(messages: List[Dict[str, str]], model: str) -> str:
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


def _stream_ollama(messages: List[Dict[str, str]], model: str):
    payload = {
        "model": model,
        "messages": messages,
        "stream": True,
    }
    try:
        with requests.post(
            OLLAMA_CHAT_URL, json=payload, timeout=REQUEST_TIMEOUT, stream=True
        ) as resp:
            resp.raise_for_status()
            for raw in resp.iter_lines(decode_unicode=True):
                if not raw:
                    continue
                try:
                    data = json.loads(raw)
                except ValueError as e:
                    raise LLMError("LLM 流式响应不是合法 JSON") from e
                chunk = data.get("message", {}).get("content")
                if chunk:
                    yield chunk
                if data.get("done"):
                    break
    except requests.Timeout as e:
        raise LLMError(f"LLM 请求超时 (>{REQUEST_TIMEOUT}s)") from e
    except requests.ConnectionError as e:
        raise LLMError("无法连接到 Ollama，确认服务已启动 (ollama serve)") from e
    except requests.HTTPError as e:
        raise LLMError(f"LLM 返回 HTTP 错误: {e}") from e


def _chat_openai(messages: List[Dict[str, str]], model: str) -> str:
    return _chat_openai_compatible(
        messages,
        model,
        f"{OPENAI_BASE_URL.rstrip('/')}/chat/completions",
        api_key=OPENAI_API_KEY,
        backend_name="OpenAI",
    )


def _chat_openai_compatible(
    messages: List[Dict[str, str]],
    model: str,
    url: str,
    api_key: str,
    backend_name: str,
) -> str:
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    elif backend_name == "OpenAI":
        raise LLMError("缺少 OPENAI_API_KEY")

    payload = {"model": model, "messages": messages, "stream": False}
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]
    except requests.Timeout as e:
        raise LLMError(f"{backend_name} 请求超时 (>{REQUEST_TIMEOUT}s)") from e
    except requests.ConnectionError as e:
        raise LLMError(f"无法连接到 {backend_name}") from e
    except requests.HTTPError as e:
        raise LLMError(f"{backend_name} 返回 HTTP 错误: {e}") from e
    except (ValueError, KeyError, TypeError, IndexError) as e:
        raise LLMError(f"{backend_name} 响应解析失败") from e


def _stream_openai_compatible(
    messages: List[Dict[str, str]],
    model: str,
    url: str,
    api_key: str,
    backend_name: str,
):
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    elif backend_name == "OpenAI":
        raise LLMError("缺少 OPENAI_API_KEY")

    payload = {"model": model, "messages": messages, "stream": True}
    try:
        with requests.post(
            url, headers=headers, json=payload, timeout=REQUEST_TIMEOUT, stream=True
        ) as resp:
            resp.raise_for_status()
            for raw in resp.iter_lines(decode_unicode=True):
                if not raw:
                    continue
                line = raw.removeprefix("data: ").strip()
                if line == "[DONE]":
                    break
                try:
                    data = json.loads(line)
                    delta = data["choices"][0].get("delta", {})
                except (ValueError, KeyError, TypeError, IndexError) as e:
                    raise LLMError(f"{backend_name} 流式响应解析失败") from e
                chunk = delta.get("content")
                if chunk:
                    yield chunk
    except requests.Timeout as e:
        raise LLMError(f"{backend_name} 请求超时 (>{REQUEST_TIMEOUT}s)") from e
    except requests.ConnectionError as e:
        raise LLMError(f"无法连接到 {backend_name}") from e
    except requests.HTTPError as e:
        raise LLMError(f"{backend_name} 返回 HTTP 错误: {e}") from e


def _chat_claude(messages: List[Dict[str, str]], model: str) -> str:
    if not ANTHROPIC_API_KEY:
        raise LLMError("缺少 ANTHROPIC_API_KEY")

    system_parts = [m["content"] for m in messages if m.get("role") == "system"]
    user_messages = [
        {"role": m.get("role", "user"), "content": m.get("content", "")}
        for m in messages
        if m.get("role") != "system"
    ]
    payload = {
        "model": model,
        "max_tokens": 2048,
        "system": "\n\n".join(system_parts),
        "messages": user_messages,
    }
    headers = {
        "Content-Type": "application/json",
        "x-api-key": ANTHROPIC_API_KEY,
        "anthropic-version": "2023-06-01",
    }
    try:
        resp = requests.post(
            f"{ANTHROPIC_BASE_URL.rstrip('/')}/v1/messages",
            headers=headers,
            json=payload,
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
        return "".join(
            part.get("text", "") for part in data.get("content", [])
            if part.get("type") == "text"
        )
    except requests.Timeout as e:
        raise LLMError(f"Claude 请求超时 (>{REQUEST_TIMEOUT}s)") from e
    except requests.ConnectionError as e:
        raise LLMError("无法连接到 Claude") from e
    except requests.HTTPError as e:
        raise LLMError(f"Claude 返回 HTTP 错误: {e}") from e
    except (ValueError, TypeError) as e:
        raise LLMError("Claude 响应解析失败") from e


def ask(prompt: str, model: Optional[str] = None, backend: Optional[str] = None) -> str:
    """单轮问答的便捷入口。"""
    resolved = backend or LLM_BACKEND or "ollama"
    log.info(f"调用 LLM ({resolved}:{model or 'default'})...")
    return chat([{"role": "user", "content": prompt}], model=model, backend=backend)
