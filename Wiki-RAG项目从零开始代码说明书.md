# Wiki-RAG 项目从零开始代码说明书

> 面向刚接触 AI 应用开发的软件工程本科生。
> 这份文档的目标不是炫技术，而是带你像读课本一样看懂：这个项目为什么存在、RAG 怎么工作、前后端如何联动、每个核心文件大概在做什么，以及面试时怎么讲。

---

## 1. 项目一句话介绍

Wiki-RAG 是一个**本地知识库问答系统**，它可以读取用户的 Markdown、文本、PDF、Word、图片和代码文件，将内容转换成可检索的向量索引，然后根据用户问题检索相关片段，并调用本地大模型生成回答。

更通俗地说：

> 你把自己的笔记、文档和代码放进去，它会变成一个可以聊天提问的本地知识库。

---

## 2. 这个项目解决了什么问题？

### 2.1 普通搜索的问题

普通搜索通常依赖关键词。

比如你的笔记里写的是：

```text
RAG 的核心思想是先检索资料，再让模型回答。
```

你搜索：

```text
大模型怎么先查资料再回答？
```

传统关键词搜索可能找不到，因为字面上没有完全匹配的词。

### 2.2 直接问大模型的问题

如果你直接问大模型：

```text
我的 Wiki-RAG 项目是怎么构建索引的？
```

普通大模型并不知道你的本地项目代码。它可能根据通用经验回答，甚至编出不存在的函数、接口或数据库。

这就是大模型常见的问题：**幻觉**。

### 2.3 RAG 的解决思路

RAG 的思路很像“开卷考试”：

1. 先从你的知识库里查相关资料；
2. 把查到的资料交给大模型；
3. 让大模型基于这些资料回答。

所以本项目的价值是：

- 让个人笔记可以被语义检索；
- 让课程资料可以像 ChatGPT 一样提问；
- 让项目文档、代码文件可以成为知识库；
- 尽量在本地完成，不依赖云端 API；
- 回答时可以显示来源，方便核对。

### 2.4 适合的场景

| 场景 | 说明 |
|---|---|
| 个人笔记问答 | 把平时写的 Markdown 笔记变成可提问知识库 |
| 课程资料问答 | 把课堂笔记、复习资料导入后快速查询 |
| 项目文档问答 | 问“这个项目怎么启动”“某个模块做什么” |
| 代码资料问答 | 上传 Java / Python / JS 等代码文件后检索解释 |
| 本地离线知识库 | 不想把资料上传到云端时使用 |

---

## 3. 项目核心流程总览

这个项目可以分成两条主线：

1. **建立知识库**：把文件变成可检索索引。
2. **用户提问**：根据问题检索资料并生成回答。

### 3.1 建立知识库流程

1. 用户上传文件，或把文件放到 `data/raw/`。
2. 后端识别文件类型，例如 Markdown、PDF、图片、代码。
3. 将文件内容抽取成 Markdown，保存到 `data/wiki/`。
4. 读取 `data/wiki/` 中的 Markdown。
5. 将文本切分成多个片段，也叫 chunk。
6. 调用 Ollama Embedding 模型，将每个片段变成向量。
7. 将片段、来源文件、向量保存到 `data/index.json`。
8. 将文件 hash 等元数据保存到 `data/index_meta.json`，用于增量索引。

流程图：

```text
原始文件 data/raw
↓
文件类型识别与文本抽取
↓
可索引 Markdown data/wiki
↓
文本切分 chunk
↓
Ollama Embedding 向量化
↓
保存 data/index.json
```

### 3.2 用户提问流程

1. 用户在 React 前端输入问题。
2. 前端发送请求到 FastAPI 后端。
3. 后端将问题转成向量。
4. 后端读取 `data/index.json`。
5. 使用 NumPy 计算问题向量和知识库向量的相似度。
6. 同时使用 BM25 做关键词检索。
7. 综合 dense 向量分数和 BM25 分数，选出 Top-K 个最相关片段。
8. 将片段拼成 Prompt 上下文。
9. 调用 Ollama 本地大模型生成回答。
10. 后端通过 SSE 将答案逐段返回给前端。
11. 前端像打字机一样显示回答，并展示来源片段。

流程图：

```text
用户问题
↓
React Chat 页面
↓
FastAPI 接口 /api/query/stream
↓
Embedding 向量化
↓
NumPy 相似度计算 + BM25 检索
↓
Top-K 文档召回
↓
拼接 Prompt
↓
Ollama 本地大模型
↓
生成答案
↓
SSE 流式返回
↓
React 前端展示
```

---

## 4. 先理解几个核心概念

### 4.1 什么是 RAG？

#### 大白话解释

RAG 就是让大模型回答问题前，先去你的资料里查一查。

普通大模型像“闭卷考试”，只能靠自己记忆回答。
RAG 像“开卷考试”，它先翻资料，再回答。

#### 专业解释

RAG 全称是 **Retrieval-Augmented Generation**，中文常叫**检索增强生成**。

- Retrieval：检索，从知识库里找相关内容。
- Augmented：增强，把检索到的内容补充给模型。
- Generation：生成，让模型基于资料生成答案。

#### 项目中怎么用

如果用户问：

```text
这个项目怎么构建索引？
```

项目不会直接让大模型凭空回答，而是先从 `data/index.json` 里找到“索引构建”“Embedding”“chunk”相关片段，再把这些片段交给 Ollama 生成回答。

---

### 4.2 什么是 Embedding？

#### 大白话解释

Embedding 就是把文字变成一串数字。

比如：

```text
"登录流程是什么" → [0.12, -0.03, 0.88, ...]
```

这一串数字不是随机的，它表示这句话的语义。

