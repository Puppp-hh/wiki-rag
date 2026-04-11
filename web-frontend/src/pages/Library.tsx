import { useEffect, useState, useCallback } from "react";
import "../styles/Library.css";

type FileItem = {
  name: string;
  kind: "md" | "image" | "other";
  chunks: number | null;
  indexed: boolean;
  updatedAt: string;
};

export function LibraryPage() {
  const [files, setFiles] = useState<FileItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState("");

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch("/api/library");
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setFiles(Array.isArray(data) ? data : []);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  async function rebuild() {
    setBusy(true);
    setError(null);
    try {
      const res = await fetch("/api/library/rebuild", { method: "POST" });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  const filtered = files.filter((f) =>
    f.name.toLowerCase().includes(query.toLowerCase())
  );
  const indexed = files.filter((f) => f.indexed).length;

  return (
    <div className="page library">
      <header className="library__header">
        <div>
          <h1 className="section-title">Library</h1>
          <p className="section-stats">
            全部 {files.length} · 已索引 {indexed} · 未索引{" "}
            {files.length - indexed}
          </p>
        </div>
        <button
          className="btn-primary"
          onClick={rebuild}
          disabled={busy || loading}
        >
          {busy ? "Rebuilding…" : "Rebuild Index"}
        </button>
      </header>

      <div className="library__toolbar">
        <input
          className="input library__search"
          placeholder="搜索文件名…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
      </div>

      {error && <div className="library__error">{error}</div>}

      <div className="library__list-wrap">
        <ul className="library__list">
          <li className="library__row library__row--head">
            <span />
            <span>文件名</span>
            <span>段数</span>
            <span>状态</span>
            <span>更新时间</span>
          </li>
          {loading && filtered.length === 0 && (
            <li className="library__row library__row--empty">加载中…</li>
          )}
          {!loading && filtered.length === 0 && (
            <li className="library__row library__row--empty">没有文件</li>
          )}
          {filtered.map((f) => (
            <li className="library__row" key={f.name}>
              <span className="library__icon">
                {f.kind === "md" ? "📄" : f.kind === "image" ? "🖼" : "📦"}
              </span>
              <span className="library__name">{f.name}</span>
              <span className="library__chunks">
                {f.chunks != null ? `${f.chunks} 段` : "—"}
              </span>
              <span
                className={
                  "library__status " +
                  (f.indexed
                    ? "library__status--ok"
                    : "library__status--off")
                }
              >
                {f.indexed ? "已索引" : "未索引"}
              </span>
              <span className="library__time">{f.updatedAt}</span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
