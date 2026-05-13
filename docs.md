# Wiki-RAG 项目说明文档

> 当前文档基于本仓库现有代码整理，目标是帮助你快速理解项目能做什么、怎么启动、核心技术怎么串起来，以及面试时怎么讲。

---

## 1. 项目简介

Wiki-RAG 是一个本地知识库问答系统。它可以把 Markdown、普通文本、PDF、Word、图片以及代码文件导入 Library，自动抽取成可索引的 Markdown，再通过 Embedding、Hybrid 检索和 LLM 生成回答。

项目适合用来管理个人笔记、课程资料、技术文档和代码片段。用户可以像使用 ChatGPT 一样提问，但回答会优先基于本地知识库，并在答案末尾展示来源引用，例如 `[source: wiki/python.md]`。

当前项目不是 Java/Spring Boot 项目，而是一个 **Python FastAPI + React + Ollama** 的本地 RAG 应用。

---

## 2. 当前核心功能

| 功能 | 当前状态 | 说明 |
|---|---|---|
| 文档导入 | 已完成 | 支持单文件上传和文件夹上传 |
| 多文件类型 | 已完成 | 支持 md、txt、pdf、docx、图片、常见代码文件 |
| 文档管理 | 已完成 | Library 页面可查看、编辑、删除、保存并索引 |
| 自动 Rebuild | 已完成 | 上传文件后自动重建索引，并显示进度 |
| 增量索引 | 已完成 | 通过文件 hash 复用未变化 chunk，只重建改动文件 |
| Hybrid 检索 | 已完成 | BM25 + dense embedding + 规则 rerank |
| 引用回显 | 已完成 | 答案末尾显示命中文档来源 |
| SSE 流式输出 | 已完成 | Chat 页面类似打字机逐段显示答案 |
| 多用户会话 | 已完成 | 会话保存到 `data/sessions/` |
| Debug 调试 | 已完成 | 展示 embedding、Top-K、阈值、检索分数、rerank 原因 |
| 可插拔 LLM | 已完成 | 支持 Ollama / OpenAI / Claude / llama.cpp |
| FAISS 后端 | 已接入 | chunk 超过阈值时尝试 FAISS，不可用则回退 numpy |
| OCR 图片识别 | 已接入 | 依赖 `pytesseract + Pillow + tesseract` |

---

## 3. 技术栈

| 技术 | 所属层级 | 项目中作用 | 掌握优先级 |
|---|---|---|---|
| Python | 后端语言 | 实现 RAG 流程、文件处理、检索与 API | 必须掌握 |
| FastAPI | API 层 | 提供 Chat、Library、Debug、Sessions 接口 | 必须掌握 |
| React 18 | 前端 | 实现 Chat / Library / Debug / Settings 页面 | 需要理解 |
| TypeScript | 前端 | 约束组件状态、接口数据结构 | 需要理解 |
| Vite | 前端工程 | 本地开发和构建 React 应用 | 了解即可 |
| Ollama | LLM Runtime | 本地运行大模型和 embedding 模型 | 必须掌握 |
| nomic-embed-text | Embedding | 把问题和文档 chunk 转成向量 | 必须掌握 |
| NumPy | 向量计算 | dense 检索时计算 cosine similarity | 必须掌握 |
| BM25 | 关键词检索 | 提升代码、文件名、精确词命中的效果 | 需要理解 |
| FAISS | 向量检索 | 大量 chunk 时加速 dense 检索 | 了解即可 |
| SSE | 流式传输 | 让前端逐段显示 LLM 输出 | 需要理解 |
| JSON 文件 | 存储 | 保存索引、索引元数据、会话、embedding 缓存 | 必须掌握 |
| pytesseract | OCR | 图片转文本，供索引使用 | 了解即可 |

---

## 4. 项目整体架构

### 4.1 数据构建链路

```text
Library 上传文件 / data/raw 放入文件
→ pipeline.documents 识别文件类型并抽取文本
→ sync_raw_markdown_to_wiki 同步到 data/wiki
→ pipeline.index 按段落切 chunk
→ core.embedding 调 Ollama 生成向量
→ 写入 data/index.json 和 data/index_meta.json
```

### 4.2 问答链路

```text
用户在 Chat 输入问题
→ 前端请求 /api/query/stream
→ FastAPI 调 pipeline.query.stream_answer
→ pipeline.retrieval 执行 Hybrid 检索
→ Top-K 命中文档片段拼接为上下文
→ core.llm 调 Ollama / OpenAI / Claude / llama.cpp
→ FastAPI 通过 SSE 持续返回 token
→ React 前端逐段追加到 assistant 消息
```