#### 专业解释

Embedding 是一种向量表示方法。它会把文本映射到高维向量空间中。语义越接近的文本，向量距离通常越近。

例如：

```text
"如何登录系统"
"登录流程是什么"
```

这两句话意思接近，所以它们的向量应该比较相似。

#### 项目中怎么用

本项目使用 Ollama 的 `nomic-embed-text` 模型生成 embedding。

- 文档片段要生成 embedding；
- 用户问题也要生成 embedding；
- 两者才能做相似度比较。

---

### 4.3 什么是向量检索？

向量检索不是按关键词查，而是按“语义接近程度”查。

项目中会把：

```text
用户问题向量
```

和：

```text
知识库每个 chunk 的向量
```

逐个比较，找到最相似的片段。

项目里主要使用 cosine similarity，也就是余弦相似度。

---

### 4.4 什么是 Top-K？

Top-K 表示取前 K 个最相关结果。

例如：

```text
Top-K = 3
```

意思是：

```text
从所有知识片段中，取相似度最高的 3 个。
```

K 太小，可能信息不够。
K 太大，可能把无关内容也塞给大模型。

所以个人知识库常用 3 到 5。

---

### 4.5 什么是 Ollama？

Ollama 是一个在本地运行大模型的工具。

在这个项目里，Ollama 主要做两件事：

1. 运行聊天模型，例如 `deepseek-r1:1.5b`。
2. 运行 embedding 模型，例如 `nomic-embed-text`。

好处：

- 不需要把资料上传到云端；
- 没有云 API 成本；
- 适合本地学习和演示。

缺点：

- 依赖本机性能；
- Ollama 服务没启动时，后端会连接失败；
- 模型越大，对电脑要求越高。

---

### 4.6 什么是 FastAPI？

FastAPI 是 Python 的 Web 后端框架。

你可以把它理解成：

> 前端和 Python 代码之间的“接口服务”。

本项目中，FastAPI 做这些事：

- 接收前端传来的问题；
- 调用 RAG 检索和 LLM 生成逻辑；
- 返回答案；
- 管理 Library 文件；
- 触发索引重建；
- 提供 Debug 调试接口；
- 提供 SSE 流式输出。

---

### 4.7 什么是 React + TypeScript + Vite？

这三者属于前端技术。

| 技术 | 大白话理解 | 项目中作用 |
|---|---|---|
| React | 用组件拼页面 | 做 Chat、Library、Debug、Settings 页面 |
| TypeScript | 带类型的 JavaScript | 减少前端数据结构错误 |
| Vite | 前端开发工具 | 启动开发服务器和打包前端 |

本项目的前端不是简单 HTML，而是一个 React 单页应用。

---

### 4.8 什么是 NumPy？

NumPy 是 Python 的数值计算库。

在项目里，它主要用于向量计算。

比如计算余弦相似度：

```python
similarity = dot(a, b) / (norm(a) * norm(b))
```

如果不用 NumPy，也可以用普通 Python 列表手写，但会更麻烦、更慢，也不适合处理大量向量。

---

### 4.9 什么是 JSON 索引？

JSON 是一种轻量级数据格式。

本项目用 `data/index.json` 保存知识库索引。

它大概长这样：

```json
[
  {
    "source": "wiki/python.md",
    "text": "Python 装饰器是一种函数增强方式。",
    "embedding": [0.12, -0.03, 0.88]
  }
]
```

字段解释：

- `source`：这个片段来自哪个文件；
- `text`：具体文本片段；
- `embedding`：这段文本的语义向量。

优点：

- 简单；
- 好查看；
- 适合个人项目和课程项目。

缺点：

- 数据特别大时不如向量数据库高效；
- 多用户复杂权限不方便；
- 并发写入能力有限。

---

## 5. 项目目录结构说明

以下是根据当前项目目录整理，不是通用模板。

| 目录 / 文件 | 作用 | 小白理解 |
|---|---|---|
| `main.py` | 命令行入口 | 用命令执行 OCR、索引、查询 |
| `core/` | 底层能力封装 | 放通用工具，不直接关心页面 |
| `core/utils.py` | 路径、配置、日志、相似度 | 项目的公共工具箱 |
| `core/embedding.py` | 调 Ollama 生成向量 | 把文字变成数字向量 |
| `core/llm.py` | 调大模型 | 统一管理 Ollama / OpenAI / Claude |
| `core/sessions.py` | 会话读写 | 保存多轮聊天记录 |
| `pipeline/` | RAG 业务流程 | 真正处理知识库和问答 |
| `pipeline/documents.py` | 文档抽取 | 把 PDF、Word、代码、图片转成 Markdown |
| `pipeline/index.py` | 构建索引 | 把 Markdown 切片并生成 embedding |
| `pipeline/retrieval.py` | 检索算法 | 找最相关的知识片段 |
| `pipeline/query.py` | 问答主流程 | 检索、拼 Prompt、调用模型 |
| `pipeline/ocr.py` | 图片 OCR | 从图片里识别文字 |
| `pipeline/sources.py` | 外部数据源同步 | 支持 Obsidian、Notion、GitHub Issues |
| `web/api.py` | FastAPI 接口 | 前端调用后端的大门 |
| `web/app.py` | Streamlit 入口 | 可选旧版/备用 UI |
| `web-frontend/` | React 前端 | 用户真正看到的页面 |
| `web-frontend/src/pages/Chat.tsx` | Chat 页面 | 输入问题、显示回答 |
| `web-frontend/src/pages/Library.tsx` | Library 页面 | 上传、编辑、删除知识库文件 |
| `web-frontend/src/pages/Debug.tsx` | Debug 页面 | 看检索分数和命中片段 |
| `web-frontend/src/pages/Settings.tsx` | 设置页面 | 主题等设置 |
| `data/raw/` | 原始文件 | 用户上传的“原料” |
| `data/wiki/` | 可索引 Markdown | 处理后的“知识库正文” |
| `data/index.json` | 向量索引 | 检索时真正读取的文件 |
| `data/index_meta.json` | 增量索引元数据 | 记录哪些文件变了 |
| `data/sessions/` | 会话数据 | 保存聊天历史 |
| `docs.md` | 项目说明文档 | 项目功能和技术说明 |

