import { useEffect, useRef, useState } from "react";
import "../styles/Chat.css";

type Hit = {
  source: string;
  text: string;
  score: number;
  dense_score?: number;
  bm25_score?: number;
  retrieval_backend?: string;
};

type Message = {
  id: string;
  role: "user" | "assistant";
  content: string;
  hits?: Hit[];
  createdAt: number;
};

const HISTORY_KEY = "wiki-rag.history";
const SESSION_KEY = "wiki-rag.session";
const SCROLL_KEY = "wiki-rag.chat.scrollTop";

function loadSessionId() {
  let sid = localStorage.getItem(SESSION_KEY);
  if (!sid) {
    sid = uid();
    localStorage.setItem(SESSION_KEY, sid);
  }
  return sid;
}

function loadHistory(): Message[] {
  try {
    const raw = localStorage.getItem(HISTORY_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    if (Array.isArray(parsed)) return parsed as Message[];
    return [];
  } catch {
    return [];
  }
}

function saveHistory(msgs: Message[]) {
  try {
    localStorage.setItem(HISTORY_KEY, JSON.stringify(msgs.slice(-200)));
  } catch {
    /* ignore quota errors */
  }
}

function uid() {
  return Math.random().toString(36).slice(2) + Date.now().toString(36);
}

export function ChatPage() {
  const [messages, setMessages] = useState<Message[]>(() => loadHistory());
  const [sessionId, setSessionId] = useState(() => loadSessionId());
  const [input, setInput] = useState("");
  const [topK, setTopK] = useState(3);
  const [answerMode, setAnswerMode] = useState("expand");
  const [minScore, setMinScore] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showScrollBottom, setShowScrollBottom] = useState(false);
  const streamRef = useRef<HTMLDivElement>(null);
  const composingRef = useRef(false);
  const lastCompositionEndRef = useRef(0);
  const abortRef = useRef<AbortController | null>(null);
  const followBottomRef = useRef(false);

  useEffect(() => {
    saveHistory(messages);
  }, [messages]);

  useEffect(() => {
    const savedTop = Number(sessionStorage.getItem(SCROLL_KEY) ?? "0");
    window.requestAnimationFrame(() => {
      const el = streamRef.current;
      if (!el) return;
      el.scrollTop = Math.max(0, Math.min(savedTop, el.scrollHeight));
      updateScrollState(el);
    });
  }, []);

  useEffect(() => {
    if (!followBottomRef.current) return;
    window.requestAnimationFrame(() => {
      scrollToBottom("auto");
    });
  }, [messages, loading]);

  async function send() {
    const q = input.trim();
    if (!q || loading) return;
    setError(null);
    setInput("");
    followBottomRef.current = true;

    const userMsg: Message = {
      id: uid(),
      role: "user",
      content: q,
      createdAt: Date.now(),
    };
    setMessages((m) => [...m, userMsg]);
    setLoading(true);

    const aiId = uid();
    const aiMsg: Message = {
      id: aiId,
      role: "assistant",
      content: "",
      hits: [],
      createdAt: Date.now(),
    };
    setMessages((m) => [...m, aiMsg]);

    const controller = new AbortController();
    abortRef.current = controller;

    try {
      const res = await fetch("/api/query/stream", {
        method: "POST",
        signal: controller.signal,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          question: q,
          top_k: topK,
          refine: false,
          answer_mode: answerMode,
          min_score: minScore,
          session_id: sessionId,
          // simple multi-turn memory: last 6 messages as history
          history: messages.slice(-6).map((m) => ({
            role: m.role,
            content: m.content,
          })),
        }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      if (!res.body) throw new Error("浏览器不支持流式响应");

      let receivedToken = false;
      let currentHits: Hit[] = [];
      await readSse(res.body, {
        onSession: (sid) => {
          setSessionId(sid);
          localStorage.setItem(SESSION_KEY, sid);
        },
        onHits: (hits) => {
          currentHits = hits;
          setMessages((m) =>
            m.map((msg) =>
              msg.id === aiId
                ? {
                    ...msg,
                    hits,
                    content: hits.length
                      ? "正在基于知识库生成回答..."
                      : "没有检索到相关结果。",
                  }
                : msg
            )
          );
        },
        onToken: (token) => {
          receivedToken = true;
          setMessages((m) =>
            m.map((msg) =>
              msg.id === aiId
                ? {
                    ...msg,
                    content:
                      msg.content === "正在基于知识库生成回答..."
                        ? token
                        : msg.content + token,
                  }
                : msg
            )
          );
        },
        onError: (msg) => {
          const fallback = currentHits[0]?.text;
          setError(msg);
          setMessages((m) =>
            m.map((item) =>
              item.id === aiId
                ? {
                    ...item,
                    content: fallback ?? msg,
                    hits: currentHits,
                  }
                : item
            )
          );
        },
      });

      if (!receivedToken && currentHits.length > 0) {
        setMessages((m) =>
          m.map((msg) =>
            msg.id === aiId
              ? { ...msg, content: currentHits[0].text, hits: currentHits }
              : msg
          )
        );
      }
    } catch (e) {
      if (e instanceof DOMException && e.name === "AbortError") {
        setMessages((m) =>
          m.map((msg) =>
            msg.id === aiId &&
            (!msg.content || msg.content === "正在基于知识库生成回答...")
              ? { ...msg, content: "已停止生成。" }
              : msg
          )
        );
        return;
      }
      const msg = e instanceof Error ? e.message : String(e);
      setError(`请求失败: ${msg}`);
      setMessages((m) => m.filter((msg) => msg.id !== aiId));
    } finally {
      if (abortRef.current === controller) {
        abortRef.current = null;
      }
      setLoading(false);
    }
  }

  function stopGeneration() {
    abortRef.current?.abort();
  }

  async function clearHistory() {
    setMessages([]);
    localStorage.removeItem(HISTORY_KEY);
    sessionStorage.removeItem(SCROLL_KEY);
    followBottomRef.current = true;
    setShowScrollBottom(false);
    try {
      await fetch(`/api/sessions/${sessionId}`, { method: "DELETE" });
    } catch {
      /* keep local clear even if backend is offline */
    }
  }

  function isNearBottom(el: HTMLDivElement) {
    return el.scrollHeight - el.scrollTop - el.clientHeight < 32;
  }

  function updateScrollState(el: HTMLDivElement) {
    const atBottom = isNearBottom(el);
    followBottomRef.current = atBottom;
    setShowScrollBottom(!atBottom);
    sessionStorage.setItem(SCROLL_KEY, String(el.scrollTop));
  }

  function handleStreamScroll() {
    const el = streamRef.current;
    if (!el) return;
    updateScrollState(el);
  }

  function scrollToBottom(behavior: ScrollBehavior = "smooth") {
    const el = streamRef.current;
    if (!el) return;
    followBottomRef.current = true;
    el.scrollTo({ top: el.scrollHeight, behavior });
    setShowScrollBottom(false);
    sessionStorage.setItem(SCROLL_KEY, String(el.scrollHeight));
  }

  return (
    <div className="chat">
      <header className="chat__header">
        <div>
          <h1 className="chat__title">Chat</h1>
          <p className="chat__subtitle">本地 RAG · 离线问答 · Ollama</p>
        </div>
        {messages.length > 0 && (
          <button className="btn-pill" onClick={clearHistory}>
            清空会话
          </button>
        )}
      </header>

      <div className="chat__stream-wrap">
        <div className="chat__stream" ref={streamRef} onScroll={handleStreamScroll}>
          {messages.length === 0 && !loading && (
            <div className="chat__empty">
              <p className="chat__empty-title">问点什么开始</p>
              <p className="chat__empty-hint">
                例如:<i>Python 装饰器是什么?</i>
              </p>
            </div>
          )}

          {messages.map((m) => (
            <MessageBubble key={m.id} msg={m} />
          ))}

          {loading && (
            <div className="chat__loading">
              <span className="chat__dot" />
              <span className="chat__dot" />
              <span className="chat__dot" />
            </div>
          )}

          {error && <div className="chat__error">{error}</div>}
        </div>

        {showScrollBottom && (
          <button
            className="chat__scroll-bottom"
            onClick={() => scrollToBottom("smooth")}
            aria-label="滑到最底部"
            title="滑到最底部"
          >
            ↓ 到底部
          </button>
        )}
      </div>

      <footer className="chat__inputbar">
        <div className="chat__inputwrap">
          <input
            className="input chat__input"
            placeholder="问点什么…  ↵ 发送"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onCompositionStart={() => {
              composingRef.current = true;
            }}
            onCompositionEnd={(e) => {
              composingRef.current = false;
              lastCompositionEndRef.current = Date.now();
              setInput(e.currentTarget.value);
            }}
            onKeyDown={(e) => {
              const nativeEvent = e.nativeEvent as KeyboardEvent & {
                keyCode?: number;
              };
              const justEndedComposition =
                Date.now() - lastCompositionEndRef.current < 160;
              const isComposing =
                nativeEvent.isComposing ||
                composingRef.current ||
                nativeEvent.keyCode === 229 ||
                justEndedComposition;
              if (isComposing) return;
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                send();
              }
            }}
            disabled={loading}
          />
        </div>

        <div className="chat__controls">
          <label className="chat__field">
            <span className="chat__field-label">Top-K</span>
            <select
              className="chat__select"
              value={topK}
              onChange={(e) => setTopK(Number(e.target.value))}
            >
              {[1, 3, 5, 7, 10].map((k) => (
                <option key={k} value={k}>
                  {k}
                </option>
              ))}
            </select>
          </label>

          <label className="chat__field">
            <span className="chat__field-label">模式</span>
            <select
              className="chat__select chat__select--mode"
              value={answerMode}
              onChange={(e) => setAnswerMode(e.target.value)}
              title="控制 Ollama 是严格基于知识库，还是允许适度拓展"
            >
              <option value="expand">拓展</option>
              <option value="summary">总结</option>
              <option value="strict">严格</option>
              <option value="extract">原文</option>
            </select>
          </label>

          <label className="chat__field">
            <span className="chat__field-label">阈值</span>
            <select
              className="chat__select"
              value={minScore}
              onChange={(e) => setMinScore(Number(e.target.value))}
              title="低于该相似度的检索结果会被过滤"
            >
              {[0, 0.2, 0.4, 0.6, 0.8].map((score) => (
                <option key={score} value={score}>
                  {score.toFixed(1)}
                </option>
              ))}
            </select>
          </label>

          <button
            className={
              "btn-primary chat__send" + (loading ? " chat__send--stop" : "")
            }
            onClick={loading ? stopGeneration : send}
            disabled={!loading && !input.trim()}
            aria-label={loading ? "停止生成" : "发送"}
            title={loading ? "停止生成" : "发送"}
          >
            {loading ? (
              <span className="chat__stop-icon" aria-hidden="true" />
            ) : (
              "发送"
            )}
          </button>
        </div>
      </footer>
    </div>
  );
}

