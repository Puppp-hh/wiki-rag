import { useState } from "react";
import "../styles/Debug.css";

type Hit = { source: string; text: string; score: number };
type DebugResp = {
  hits: Hit[];
  embedding: {
    dim: number;
    cached: boolean;
    preview: number[];
    model: string;
  };
  topK: number;
};

export function DebugPage() {
  const [question, setQuestion] = useState("");
  const [topK, setTopK] = useState(5);
  const [data, setData] = useState<DebugResp | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function run() {
    if (!question.trim() || loading) return;
    setLoading(true);
    setError(null);
    try {
      const res = await fetch("/api/debug", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question, top_k: topK }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const json = await res.json();
      setData(json);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="page debug">
      <header className="debug__header">
        <h1 className="section-title">Debug</h1>
        <p className="section-stats">
          看一下 RAG 黑盒里发生了什么:embedding、相似度、top-k。
        </p>
      </header>

      <div className="debug__bar">
        <input
          className="input debug__input"
          placeholder="输入问题,看检索发生了什么…"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && run()}
        />
        <select
          className="debug__select"
          value={topK}
          onChange={(e) => setTopK(Number(e.target.value))}
        >
          {[1, 3, 5, 7, 10].map((k) => (
            <option key={k} value={k}>
              Top-K {k}
            </option>
          ))}
        </select>
        <button
          className="btn-primary"
          onClick={run}
          disabled={loading || !question.trim()}
        >
          {loading ? "Running…" : "Run"}
        </button>
      </div>

      {error && <div className="debug__error">{error}</div>}

      {data && (
        <>
          <h3 className="debug__section">Embedding</h3>
          <div className="debug__kv">
            <span>模型</span>
            <code>{data.embedding.model}</code>
            <span>向量维度</span>
            <b className="debug__num">{data.embedding.dim}</b>
            <span>缓存命中</span>
            <b>{data.embedding.cached ? "是" : "否"}</b>
            <span>Top-K</span>
            <b className="debug__num">{data.topK}</b>
            <span>查询向量预览</span>
            <code className="debug__vec">
              [
              {data.embedding.preview
                .map((n) => n.toFixed(3))
                .join(", ")}
              , …]
            </code>
          </div>

          <h3 className="debug__section">检索结果</h3>
          <div className="debug__hits">
            {data.hits.map((h, i) => {
              const pct = Math.max(0, Math.min(1, h.score)) * 100;
              return (
                <div className="debug__hit" key={i}>
                  <div className="debug__hit-meta">
                    <span className="debug__rank">#{i + 1}</span>
                    <span className="debug__cosine">
                      cosine {h.score.toFixed(4)}
                    </span>
                    <span className="debug__src">{h.source}</span>
                  </div>
                  <div className="debug__bar-bg">
                    <div
                      className="debug__bar-fill"
                      style={{ width: `${pct}%` }}
                    />
                  </div>
                  <p className="debug__text">{h.text}</p>
                </div>
              );
            })}
          </div>
        </>
      )}
    </div>
  );
}