---

## 6. 后端代码从零讲解

### 6.1 FastAPI 启动入口

本项目的 FastAPI 应用主要在：

```text
web/api.py
```

核心代码类似：

```python
app = FastAPI(title="Wiki-RAG API")
```

解释：

- `FastAPI()` 创建了一个后端应用对象；
- `app` 就是整个后端服务的入口；
- 后续的接口都通过 `@app.get()`、`@app.post()` 挂到这个对象上。

例如：

```python
@app.post("/api/query")
def api_query(req: QueryReq):
    ...
```

解释：

- `@app.post("/api/query")` 表示这是一个 POST 接口；
- 前端向 `/api/query` 发请求时，会执行 `api_query()`；
- `req` 是前端传来的请求体。

### 6.2 问答接口是怎么工作的？

普通问答接口大概是：

```python
@app.post("/api/query")
def api_query(req: QueryReq):
    top, _ = _retrieve(req.question, req.top_k)
    top = filter_top(top, req.min_score)
    answer = answer_question(
        req.question,
        top_k=req.top_k,
        refine=req.refine,
        answer_mode=req.answer_mode,
        min_score=req.min_score,
    )
    return {"answer": answer, "hits": _serialize_hits(top)}
```

逐行解释：

- `req.question`：用户的问题；
- `req.top_k`：要取几个最相关片段；
- `_retrieve()`：执行检索；
- `filter_top()`：按相似度阈值过滤；
- `answer_question()`：真正调用 RAG 和 LLM 生成答案；
- `_serialize_hits()`：把命中片段转成前端能展示的 JSON。

### 6.3 流式问答接口

Chat 页面主要使用：

```text
/api/query/stream
```

它返回的是 SSE 流。

简化代码：

```python
@app.post("/api/query/stream")
def api_query_stream(req: QueryReq):
    def events():
        yield _sse("hits", hits)
        for part in stream_answer(req.question):
            yield _sse("token", part)

    return StreamingResponse(events(), media_type="text/event-stream")
```

解释：

- `events()` 是一个生成器；
- `yield` 一次，前端就收到一小段；
- `StreamingResponse` 表示不要一次性返回，而是持续返回；
- `text/event-stream` 是 SSE 的响应类型。

所以前端会看到类似打字机的效果。

### 6.4 索引重建接口是怎么工作的？

接口：

```text
POST /api/library/rebuild
```

作用：

- 将 `data/raw/` 中的文件同步成 `data/wiki/` 的 Markdown；
- 对 Markdown 切片；
- 生成 embedding；
- 更新 `data/index.json`。

为什么需要重建索引？

因为新增文件后，旧的 `index.json` 并不知道新内容。只有重新构建索引，检索时才能搜到新文件。

### 6.5 知识库文件列表接口

接口：

```text
GET /api/library
```

它会扫描：

```text
data/raw/
```

并返回：

- 文件名；
- 文件类型；
- 是否可编辑；
- 是否已索引；
- chunk 数量；
- 更新时间。

前端 Library 页面就是靠这个接口展示文件列表。

### 6.6 Debug 调试接口

接口：

```text
POST /api/debug
```

作用：

- 看某个问题命中了哪些片段；
- 看每个片段的相似度；
- 看 dense 分数、BM25 分数、rerank 细节；
- 判断“为什么搜到了这个结果”。

Debug 页面很适合排查：

- 检索结果不准；
- Top-K 设置不合理；
- 阈值太高或太低；
- 某个文件内容干扰了结果。

---

## 7. RAG 核心代码逻辑讲解

### 7.1 文档读取

文档读取主要在 `pipeline/documents.py` 和 `pipeline/index.py`。

普通文本读取类似：

```python
text = path.read_text(encoding="utf-8", errors="replace")
```

解释：

- `path` 是文件路径；
- `read_text()` 读取文本内容；
- `encoding="utf-8"` 指定编码；
- `errors="replace"` 表示遇到无法识别的字符时替换掉，避免程序直接崩溃。

为什么要注意编码？

因为用户上传的文件可能来自不同系统。如果编码处理不好，中文内容容易乱码或读取失败。

### 7.2 文本切分

索引构建中有一个简单切分函数：

```python
def _split_paragraphs(text: str):
    return [p.strip() for p in text.split("\n\n") if p.strip()]
```

解释：

- `text.split("\n\n")` 按空行切分；
- `p.strip()` 去掉前后空白；
- `if p.strip()` 过滤空段落。

为什么要切分？

不能把整篇文章直接变成一个向量，因为一篇文章可能包含很多主题。
切成小片段后，每个向量表达的语义更集中，检索更准。

优点：

- 简单；
- 适合 Markdown；
- 容易理解。

缺点：

- 不理解标题层级；
- 不理解代码函数边界；
- 后续可以优化为按标题、语义或 AST 切分。

### 7.3 Embedding 生成

核心逻辑在 `core/embedding.py`。

伪代码：

```python
vector = embed(para)
```

解释：

- `para` 是一个文本片段；
- `embed()` 会调用 Ollama 的 embedding 接口；
- 返回结果是一组数字，也就是向量。