function MessageBubble({ msg }: { msg: Message }) {
  const [copied, setCopied] = useState(false);

  async function copyMessage() {
    if (!msg.content.trim()) return;
    try {
      await navigator.clipboard.writeText(msg.content);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1200);
    } catch {
      setCopied(false);
    }
  }

  if (msg.role === "user") {
    return (
      <div className="bubble bubble--user">
        <div className="bubble__body">{msg.content}</div>
        <button className="bubble__copy" onClick={copyMessage}>
          {copied ? "已复制" : "复制"}
        </button>
      </div>
    );
  }

  return (
    <div className="bubble bubble--assistant">
      <div className="bubble__body">
        {msg.hits && msg.hits.length > 0 && (
          <div className="best-hit">
            <span className="best-hit__label">最相关结果</span>
            <span className="best-hit__source">{msg.hits[0].source}</span>
            <span className="best-hit__score">{msg.hits[0].score.toFixed(4)}</span>
          </div>
        )}
        {msg.content ? renderMarkdownLite(msg.content) : <span className="muted">正在检索...</span>}
      </div>
      <button className="bubble__copy" onClick={copyMessage} disabled={!msg.content.trim()}>
        {copied ? "已复制" : "复制"}
      </button>
      {msg.hits && msg.hits.length > 1 && (
        <details className="hits">
          <summary className="hits__summary">
            ▸ 其他相关结果 ({msg.hits.length - 1} 段)
          </summary>
          <div className="hits__list">
            {msg.hits.slice(1).map((h, i) => (
              <HitRow key={i} index={i + 2} hit={h} />
            ))}
          </div>
        </details>
      )}
    </div>
  );
}

