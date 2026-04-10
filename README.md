# 🧠 Wiki-RAG (Local RAG System)

A lightweight local RAG (Retrieval-Augmented Generation) system built with:

- 🧠 Ollama (local LLM)
- 📄 Markdown-based knowledge base
- 🔍 Embedding + cosine similarity (numpy)
- ⚡ No vector database required

---

## 🚀 Features

- Convert raw notes → structured wiki
- Build embedding index locally
- Query knowledge with semantic search
- Fully offline (no API cost)

---

## 🏗 Project Structure

wiki-rag/
├── main.py          # CLI 入口（argparse 子命令）
├── utils.py         # 路径常量、日志、cosine_sim
├── llm.py           # Ollama chat 封装（LLMError）
├── embedding.py     # Ollama embedding + 磁盘缓存（EmbeddingError）
├── compiler.py      # raw/ → wiki/（用 llm）
├── index.py         # wiki/ → index.json（用 embedding）
├── query.py         # 检索 + 生成
├── raw/  wiki/  index.json   # 原有数据
└── .embedding_cache.json     # 新增：embedding 缓存（自动生成）

---

## ⚙️ Setup

```bash
brew install ollama
ollama pull deepseek-r1:1.5b
ollama pull nomic-embed-text

▶️ Usage
python main.py compile
python main.py index
python main.py query "your question"