项目还做了 embedding 缓存。
同一段文本如果已经算过向量，下次就不用重复请求模型。

### 7.4 向量索引保存

`data/index.json` 大概长这样：

```json
[
  {
    "chunk_id": "wiki/python.md#0:abc123",
    "source": "wiki/python.md",
    "position": 0,
    "text": "Python 装饰器是一种函数增强方式。",
    "embedding": [0.12, -0.03, 0.88]
  }
]
```

字段解释：

| 字段 | 含义 |
|---|---|
| `chunk_id` | 片段唯一 ID |
| `source` | 来源文件 |
| `position` | 在文件中的片段位置 |
| `text` | 片段原文 |
| `embedding` | 片段向量 |

### 7.5 用户问题向量化

用户问题也要转成向量。

伪代码：

```python
q_emb = embed(question)
```

原因：

只有问题和文档都变成向量，才能计算它们之间的相似度。

### 7.6 cosine similarity 相似度计算

项目中的余弦相似度函数在 `core/utils.py`。

简化公式：

```python
similarity = dot(a, b) / (norm(a) * norm(b))
```

解释：

- `dot(a, b)` 是点积；
- `norm(a)` 是向量 a 的长度；
- `norm(b)` 是向量 b 的长度；
- 结果越接近 1，说明方向越接近，语义越相似。

项目代码大概是：

```python
def cosine_sim(a, b) -> float:
    a = np.asarray(a, dtype=np.float32)
    b = np.asarray(b, dtype=np.float32)
    na = float(np.linalg.norm(a))
    nb = float(np.linalg.norm(b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return float(np.dot(a, b) / (na * nb))
```

解释：

- `np.asarray()` 把普通列表转成 NumPy 数组；
- `np.linalg.norm()` 计算向量长度；
- `np.dot()` 计算点积；
- 如果向量长度为 0，就返回 0，避免除零错误。

### 7.7 Top-K 召回

简化逻辑：

```python
scored = []
for chunk in chunks:
    score = cosine_sim(q_emb, chunk["embedding"])
    scored.append((score, chunk))

scored.sort(key=lambda x: x[0], reverse=True)
top = scored[:top_k]
```

解释：

- 给每个 chunk 算一个分数；
- 按分数从高到低排序；
- 取前 `top_k` 个；
- 这些就是最相关的资料片段。

当前项目实际还加入了 BM25 和 rerank，不只是单纯 cosine。

### 7.8 Prompt 拼接

不能只把问题发给模型，还要把检索到的资料也发给模型。

简化 Prompt：

```text
请根据以下资料回答问题：

资料：
{context}

问题：
{question}
```

项目中 `pipeline/query.py` 会把 Top-K 片段拼成 context，并加上回答模式要求。

这样做的原因：

- 限制模型不要乱编；
- 让模型基于本地资料回答；
- 让回答更贴近知识库内容。

### 7.9 LLM 生成答案

项目通过 `core/llm.py` 调用大模型。

简化代码：

```python
answer = ask(prompt)
```

解释：

- `prompt` 是“资料 + 问题 + 要求”；
- `ask()` 会调用当前 LLM 后端；
- 默认后端是 Ollama；
- 返回自然语言答案。

### 7.10 refine 二次优化

项目支持 refine。

大白话：

> 第一次回答可能有点乱，再让模型整理一遍。

项目逻辑：

- 先生成初始答案；
- 如果开启 refine，就调用 `pipeline/refine.py`；
- 如果 refine 失败，就返回原始答案。

好处：

- 回答更规整；
- 更适合学习和面试复述。

缺点：

- 会多一次 LLM 调用；
- 本地模型慢时会增加等待时间。

---

## 8. 前端代码从零讲解

### 8.1 React 前端整体作用

前端负责用户能看到和操作的部分。

它主要做：

- 输入问题；
- 发送请求；
- 展示回答；
- 展示来源片段；
- 调整 Top-K 和阈值；
- 上传知识库文件；
- 触发 Rebuild；
- 查看 Debug 结果；
- 切换主题。

### 8.2 `main.tsx` 是什么？

文件：

```text
web-frontend/src/main.tsx
```

它是前端入口。

通俗理解：

> 浏览器加载前端时，最先从这里把 React 应用挂到页面上。

常见代码类似：

```tsx
ReactDOM.createRoot(document.getElementById("root")!).render(<App />);
```

解释：

- 找到 HTML 里的 `root` 节点；
- 把 React 的 `App` 组件渲染进去；
- 从此页面由 React 接管。

### 8.3 `App.tsx` 是做什么的？

文件：

```text
web-frontend/src/App.tsx
```

它负责组织整个前端页面。

当前项目中，`App.tsx` 使用 React Router：

```tsx
<Routes>
  <Route path="/" element={<ChatPage />} />
  <Route path="/library" element={<LibraryPage />} />
  <Route path="/debug" element={<DebugPage />} />
  <Route path="/settings" element={<SettingsPage />} />
</Routes>
```

解释：

- `/` 显示 Chat；
- `/library` 显示 Library；
- `/debug` 显示 Debug；
- `/settings` 显示 Settings。

### 8.4 Chat 页面

文件：

```text
web-frontend/src/pages/Chat.tsx
```

Chat 页面负责：

- 输入问题；
- 设置 Top-K；
- 设置回答模式；
- 设置相似度阈值；
- 发送请求到 `/api/query/stream`；
- 接收 SSE 流式回答；
- 展示最相关结果和其他相关结果；
- 支持复制消息；
- 支持停止生成；
- 记住滚动位置。

前端发送请求的核心类似：

```tsx
const res = await fetch("/api/query/stream", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({
    question: q,
    top_k: topK,
    answer_mode: answerMode,
    min_score: minScore
  })
});
```

