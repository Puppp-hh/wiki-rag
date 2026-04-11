# 🧠 Wiki-RAG

> **把你散落的 Markdown 笔记，变成一个 100% 离线、可以用自然语言对话的私人知识库。**
>
> Turn your scattered Markdown notes into a fully offline, conversational personal knowledge base.

[![Python](https://img.shields.io/badge/python-3.9%2B-blue)](https://www.python.org/)
[![Node](https://img.shields.io/badge/node-18%2B-green)](https://nodejs.org/)
[![Ollama](https://img.shields.io/badge/powered%20by-Ollama-black)](https://ollama.com)
[![Offline](https://img.shields.io/badge/runs-100%25%20offline-blue)](#)
[![License](https://img.shields.io/badge/license-MIT-blue)](#)

---

## 📌 Project Overview

**Wiki-RAG** 是一个**完全本地运行**的 Retrieval-Augmented Generation (RAG) 系统。

它把你的 Markdown 笔记(甚至截图)做成一个可以「**像问 ChatGPT 一样**」提问的知识库,但全程不联网、不调云端 API、不上传任何数据。

* **LLM** = Ollama 跑的 `deepseek-r1:1.5b`
* **Embedding** = `nomic-embed-text` (768 维)
* **检索** = `numpy` + cosine similarity
* **存储** = 一个 JSON 文件 (`data/index.json`)
* **前端** = Apple 风格的 React + TypeScript UI

> 📖 想从零学懂 RAG?直接读 [`docs.md`](./docs.md)——一份「零基础到精通」的手把手教学手册。

---

## 🚀 Features

| 特性 | 说明 |
|------|------|
| 🔒 **100% Local** | 所有 LLM、embedding、索引、检索全部在本机跑,无云 API |
| 💸 **No API Cost** | 没有 OpenAI / Anthropic 账单,自己的硬件就是上限 |
| 📝 **Markdown Native** | 笔记永远是 plain `.md`,可被 git diff、grep、编辑器直接用 |
| 🧱 **Two-Stage Ingestion** | `raw → wiki`:LLM 先把草稿整理成结构化笔记,再 embed |
| 🖼 **OCR 支持** | 截图丢进 `data/raw/`,自动 OCR 成 Markdown |
| ♻️ **Embedding 缓存** | `sha256(model + text)` 缓存,换模型自动失效 |
| 🎯 **可扩展架构** | 换 LLM / embedding / 存储后端只改一个文件 |
| 🎨 **Apple 风格 UI** | React + TS 前端,Light/Dark 双主题,严格遵守 DESIGN.md |

---

## 🛠 Tech Stack

| 层 | 选型 | 中文 |
|------|------|------|
| LLM Runtime | [Ollama](https://ollama.com) | 本地大模型托管 |
| LLM Model | `deepseek-r1:1.5b` | 1.5B 参数推理模型 |
| Embedding Model | `nomic-embed-text` | 768 维语义向量模型 |
| Backend | Python 3.9+ · `requests` · `numpy` | 极简后端 |
| API | FastAPI · Uvicorn | HTTP 接口层 |
| Frontend | React 18 · TypeScript · Vite | 前端工程 |
| Styling | CSS Variables (无 Tailwind) | Apple 风设计系统 |
| Storage | JSON (`index.json`) + sha256 cache | 无外部数据库 |
| OCR (可选) | `pytesseract` + Pillow | 图片转文本 |

---

## 📂 Project Structure

```
wiki-rag/
├── main.py                       # CLI 入口(argparse 分发)
├── core/                         # 能力层(不依赖业务)
│   ├── utils.py                  # 路径常量 / 日志 / cosine_sim
│   ├── llm.py                    # Ollama chat 封装 + LLMError
│   └── embedding.py              # Ollama embedding + 磁盘缓存
├── pipeline/                     # 业务层
│   ├── ocr.py                    # 图片 → Markdown
│   ├── compiler.py               # raw/ → wiki/(LLM 整理)
│   ├── index.py                  # wiki/ → index.json
│   ├── query.py                  # 检索 + 生成
│   └── refine.py                 # 二次重写,清理小模型噪音
├── web/
│   ├── app.py                    # Streamlit UI(可选)
│   └── api.py                    # FastAPI 接口(给 React 前端用)
├── web-frontend/                 # React + TS 前端
│   ├── src/
│   │   ├── App.tsx
│   │   ├── theme.css             # Apple 风 CSS Variables
│   │   ├── hooks/useTheme.ts     # Light/Dark 主题 Hook
│   │   ├── components/GlassNav.tsx
│   │   ├── pages/
│   │   │   ├── Chat.tsx
│   │   │   ├── Library.tsx
│   │   │   ├── Debug.tsx
│   │   │   └── Settings.tsx
│   │   └── styles/*.css
│   ├── index.html
│   ├── package.json
│   ├── tsconfig.json
│   └── vite.config.ts
├── design/
│   └── DESIGN.md                 # Apple 风设计系统(UI 唯一真相源)
├── data/
│   ├── raw/                      # 原始笔记 + 截图
│   ├── wiki/                     # LLM 整理后的结构化笔记
│   └── index.json                # embedding 索引
├── cache/
│   └── embedding_cache.json      # sha256-keyed 缓存
├── docs.md                       # 📖 零基础教学手册(必读)
└── README.md
```

---

## ⚡ Quick Start

### 0. 环境要求 (Prerequisites)

* **Python 3.9+**
* **Node.js 18+**(只要前端时需要)
* **[Ollama](https://ollama.com)**(必须)
* *(可选)* **Tesseract** 用于 OCR
  * macOS: `brew install tesseract tesseract-lang`
  * Ubuntu: `sudo apt install tesseract-ocr tesseract-ocr-chi-sim`

### 1. 克隆项目

```bash
git clone https://github.com/<your-name>/wiki-rag.git
cd wiki-rag
```

### 2. 装 Python 依赖

```bash
pip install -r requirements.txt
# 如果跑前端 API,再装:
pip install fastapi uvicorn
```

`requirements.txt` 最小集:

```
requests
numpy
pytesseract   # 可选 — OCR
Pillow        # 可选 — OCR
streamlit     # 可选 — Streamlit UI
```

### 3. 启动 Ollama 并拉模型

```bash
ollama serve &
ollama pull deepseek-r1:1.5b
ollama pull nomic-embed-text
```

### 4. 把笔记放进 `data/raw/`

```bash
cp ~/notes/*.md data/raw/
# 也可以丢截图
cp ~/screenshots/*.png data/raw/
```

### 5. 跑完整流水线

```bash
python main.py ocr       # 截图 → Markdown(可选)
python main.py compile   # raw/ → wiki/
python main.py index     # wiki/ → index.json
python main.py query "Python 装饰器是什么?"
```

### 6. (可选)启动前端 + API

```bash
# Terminal 1 — FastAPI 后端
uvicorn web.api:app --reload --port 8000

# Terminal 2 — React 前端
cd web-frontend
npm install
npm run dev    # http://localhost:5173
```

---

## 💡 Usage

### CLI 一句话问答

```bash
python main.py query "什么是 Python 装饰器?"
```

### 多轮 Chat REPL

```bash
python main.py chat
```

### 调整检索深度 / 关闭二次重写

```bash
python main.py query "解释 useEffect" --top-k 5 --no-refine
```

### Streamlit UI(简易)

```bash
streamlit run web/app.py     # http://localhost:8501
```

### React 前端(完整)

进入 `http://localhost:5173`,会看到四个页面:

| 页面 | 功能 |
|------|------|
| **Chat** | 主问答(多轮记忆 + 折叠的检索结果 + 相似度横向条) |
| **Library** | raw / wiki 文件管理 + 一键 Rebuild Index |
| **Debug** | embedding 维度、Top-K、cosine 分数可视化 |
| **Settings** | Light / Dark 主题切换 + 模型信息 |

---

## 📖 Example

```bash
$ python main.py query "Python 装饰器是什么?"

[INFO] 计算问题 embedding...
[INFO]   hit 0.8412 | [python.md] 装饰器是一种在不修改原函数的情况下...
[INFO]   hit 0.7891 | [python.md] @decorator 语法等价于 func = decorator(func) ...
[INFO]   hit 0.6320 | [python.md] 常见装饰器:@staticmethod / @classmethod ...
[INFO] 生成初始回答...
[INFO] 二次优化回答 (refine)...

--- 回答 ---
### 定义
装饰器(decorator)是一个**接收函数并返回新函数**的可调用对象,用于在不修改原函数源码的情况下扩展行为。

### 原理
`@decorator` 是 `func = decorator(func)` 的语法糖。常见用途包括日志、缓存、权限校验、重试等横切关注点。

### 示例
```python
from functools import wraps
def log_calls(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        print(f"calling {func.__name__}")
        return func(*args, **kwargs)
    return wrapper
```

### 总结
装饰器是 Python 里给函数「包一层」的标准手法,干净、可组合、定义即生效。
```

---

## 🌐 API Reference

后端在 `web/api.py`,启动后默认 `http://localhost:8000`:

| Method | Path | 说明 |
|--------|------|------|
| `POST` | `/api/query` | 完整 RAG 问答(检索 + 生成 + refine),返回 `{answer, hits}` |
| `POST` | `/api/debug` | 只做检索 + 暴露 embedding 元信息 |
| `GET`  | `/api/library` | 列出 raw/ 文件 + 是否已索引 + 段数 |
| `POST` | `/api/library/rebuild` | 重新构建索引 |

请求示例:

```bash
curl -X POST http://localhost:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{"question": "Python 装饰器是什么?", "top_k": 3, "refine": true}'
```

---

## 📸 Screenshots

> 截图会在前端首发后补上。所有页面严格遵守 [`design/DESIGN.md`](./design/DESIGN.md) 的 Apple 风格。

| 页面 | 占位 |
|------|------|
| Chat (Light) | `docs/images/chat-light.png` *(coming soon)* |
| Chat (Dark)  | `docs/images/chat-dark.png` *(coming soon)* |
| Library      | `docs/images/library.png` *(coming soon)* |
| Debug        | `docs/images/debug.png` *(coming soon)* |
| Settings     | `docs/images/settings.png` *(coming soon)* |

---

## 🗺 Roadmap

* [ ] 增量索引(只 re-embed 改动文件)
* [ ] Hybrid 检索(BM25 + dense)
* [ ] 引用回显(答案末尾贴 `[source: wiki/python.md]`)
* [ ] FAISS 后端(>10K chunks 时自动启用)
* [ ] 可插拔 LLM 后端(OpenAI / Claude / llama.cpp)
* [ ] 可插拔数据源(Obsidian / Notion / GitHub Issues)
* [ ] 流式输出(SSE)前端打字机效果
* [ ] 多用户会话存储(`data/sessions/`)
* [ ] Dockerfile(Ollama bundled)

---

## 🙋 FAQ

**Q: 为什么不用向量数据库?**
A: chunk 数 < 1 万 时,`numpy` 线性扫描比任何 vector DB 都快,而且 `index.json` 可被 `git diff`、`grep`、人眼直接看。等真的扛不住再换 FAISS。

**Q: 能换 LLM 吗?**
A: 改 `core/utils.py::LLM_MODEL`,或重写 `core/llm.py::chat()` 接 OpenAI/Claude——业务层无感。

**Q: 为什么有 `raw/` 和 `wiki/` 两层?**
A: 「写笔记」和「整理笔记」是两件事。`raw/` 让你想到啥写啥,LLM compiler 自动整理成结构化 wiki,降低写笔记心智负担。

更多问题请见 [`docs.md` § 8 FAQ](./docs.md#8-faq你一定会遇到的问题)。

---

## 📄 License

[MIT](./LICENSE) © 2026

---

## 🎓 想从零学懂 RAG?

直接打开 [`docs.md`](./docs.md)——一份**零基础到精通**的中文教学手册:

1. 什么是 RAG(开卷考试类比)
2. 为什么 RAG 比裸 LLM 强
3. 完整工作流程(讲故事 + 文字流程图)
4. 三个核心概念:Embedding / Cosine Similarity / 语义搜索
5. 五步手把手实现一个最小 RAG
6. 本项目代码逐文件解析
7. 实际运行示例
8. FAQ
9. 进阶优化(chunk / top-k / 缓存 / prompt)
10. 扩展方向(Web UI / OCR / Obsidian / Agent 记忆)
