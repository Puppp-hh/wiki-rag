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
├── raw/          # original notes
├── wiki/         # generated notes
├── index.json    # embeddings
├── compiler.py   # raw → wiki
├── embedding.py  # embedding logic
├── index.py      # build index
├── query.py      # search + answer
├── llm.py        # LLM request wrapper
├── utils.py
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