解释：

- `fetch()` 向后端发 HTTP 请求；
- `method: "POST"` 表示提交数据；
- `Content-Type` 表示请求体是 JSON；
- `JSON.stringify()` 把 JS 对象转成 JSON 字符串；
- 后端收到后执行 RAG 流程。

### 8.5 Library 页面

文件：

```text
web-frontend/src/pages/Library.tsx
```

Library 页面负责：

- 展示知识库文件；
- 上传单个或多个文件；
- 上传整个文件夹；
- 新建 Markdown / Text / Python / Java 文件；
- 编辑可编辑文件；
- 删除文件；
- 保存并索引；
- 展示 Rebuild 进度。

当前支持的文件包括：

- `.md`
- `.txt`
- `.pdf`
- `.docx`
- 图片文件
- Java / Python / JS / TS / Vue / HTML / CSS / JSON / SQL 等代码文件

### 8.6 Debug 页面

文件：

```text
web-frontend/src/pages/Debug.tsx
```

Debug 页面不是给普通用户看的，而是给开发者排查 RAG 用的。

它展示：

- embedding 模型；
- 向量维度；
- Top-K；
- 相似度阈值；
- dense 分数；
- BM25 分数；
- rerank 原因；
- 命中的文本片段。

如果你问一个问题，结果不对，就应该先去 Debug 看：

> 到底检索阶段有没有找对资料？

### 8.7 Settings 页面

文件：

```text
web-frontend/src/pages/Settings.tsx
```

当前 Settings 页面主要用于前端设置，例如主题。
更复杂的模型配置、API key 配置等可以作为后续优化方向。

### 8.8 前端如何调用后端？

项目使用浏览器原生 `fetch()`。

示例：

```tsx
const res = await fetch("/api/debug", {
  method: "POST",
  headers: {
    "Content-Type": "application/json"
  },
  body: JSON.stringify({
    question,
    top_k: 5
  })
});

const data = await res.json();
```

逐行解释：

- `fetch("/api/debug")`：请求后端 Debug 接口；
- `method: "POST"`：用 POST 提交数据；
- `headers`：告诉后端请求体是 JSON；
- `body`：真正发送的数据；
- `await res.json()`：把后端返回的 JSON 解析成前端对象。

---

## 9. 前后端完整调用链

假设用户问：

```text
这个项目的 RAG 流程是什么？
```

完整流程如下：

1. 用户在 React Chat 输入框输入问题。
2. 点击发送按钮。
3. `Chat.tsx` 将问题、Top-K、阈值、回答模式封装成 JSON。
4. 前端发送 POST 请求到 `/api/query/stream`。
5. `web/api.py` 中的 FastAPI 接口接收请求。
6. 后端调用 `pipeline.query.stream_answer()`。
7. `stream_answer()` 调用 `pipeline.retrieval.retrieve()`。
8. 后端用 Ollama embedding 模型把问题转成向量。
9. 后端读取 `data/index.json`。
10. NumPy 计算问题向量和每个 chunk 向量的相似度。
11. BM25 计算关键词相关性。
12. 系统融合分数并 rerank。
13. 取 Top-K 个最相关片段。
14. `pipeline/query.py` 把片段拼成 Prompt。
15. `core/llm.py` 调 Ollama 本地大模型。
16. 模型生成回答。
17. FastAPI 通过 SSE 持续返回 token。
18. `Chat.tsx` 的 `readSse()` 解析 token。
19. 前端不断更新 assistant 消息内容。
20. 用户看到逐字输出的回答和来源引用。

---

## 10. 每个技术在项目中到底有什么用

| 技术 | 项目中具体用途 | 解决的问题 | 不用会怎样 |
|---|---|---|---|
| Python | 实现后端、RAG、检索、文件处理 | 快速开发 AI 应用逻辑 | 后端和 AI 流程难以实现 |
| FastAPI | 提供 HTTP API | 让前端能调用 Python 能力 | 前后端无法通过接口联动 |
| Ollama | 本地运行 LLM 和 Embedding | 不依赖云端模型 API | 需要接云 API 或自己部署模型 |
| Embedding | 把文本转成向量 | 支持语义检索 | 只能做关键词搜索 |
| RAG | 先检索再生成 | 降低幻觉，利用本地知识 | 模型不知道用户私有资料 |
| NumPy | 计算向量相似度 | 高效处理向量运算 | 手写计算麻烦且性能差 |
| JSON | 保存索引、元数据、会话 | 简单可读，适合个人项目 | 需要更复杂数据库 |
| React | 构建前端页面 | 实现交互式 Chat 和 Library | 用户只能用命令行 |
| TypeScript | 给前端数据加类型 | 减少字段名和类型错误 | 前端维护更容易出错 |
| Vite | 前端开发和打包 | 快速启动 React 项目 | 前端开发体验差 |
| Markdown | 统一知识库文本格式 | 便于展示、切分和索引 | 多格式文件难统一处理 |

---

## 11. 常见问题和排查方式

### 11.1 Ollama 没启动

表现：

- 后端请求模型失败；
- 连接被拒绝；
- 请求 timeout。

排查：

```bash
ollama serve
ollama list
```

确认模型是否存在。

### 11.2 模型不存在

需要先拉取模型：

```bash
ollama pull deepseek-r1:1.5b
ollama pull nomic-embed-text
```

如果模型名写错，后端也会调用失败。

### 11.3 `index.json` 不存在

表现：

```text
索引文件不存在
```

解决：

- 在 Library 点击 `Rebuild Index`；
- 或命令行执行：

```bash
python main.py index
```

### 11.4 检索结果不准确

可能原因：

