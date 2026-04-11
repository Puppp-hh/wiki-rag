import { useTheme } from "../hooks/useTheme";
import "../styles/Settings.css";

export function SettingsPage() {
  const { theme, setTheme } = useTheme();

  return (
    <div className="page settings">
      <header className="settings__header">
        <h1 className="section-title">Settings</h1>
        <p className="section-stats">个性化你的 wiki-rag 体验。</p>
      </header>

      <section className="settings__section">
        <h3 className="settings__section-title">外观</h3>
        <div className="settings__row">
          <div className="settings__row-text">
            <div className="settings__row-title">主题</div>
            <div className="settings__row-desc">
              选择浅色或深色界面。默认跟随系统。
            </div>
          </div>
          <div className="settings__seg">
            <button
              className={
                "settings__seg-btn" +
                (theme === "light" ? " is-active" : "")
              }
              onClick={() => setTheme("light")}
            >
              ☀ Light
            </button>
            <button
              className={
                "settings__seg-btn" +
                (theme === "dark" ? " is-active" : "")
              }
              onClick={() => setTheme("dark")}
            >
              🌙 Dark
            </button>
          </div>
        </div>
      </section>

      <section className="settings__section">
        <h3 className="settings__section-title">模型</h3>
        <div className="settings__row">
          <div className="settings__row-text">
            <div className="settings__row-title">LLM</div>
            <div className="settings__row-desc">
              本地 Ollama,默认 deepseek-r1:1.5b。
            </div>
          </div>
          <code className="settings__code">deepseek-r1:1.5b</code>
        </div>
        <div className="settings__divider" />
        <div className="settings__row">
          <div className="settings__row-text">
            <div className="settings__row-title">Embedding</div>
            <div className="settings__row-desc">
              用于把文本转成 768 维向量。
            </div>
          </div>
          <code className="settings__code">nomic-embed-text</code>
        </div>
      </section>

      <section className="settings__section">
        <h3 className="settings__section-title">关于</h3>
        <p className="settings__about">
          Wiki-RAG · 本地优先的个人知识库 · 100% 离线 · 无 API 费用。
        </p>
      </section>
    </div>
  );
}