### 4.3 RAG 核心流程

```text
用户提问
→ 查询改写
→ Embedding 向量生成
→ BM25 关键词召回
→ Dense 向量相似度召回
→ 分数归一化与融合
→ 规则 rerank
→ Top-K 结果返回
→ 拼接上下文
→ LLM 生成回答
→ 引用来源回显
```

---

## 5. 如何启动项目

### 5.1 启动 Ollama

```bash
ollama serve
```

如果还没有模型，先拉取：

```bash
ollama pull deepseek-r1:1.5b
ollama pull nomic-embed-text
```

### 5.2 启动 FastAPI 后端

在项目根目录执行：

```bash
python3 -m uvicorn web.api:app --reload --port 8000
```

### 5.3 启动 React 前端

```bash
cd web-frontend
npm install
npm run dev
```

默认访问：

```text
http://localhost:5173
```

### 5.4 命令行方式

```bash
python main.py index
python main.py query "Wiki-RAG 是什么"
python main.py chat
```

---

## 6. 目录结构说明

| 目录 / 文件 | 作用 | 重点关注 |
|---|---|---|
| `main.py` | CLI 入口 | `ocr`、`compile`、`index`、`query`、`chat` 命令 |
| `core/utils.py` | 公共配置 | 路径、模型名、环境变量、相似度函数 |
| `core/embedding.py` | Embedding 封装 | 调 Ollama embedding，并做缓存 |
| `core/llm.py` | LLM 后端封装 | Ollama / OpenAI / Claude / llama.cpp |
| `core/sessions.py` | 会话存储 | 多用户 session JSON |
| `pipeline/documents.py` | 文档抽取 | md/txt/pdf/docx/image/code 转 Markdown |
| `pipeline/index.py` | 索引构建 | raw → wiki → chunk → embedding → index |
| `pipeline/retrieval.py` | 检索算法 | BM25、dense、FAISS、rerank、citation |
| `pipeline/query.py` | RAG 问答 | 构造 prompt、调用 LLM、流式输出 |
| `pipeline/ocr.py` | 图片 OCR | 图片识别为文本 |
| `pipeline/sources.py` | 数据源同步 | Obsidian / Notion / GitHub Issues |
| `web/api.py` | FastAPI 接口 | Chat、Library、Debug、Session API |
| `web-frontend/src/pages/Chat.tsx` | Chat 页面 | 问答、流式输出、复制、滚动位置 |
| `web-frontend/src/pages/Library.tsx` | Library 页面 | 文件上传、文件夹上传、编辑、删除、Rebuild |
| `web-frontend/src/pages/Debug.tsx` | Debug 页面 | 查看检索分数与 rerank 细节 |
| `data/raw/` | 原始文件 | 用户上传或同步来的原文件 |
| `data/wiki/` | 可索引 Markdown | 文档抽取后的 Markdown |
| `data/index.json` | 向量索引 | chunk 文本与 embedding |
| `data/index_meta.json` | 增量索引元数据 | 文件 hash、mtime、chunk 数 |
| `data/sessions/` | 会话数据 | 多用户对话记录 |

---

## 7. Library 文档管理

### 7.1 支持的文件类型

| 类型 | 扩展名 | 是否可编辑 | 如何索引 |
|---|---|---|---|
| Markdown | `.md` | 是 | 直接作为 Markdown |
| Text | `.txt` | 是 | 加标题后转 Markdown |
| Word | `.docx` | 否 | 解析 `word/document.xml` 抽取段落 |
| PDF | `.pdf` | 否 | 使用 `pypdf` / `PyPDF2` / `pdfplumber` 抽取文本 |
| 图片 | `.png` `.jpg` `.jpeg` `.webp` | 否 | 使用 OCR 抽取文本 |
| 代码 | `.java` `.py` `.js` `.ts` `.vue` `.html` `.css` `.json` `.xml` `.sql` 等 | 是 | 包装成 Markdown 代码块 |

### 7.2 文件夹上传

前端的 `Upload Folder` 会使用浏览器的目录上传能力，保留相对路径。例如上传：

```text
src/main/java/App.java
src/main/resources/application.yml
```

后端会保存到：

```text
data/raw/src/main/java/App.java
data/raw/src/main/resources/application.yml
```

重建索引后会同步到：

```text
data/wiki/src/main/java/App-java.md
data/wiki/src/main/resources/application-yml.md
```

