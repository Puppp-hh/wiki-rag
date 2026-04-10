# 🧠 Wiki-RAG

> **Turn your Markdown notes into a private, offline knowledge base you can actually talk to.**

A local-first Retrieval-Augmented Generation pipeline for personal Markdown wikis. Embedding, retrieval, and generation all run on your machine — no cloud APIs, no vector database, no telemetry.

**中文简介**：本地优先的 RAG 系统。用 Ollama + Markdown + 纯 JSON 索引，把零散的笔记（甚至截图）变成一个能用自然语言提问的私人知识库。全程离线，无 API 费用。

![Python](https://img.shields.io/badge/python-3.9%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Offline](https://img.shields.io/badge/runs-100%25%20offline-brightgreen)
![Ollama](https://img.shields.io/badge/powered%20by-Ollama-black)

---

## ✨ Features

- **100% offline** — powered by [Ollama](https://ollama.com) running `deepseek-r1:1.5b` for generation and `nomic-embed-text` for semantic search
- **Markdown-native** — notes stay as plain `.md` files; version-controllable, diffable, future-proof
- **Two-stage ingestion** — raw drafts are auto-compiled by an LLM into structured wiki entries *before* indexing, so retrieval operates on clean text
- **OCR pipeline** — drop screenshots (`.png/.jpg`) into `data/raw/` and `pytesseract` turns them into searchable notes (中英双语 `chi_sim+eng`)
- **Answer refinement** — a second LLM pass rewrites noisy outputs into `definition → principle → example → summary` structure
- **Three interfaces** — one-shot CLI, interactive `chat` REPL, and a Streamlit web UI
- **No vector DB required** — a single `data/index.json` + vectorized `numpy` cosine scan handles thousands of chunks in milliseconds
- **Embedding cache** — `sha256(model + text)` keyed, per-model, automatically invalidated when you swap models
- **Layered architecture** — swapping Ollama for OpenAI/Claude is a single-file change

---

## 🏛 Architecture

```
  data/raw/*.png,.jpg ──► OCR (pytesseract) ──┐
                                               ▼
  data/raw/*.md ──► compile (LLM) ──► data/wiki/*.md
                                               │
                                               ▼
                                    chunk + embed (Ollama)
                                               │
                                               ▼
                                     data/index.json
                                               │
  user question ──► embed ──► cosine top-k ──► RAG prompt ──► LLM ──► refine ──► answer
```

The codebase is strictly layered — lower layers never import upper layers:

| Layer | Responsibility | Depends on |
|---|---|---|
| `core/` | Capability primitives: LLM call, embedding, config, cosine similarity | External libs only |
| `pipeline/` | Business workflows: OCR, compile, index, query, refine | `core/` |
| `main.py` / `web/` | Entry points: CLI dispatcher and Streamlit UI | `pipeline/` |

Want to plug in OpenAI or Claude? Rewrite `core/llm.py::chat()` — nothing else changes.

---

## 📁 Project Structure

```
wiki-rag/
├── main.py                     # CLI entry (argparse dispatcher)
├── core/                       # Capability layer
│   ├── utils.py                # paths, logging, cosine similarity
│   ├── llm.py                  # Ollama chat wrapper + LLMError
│   └── embedding.py            # Ollama embedding + disk cache
├── pipeline/                   # Workflow layer
│   ├── ocr.py                  # image → markdown (pytesseract)
│   ├── compiler.py             # raw/ → wiki/ via LLM
│   ├── index.py                # wiki/ → data/index.json
│   ├── query.py                # retrieve + generate + refine
│   └── refine.py               # second-pass answer cleanup
├── web/
│   └── app.py                  # Streamlit UI
├── data/
│   ├── raw/                    # original notes + screenshots
│   ├── wiki/                   # LLM-compiled structured notes
│   └── index.json              # embedding index
├── cache/
│   └── embedding_cache.json    # sha256-keyed embedding cache
├── docs.md                     # learning guide
└── README.md
```

---

## ⚙️ How It Works

The RAG pipeline has four stages, each independently runnable:

1. **OCR** *(optional)* — `pipeline.ocr` scans `data/raw/` for `.png/.jpg/.jpeg`, runs `pytesseract` with `chi_sim+eng`, strips symbol noise, and writes a sibling `.md`.
2. **Compile** — `pipeline.compiler` sends each raw note to the LLM with a strict rewrite prompt (hierarchical headings, bolded keywords, trailing summary). Output lands in `data/wiki/`.
3. **Index** — `pipeline.index` splits each wiki file on blank lines, embeds every chunk via `nomic-embed-text`, and serializes `{source, text, embedding}` records into `data/index.json`. Embeddings are cached on disk, so re-indexing unchanged notes is near-instant.
4. **Query** — `pipeline.query` embeds the question, computes cosine similarity against every chunk in the embedding space, picks top-k, stuffs them into a RAG prompt, and asks the LLM. A second `refine` pass rewrites the output into a clean structured answer.

---

## 🚀 Setup

### Prerequisites

- **Python 3.9+**
- **[Ollama](https://ollama.com)** running locally (`ollama serve`)
- *(Optional, for OCR)* **Tesseract**:
  - macOS: `brew install tesseract tesseract-lang`
  - Ubuntu: `sudo apt install tesseract-ocr tesseract-ocr-chi-sim`

### Install

```bash
git clone https://github.com/<you>/wiki-rag.git
cd wiki-rag

pip install -r requirements.txt

# Pull the local models
ollama pull deepseek-r1:1.5b
ollama pull nomic-embed-text
```

Minimal `requirements.txt`:

```
requests
numpy
pytesseract   # optional — OCR
Pillow        # optional — OCR
streamlit     # optional — Web UI
```

---

## 💻 Usage

All commands run from the project root.

### CLI

```bash
# 1. (Optional) OCR screenshots dropped into data/raw/
python main.py ocr

# 2. Compile raw notes into structured wiki markdown
python main.py compile

# 3. Build the embedding index
python main.py index

# 4. Ask a one-shot question
python main.py query "What is a Python decorator?"

# 4b. Tune retrieval depth / skip the refinement pass
python main.py query "What is a Python decorator?" --top-k 5 --no-refine

# 5. Interactive chat REPL (ChatGPT-style)
python main.py chat
```

### Web UI

```bash
streamlit run web/app.py
```

Opens at `http://localhost:8501` — sidebar controls for top-k and the refine toggle.

---

## 📖 Example

```bash
$ python main.py query "What is a Python decorator?"
```

**Output:**

### Definition
A decorator is a callable that takes a function (or class) and returns a new one with additional behavior, without modifying the original source.

### Principle
The `@decorator` syntax is syntactic sugar for `func = decorator(func)`. It lets you wrap cross-cutting concerns — logging, caching, permission checks, retries — around existing functions in a reusable, composable way.

### Example

```python
from functools import wraps

def log_calls(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        print(f"calling {func.__name__}")
        return func(*args, **kwargs)
    return wrapper

@log_calls
def greet(name):
    return f"hello, {name}"
```

### Summary
Decorators transform functions at definition time — a clean, idiomatic way to add cross-cutting behavior in Python.

---

## 🧭 Design Philosophy

### Why not use a vector database?

Vector databases (FAISS, Chroma, Milvus, Qdrant) are purpose-built for million-scale retrieval with low-latency ANN indexes. They are **the right tool** when:

- Your corpus exceeds ~100K chunks
- You need sub-100ms retrieval at high QPS
- You need filtering, hybrid search, or incremental updates at scale

Personal knowledge bases rarely hit any of those thresholds. A few thousand paragraphs fit comfortably in memory, and a vectorized cosine scan over a `numpy.ndarray` finishes in **single-digit milliseconds**. Adding a vector DB buys you:

- Another daemon to keep running
- Another schema to migrate
- Another failure mode to debug
- A new abstraction wall between you and your own data

…in exchange for performance you don't need. `index.json` is greppable, diffable, portable, and human-inspectable. When the corpus eventually outgrows linear search, swapping in FAISS is a ~20-line change isolated to `pipeline/index.py` and `pipeline/query.py`.

> **Principle: use the simplest thing that works. Graduate only when the data forces you to.**

### Why the two-stage `raw → wiki` ingestion?

Writing notes and *structuring* notes are different cognitive tasks. `raw/` lets you dump ideas without format overhead; the LLM compiler turns that dump into clean, retrieval-friendly markdown. Clean separation between **authoring** and **organizing**.

### Why a second `refine` pass on the answer?

Small local models (sub-3B params) produce noisy, off-topic, occasionally hallucinated output even with good retrieval. A second LLM pass with a strict rewrite prompt — *stay on topic, remove fabrications, produce definition/principle/example/summary structure* — dramatically improves output quality at the cost of one extra call. Disable it with `--no-refine` when latency matters.

---

## 🗺 Roadmap

- [ ] Pluggable LLM backends (OpenAI / Claude / `llama.cpp`)
- [ ] Pluggable embedding backends (sentence-transformers, BGE, Voyage)
- [ ] Hybrid retrieval (BM25 + dense)
- [ ] Incremental indexing (only re-embed changed files)
- [ ] Citation rendering in answers (`[source: wiki/python.md]`)
- [ ] Conversational memory in `chat` mode
- [ ] FAISS backend auto-enabled above 10K chunks
- [ ] Dockerfile with Ollama bundled

---

## 📄 License

[MIT](./LICENSE) © 2026