- 文档内容太乱；
- chunk 切分不合理；
- Top-K 太小；
- 阈值太低或太高；
- Embedding 模型效果一般；
- 用户问题太模糊。

排查方式：

- 打开 Debug 页面；
- 查看命中的片段；
- 查看 dense / BM25 / rerank 分数；
- 调整 Top-K 和阈值；
- 补充更明确的笔记。

### 11.5 前端请求失败

可能原因：

- FastAPI 后端没启动；
- 端口不对；
- Vite 代理或接口路径不对；
- 浏览器缓存了旧前端。

解决：

```bash
python3 -m uvicorn web.api:app --reload --port 8000
cd web-frontend
npm run dev
```

### 11.6 Python 依赖没安装

表现：

```text
ModuleNotFoundError
```

解决：

```bash
pip install requests numpy fastapi uvicorn
```

如果需要 OCR 或 PDF：

```bash
pip install pytesseract Pillow pypdf pdfplumber
```

### 11.7 前端依赖没安装

表现：

```text
vite: command not found
```

解决：

```bash
cd web-frontend
npm install
npm run dev
```

---

## 12. 如何从零运行项目

### 12.1 准备环境

需要：

- Python 3.9+
- Node.js 18+
- npm
- Ollama
- Git

### 12.2 启动 Ollama

```bash
ollama serve
```

新开一个终端拉模型：

```bash
ollama pull deepseek-r1:1.5b
ollama pull nomic-embed-text
```

### 12.3 安装后端依赖

当前仓库没有在目录列表中看到完整 `requirements.txt`，所以可以先手动安装核心依赖：

```bash
pip install requests numpy fastapi uvicorn
```

可选依赖：

```bash
pip install pytesseract Pillow pypdf pdfplumber
```

### 12.4 启动 FastAPI 后端

项目根目录执行：

```bash
python3 -m uvicorn web.api:app --reload --port 8000
```

### 12.5 安装前端依赖

```bash
cd web-frontend
npm install
```

### 12.6 启动前端

```bash
npm run dev
```

浏览器访问：

```text
http://localhost:5173
```

### 12.7 构建索引

方式一：前端 Library 页面点击 `Rebuild Index`。
方式二：命令行：

```bash
python main.py index
```

### 12.8 开始提问

1. 打开 Chat 页面；
2. 输入问题；
3. 选择 Top-K、模式、阈值；
4. 点击发送；
5. 查看回答和来源引用。

---

## 13. 关键代码逐段解释

### 文件：`core/utils.py`

#### 这个文件是干什么的？

它是项目公共工具文件，负责路径、配置、日志和相似度计算。

#### 它在项目流程中的位置

几乎所有后端模块都会 import 它。

#### 核心代码解释

```python
ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
WIKI_DIR = DATA_DIR / "wiki"
INDEX_FILE = DATA_DIR / "index.json"
```

解释：

- `ROOT` 是项目根目录；
- `DATA_DIR` 是数据目录；
- `RAW_DIR` 存原始文件；
- `WIKI_DIR` 存抽取后的 Markdown；
- `INDEX_FILE` 是最终索引文件。

小白容易误解：

> 不要在各个文件里手写路径，统一从 `utils.py` 引用，后续维护更方便。

面试可以说：

> 我把项目路径和公共配置集中到 `core/utils.py`，避免路径散落在各个模块里，提高可维护性。

---

### 文件：`core/embedding.py`

#### 这个文件是干什么的？

它负责把文本变成 embedding 向量。

#### 核心代码示例

```python
vec = embed(text)
```

解释：

- 输入是文本；
- 内部调用 Ollama embedding 接口；
- 输出是数字向量；
- 项目会缓存已经算过的 embedding。

小白容易误解：

> Embedding 不是大模型回答，它只是把文字变成适合计算相似度的数字。

面试可以说：

> 我封装了 embedding 调用，并使用文本 hash 做缓存，避免重复文本反复请求模型，提高索引构建效率。

---

### 文件：`core/llm.py`

#### 这个文件是干什么的？

它统一封装 LLM 调用。

#### 核心代码示例

```python
answer = chat(messages)
```

解释：

- `messages` 是对话消息；
- 默认调用 Ollama；
- 也可以通过环境变量切换 OpenAI、Claude、llama.cpp；
- 对外暴露统一接口，业务层不用关心具体后端。

小白容易误解：

> LLM 后端和 embedding 后端不是一回事。当前聊天模型可切换，但 embedding 仍主要依赖 Ollama。

面试可以说：

> 我把 LLM 调用封装成可插拔接口，让业务层只调用统一的 `chat` 或 `stream_chat`，后续替换模型服务时改动范围更小。

---

### 文件：`pipeline/documents.py`

#### 这个文件是干什么的？

它负责把不同格式文件变成 Markdown。

#### 支持内容

- Markdown；
- Text；
- Word；
- PDF；
- 图片 OCR；
- Java / Python / JS 等代码文件。

#### 代码文件转换示例

```md
# App.java

> 原始路径：`src/App.java`

```java
public class App {}
```
```

解释：

- 文件名成为标题；
- 原始路径保留；
- 代码被放入 Markdown 代码块；
- 后续可以正常进入索引。

面试可以说：

> 我设计了统一的文档抽取层，将多种文件格式转换为 Markdown，使后续 chunk、embedding 和检索流程不需要关心原始文件类型。

---

### 文件：`pipeline/index.py`

#### 这个文件是干什么的？

它负责构建索引。

#### 核心流程

```text
扫描 raw
→ 抽取成 wiki Markdown
→ 扫描 wiki
→ 切 chunk
→ 生成 embedding
→ 写入 index.json
```

#### 小白容易误解的地方

