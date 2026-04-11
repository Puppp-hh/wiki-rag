import { useEffect, useRef, useState } from "react";
import "../styles/Chat.css";

type Hit = {
  source: string;
  text: string;
  score: number;
};

type Message = {
  id: string;
  role: "user" | "assistant";
  content: string;
  hits?: Hit[];
  createdAt: number;
};

const HISTORY_KEY = "wiki-rag.history";

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
  const [input, setInput] = useState("");
  const [topK, setTopK] = useState(3);
  const [refine, setRefine] = useState(true);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const streamRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    saveHistory(messages);
    streamRef.current?.scrollTo({
      top: streamRef.current.scrollHeight,
      behavior: "smooth",
    });
  }, [messages]);

  async function send() {
    const q = input.trim();
    if (!q || loading) return;
    setError(null);
    setInput("");

    const userMsg: Message = {
      id: uid(),
      role: "user",
      content: q,
      createdAt: Date.now(),
    };
    setMessages((m) => [...m, userMsg]);
    setLoading(true);

    try {
      const res = await fetch("/api/query", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          question: q,
          top_k: topK,
          refine,
          // simple multi-turn memory: last 6 messages as history
          history: messages.slice(-6).map((m) => ({
            role: m.role,
            content: m.content,
          })),
        }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      const aiMsg: Message = {
        id: uid(),
        role: "assistant",
        content: data.answer ?? "(空回答)",
        hits: data.hits ?? [],
        createdAt: Date.now(),
      };
      setMessages((m) => [...m, aiMsg]);
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      setError(`请求失败: ${msg}`);
    } finally {
      setLoading(false);
    }
  }

  function clearHistory() {
    setMessages([]);
    localStorage.removeItem(HISTORY_KEY);
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

      <div className="chat__stream" ref={streamRef}>
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

      <footer className="chat__inputbar">
        <div className="chat__inputwrap">
          <input
            className="input chat__input"
            placeholder="问点什么…  ↵ 发送"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
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

          <label className="chat__refine">
            <input
              type="checkbox"
              checked={refine}
              onChange={(e) => setRefine(e.target.checked)}
            />
            <span>Refine</span>
          </label>

          <button
            className="btn-primary chat__send"
            onClick={send}
            disabled={loading || !input.trim()}
          >
            发送
          </button>
        </div>
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
      <div className="bubble__body">{renderMarkdownLite(msg.content)}</div>
      {msg.hits && msg.hits.length > 0 && (
        <details className="hits">
          <summary className="hits__summary">
            ▸ 检索结果 ({msg.hits.length} 段)
          </summary>
          <div className="hits__list">
            {msg.hits.map((h, i) => (
              <HitRow key={i} index={i + 1} hit={h} />
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
      </div>
      <div className="hit__bar">
        <div className="hit__bar-fill" style={{ width: `${pct}%` }} />
      </div>
      <p className="hit__text">{hit.text}</p>
    </div>
  );
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
