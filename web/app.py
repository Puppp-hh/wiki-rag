"""Streamlit 网页问答界面。

启动（在项目根目录执行）：
    streamlit run web/app.py
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

# 让 Streamlit 直接执行本文件时也能找到 core/ 和 pipeline/ 包
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import streamlit as st  # noqa: E402

from pipeline.query import answer_question  # noqa: E402

# Streamlit 自带控制台输出，关掉 INFO 噪音
logging.getLogger("wiki-rag").setLevel(logging.WARNING)

st.set_page_config(page_title="Wiki RAG", page_icon="📚")
st.title("Wiki RAG 本地问答")
st.caption("Ollama + nomic-embed-text + 本地索引")

with st.sidebar:
    top_k = st.slider("召回段落数", min_value=1, max_value=10, value=3)
    refine = st.checkbox("启用答案二次优化 (refine)", value=True)

question = st.text_input("问题", placeholder="例如：Python 装饰器是什么？")

if st.button("提问", type="primary") and question.strip():
    with st.spinner("思考中..."):
        try:
            answer = answer_question(question, top_k=top_k, refine=refine)
        except Exception as e:  # noqa: BLE001 — UI 层兜底
            st.error(f"出错了: {e}")
        else:
            st.markdown("### 回答")
            st.markdown(answer)