function HitRow({ index, hit }: { index: number; hit: Hit }) {
  const pct = Math.max(0, Math.min(1, hit.score)) * 100;
  return (
    <div className="hit">
      <div className="hit__meta">
        <span className="hit__rank">#{index}</span>
        <span className="hit__src">{hit.source}</span>
        <span className="hit__score">{hit.score.toFixed(4)}</span>
        {hit.retrieval_backend && (
          <span className="hit__src">{hit.retrieval_backend}</span>
        )}
      </div>
      <div className="hit__bar">
        <div className="hit__bar-fill" style={{ width: `${pct}%` }} />
      </div>
      <p className="hit__text">{hit.text}</p>
      {(hit.dense_score != null || hit.bm25_score != null) && (
        <div className="hit__meta">
          <span>dense {(hit.dense_score ?? 0).toFixed(4)}</span>
          <span>bm25 {(hit.bm25_score ?? 0).toFixed(4)}</span>
        </div>
      )}
    </div>
  );
}

async function readSse(
  body: ReadableStream<Uint8Array>,
  handlers: {
    onSession: (sessionId: string) => void;
    onHits: (hits: Hit[]) => void;
    onToken: (token: string) => void;
    onError: (msg: string) => void;
  }
) {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const parts = buffer.split("\n\n");
    buffer = parts.pop() ?? "";
    for (const part of parts) {
      const evt = parseSseEvent(part);
      if (!evt) continue;
      if (evt.event === "session") {
        handlers.onSession(evt.data.session_id);
      } else if (evt.event === "hits") {
        handlers.onHits(Array.isArray(evt.data) ? evt.data : []);
      } else if (evt.event === "token") {
        handlers.onToken(String(evt.data ?? ""));
      } else if (evt.event === "error") {
        handlers.onError(String(evt.data ?? "流式请求失败"));
      }
    }
  }
}