这样做的好处是：检索结果和引用来源能保留原始目录信息，适合导入小型代码项目或课程代码。

### 7.3 代码文件如何进入 RAG

代码文件不会直接把原文塞进索引，而是转换成 Markdown 代码块：

````md
# App.java

> 原始路径：`src/App.java`

```java
public class App {}
```
````

这样 LLM 在回答时可以同时看到文件名、路径和代码内容。

---

## 8. 索引构建机制

### 8.1 raw 与 wiki 的分工

```text
data/raw  = 原始文件，保留用户上传的真实文件
data/wiki = 可索引 Markdown，供 chunk 和 embedding 使用
```

这样设计的原因：

- 原始文件不会被破坏；
- PDF、Word、图片、代码都能统一转成 Markdown；
- 后续只需要索引 `data/wiki/**/*.md`，流程简单稳定。

### 8.2 增量索引

`pipeline.index.build_index()` 会读取 `data/index_meta.json`。如果某个 wiki 文件内容 hash 没变，就复用旧 chunk 和旧 embedding；只有文件变化时才重新切分和 re-embed。

好处：

- 文件多时 Rebuild 更快；
- 上传少量文件不用全量重算；
- 保持 JSON 索引简单可查。

### 8.3 空索引处理

如果删除所有文件，项目会写入空的 `index.json` 和 `index_meta.json`，避免旧索引残留导致“Library 已删除但 Chat 仍能搜到旧内容”的问题。

---

## 9. 检索算法说明

### 9.1 Top-K 是什么

Top-K 表示每次检索返回相似度最高的前 K 个片段。

例如 `Top-K = 3`：

```text
问题：Wiki-RAG 是什么？
→ 检索所有 chunk
→ 按相关性排序
→ 取前 3 个片段作为上下文
```

K 太小可能漏信息，K 太大可能把无关内容塞给 LLM。个人知识库一般用 3 到 5 比较合适。

### 9.2 相似度阈值

前端支持阈值：

```text
0.0 / 0.2 / 0.4 / 0.6 / 0.8
```

阈值越高，检索结果越严格。若没有结果，可以降低阈值；如果回答经常跑题，可以提高阈值。

### 9.3 Hybrid 检索

项目不是只用向量检索，而是 Hybrid：

```text
final_score = dense_score * WIKI_RAG_DENSE_WEIGHT
            + bm25_score  * (1 - WIKI_RAG_DENSE_WEIGHT)
```

默认：

```text
WIKI_RAG_DENSE_WEIGHT=0.7
```

原因：

- dense embedding 擅长语义相似；
- BM25 擅长精确关键词、文件名、代码符号；
- 两者结合比单独使用更稳。

### 9.4 查询改写与 rerank

`pipeline/retrieval.py` 对部分查询做规则扩展，例如：

```text
wikirag → wiki-rag / wiki rag / Wiki-RAG / 本地知识库 / RAG
```

之后再根据文件名、标题、正文命中、覆盖率、长度等规则做轻量 rerank。Debug 页面可以看到这些细节。

### 9.5 FAISS 自动后端

当 chunk 数量超过：

```text
WIKI_RAG_FAISS_THRESHOLD=10000
```

系统会优先尝试使用 FAISS 做 dense 检索。如果本地没有安装 FAISS，会自动回退到 NumPy。

---

## 10. Chat 问答模式

前端 Chat 支持 4 种回答模式：

| 模式 | 含义 | 适合场景 |
|---|---|---|
| 拓展 | 基于知识库，允许补充通用背景知识 | 学习、面试准备 |
| 总结 | 只总结命中的知识库内容 | 笔记归纳 |
| 严格 | 只能根据知识库回答，不足就说明不足 | 查资料、避免幻觉 |
| 原文 | 不调用 LLM，直接返回最相关片段 | 验证检索效果 |

答案末尾会追加引用：

```text
[source: wiki/wiki-rag项目技术说明书.md]
```

---

## 11. 为什么支持流式输出

项目使用 **SSE（Server-Sent Events）** 实现打字机效果。

普通接口：

```text
前端提问
→ 后端等 LLM 完整生成完
→ 一次性返回整段答案
→ 前端一次性显示
```

当前流式接口：

```text
前端请求 /api/query/stream
→ FastAPI 返回 text/event-stream
→ Ollama 每生成一小段 token
→ 后端 yield 一个 SSE event
→ 前端 readSse() 收到 token
→ setMessages() 追加到当前回答
```

核心代码位置：