`index.json` 不是数据库表，它只是一个本地 JSON 文件。
对个人项目来说简单够用，但大规模场景要换成向量数据库。

面试可以说：

> 索引构建模块支持增量索引，通过记录文件 hash 判断内容是否变化，只对变化文件重新生成 embedding，减少重复计算。

---

### 文件：`pipeline/retrieval.py`

#### 这个文件是干什么的？

它负责检索最相关的知识片段。

#### 核心逻辑

```text
问题改写
→ BM25 关键词检索
→ dense 向量检索
→ 分数归一化
→ 融合排序
→ rerank
→ 返回 Top-K
```

小白容易误解：

> RAG 的效果不只看大模型，检索是否准确更关键。

面试可以说：

> 我使用 BM25 + dense embedding 的 Hybrid 检索，同时增加轻量 rerank，兼顾语义相似和关键词精确命中。

---

### 文件：`pipeline/query.py`

#### 这个文件是干什么的？

它是 RAG 问答主流程。

#### 核心伪代码

```python
top = retrieve(question, top_k)
prompt = build_prompt(question, top)
answer = ask(prompt)
return answer + citation_block(top)
```

解释：

- `retrieve()` 找资料；
- `build_prompt()` 拼上下文；
- `ask()` 调大模型；
- `citation_block()` 加来源引用。

面试可以说：

> 问答模块把检索结果拼接为 Prompt，并支持严格、总结、拓展、原文等回答模式，同时在答案末尾回显 source，方便用户核对答案来源。

---

### 文件：`web/api.py`

#### 这个文件是干什么的？

它是 FastAPI 接口层。

#### 它在项目流程中的位置

前端不直接调用 `pipeline/query.py`，而是请求 `web/api.py` 提供的 HTTP 接口。

#### 核心接口

- `/api/query/stream`
- `/api/debug`
- `/api/library`
- `/api/library/upload`
- `/api/library/rebuild`
- `/api/sessions/{session_id}`

面试可以说：

> 我用 FastAPI 将 RAG 能力封装成 HTTP 接口，前端通过 fetch 调用，实现前后端分离。

---

### 文件：`web-frontend/src/pages/Chat.tsx`

#### 这个文件是干什么的？

它实现聊天页面。

#### 核心功能

- 输入问题；
- 发送请求；
- 接收 SSE；
- 显示回答；
- 显示来源；
- 复制消息；
- 停止生成；
- 记住滚动位置。

面试可以说：

> Chat 页面使用 SSE 读取后端流式响应，每收到一个 token 就更新当前 assistant 消息，实现类似 ChatGPT 的打字机效果。

---

### 文件：`web-frontend/src/pages/Library.tsx`

#### 这个文件是干什么的？

它实现知识库管理页面。

#### 核心功能

- 上传文件；
- 上传文件夹；
- 新建文件；
- 编辑文件；
- 删除文件；
- 保存并索引；
- 展示 Rebuild 进度。

面试可以说：

> Library 页面把文件管理和索引重建流程串起来，用户上传文件后会自动触发后端 Rebuild，并通过轮询展示进度。

---

### 文件：`web-frontend/src/pages/Debug.tsx`

#### 这个文件是干什么的？

它用于调试检索过程。

#### 核心功能

- 输入测试问题；
- 查看命中片段；
- 查看分数；
- 查看查询改写；
- 查看 rerank 原因。

面试可以说：

> Debug 页面用于观察 RAG 的检索中间结果，帮助判断问题是出在检索阶段还是生成阶段。

---

## 14. 项目可以怎么优化

### 14.1 换成向量数据库

当前用 JSON 保存索引，简单直观。
但如果数据量很大，可以考虑：

- Chroma；
- FAISS；
- Milvus；
- Qdrant。

为什么？

- 查询更快；
- 支持更大规模；
- 支持更丰富的过滤条件。

### 14.2 优化文本切分

当前主要按段落切。

可以优化为：

- 按 Markdown 标题切；
- 按固定 chunk size 切；
- 增加 overlap；
- 代码按 class / function 切；
- PDF 按页和标题切。

### 14.3 增加更强来源引用

当前已有 `[source: wiki/xxx.md]`。

可以继续增强：

- 显示页码；
- 显示行号；
- 点击跳转到原文；
- 高亮命中句子。

### 14.4 增强用户上传文件

当前已经支持多文件和文件夹上传。

后续可以增强：

- 拖拽上传；
- 上传队列；
- 文件树展示；
- 上传失败重试；
- 大文件分片上传。

### 14.5 增加历史会话管理

当前已有 `data/sessions/`。

可以继续增加：

- 会话列表；
- 会话重命名；
- 会话搜索；
- 删除单条消息；
- 导出对话记录。

### 14.6 增加 Docker 部署

可以用 Docker Compose 管理：

- FastAPI 后端；
- React 前端；
- Ollama 服务；
- 数据卷。

但注意：如果要让 Ollama 在容器里跑模型，还要考虑本机 GPU、模型存储和性能问题。

---

## 15. 面试怎么介绍这个项目

### 15.1 30 秒介绍

Wiki-RAG 是一个本地知识库问答系统。我用 Python 和 FastAPI 实现后端 RAG 流程，用 React 做前端页面，支持导入 Markdown、PDF、Word、图片和代码文件。系统会将文档切分并生成 embedding，用户提问时通过 Hybrid 检索召回相关片段，再调用 Ollama 本地大模型生成回答，并显示来源引用。

### 15.2 1 分钟介绍