function parseSseEvent(raw: string): { event: string; data: any } | null {
  const eventLine = raw.split("\n").find((line) => line.startsWith("event: "));
  const dataLine = raw.split("\n").find((line) => line.startsWith("data: "));
  if (!eventLine || !dataLine) return null;
  try {
    return {
      event: eventLine.slice("event: ".length),
      data: JSON.parse(dataLine.slice("data: ".length)),
    };
  } catch {
    return null;
  }
}

/**
 * Tiny markdown renderer:
 * - paragraphs (split on blank lines)
 * - ### / ## headings
 * - ```code``` blocks
 * - **bold**
 * No HTML injection: we render via React nodes only.
 */
function renderMarkdownLite(md: string) {
  const blocks: React.ReactNode[] = [];
  const lines = md.split("\n");
  let i = 0;
  let key = 0;

  while (i < lines.length) {
    const line = lines[i];

    if (line.trim().startsWith("```")) {
      const buf: string[] = [];
      i++;
      while (i < lines.length && !lines[i].trim().startsWith("```")) {
        buf.push(lines[i]);
        i++;
      }
      i++;
      blocks.push(
        <pre key={key++} className="md-code">
          <code>{buf.join("\n")}</code>
        </pre>
      );
      continue;
    }

    if (line.startsWith("### ")) {
      blocks.push(
        <h3 key={key++} className="md-h3">
          {line.slice(4)}
        </h3>
      );
      i++;
      continue;
    }
    if (line.startsWith("## ")) {
      blocks.push(
        <h2 key={key++} className="md-h2">
          {line.slice(3)}
        </h2>
      );
      i++;
      continue;
    }

    if (line.trim() === "") {
      i++;
      continue;
    }

    // gather paragraph until blank line
    const para: string[] = [];
    while (
      i < lines.length &&
      lines[i].trim() !== "" &&
      !lines[i].startsWith("#") &&
      !lines[i].trim().startsWith("```")
    ) {
      para.push(lines[i]);
      i++;
    }
    blocks.push(
      <p key={key++} className="md-p">
        {renderInline(para.join(" "))}
      </p>
    );
  }
  return <>{blocks}</>;
}

function renderInline(s: string): React.ReactNode {
  // Split by **bold**
  const parts = s.split(/(\*\*[^*]+\*\*)/g);
  return parts.map((p, idx) => {
    if (p.startsWith("**") && p.endsWith("**")) {
      return <strong key={idx}>{p.slice(2, -2)}</strong>;
    }
    return <span key={idx}>{p}</span>;
  });
}
