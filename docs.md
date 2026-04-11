# 📘 Wiki-RAG 从零到精通：一份手把手教学手册

> 写给「一行 RAG 代码都没写过、Python 只会一点点」的你。
> 看完这份手册，你不仅能跑起 wiki-rag，还能彻底理解 **RAG 是什么、为什么这样设计、未来怎么扩展**。

---

## 📑 目录

1. [什么是 RAG](#1-什么是-rag)
2. [为什么需要 RAG](#2-为什么需要-rag)
3. [系统工作流程（核心故事）](#3-系统工作流程核心故事)
4. [核心概念：必须讲透的三件事](#4-核心概念必须讲透的三件事)
5. [手把手实现一个最小 RAG](#5-手把手实现一个最小-rag)
6. [项目代码逐文件解析](#6-项目代码逐文件解析)
7. [实际运行示例](#7-实际运行示例)
8. [FAQ:你一定会遇到的问题](#8-faq你一定会遇到的问题)
9. [进阶优化](#9-进阶优化)
10. [扩展方向:把它变成更厉害的东西](#10-扩展方向把它变成更厉害的东西)

---

## 1. 什么是 RAG

### 1.1 一句话解释

> **RAG = 让大模型「先查资料,再回答你」。**

英文全称:**Retrieval-Augmented Generation**(检索增强生成)。

我们把它拆开看:

| 英文 | 中文 | 干什么 |
|------|------|--------|
| **R**etrieval | 检索 | 从你自己的笔记 / 文档里,找出和问题最相关的几段 |
| **A**ugmented | 增强 | 把找到的内容塞进给大模型的提问里 |
| **G**eneration | 生成 | 大模型基于这些资料,生成一段回答 |

### 1.2 一个生活中的例子

想象你考试前问学霸同学一道题。

* **没有 RAG 的大模型** = 一个「记忆超群但闭卷考试」的学霸:
  他回答得头头是道,但你的课本他没看过,所以可能编一个不存在的公式给你。
* **有 RAG 的大模型** = 同一个学霸,但**手里翻着你的笔记本**:
  他先翻到「第 12 页 · 装饰器」那一节,看完再开口。

这就是 RAG。它不会让模型变更聪明,但它让模型**有据可依**。

### 1.3 为什么这事在 2023 年后火起来

因为发现了一个非常朴素的事实:

> 与其训练一个新模型记住你的数据(贵、慢、危险),
> 不如让模型在回答的瞬间「现查」你的数据(便宜、快、可控)。

RAG 是「**让通用大模型变得专属于你**」最便宜的路径。

---

## 2. 为什么需要 RAG

我们对比一下,看看 LLM 单独使用有什么问题,RAG 又分别怎么解决。

### 2.1 LLM 单独使用的四大痛点

| 痛点 | 表现 | 例子 |
|------|------|------|
| ❌ **知识截止** | 只懂训练时的世界 | 你问它「昨天我写的笔记里讲了啥」——它根本没见过 |
| ❌ **幻觉** | 没把握时会「编」 | 编一个不存在的 API、伪造一段不存在的论文标题 |
| ❌ **没有私域知识** | 不知道你的代码、文档、习惯 | 你问它「我们公司项目的部署流程」——它瞎猜 |
| ❌ **无法引用来源** | 你不知道答案是从哪儿来的 | 它说「Python 装饰器是…」——出处?没有 |

### 2.2 RAG 怎么解决

| 痛点 | RAG 的解法 |
|------|-----------|
| 知识截止 | 检索的是**你本地的文件**,文件多新答案就多新 |
| 幻觉 | 把检索到的原文喂给模型,告诉它「只能根据这些回答」 |
| 没有私域知识 | 你的笔记 / wiki / 代码就是它的「私域知识库」 |
| 没有来源 | 检索阶段保留了 `source` 字段,可以回显「答案来自 wiki/python.md」 |

### 2.3 RAG vs Fine-tuning(微调)

很多新人会问:「我直接用我的数据微调一个模型不就行了?」

| 维度 | Fine-tuning | RAG |
|------|------------|-----|
| 成本 | 高(GPU + 时间) | 低(一次 embedding) |
| 更新数据 | 要重训 | 直接改文件 |
| 出错时定位 | 黑盒 | 能看到检索到了什么 |
| 适合 | 改风格、改语气 | 注入新知识 |

**结论:注入「事实知识」永远优先选 RAG,微调留给「教模型说话风格」。**

---

## 3. 系统工作流程(核心故事)

我们用「讲故事」的方式过一遍 wiki-rag 的完整流程。

### 3.1 故事开场

你现在有一堆 Markdown 笔记躺在 `data/raw/`:
有一些是手写的草稿,有一些是从 PDF / 截图里抠出来的乱七八糟的句子。
你想问:**「Python 装饰器是什么?」**

### 3.2 文字流程图

```
┌─────────────────────────────────────────────────────────────┐
│  阶段 0:你的原始资料(人类视角)                              │
│  data/raw/python.md      ← 你的草稿                          │
│  data/raw/screenshot.png ← 你随手截的图                      │
└─────────────────────────────────────────────────────────────┘
                    │
                    │  pipeline/ocr.py
                    ▼
┌─────────────────────────────────────────────────────────────┐
│  阶段 1:图片 → 文本(OCR)                                   │
│  pytesseract 把截图识别成 .md,跟其它笔记合在一起             │
└─────────────────────────────────────────────────────────────┘
                    │
                    │  pipeline/compiler.py
                    ▼
┌─────────────────────────────────────────────────────────────┐
│  阶段 2:草稿 → 结构化 wiki                                  │
│  让 LLM 读你的草稿,重写成「分层标题 + 重点加粗 + 总结」      │
│  data/raw/python.md  ──►  data/wiki/python.md               │
└─────────────────────────────────────────────────────────────┘
                    │
                    │  pipeline/index.py
                    ▼
┌─────────────────────────────────────────────────────────────┐
│  阶段 3:文本 → 向量(Embedding)                             │
│  按空行切段 → 每段调 nomic-embed-text → 得到一个向量         │
│  全部存到 data/index.json                                    │
│  [                                                          │
│    {                                                        │
│      "source": "python.md",                                 │
│      "text": "装饰器是一种...",                              │
│      "embedding": [0.12, -0.04, 0.88, ...]                  │
│    },                                                       │
│    ...                                                      │
│  ]                                                          │
└─────────────────────────────────────────────────────────────┘
                    │
                    │  pipeline/query.py
                    ▼
┌─────────────────────────────────────────────────────────────┐
│  阶段 4:你提问 → 检索 → 生成                                │
│                                                             │
│  Q: "Python 装饰器是什么?"                                  │
│       │                                                     │
│       ▼                                                     │
│  embed("Python 装饰器是什么?") → q_vec                      │
│       │                                                     │
│       ▼                                                     │
│  对 index.json 里每段算 cosine_sim(q_vec, chunk_vec)        │
│       │                                                     │
│       ▼                                                     │
│  排序,取 top-k = 3 段                                       │
│       │                                                     │
│       ▼                                                     │
│  把这 3 段拼成 prompt:                                      │
│    「基于以下内容回答问题:                                   │
│     {3 段原文}                                              │
│     问题:Python 装饰器是什么?」                             │
│       │                                                     │
│       ▼                                                     │
│  ask(prompt) → deepseek-r1:1.5b → 初始回答                  │
│       │                                                     │
│       ▼                                                     │
│  pipeline/refine.py 二次重写,规整成                         │
│  「定义 / 原理 / 示例 / 总结」结构                          │
│       │                                                     │
│       ▼                                                     │
│  ✅ 最终答案返回给你                                        │
└─────────────────────────────────────────────────────────────┘
```

请注意一件事:**整个流程没有任何一次走出过你这台机器**。所有 LLM、embedding 都跑在本地 Ollama 里。

---

## 4. 核心概念:必须讲透的三件事

接下来我们慢慢讲三个一定要懂的概念:**Embedding、Cosine Similarity、语义搜索**。

### 4.1 Embedding(向量、嵌入)

#### 4.1.1 用「坐标」做类比

想象一张地图。每座城市都有 (经度, 纬度) 两个数字。
两座城市坐标越接近,它们就**地理上越接近**。

```
北京 = (116.4, 39.9)
天津 = (117.2, 39.1)   ← 离北京很近
广州 = (113.3, 23.1)   ← 离北京很远
```

Embedding 做的事一模一样,只不过它把**「文字」**变成了**「高维空间里的坐标」**。
本项目用的 `nomic-embed-text` 模型输出的是 **768 维**向量——也就是说,每段文字会被映射成一个有 768 个数字的列表。

```
"猫"   = [0.12, -0.04, ..., 0.88]   (768 个数字)
"狗"   = [0.10, -0.03, ..., 0.85]   ← 离"猫"很近
"苹果" = [0.51,  0.22, ..., -0.30]  ← 离"猫"远多了
```

#### 4.1.2 为什么这样就能比较「相似度」

因为这些 embedding 模型是在**海量人类文字**上训练出来的。
它学会了一个事实:

> 「在人类语言里经常出现在相似上下文的词,应该在空间里离得近。」

* 「猫」「狗」经常出现在「我家的 ___ 很可爱」「___ 是宠物」这种句子里 → 空间上近
* 「猫」「苹果」几乎不会出现在同一种上下文 → 空间上远

这套学习方式叫 **distributional semantics**(分布式语义):
**意义不来自于词本身,而来自于它和谁一起出现。**

#### 4.1.3 一个直觉小例子

```python
embed("我养了一只猫")  ≈ embed("我家的狗超可爱")        # 都在讲宠物
embed("我养了一只猫")  ≠ embed("二次方程的求根公式")     # 完全不同的话题
```

embedding 不在乎你用「猫」还是「猫咪」还是「kitty」——只要语义相似,向量就会靠在一起。
**这就是 RAG 检索能跨越同义词、跨越语种的根本原因。**

---

### 4.2 Cosine Similarity(余弦相似度)

有了向量,怎么算「两个向量相似不相似」?

#### 4.2.1 用「方向」来理解

想象你站在原点,伸出两只手臂指向两个向量。

* 两只手臂**几乎重合** → 这两个向量「方向一致」 → 相似度 ≈ 1
* 两只手臂**互相垂直**(90°) → 没什么关系 → 相似度 ≈ 0
* 两只手臂**指向相反**(180°) → 完全相反 → 相似度 ≈ -1

**关键:cosine 只关心方向,不关心长度。**
所以「猫」和「猫咪猫咪猫咪」的 embedding,向量长度可能不同,但方向几乎一致——cosine 仍然给出接近 1 的分数。

这是个非常贴心的性质:你不需要先把向量「标准化」再比较。

#### 4.2.2 数学公式(很简单)

```
                    a · b
cosine(a, b) = ─────────────
                ||a|| · ||b||
```

* 分子:两个向量的「点积」(对应位置相乘再相加)
* 分母:两个向量的「长度」相乘(用来归一化)

在 `core/utils.py` 里就五行:

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

**就这么朴素**——RAG 的检索内核就是这么 5 行代码。

---

### 4.3 语义搜索 vs 关键词搜索

#### 4.3.1 关键词搜索的痛

传统搜索(比如 `grep`、SQL `LIKE`、Elasticsearch 默认的 BM25)依赖**字面匹配**。

| 你搜 | 它能找到 | 它找不到 |
|------|---------|---------|
| `decorator` | 含 "decorator" 字样的段落 | 写的是 "装饰器" 的段落 |
| `怎么写循环` | 含 "怎么写循环" 字样的段落 | 写的是 "for 语句的用法" 的段落 |

#### 4.3.2 语义搜索

语义搜索把你和文档**都翻译成向量**,再比较向量。

| 你搜 | 即使段落里写的是 | 也能找到 |
|------|---------|---------|
| "Python decorator" | "Python 装饰器" | ✅ |
| "怎么写循环" | "for 语句的用法" | ✅ |
| "心情低落" | "今天有点 emo" | ✅ |

#### 4.3.3 一个对比小实验

假设你的笔记里只有这一段:

> **for 循环可以遍历任意可迭代对象,写法是 `for x in xs:`。**

| 查询方式 | 「怎么写循环」 |
|---------|---------------|
| grep / 关键词 | ❌ 找不到,没有「循环」二字 |
| RAG / 语义 | ✅ 余弦相似度高,会被召回 |

> ⚠️ 但这不意味着语义搜索碾压关键词搜索。
> 在「精确匹配错误码、命令、API 名」时,关键词反而更准。
> 工业级 RAG 通常做 **hybrid search**(BM25 + 语义),互相补位。

---

## 5. 手把手实现一个最小 RAG

理论讲完了,我们现在「假装从零开始」搭一遍 RAG,看完你就能彻底吃透 wiki-rag 在干嘛。

我们分五步走,每步都要解释**为什么要这样做**。

### 5.1 第一步:准备 raw 数据

```
data/
└── raw/
    ├── python.md       ← 一些 Python 草稿
    ├── react.md        ← 一些 React 草稿
    └── screenshot.png  ← 一张截图
```

**为什么要这样做?**
因为「写笔记」和「整理笔记」是两种不同的脑力活。
我们让 `raw/` 成为「想到啥写啥」的草稿堆,**降低写笔记的心智负担**。

### 5.2 第二步:compiler 整理草稿

我们让 LLM 读 `raw/python.md`,把它重写成结构清晰的 wiki:

```python
PROMPT = """你是一个知识整理专家,请整理以下内容:

{content}

要求:
1. 分层标题
2. 重点加粗
3. 结构清晰
4. 最后一句总结
"""
```

输出落到 `data/wiki/python.md`。

**为什么要这样做?**

* 草稿里全是「啊…就是…那个…」这种噪音,embedding 后会污染语义。
* 整理后的 wiki **每一段都是自包含的小知识点**,非常利于后续切片 + 检索。
* 这一步实质上是把**「人类的混乱」**翻译成**「机器友好的结构」**。

### 5.3 第三步:把 wiki 变成 embedding

```python
def build_index():
    chunks = []
    for f in WIKI_DIR.glob("*.md"):
        text = f.read_text("utf-8")
        for para in text.split("\n\n"):     # 按空行分段
            if not para.strip():
                continue
            vec = embed(para)               # 调 nomic-embed-text
            chunks.append({
                "source": f.name,
                "text": para,
                "embedding": vec,
            })
    INDEX_FILE.write_text(json.dumps(chunks, ensure_ascii=False))
```

**为什么按空行分段?**
* 太长的段落 embedding 会模糊(一个向量代表的语义太杂);
* 太短的段落(如「### 标题」一行)几乎没有上下文;
* Markdown 写法本身就是「一段一个想法」,按空行切是最朴素也最有效的策略。

**为什么把 embedding 存 JSON?**
* 一次跑完,下次问问题可以**完全离线**地直接读;
* JSON 是文本,diffable、greppable、可以提交进 git;
* 当总段落数 < 1 万时,直接 numpy 算 cosine 比起一个 vector DB 还要快。

### 5.4 第四步:相似度检索

```python
def retrieve(question, top_k=3):
    chunks = json.load(open(INDEX_FILE))
    q_emb = embed(question)
    scored = [(cosine_sim(q_emb, c["embedding"]), c) for c in chunks]
    scored.sort(key=lambda x: x[0], reverse=True)
    return scored[:top_k]
```

**为什么要 top-k?**

* k 太大 → 上下文里塞太多无关段,模型容易跑题;
* k 太小 → 可能漏掉关键事实;
* 实测 k=3~5 对个人知识库是甜点,wiki-rag 默认 3。

### 5.5 第五步:生成回答

```python
PROMPT = """基于以下内容回答问题:

{context}

问题:{question}
"""

def answer(question):
    top = retrieve(question, top_k=3)
    context = "\n\n".join(c["text"] for _, c in top)
    return ask(PROMPT.format(context=context, question=question))
```

**为什么要这样写 prompt?**

* 「基于以下内容回答问题」这一句是**护栏**——告诉模型「不要瞎编」。
* 把 context 放在 question 之前,符合人类「先给材料后提问」的直觉,模型表现更好。
* 不对模型说「你是 XX 专家」之类的角色话术——这一行没用,纯增加 token 成本。

**最后还要不要 refine?**
本项目用的是 1.5B 的小模型,初始回答经常带噪音、跑题、夹中英乱码。
所以我们再让 LLM 对自己的回答**重写一次**,用一个更严格的 prompt 强制它产出「定义 / 原理 / 示例 / 总结」结构。
代价:多一次 LLM 调用;收益:答案质量肉眼可见的改善。
当你嫌慢时,CLI 可以 `--no-refine` 关掉。

---

至此,你已经从 0 实现完一个完整的 RAG 系统了。
接下来我们对照真实代码一个一个文件看。

---

## 6. 项目代码逐文件解析

代码组织遵循「**底层永远不依赖上层**」的分层原则:

```
core/      ← 能力原语(不知道业务存在)
pipeline/  ← 业务流程(拼装 core 完成具体任务)
main.py    ← 入口(只负责命令分发)
web/       ← 入口(Streamlit UI)
```

我们从 `core/` 开始往上讲。

---

### 6.1 `core/utils.py` — 公共工具与常量

#### 作用

* 定义所有的**路径常量**(项目中任何地方需要路径都从这里 import)
* 定义日志器
* 提供 `cosine_sim()`

#### 核心片段

```python
ROOT = Path(__file__).resolve().parent.parent
DATA_DIR  = ROOT / "data"
RAW_DIR   = DATA_DIR / "raw"
WIKI_DIR  = DATA_DIR / "wiki"
INDEX_FILE = DATA_DIR / "index.json"

LLM_MODEL    = "deepseek-r1:1.5b"
EMBED_MODEL  = "nomic-embed-text"
```

#### 为什么这样设计

* **唯一真相源**:路径只在这里定义一次。要改 `data/` 位置?只改这里。
* **不要在别处 hardcode 路径**——这是工程味儿的开端。

---

### 6.2 `core/llm.py` — LLM 调用封装

#### 作用

把对 Ollama HTTP 接口的调用封装成一个干净的 `chat()` / `ask()` 函数。

#### 核心函数

```python
def chat(messages: List[Dict[str, str]], model: str = LLM_MODEL) -> str:
    payload = {"model": model, "messages": messages, "stream": False}
    resp = requests.post(OLLAMA_CHAT_URL, json=payload, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    return resp.json()["message"]["content"]


def ask(prompt: str) -> str:
    return chat([{"role": "user", "content": prompt}])
```

#### 为什么这样设计

* `chat()` 是**通用接口**(接收 messages 列表,未来要做多轮对话直接复用);
* `ask()` 是**便捷糖**(只问一句话时不用手动构造 messages);
* 把所有错误统一包成 `LLMError` 抛出 → 业务层只 catch 一种异常即可;
* **要换成 OpenAI / Claude?只改这一个文件就够。**

---

### 6.3 `core/embedding.py` — 向量化 + 缓存

#### 作用

* 调 `nomic-embed-text` 把文字变成 768 维向量
* 用 `sha256(model + text)` 做磁盘缓存

#### 核心函数

```python
def _cache_key(text: str, model: str) -> str:
    h = hashlib.sha256()
    h.update(model.encode("utf-8"))
    h.update(b"\0")
    h.update(text.encode("utf-8"))
    return h.hexdigest()

def embed(text: str, model: str = EMBED_MODEL) -> List[float]:
    cache = _load_cache()
    key = _cache_key(text, model)
    if key in cache:
        return cache[key]
    # ... 调 Ollama ...
    cache[key] = vec
    return vec
```

#### 为什么这样设计

* **embedding 调用是整个流程里最慢的一步**(文件越多越慢);
* 同一段文字 embed 一次就够了,缓存避免重算;
* 缓存 key 加上 `model` 名称——**换模型时旧缓存自动失效**,避免拿着错向量比较。

---

### 6.4 `pipeline/compiler.py` — raw → wiki

#### 作用

把 `data/raw/*.md` 喂给 LLM,让它整理结构,输出到 `data/wiki/`。

#### 核心函数

```python
def compile_note(src: Path) -> Optional[Path]:
    content = src.read_text("utf-8")
    result = ask(_PROMPT.format(content=content))
    dst = WIKI_DIR / src.name
    dst.write_text(result, encoding="utf-8")
    return dst

def compile_all() -> None:
    for f in sorted(RAW_DIR.glob("*.md")):
        compile_note(f)
```

#### 为什么这样设计

* **每个文件独立处理**:一个文件失败不会拖死全部;
* 失败 → log error → 继续下一个;
* `compile_note` 返回 `Optional[Path]`:上层可以据此统计「成功多少个」。

---

### 6.5 `pipeline/index.py` — wiki → index.json

#### 作用

* 读 `data/wiki/*.md`
* 按空行切段
* 每段调 `embed()`
* 全部序列化进 `data/index.json`

#### 核心函数

```python
def _split_paragraphs(text: str) -> List[str]:
    return [p.strip() for p in text.split("\n\n") if p.strip()]

def build_index() -> None:
    chunks = []
    for f in sorted(WIKI_DIR.glob("*.md")):
        for para in _split_paragraphs(f.read_text("utf-8")):
            vec = embed(para)
            chunks.append({"source": f.name, "text": para, "embedding": vec})
    INDEX_FILE.write_text(json.dumps(chunks, ensure_ascii=False))
    save_cache()
```

#### 为什么这样设计

* **chunk 粒度 = 段落**:足够细以保留语义、足够粗以保留上下文;
* 每个 chunk 自带 `source` 字段:未来要做「答案标注来源」轻而易举;
* 最后调 `save_cache()`:把这次新算的向量落盘,下次复用。

---

### 6.6 `pipeline/query.py` — 检索 + 生成

#### 作用

整个 RAG 的「问问题」入口。

#### 核心函数

```python
def answer_question(question: str, top_k: int = 3, refine: bool = True) -> str:
    top, _ = _retrieve(question, top_k)         # 1. 召回
    context = "\n\n".join(c["text"] for _, c in top)
    prompt  = _PROMPT.format(context=context, question=question)
    initial = ask(prompt)                       # 2. 生成
    if not refine:
        return initial
    return refine_answer(question, initial)     # 3. 重写
```

#### 为什么拆成 `answer_question` + `query`

* `answer_question()` 返回字符串 → Streamlit / chat REPL / 测试都能直接调用;
* `query()` 是 CLI 风格 → 捕获异常并 `print()`;
* **「计算逻辑」和「IO 副作用」分离**——这是 Python 工程化的基本品味。

---

### 6.7 `pipeline/refine.py` — 二次重写

#### 作用

让 LLM 把自己的初始回答**重写一遍**,去掉噪音、统一结构。

#### Prompt 节选

```text
请对以下回答进行优化:
1. 严格围绕用户问题
2. 删除模型编造的信息
3. 输出结构:定义 / 原理 / 示例 / 总结
4. 删除路径、--- 分隔符、重复内容
```

#### 为什么需要 refine

小模型(< 3B)的输出**结构感很差**,常出现:

* 答到一半跑题
* 把上下文里的路径、`---` 直接抄出来
* 编一个不存在的 API

把这些统一交给一次「自我审查」式的重写,几乎可以把 1.5B 模型拉到 7B 的体感水平。
代价是多一次 LLM 调用,加入 `--no-refine` 让用户自己选。

---

### 6.8 `pipeline/ocr.py` — 图片 → 文本

#### 作用

扫 `data/raw/*.png|jpg`,跑 `pytesseract`,输出同名 `.md`。

#### 核心函数

```python
def ocr_image(path: Path) -> str:
    img = Image.open(path)
    text = pytesseract.image_to_string(img, lang="chi_sim+eng")
    return _clean_text(text)
```

#### 为什么自带清洗

OCR 经常把页面上的横线、噪点识别成 `---`、`|||` 这种乱码。
`_clean_text()` 把「不含任何字母 / 数字 / 汉字的行」直接扔掉。一步预处理省后续无数烦恼。

---

### 6.9 `main.py` — CLI 入口

只做一件事:**解析参数 + 分发到 pipeline**。

```python
if   args.cmd == "ocr":      ocr_all()
elif args.cmd == "compile":  compile_all()
elif args.cmd == "index":    build_index()
elif args.cmd == "query":    query(args.question, top_k=args.top_k, refine=...)
elif args.cmd == "chat":     _chat_loop(...)
```

**严禁在 main.py 写业务逻辑**——main 应该薄到拿掉它整个项目仍能用。

---

## 7. 实际运行示例

### 7.1 一次完整的端到端跑通

```bash
# 1. 起 Ollama
ollama serve &
ollama pull deepseek-r1:1.5b
ollama pull nomic-embed-text

# 2. 把笔记丢进 raw/
cp ~/notes/*.md data/raw/

# 3. 一条龙
python main.py ocr      # 如果有图片
python main.py compile  # raw → wiki
python main.py index    # wiki → index.json
python main.py query "Python 装饰器是什么?"
```

### 7.2 检索阶段日志(节选)

```
[INFO] 计算问题 embedding...
[INFO]   hit 0.8412 | [python.md] 装饰器是一种在不修改原函数的情况下...
[INFO]   hit 0.7891 | [python.md] @decorator 语法等价于 func = decorator(func) ...
[INFO]   hit 0.6320 | [python.md] 常见装饰器:@staticmethod / @classmethod ...
[INFO] 生成初始回答...
[INFO] 二次优化回答 (refine)...
```

### 7.3 最终回答

> ### 定义
> 装饰器(decorator)是一个**接收函数并返回新函数**的可调用对象,用于在不修改原函数源码的情况下扩展行为。
>
> ### 原理
> `@decorator` 是 `func = decorator(func)` 的语法糖。常见用途包括日志、缓存、权限校验、重试等横切关注点。
>
> ### 示例
> ```python
> from functools import wraps
> def log_calls(func):
>     @wraps(func)
>     def wrapper(*args, **kwargs):
>         print(f"calling {func.__name__}")
>         return func(*args, **kwargs)
>     return wrapper
> ```
>
> ### 总结
> 装饰器是 Python 里给函数「包一层」的标准手法,干净、可组合、定义即生效。

---

## 8. FAQ:你一定会遇到的问题

### Q1:为什么回答不准?

可能原因(按概率排序):

1. **raw 笔记本身就没写过这个知识点** → 检索阶段就召不回,模型只能瞎编。
2. **chunk 切得太碎/太粗**:试试调整空行分段策略,或用 200-500 字的固定窗口。
3. **top-k 太小**:默认 3,可以加到 5。
4. **小模型本身不够强**:换个 7B 模型立马变好。

调试方法:跑 `--no-refine` 看看初始回答;再去 `data/index.json` 里 `grep` 关键词,确认笔记本身有没有相关段落。

---

### Q2:为什么很慢?

阶段分解:

| 阶段 | 主要耗时 | 怎么提速 |
|------|---------|---------|
| `index` | embedding 一段段算 | 第一次慢,之后命中缓存只算新段 |
| `query` 检索 | numpy 算余弦 | 1 万段以下毫秒级,再大就上 FAISS |
| `query` 生成 | LLM 推理 | 用更小的模型 / 用 GPU / 加大 `num_thread` |
| `refine` | 又一次 LLM 调用 | `--no-refine` 关掉 |

**经验值**:在 M1 Mac 上,1.5B 模型一次 query+refine 大概 8~15 秒。

---

### Q3:为什么 Ollama 报 connection refused?

99% 是没 `ollama serve`。一行命令解决:

```bash
ollama serve &
```

---

### Q4:我能不能加入新笔记后只 embed 新增的部分?

可以——而且代价几乎为 0,因为 embedding 已经做了 sha256 缓存。
你只要重新 `python main.py index`,命中过的段会瞬间跳过。
真正的「增量索引」(只读改动文件)在 Roadmap 里。

---

### Q5:能不能换 LLM?

可以。改 `core/utils.py::LLM_MODEL`,或者重写 `core/llm.py::chat()` 的实现接 OpenAI / Claude——**业务层完全无感**。
这就是分层架构的回报。

---

### Q6:我有 10 万段笔记还能用 JSON 吗?

能,但你不会想这么干。
当 chunk 数 > 1 万 时,建议换 FAISS 或 Chroma。改动只需要在 `pipeline/index.py` 和 `pipeline/query.py` 里替换存储/查询后端,其它代码完全不用动。

---

## 9. 进阶优化

### 9.1 Embedding 缓存(已实现)

`core/embedding.py` 已经按 `sha256(model + text)` 做磁盘缓存,关键点:

* **缓存 key 包含 model 名**:换模型自动失效;
* **写盘只在 `build_index()` 末尾发生一次**:避免每段都 IO;
* 缓存文件就是 JSON,可以直接 `cat` 查看。

### 9.2 Chunk 优化

朴素的「按空行分段」适合写得规整的 Markdown,但你可以更聪明:

| 策略 | 优点 | 缺点 |
|------|------|------|
| 固定窗口(如 300 字) | 简单可控 | 可能切断句子 |
| 滑动窗口(窗口 300 + 重叠 50) | 不丢上下文 | chunks 数量翻倍 |
| 按 Markdown 标题切 | 每段语义自包含 | 需要解析 Markdown 结构 |
| 递归字符切(langchain 风格) | 通用 | 实现复杂 |

> **建议**:先用空行分段把流程跑通,等真的发现召回不准了再升级。

### 9.3 Top-K 调整

* **k=1**:只看最相似的一段。准但容易漏。
* **k=3**(默认):甜点。
* **k=5+**:召回更全,但 prompt 变长,模型容易跑题。
* 高级玩法:先取 k=10,再用 LLM 做一次 **rerank**(让模型选出最相关的 3 段),效果显著。

### 9.4 Hybrid Search(BM25 + 向量)

* 关键词搜索擅长:API 名、错误码、命令、专有名词
* 语义搜索擅长:自然语言提问
* 两者结果**加权融合**,对个人知识库提升尤其明显(笔记里经常有 `useEffect`、`__init__` 这种)。

### 9.5 加入引用回显

在 `answer_question` 末尾追加:

```python
sources = sorted({c["source"] for _, c in top})
return f"{answer}\n\n> 来源:{', '.join(sources)}"
```

一行代码让答案变得可追溯——**信任感的关键**。

---

## 10. 扩展方向:把它变成更厉害的东西

### 10.1 全新 Web UI(重点)

不止是 Streamlit。后面我们会基于 DESIGN.md 设计一个 Apple 风格的前端,支持:

* 主对话界面(ChatGPT 式)
* 知识库管理页(看哪些文件已索引)
* 调试面板(看 embedding 长度、top-k、cosine 分数)
* Light / Dark 双模式

→ 详见本文档「**第二部分:UI 设计说明**」。

### 10.2 Obsidian 集成

直接让 wiki-rag 把 Obsidian 仓库作为 `data/raw/`:

```python
RAW_DIR = Path.home() / "Documents" / "ObsidianVault"
```

每次保存笔记 → 后台触发增量 embedding → 你随时可以问自己整个第二大脑。

### 10.3 OCR 识别(已实现)

可以再扩展:

* 识别 PDF(用 `pdfplumber` / `PyMuPDF`)
* 识别手写笔记(GPT-4o-mini Vision、本地 LLaVA)
* 自动识别公式(LaTeX OCR)

### 10.4 Agent 记忆系统

把 RAG 当作一个 Agent 的「**长期记忆**」:

```
对话历史 → 自动写入 raw/ → 自动 embed → 下一次对话可检索
```

这是搭建「**和你共同成长的 AI 助手**」最核心的一块拼图。

### 10.5 多源插件化

设计一个 `Source` 接口:

```python
class Source(Protocol):
    def list(self) -> Iterable[Document]: ...
    def watch(self, callback: Callable[[Document], None]) -> None: ...
```

然后实现:

* `MarkdownSource`(当前)
* `ObsidianSource`
* `NotionSource`
* `GitHubIssueSource`
* `EmailSource`
* `ChromeBookmarkSource`

→ wiki-rag 就从一个「Markdown 工具」变成一个「**通用个人知识平台**」。

---

# 📐 第二部分:UI 设计说明(基于 DESIGN.md)

> 本节定义 wiki-rag 全新前端的页面结构、组件、交互与配色,**严格遵守 `design/DESIGN.md`(Apple 风格设计系统)**。

## A. 设计原则(从 DESIGN.md 提取的硬约束)

| 维度 | 规范 |
|------|------|
| 字体(>= 20px) | `SF Pro Display` |
| 字体(< 20px) | `SF Pro Text` |
| 字距 | 全局负字距:56px → -0.28px;17px → -0.374px;14px → -0.224px |
| 主色 | **唯一**强调色 Apple Blue `#0071e3`,仅用于交互元素 |
| 浅色页背景 | `#f5f5f7` |
| 深色页背景 | `#000000` |
| 浅色文字 | `#1d1d1f` |
| 深色文字 | `#ffffff` |
| 链接(浅) | `#0066cc` |
| 链接(深) | `#2997ff` |
| 卡片圆角 | 5–8px(按钮 8px、卡片 8px、搜索框 11px、Pill 980px、圆形控件 50%) |
| 卡片阴影 | `rgba(0,0,0,0.22) 3px 5px 30px 0px`(仅在浅色页面用) |
| 导航栏 | `rgba(0,0,0,0.8)` + `backdrop-filter: saturate(180%) blur(20px)`,48px 高 |
| 焦点环 | `2px solid #0071e3` |
| 渐变 / 多色 / 边框 | ❌ 一律禁止 |

---

## B. 信息架构(IA)

```
┌──────────────────────────────────────────────────────────┐
│ ⌘ Wiki-RAG    Chat   Library   Debug          ☀ / 🌙     │ ← 顶部 Glass Nav
├──────────────────────────────────────────────────────────┤
│                                                          │
│                  [当前页面内容]                           │
│                                                          │
└──────────────────────────────────────────────────────────┘
```

四个一级页面:

| 路由 | 名称 | 作用 |
|------|------|------|
| `/` | **Chat**(主页) | 主问答界面(ChatGPT 式) |
| `/library` | **Library** | raw / wiki 文件管理 + 一键 rebuild |
| `/debug` | **Debug** | 检索调试面板,看 top-k、相似度、向量长度 |
| `/settings` | Settings | top-k、refine 开关、模型选择、Light/Dark |

---

## C. 页面 1:Chat(主对话界面)

### C.1 布局

```
┌─────────────────────────────────────────────────────────┐
│  Glass Nav (48px)                                       │
├──────────┬──────────────────────────────────────────────┤
│          │                                              │
│ 历史     │   ┌──────────────────────────────────┐       │
│ 会话     │   │  你:Python 装饰器是什么?         │       │
│          │   └──────────────────────────────────┘       │
│ • 今天   │                                              │
│ • 昨天   │   ┌──────────────────────────────────┐       │
│ • 7 天前 │   │  Wiki-RAG:                       │       │
│          │   │  ## 定义 ...                     │       │
│ + 新建   │   │  ## 原理 ...                     │       │
│          │   │  ## 示例 ...                     │       │
│          │   │  ▸ 检索结果(3 段·展开)         │       │
│          │   └──────────────────────────────────┘       │
│          │                                              │
│          │   ┌──────────────────────────────────┐       │
│          │   │ ⌘ 提问框…           [Top-K 3 ▾] │       │
│          │   └──────────────────────────────────┘       │
└──────────┴──────────────────────────────────────────────┘
```

### C.2 关键组件

| 组件 | 规格 |
|------|------|
| 顶部导航 | Glass:`rgba(0,0,0,0.8)` + blur 20px,48px 高,左侧 Logo + 应用名,中间 Tab |
| 会话侧栏 | 256px 宽,浅色页 `#f5f5f7`,深色页 `#1d1d1f` |
| 用户气泡 | 浅色页 `#1d1d1f` 背景 + 白字;深色页 `#272729` + 白字。圆角 8px。 |
| 助手气泡 | 浅色页:透明背景 + `#1d1d1f` 字;深色页:透明 + 白字。无气泡感(与用户区分)。 |
| 检索结果折叠 | 默认收起。展开后每条命中显示「源文件 + cosine 分数 + 段落预览」。 |
| 输入框 | 圆角 11px,`#fafafc` 浅 / `#272729` 深,3px 透明边框,focus 时换 2px Apple Blue |
| 提交按钮 | Apple Blue `#0071e3`,圆角 8px,padding 8px 15px,白字 17px |

### C.3 交互细节

* `Enter` 发送,`Shift+Enter` 换行
* 流式打字效果(基于 SSE / fetch streaming)
* 长答案自动 markdown 渲染(含代码块语法高亮)
* 每条助手回答下方有 **Copy / Regenerate / 调试** 三个 14px 链接(`#0066cc`)

---

## D. 页面 2:Library(知识库管理)

### D.1 布局

```
┌─────────────────────────────────────────────────────────┐
│  Glass Nav                                              │
├─────────────────────────────────────────────────────────┤
│   Library                                  [Rebuild ↻] │ ← 56px Display 标题
│   全部 24  ·  已索引 22  ·  未索引 2                    │
│                                                         │
│   ┌────────────────────────────────────────────────┐    │
│   │ 📄 python.md         24 段  ✅ 已索引   23:14 │    │
│   ├────────────────────────────────────────────────┤    │
│   │ 📄 react.md          18 段  ✅ 已索引   23:14 │    │
│   ├────────────────────────────────────────────────┤    │
│   │ 🖼  screenshot.png    OCR    ⚠ 未索引     ─    │    │
│   └────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────┘
```

### D.2 元素

| 元素 | 规格 |
|------|------|
| 页面标题 | SF Pro Display 56px / weight 600 / line-height 1.07 / letter-spacing -0.28px |
| 副标题统计 | SF Pro Text 17px / weight 400 / `rgba(0,0,0,0.48)` |
| Rebuild 按钮 | Apple Blue 主按钮 |
| 文件行 | 分隔线 `rgba(0,0,0,0.08)`;hover 背景 `#fafafc`;点击展开预览 |
| 状态徽章 | 「已索引」用 `#1d1d1f`(全站只有 Apple Blue 一种强调色,绝不引入绿/红);「未索引」用 `rgba(0,0,0,0.48)` |

> ⚠️ 即使代表「成功」,也**不许加绿色**——DESIGN.md 明确说唯一的强调色就是 Apple Blue。状态用文案 + 字重对比表达。

---

## E. 页面 3:Debug(调试面板)

### E.1 布局

```
┌─────────────────────────────────────────────────────────┐
│  Debug                                                  │
│                                                         │
│   提问  ┌─────────────────────────┐ [Run]               │
│         └─────────────────────────┘                     │
│                                                         │
│   ── 检索结果 ─────────────────────                     │
│   #1  cosine 0.8412   python.md                         │
│        装饰器是一种在不修改原函数...                    │
│        [██████████░░░░░░░░░] 84.1%                      │
│                                                         │
│   #2  cosine 0.7891   python.md                         │
│        @decorator 语法等价于...                         │
│        [████████████░░░░░░░] 78.9%                      │
│                                                         │
│   ── Embedding 信息 ──────────────                      │
│   维度: 768                                             │
│   缓存命中: 是                                          │
│   查询向量预览: [0.12, -0.04, 0.88, ...]                │
└─────────────────────────────────────────────────────────┘
```

### E.2 组件

| 组件 | 规格 |
|------|------|
| 检索行 | 卡片 `#f5f5f7` / `#272729`,圆角 8px |
| 进度条 | 100% 宽度,高 4px,背景 `rgba(0,0,0,0.08)`,前景 Apple Blue |
| 数字 | SF Pro Text 17px,weight 600 |
| 向量预览 | 等宽字体(`SF Mono`),14px |

> Debug 是给「想知道发生了什么」的人看的,把 RAG 的黑盒撕开。

---

## F. Light / Dark Mode 切换规范

| 元素 | Light | Dark |
|------|-------|------|
| 页面背景 | `#f5f5f7` | `#000000` |
| 卡片背景 | `#ffffff` 或 `#f5f5f7` | `#272729` |
| 主文字 | `#1d1d1f` | `#ffffff` |
| 副文字 | `rgba(0,0,0,0.8)` | `rgba(255,255,255,0.8)` |
| 弱文字 | `rgba(0,0,0,0.48)` | `rgba(255,255,255,0.48)` |
| 链接 | `#0066cc` | `#2997ff` |
| 主按钮 | `#0071e3` / 白字 | `#0071e3` / 白字 |
| 输入框 | `#fafafc` + 3px `rgba(0,0,0,0.04)` 边框 | `#272729` + 3px `rgba(255,255,255,0.04)` 边框 |
| 焦点环 | `2px solid #0071e3` | `2px solid #0071e3` |
| 导航 | Glass 仍为暗色(无论 light/dark) | Glass 仍为暗色 |

**切换方式**:

* 跟随系统:`prefers-color-scheme`
* 手动覆盖:右上角 `☀ / 🌙` 按钮(Pill,980px 圆角)
* 用户选择存 `localStorage.theme`

---

## G. 功能增强(必做)

### G.1 多轮对话记忆

* 当前会话保持 `messages: [{role, content}, ...]`,每次 query 时把最近 N 轮塞进 prompt 之前。
* 历史保留在 `localStorage` + 后端 `data/sessions/{id}.json`。

### G.2 查询历史

* 侧栏「会话」list 按时间分组:今天 / 昨天 / 7 天前 / 更早
* 点击会话回到完整对话上下文

### G.3 可视化检索结果(每条回答内嵌)

每条 assistant 消息下方默认有「▸ 检索结果(3 段)」折叠块:

```
▾ 检索结果
  ├ #1  0.84  python.md   装饰器是一种...
  ├ #2  0.79  python.md   @decorator 语法...
  └ #3  0.63  python.md   常见装饰器...
```

可视化部分:每条命中带一个 **horizontal bar** 表示 cosine 分数(4px 高,Apple Blue)。

### G.4 插件化数据源

设置页面的 **Sources** Tab:

```
[ ✓ ] Markdown (data/raw/)
[   ] Obsidian Vault          [Connect]
[   ] Notion                  [Connect]
[   ] GitHub Issues           [Connect]
```

后端实现 `Source` Protocol;前端只显示每个 source 的同步状态。

---

# 💻 第三部分:前端代码示例(React + TS)

> 下面给出**可直接落地的关键组件**:主题变量、Glass Nav、Chat 页、Library 行、Debug 面板。
> 使用 React + TypeScript + 原生 CSS(CSS Variables 实现 Light/Dark)。
> 直接复制到 `web-frontend/` 目录即可。

## 1. 全局 CSS 变量与字体

`web-frontend/src/styles/theme.css`

```css
:root {
  /* === Apple Light === */
  --color-bg:           #f5f5f7;
  --color-surface:      #ffffff;
  --color-text:         #1d1d1f;
  --color-text-soft:    rgba(0, 0, 0, 0.8);
  --color-text-muted:   rgba(0, 0, 0, 0.48);
  --color-link:         #0066cc;
  --color-accent:       #0071e3;
  --color-divider:      rgba(0, 0, 0, 0.08);
  --color-input-bg:     #fafafc;
  --color-input-border: rgba(0, 0, 0, 0.04);
  --shadow-card:        rgba(0, 0, 0, 0.22) 3px 5px 30px 0px;

  --radius-sm:  5px;
  --radius-md:  8px;
  --radius-lg:  11px;
  --radius-pill: 980px;

  --font-display: "SF Pro Display", "SF Pro Icons", "Helvetica Neue",
                  Helvetica, Arial, sans-serif;
  --font-text:    "SF Pro Text", "SF Pro Icons", "Helvetica Neue",
                  Helvetica, Arial, sans-serif;
  --font-mono:    "SF Mono", ui-monospace, Menlo, Consolas, monospace;
}

[data-theme="dark"] {
  --color-bg:           #000000;
  --color-surface:      #272729;
  --color-text:         #ffffff;
  --color-text-soft:    rgba(255, 255, 255, 0.8);
  --color-text-muted:   rgba(255, 255, 255, 0.48);
  --color-link:         #2997ff;
  --color-accent:       #0071e3;
  --color-divider:      rgba(255, 255, 255, 0.08);
  --color-input-bg:     #272729;
  --color-input-border: rgba(255, 255, 255, 0.04);
  --shadow-card:        none;
}

* { box-sizing: border-box; }

html, body, #root {
  margin: 0;
  padding: 0;
  background: var(--color-bg);
  color: var(--color-text);
  font-family: var(--font-text);
  font-size: 17px;
  line-height: 1.47;
  letter-spacing: -0.374px;
  -webkit-font-smoothing: antialiased;
}

h1, h2, h3 {
  font-family: var(--font-display);
  font-weight: 600;
  letter-spacing: -0.28px;
  line-height: 1.07;
  margin: 0;
}

h1 { font-size: 56px; }
h2 { font-size: 40px; line-height: 1.10; }
h3 { font-size: 28px; line-height: 1.14; letter-spacing: 0.196px; font-weight: 400; }

a {
  color: var(--color-link);
  text-decoration: none;
}
a:hover { text-decoration: underline; }

button {
  font-family: var(--font-text);
  font-size: 17px;
  letter-spacing: -0.374px;
  border: none;
  cursor: pointer;
}
button:focus-visible {
  outline: 2px solid var(--color-accent);
  outline-offset: 2px;
}
```

---

## 2. 主题切换 Hook

`web-frontend/src/hooks/useTheme.ts`

```ts
import { useEffect, useState } from "react";

export type Theme = "light" | "dark";

export function useTheme() {
  const [theme, setTheme] = useState<Theme>(() => {
    const saved = localStorage.getItem("theme") as Theme | null;
    if (saved) return saved;
    return window.matchMedia("(prefers-color-scheme: dark)").matches
      ? "dark"
      : "light";
  });

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    localStorage.setItem("theme", theme);
  }, [theme]);

  return {
    theme,
    toggle: () => setTheme((t) => (t === "light" ? "dark" : "light")),
  };
}
```

---

## 3. Glass Nav 组件

`web-frontend/src/components/GlassNav.tsx`

```tsx
import { NavLink } from "react-router-dom";
import { useTheme } from "../hooks/useTheme";
import "./GlassNav.css";

export function GlassNav() {
  const { theme, toggle } = useTheme();
  return (
    <nav className="glass-nav">
      <div className="glass-nav__brand">⌘ Wiki-RAG</div>
      <ul className="glass-nav__tabs">
        <li><NavLink to="/">Chat</NavLink></li>
        <li><NavLink to="/library">Library</NavLink></li>
        <li><NavLink to="/debug">Debug</NavLink></li>
      </ul>
      <button
        className="glass-nav__theme"
        onClick={toggle}
        aria-label="切换主题"
      >
        {theme === "light" ? "🌙" : "☀"}
      </button>
    </nav>
  );
}
```

`GlassNav.css`

```css
.glass-nav {
  position: sticky;
  top: 0;
  z-index: 1000;
  height: 48px;
  padding: 0 22px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: rgba(0, 0, 0, 0.8);
  backdrop-filter: saturate(180%) blur(20px);
  -webkit-backdrop-filter: saturate(180%) blur(20px);
  color: #ffffff;
}

.glass-nav__brand {
  font-family: var(--font-text);
  font-size: 14px;
  letter-spacing: -0.224px;
  font-weight: 600;
}

.glass-nav__tabs {
  list-style: none;
  display: flex;
  gap: 24px;
  margin: 0;
  padding: 0;
}

.glass-nav__tabs a {
  color: #ffffff;
  font-size: 12px;
  letter-spacing: -0.12px;
  opacity: 0.8;
}
.glass-nav__tabs a.active,
.glass-nav__tabs a:hover {
  opacity: 1;
}

.glass-nav__theme {
  background: transparent;
  color: #ffffff;
  font-size: 14px;
  border-radius: 980px;
  padding: 4px 12px;
}
```

---

## 4. Chat 页面(主对话)

`web-frontend/src/pages/Chat.tsx`

```tsx
import { useState } from "react";
import "./Chat.css";

type Hit = { source: string; text: string; score: number };
type Message = {
  role: "user" | "assistant";
  content: string;
  hits?: Hit[];
};

export function ChatPage() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [topK, setTopK] = useState(3);
  const [loading, setLoading] = useState(false);

  async function send() {
    const q = input.trim();
    if (!q) return;
    setInput("");
    setMessages((m) => [...m, { role: "user", content: q }]);
    setLoading(true);
    try {
      const res = await fetch("/api/query", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: q, top_k: topK, refine: true }),
      });
      const data = await res.json();
      setMessages((m) => [
        ...m,
        { role: "assistant", content: data.answer, hits: data.hits },
      ]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="chat">
      <main className="chat__stream">
        {messages.map((m, i) => (
          <MessageBubble key={i} msg={m} />
        ))}
        {loading && <div className="chat__loading">思考中…</div>}
      </main>

      <footer className="chat__inputbar">
        <input
          className="chat__input"
          placeholder="问点什么…  ⌘ + ↵ 发送"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && send()}
        />
        <select
          className="chat__topk"
          value={topK}
          onChange={(e) => setTopK(Number(e.target.value))}
        >
          {[1, 3, 5, 7, 10].map((k) => (
            <option key={k} value={k}>Top-K {k}</option>
          ))}
        </select>
        <button className="chat__send" onClick={send} disabled={loading}>
          发送
        </button>
      </footer>
    </div>
  );
}

function MessageBubble({ msg }: { msg: Message }) {
  if (msg.role === "user") {
    return (
      <div className="bubble bubble--user">
        <div className="bubble__body">{msg.content}</div>
      </div>
    );
  }
  return (
    <div className="bubble bubble--assistant">
      <div
        className="bubble__body"
        dangerouslySetInnerHTML={{ __html: renderMarkdown(msg.content) }}
      />
      {msg.hits && msg.hits.length > 0 && (
        <details className="bubble__hits">
          <summary>检索结果 ({msg.hits.length} 段)</summary>
          {msg.hits.map((h, i) => (
            <div className="hit" key={i}>
              <div className="hit__meta">
                <span className="hit__rank">#{i + 1}</span>
                <span className="hit__src">{h.source}</span>
                <span className="hit__score">{h.score.toFixed(4)}</span>
              </div>
              <div className="hit__bar">
                <div
                  className="hit__bar-fill"
                  style={{ width: `${Math.max(0, h.score) * 100}%` }}
                />
              </div>
              <p className="hit__text">{h.text}</p>
            </div>
          ))}
        </details>
      )}
    </div>
  );
}

function renderMarkdown(md: string) {
  // 实战中接 marked / react-markdown,这里仅占位
  return md.replace(/\n/g, "<br/>");
}
```

`Chat.css`

```css
.chat {
  max-width: 820px;
  margin: 0 auto;
  padding: 40px 24px 120px;
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.chat__stream {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.bubble { display: flex; flex-direction: column; }
.bubble--user { align-items: flex-end; }
.bubble--assistant { align-items: flex-start; }

.bubble__body {
  max-width: 90%;
  font-family: var(--font-text);
  font-size: 17px;
  line-height: 1.47;
  letter-spacing: -0.374px;
}

.bubble--user .bubble__body {
  background: var(--color-text);
  color: var(--color-bg);
  padding: 10px 14px;
  border-radius: var(--radius-md);
}

.bubble--assistant .bubble__body {
  color: var(--color-text);
}

.bubble__hits {
  margin-top: 12px;
  font-size: 14px;
  letter-spacing: -0.224px;
  color: var(--color-text-soft);
  width: 100%;
}
.bubble__hits summary {
  cursor: pointer;
  color: var(--color-link);
}

.hit {
  margin: 12px 0;
  padding: 12px 14px;
  background: var(--color-surface);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-card);
}
[data-theme="dark"] .hit { box-shadow: none; }

.hit__meta {
  display: flex;
  gap: 12px;
  font-size: 12px;
  letter-spacing: -0.12px;
  color: var(--color-text-muted);
}
.hit__rank { font-weight: 600; color: var(--color-text); }
.hit__src  { font-family: var(--font-mono); }
.hit__score { margin-left: auto; color: var(--color-accent); font-weight: 600; }

.hit__bar {
  margin-top: 8px;
  height: 4px;
  border-radius: var(--radius-pill);
  background: var(--color-divider);
  overflow: hidden;
}
.hit__bar-fill {
  height: 100%;
  background: var(--color-accent);
}

.hit__text {
  margin: 8px 0 0;
  font-size: 14px;
  letter-spacing: -0.224px;
  color: var(--color-text-soft);
}

.chat__inputbar {
  position: fixed;
  left: 0; right: 0; bottom: 24px;
  display: flex;
  gap: 8px;
  max-width: 820px;
  margin: 0 auto;
  padding: 0 24px;
}

.chat__input {
  flex: 1;
  font-family: var(--font-text);
  font-size: 17px;
  letter-spacing: -0.374px;
  padding: 12px 14px;
  border-radius: var(--radius-lg);
  background: var(--color-input-bg);
  border: 3px solid var(--color-input-border);
  color: var(--color-text);
  outline: none;
}
.chat__input:focus {
  border-color: transparent;
  outline: 2px solid var(--color-accent);
}

.chat__topk {
  font-family: var(--font-text);
  font-size: 14px;
  letter-spacing: -0.224px;
  padding: 0 12px;
  border-radius: var(--radius-lg);
  background: var(--color-input-bg);
  border: 3px solid var(--color-input-border);
  color: var(--color-text);
}

.chat__send {
  padding: 8px 15px;
  border-radius: var(--radius-md);
  background: var(--color-accent);
  color: #ffffff;
  font-size: 17px;
}
.chat__send:disabled { opacity: 0.5; cursor: not-allowed; }

.chat__loading {
  font-size: 14px;
  color: var(--color-text-muted);
}
```

---

## 5. Library 页面(知识库管理)

`web-frontend/src/pages/Library.tsx`

```tsx
import { useEffect, useState } from "react";
import "./Library.css";

type FileItem = {
  name: string;
  kind: "md" | "image";
  chunks: number | null;
  indexed: boolean;
  updatedAt: string;
};

export function LibraryPage() {
  const [files, setFiles] = useState<FileItem[]>([]);
  const [busy, setBusy] = useState(false);

  useEffect(() => { refresh(); }, []);

  async function refresh() {
    const res = await fetch("/api/library");
    setFiles(await res.json());
  }

  async function rebuild() {
    setBusy(true);
    try {
      await fetch("/api/library/rebuild", { method: "POST" });
      await refresh();
    } finally { setBusy(false); }
  }

  const indexed = files.filter((f) => f.indexed).length;

  return (
    <div className="library">
      <header className="library__header">
        <h1>Library</h1>
        <button className="btn-primary" onClick={rebuild} disabled={busy}>
          {busy ? "Rebuilding…" : "Rebuild Index"}
        </button>
      </header>
      <p className="library__stats">
        全部 {files.length} · 已索引 {indexed} · 未索引 {files.length - indexed}
      </p>
      <ul className="library__list">
        {files.map((f) => (
          <li className="library__row" key={f.name}>
            <span className="library__icon">
              {f.kind === "md" ? "📄" : "🖼"}
            </span>
            <span className="library__name">{f.name}</span>
            <span className="library__chunks">
              {f.chunks != null ? `${f.chunks} 段` : "—"}
            </span>
            <span
              className={
                "library__status " +
                (f.indexed ? "library__status--ok" : "library__status--off")
              }
            >
              {f.indexed ? "已索引" : "未索引"}
            </span>
            <span className="library__time">{f.updatedAt}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
```

`Library.css`

```css
.library {
  max-width: 980px;
  margin: 0 auto;
  padding: 64px 24px;
}

.library__header {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  margin-bottom: 8px;
}

.library__stats {
  color: var(--color-text-muted);
  font-size: 17px;
  margin: 0 0 32px;
}

.btn-primary {
  background: var(--color-accent);
  color: #ffffff;
  padding: 8px 15px;
  border-radius: var(--radius-md);
  font-size: 17px;
}

.library__list {
  list-style: none;
  margin: 0;
  padding: 0;
  background: var(--color-surface);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-card);
  overflow: hidden;
}
[data-theme="dark"] .library__list { box-shadow: none; }

.library__row {
  display: grid;
  grid-template-columns: 32px 1fr 80px 80px 120px;
  align-items: center;
  gap: 16px;
  padding: 14px 20px;
  border-bottom: 1px solid var(--color-divider);
  font-size: 14px;
  letter-spacing: -0.224px;
}
.library__row:last-child { border-bottom: none; }
.library__row:hover { background: var(--color-input-bg); }

.library__name { font-family: var(--font-mono); }
.library__chunks { color: var(--color-text-muted); }
.library__status { font-weight: 600; }
.library__status--ok  { color: var(--color-text); }
.library__status--off { color: var(--color-text-muted); }
.library__time { color: var(--color-text-muted); text-align: right; }
```

---

## 6. Debug 面板

`web-frontend/src/pages/Debug.tsx`

```tsx
import { useState } from "react";
import "./Debug.css";

type DebugResp = {
  hits: { source: string; text: string; score: number }[];
  embedding: { dim: number; cached: boolean; preview: number[] };
};

export function DebugPage() {
  const [q, setQ] = useState("");
  const [data, setData] = useState<DebugResp | null>(null);

  async function run() {
    if (!q.trim()) return;
    const res = await fetch("/api/debug", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question: q }),
    });
    setData(await res.json());
  }

  return (
    <div className="debug">
      <h1>Debug</h1>

      <div className="debug__bar">
        <input
          className="debug__input"
          placeholder="输入问题,看检索发生了什么"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && run()}
        />
        <button className="btn-primary" onClick={run}>Run</button>
      </div>

      {data && (
        <>
          <h3 className="debug__section">检索结果</h3>
          {data.hits.map((h, i) => (
            <div className="debug__hit" key={i}>
              <div className="debug__hit-meta">
                <span>#{i + 1}</span>
                <span>cosine {h.score.toFixed(4)}</span>
                <span>{h.source}</span>
              </div>
              <div className="debug__bar-bg">
                <div
                  className="debug__bar-fill"
                  style={{ width: `${Math.max(0, h.score) * 100}%` }}
                />
              </div>
              <p className="debug__text">{h.text}</p>
            </div>
          ))}

          <h3 className="debug__section">Embedding 信息</h3>
          <div className="debug__kv">
            <span>维度</span><b>{data.embedding.dim}</b>
            <span>缓存命中</span><b>{data.embedding.cached ? "是" : "否"}</b>
            <span>查询向量预览</span>
            <code>[{data.embedding.preview.map(n => n.toFixed(3)).join(", ")}, ...]</code>
          </div>
        </>
      )}
    </div>
  );
}
```

`Debug.css`

```css
.debug {
  max-width: 980px;
  margin: 0 auto;
  padding: 64px 24px;
}

.debug__bar {
  display: flex;
  gap: 8px;
  margin: 24px 0 40px;
}
.debug__input {
  flex: 1;
  padding: 12px 14px;
  font-size: 17px;
  letter-spacing: -0.374px;
  border-radius: var(--radius-lg);
  background: var(--color-input-bg);
  border: 3px solid var(--color-input-border);
  color: var(--color-text);
  outline: none;
}
.debug__input:focus {
  border-color: transparent;
  outline: 2px solid var(--color-accent);
}

.debug__section {
  margin: 32px 0 12px;
}

.debug__hit {
  background: var(--color-surface);
  border-radius: var(--radius-md);
  padding: 14px 18px;
  margin-bottom: 12px;
  box-shadow: var(--shadow-card);
}
[data-theme="dark"] .debug__hit { box-shadow: none; }

.debug__hit-meta {
  display: flex;
  gap: 16px;
  font-size: 12px;
  letter-spacing: -0.12px;
  color: var(--color-text-muted);
}
.debug__hit-meta span:nth-child(2) {
  color: var(--color-accent);
  font-weight: 600;
}

.debug__bar-bg {
  height: 4px;
  margin: 8px 0;
  background: var(--color-divider);
  border-radius: var(--radius-pill);
  overflow: hidden;
}
.debug__bar-fill {
  height: 100%;
  background: var(--color-accent);
}

.debug__text {
  margin: 8px 0 0;
  font-size: 14px;
  letter-spacing: -0.224px;
  color: var(--color-text-soft);
}

.debug__kv {
  display: grid;
  grid-template-columns: 140px 1fr;
  gap: 12px 24px;
  font-size: 14px;
  letter-spacing: -0.224px;
}
.debug__kv b { color: var(--color-text); }
.debug__kv code {
  font-family: var(--font-mono);
  color: var(--color-text-soft);
  word-break: break-all;
}
```

---

## 7. 应用入口

`web-frontend/src/App.tsx`

```tsx
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { GlassNav } from "./components/GlassNav";
import { ChatPage } from "./pages/Chat";
import { LibraryPage } from "./pages/Library";
import { DebugPage } from "./pages/Debug";
import "./styles/theme.css";

export default function App() {
  return (
    <BrowserRouter>
      <GlassNav />
      <Routes>
        <Route path="/" element={<ChatPage />} />
        <Route path="/library" element={<LibraryPage />} />
        <Route path="/debug" element={<DebugPage />} />
      </Routes>
    </BrowserRouter>
  );
}
```

---

## 8. 后端需要新增的 HTTP 接口(FastAPI 草图)

为了让上面的前端跑起来,给 wiki-rag 加一个轻量 HTTP 层即可(不影响 CLI / Streamlit):

`web/api.py`(建议新增文件)

```python
from fastapi import FastAPI
from pydantic import BaseModel
from pipeline.query import answer_question, _retrieve
from pipeline.index import build_index
from core.embedding import embed
from core.utils import RAW_DIR, WIKI_DIR

app = FastAPI()

class QueryReq(BaseModel):
    question: str
    top_k: int = 3
    refine: bool = True

@app.post("/api/query")
def api_query(req: QueryReq):
    top, _ = _retrieve(req.question, req.top_k)
    answer = answer_question(req.question, top_k=req.top_k, refine=req.refine)
    return {
        "answer": answer,
        "hits": [
            {"source": c.get("source", "?"), "text": c["text"], "score": s}
            for s, c in top
        ],
    }

@app.post("/api/debug")
def api_debug(req: QueryReq):
    top, _ = _retrieve(req.question, req.top_k)
    q_emb = embed(req.question)
    return {
        "hits": [
            {"source": c.get("source", "?"), "text": c["text"], "score": s}
            for s, c in top
        ],
        "embedding": {
            "dim": len(q_emb),
            "cached": True,
            "preview": q_emb[:8],
        },
    }

@app.get("/api/library")
def api_library():
    items = []
    for p in sorted(RAW_DIR.glob("*")):
        items.append({
            "name": p.name,
            "kind": "md" if p.suffix == ".md" else "image",
            "chunks": None,
            "indexed": (WIKI_DIR / p.name).exists(),
            "updatedAt": str(p.stat().st_mtime),
        })
    return items

@app.post("/api/library/rebuild")
def api_rebuild():
    build_index()
    return {"ok": True}
```

启动:

```bash
uvicorn web.api:app --reload --port 8000
```

前端在 `vite.config.ts` 配置代理:

```ts
server: { proxy: { "/api": "http://localhost:8000" } }
```

---

# 🎓 写在最后

这份文档不只是「告诉你怎么用 wiki-rag」,更是想让你理解:

1. **RAG 的本质**:不是魔法,是「先查后答」,五行 cosine 加一段 prompt 就够了。
2. **分层架构的回报**:换 LLM、换 embedding、换前端,都只动**一个文件**。
3. **简单 ≠ 简陋**:在数据规模没逼到你之前,JSON + numpy 就是最香的方案。
4. **本地优先的价值**:你的笔记永远在你自己的硬盘上,无 API、无计费、无审查。

> 🪄 最好的教科书不是被读完的,而是被改完的。
> 把 wiki-rag clone 下来,按照本文档的扩展方向加点东西——
> 当你写出第一个自己的 `Source` 插件时,你就是真正会 RAG 的人。