- 后端：`web/api.py` 的 `/api/query/stream`
- 生成：`pipeline/query.py` 的 `stream_answer()`
- LLM：`core/llm.py` 的 `stream_chat()`
- 前端：`Chat.tsx` 的 `readSse()` 和 `onToken`

面试表达：

> 项目中我用 SSE 实现流式输出。FastAPI 使用 StreamingResponse 返回 text/event-stream，LLM 每生成一段 token，后端就通过 yield 推给前端。前端使用 ReadableStream 解析 SSE event，在 onToken 回调里不断更新 assistant 消息内容，因此用户看到的就是类似 ChatGPT 的打字机效果。

---

## 12. FastAPI 接口说明

| 模块 | 接口 | 方法 | 作用 |
|---|---|---|---|
| Chat | `/api/query` | POST | 普通问答，一次性返回 |
| Chat | `/api/query/stream` | POST | SSE 流式问答 |
| Search | `/api/search` | POST | 只检索，不依赖 LLM |
| Debug | `/api/debug` | POST | 返回 embedding 和检索细节 |
| Library | `/api/library` | GET | 列出所有支持文件 |
| Library | `/api/library/upload` | POST | 上传文件并自动 Rebuild |
| Library | `/api/library/file/{name}` | GET | 读取文件预览 |
| Library | `/api/library/file/{name}` | PUT | 保存可编辑文件并索引 |
| Library | `/api/library/file/{name}` | DELETE | 删除 raw 和对应 wiki 文件 |
| Library | `/api/library/blob/{name}` | GET | 返回图片/PDF 等原始文件 |
| Rebuild | `/api/library/rebuild` | POST | 启动重建索引任务 |
| Rebuild | `/api/library/rebuild/{task_id}` | GET | 查询重建进度 |
| Sources | `/api/sources/sync` | POST | 同步外部数据源 |
| Sessions | `/api/sessions/{session_id}` | GET | 读取会话 |
| Sessions | `/api/sessions/{session_id}` | DELETE | 清空会话 |

---

## 13. 可插拔 LLM 后端

默认使用 Ollama：

```bash
export WIKI_RAG_LLM_BACKEND=ollama
```

可切换到 OpenAI：

```bash
export WIKI_RAG_LLM_BACKEND=openai
export OPENAI_API_KEY=你的 key
export OPENAI_MODEL=gpt-4o-mini
```

可切换到 Claude：

```bash
export WIKI_RAG_LLM_BACKEND=claude
export ANTHROPIC_API_KEY=你的 key
export ANTHROPIC_MODEL=claude-3-5-haiku-latest
```

可切换到 llama.cpp：

```bash
export WIKI_RAG_LLM_BACKEND=llama.cpp
export LLAMA_CPP_BASE_URL=http://localhost:8080
```

注意：当前 embedding 仍使用 Ollama 的 `nomic-embed-text`。

---

## 14. 常见问题与排查

| 问题 | 可能原因 | 解决方案 |
|---|---|---|
| Chat 没有回答 | Ollama 未启动 / 模型未拉取 | 运行 `ollama serve`，确认模型存在 |
| 提示索引不存在 | 没有 Rebuild / 没有执行 index | 在 Library 点击 Rebuild Index |
| 上传后仍未索引 | 抽取失败或 Rebuild 未完成 | 查看 Library 进度条和后端日志 |
| PDF 没有文本 | 缺少 PDF 解析库或 PDF 是扫描件 | 安装 `pypdf` / `pdfplumber`，扫描件需要 OCR |
| 图片没有文本 | 缺少 OCR 依赖 | 安装 `pytesseract Pillow` 和系统 tesseract |
| 检索结果不准 | 阈值过低、Top-K 不合适、笔记内容太泛 | 提高阈值，调整 Top-K，补充更明确的笔记 |
| 问 wikirag 命中别的项目 | 文件名或正文关键词干扰 | 使用 Debug 看 rerank 原因，补充更明确的 Wiki-RAG 笔记 |
| 中文输入按回车误发送 | 输入法组合态处理问题 | 当前 Chat 和 Debug 已加 composition guard |
| 前端看不到新功能 | 后端或前端没重启 / 浏览器缓存 | 重启 FastAPI，刷新 Vite 页面 |
| 端口占用 | 8000 或 5173 已被占用 | 换端口或关闭旧进程 |

---

## 15. 面试速记版

### 15.1 一分钟介绍

