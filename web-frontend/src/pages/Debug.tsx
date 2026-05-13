import { useRef, useState } from "react";
import "../styles/Debug.css";

type Hit = {
  source: string;
  text: string;
  score: number;
  dense_score?: number;
  bm25_score?: number;
  retrieval_backend?: string;
  rerank?: {
    base_score?: number;
    final_score?: number;
    dense_norm?: number;
    bm25_norm?: number;
    keyword_boost?: number;
    coverage?: number;
    length_score?: number;
    matched_terms?: number;
    reasons?: string[];
  };
};
type DebugResp = {
  hits: Hit[];
  embedding: {
    dim: number;
    cached: boolean;
    preview: number[];
    model: string;
  };
  topK: number;
  minScore: number;
  query?: string;
  expandedQuery?: string;
  queryTerms?: string[];
  retrievalMode?: string;
  denseBackend?: string;
};

export function DebugPage() {
  const [question, setQuestion] = useState("");
  const [topK, setTopK] = useState(5);
  const [minScore, setMinScore] = useState(0);
  const [data, setData] = useState<DebugResp | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const composingRef = useRef(false);
  const lastCompositionEndRef = useRef(0);

  async function run() {
    if (!question.trim() || loading) return;
    setLoading(true);
    setError(null);
    try {
      const res = await fetch("/api/debug", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question, top_k: topK, min_score: minScore }),
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
          onCompositionStart={() => {
            composingRef.current = true;
          }}
          onCompositionEnd={(e) => {
            composingRef.current = false;
            lastCompositionEndRef.current = Date.now();
            setQuestion(e.currentTarget.value);
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
            if (e.key === "Enter") {
              e.preventDefault();
              run();
            }
          }}
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
        <select
          className="debug__select"
          value={minScore}
          onChange={(e) => setMinScore(Number(e.target.value))}
          title="低于该相似度的结果会被过滤"
        >
          {[0, 0.2, 0.4, 0.6, 0.8].map((score) => (
            <option key={score} value={score}>
              阈值 {score.toFixed(1)}
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
            <span>相似度阈值</span>
            <b className="debug__num">{data.minScore.toFixed(1)}</b>
            <span>检索模式</span>
            <b>{data.retrievalMode ?? "hybrid"}</b>
            <span>Dense 后端</span>
            <b>{data.denseBackend ?? "numpy"}</b>
            <span>查询改写</span>
            <code className="debug__vec">{data.expandedQuery ?? data.query}</code>
            <span>关键词</span>
            <code className="debug__vec">
              {(data.queryTerms ?? []).length
                ? (data.queryTerms ?? []).join(", ")
                : "无"}
            </code>
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
                      final {h.score.toFixed(4)}
                    </span>
                    <span className="debug__src">{h.source}</span>
                  </div>
                  <div className="debug__score-grid">
                    <ScorePill label="dense" value={h.rerank?.dense_norm} />
                    <ScorePill label="bm25" value={h.rerank?.bm25_norm} />
                    <ScorePill label="base" value={h.rerank?.base_score} />
                    <ScorePill label="keyword" value={h.rerank?.keyword_boost} />
                    <ScorePill label="coverage" value={h.rerank?.coverage} />
                  </div>
                  {h.rerank?.reasons && h.rerank.reasons.length > 0 && (
                    <div className="debug__reasons">
                      {h.rerank.reasons.map((reason) => (
                        <span key={reason}>{reason}</span>
                      ))}
                    </div>
                  )}
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

function ScorePill({ label, value }: { label: string; value?: number }) {
  return (
    <span className="debug__score-pill">
      {label} <b>{(value ?? 0).toFixed(3)}</b>
    </span>
  );
}