这个项目主要解决个人资料难以语义检索的问题。用户可以把笔记、课程资料、项目文档和代码文件上传到 Library，后端会将它们抽取成 Markdown，切分成 chunk，并调用 Ollama 的 embedding 模型生成向量索引。用户在 Chat 页面提问时，系统会用 BM25 和向量检索做 Hybrid 召回，找到最相关的 Top-K 片段，再把上下文拼成 Prompt 交给本地大模型生成答案。项目还实现了增量索引、流式输出、来源引用、多用户会话和 Debug 检索分析。

### 15.3 3 分钟介绍

Wiki-RAG 是我做的一个本地 RAG 知识库问答项目，整体采用 FastAPI + React 前后端分离架构。后端负责文档抽取、索引构建、检索和 LLM 调用，前端负责 Chat、Library、Debug 和 Settings 页面。

在数据构建阶段，用户可以上传 Markdown、普通文本、PDF、Word、图片和常见代码文件。系统会保留原始文件到 `data/raw`，再通过文档抽取模块转换成统一的 Markdown，保存到 `data/wiki`。之后索引模块会按段落切分文本，调用 Ollama 的 `nomic-embed-text` 生成 embedding，并保存到 `data/index.json`。为了避免每次都重新计算，我还做了基于文件 hash 的增量索引。

在问答阶段，用户问题会先被转成 embedding，然后系统读取索引，对所有 chunk 做 dense 相似度计算，同时用 BM25 做关键词检索，再融合分数并 rerank，得到 Top-K 相关片段。之后系统把这些片段拼成 Prompt，调用 Ollama 本地大模型生成答案。前端通过 SSE 接收后端流式返回，所以回答会像打字机一样逐段显示。答案末尾还会附带 source 引用，方便用户核对来源。

这个项目的亮点是它不是简单调用大模型，而是完整实现了本地知识库导入、增量索引、Hybrid 检索、流式输出、Debug 可观测性和多类型文件管理，比较适合作为 AI 应用方向的个人项目。

### 15.4 面试官可能问的问题

1. **RAG 是什么？**
   RAG 是检索增强生成，先从知识库检索相关资料，再让大模型基于资料回答。

2. **为什么不用普通关键词搜索？**
   关键词搜索只能匹配字面词，向量检索可以根据语义找相近内容。

3. **Embedding 是什么？**
   Embedding 是把文本转换成数字向量，用于表达语义。

4. **你的文档怎么切分？**
   当前主要按空行切段，简单适合 Markdown；后续可按标题或语义切分。

5. **`index.json` 里存了什么？**
   存 chunk 文本、来源文件、位置和 embedding 向量。

6. **cosine similarity 怎么计算？**
   用两个向量点积除以它们长度乘积，判断方向接近程度。

7. **Top-K 是什么？**
   从所有片段中取相似度最高的 K 个作为上下文。

8. **Ollama 在项目里做什么？**
   负责本地运行聊天模型和 embedding 模型。

9. **FastAPI 提供了哪些接口？**
   提供问答、流式问答、Debug、Library 文件管理、Rebuild、Session 等接口。

10. **前端怎么调用后端？**
    前端使用 `fetch()` 发送 JSON 请求到 FastAPI 接口。

11. **如果检索结果不准怎么办？**
    看 Debug 页面，检查命中片段、分数、Top-K 和阈值，再优化文档或切分方式。

12. **如果知识库变大怎么办？**
    可以接 FAISS 或向量数据库，并优化 chunk 和索引结构。

13. **为什么不用向量数据库？**
    当前是个人项目，JSON 简单可读，足够支撑小规模知识库。

14. **为什么用 JSON 存索引？**
    开发成本低，方便调试，适合教学和本地项目。

15. **这个项目和普通 ChatGPT 问答有什么区别？**
    普通 ChatGPT 不知道本地资料；Wiki-RAG 会先检索本地知识库再回答。

16. **本地模型有什么优缺点？**
    优点是隐私好、无 API 成本；缺点是依赖本机性能，模型能力可能弱于云端大模型。

17. **如何减少重复 embedding 计算？**
    使用文本 hash 和文件 hash 做缓存与增量索引。

18. **你怎么展示来源片段？**
    每个 chunk 保存 `source`，回答末尾通过 citation block 输出来源。

19. **这个项目最大的难点是什么？**
    难点在于检索质量调优，包括 Hybrid 检索、阈值、Top-K、rerank 和 Debug 可观测性。

20. **如果继续优化，你会怎么做？**
    我会优先做文件树视图、代码 AST 切分、更好的 PDF OCR、向量数据库和 Docker 部署。

---

## 16. 小白学习路线

### 第一阶段：先看懂项目

- HTTP 请求；
- FastAPI 基础；
- React 组件；
- JSON 文件读写；
- 文件目录结构。

### 第二阶段：看懂 RAG

- Embedding；
- 向量；
- cosine similarity；
- Top-K 检索；
- Prompt 拼接；
- LLM 调用。

### 第三阶段：看懂工程化

- 前后端联调；
- 依赖管理；
- 环境变量；
- 错误处理；
- 日志；
- 增量索引。

### 第四阶段：准备面试

- 项目介绍；
- 技术亮点；
- 难点解决；
- 后续优化；
- Debug 排查思路。

---

## 17. 最后总结

Wiki-RAG 的核心价值是把个人资料变成一个可以自然语言提问的本地知识库。通过这个项目，你可以学到 AI 应用开发中最典型的一条链路：文档处理、文本切分、Embedding、向量检索、Prompt 拼接、LLM 生成、前后端联动和流式输出。

从简历角度看，这个项目可以体现你对 RAG 原理、Python 后端、FastAPI 接口、React 前端、文件处理、检索调优和工程化组织的综合能力。它不是一个只会调用大模型 API 的玩具项目，而是一个能讲清楚数据流、代码结构和技术取舍的 AI 应用项目。