Wiki-RAG 是我做的一个本地知识库问答系统，支持把 Markdown、文本、PDF、Word、图片和代码文件导入 Library，并自动抽取成 Markdown 构建向量索引。用户在 Chat 页面提问后，系统会先通过 BM25 + dense embedding 做 Hybrid 检索，召回最相关的 Top-K 片段，再把上下文交给 Ollama 生成回答，并在答案末尾回显来源引用。项目还实现了增量索引、SSE 流式输出、Debug 检索分析和多用户会话存储。

### 15.2 技术亮点

- 设计 `raw → wiki → index` 三层数据链路，统一支持多类型文件索引。
- 实现增量索引，通过文件 hash 避免重复 re-embed。
- 使用 BM25 + dense embedding 的 Hybrid 检索，提高语义检索和关键词命中的稳定性。
- 在 Debug 页面展示 dense、BM25、rerank、查询改写等中间结果，便于排查检索问题。
- 使用 FastAPI SSE 实现流式输出，前端呈现打字机效果。
- Library 支持文件夹上传，保留目录结构，适合导入小型代码项目。
- 答案末尾自动追加 source 引用，降低 RAG 幻觉排查成本。
- LLM 层封装为可插拔后端，支持 Ollama、OpenAI、Claude 和 llama.cpp。

### 15.3 高频问题

**1. 这个项目的核心流程是什么？**
先导入文件，抽取成 Markdown，再切分 chunk，生成 embedding，保存索引。用户提问时，系统检索 Top-K 相关 chunk，拼接上下文给 LLM 生成回答。

**2. 为什么要有 `data/raw` 和 `data/wiki` 两层？**
`raw` 保留原始文件，`wiki` 保存统一抽取后的 Markdown。这样 PDF、Word、图片、代码都能统一进入同一套索引流程。

**3. 为什么不用数据库？**
当前数据规模偏个人知识库，JSON 足够简单直观；索引和会话都可以本地文件存储。后续如果需要多用户权限、复杂查询、审计日志，再接数据库更合适。

**4. Top-K 是什么？**
Top-K 是检索时返回最相关的 K 个片段。K 太小容易漏信息，K 太大容易引入噪音。

**5. 为什么要 Hybrid 检索？**
向量检索擅长语义相似，BM25 擅长关键词、文件名和代码符号。两者融合比单一检索更稳。

**6. 流式输出怎么实现？**
后端 FastAPI 使用 StreamingResponse 返回 SSE，LLM 生成一个 token 就推送一次，前端用 ReadableStream 解析并追加显示。

**7. 如何减少幻觉？**
通过检索上下文约束回答、使用严格模式、设置相似度阈值，并在答案末尾回显 source 方便核对。

---

## 16. 后续可完善方向

| 方向 | 说明 | 优先级 |
|---|---|---|
| SQLite / Postgres | 存储用户、文件元数据、操作日志 | 中 |
| 权限系统 | 多用户登录、个人知识库隔离 | 中 |
| 更强 PDF OCR | 扫描 PDF 自动逐页 OCR | 中 |
| 代码结构解析 | 按 class/function 级别切 chunk | 高 |
| 更好的 Markdown 渲染 | Chat 支持表格、列表、代码高亮 | 中 |
| 文件树视图 | Library 按目录树展示上传文件夹 | 高 |
| 检索评估集 | 固定问题集评估召回质量 | 中 |
| Docker Compose | 一键启动 Ollama/API/前端 | 中 |

---

## 17. 当前限制

- PDF 如果是扫描件，普通文本抽取可能失败，需要 OCR。
- 图片 OCR 依赖系统安装 tesseract。
- 代码文件当前只是作为文本代码块索引，没有做 AST 级别结构分析。
- JSON 索引适合个人或课程项目；如果数据量继续增长，需要考虑向量数据库或更完整的持久化方案。
- Claude 的流式输出当前是安全降级为一次性返回，OpenAI 兼容接口和 Ollama 支持流式。

---

## 18. 推荐学习顺序

### 18.1 立刻掌握

- RAG 基本流程：切分、Embedding、检索、生成。
- Top-K、相似度阈值、source 引用。
- FastAPI 接口与 React 请求链路。
- Library 上传后如何触发 Rebuild。

### 18.2 面试前会讲

- 为什么用 Hybrid 检索。
- 增量索引如何避免重复 embedding。
- SSE 为什么能实现打字机效果。
- Debug 页面如何排查“检索不准”。

### 18.3 后续深入

- FAISS 原理和向量索引结构。
- BM25 公式和参数含义。
- 代码文件按 AST 切分。
- 数据库与权限系统设计。
