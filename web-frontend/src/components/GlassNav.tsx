import { NavLink } from "react-router-dom";
import { useTheme } from "../hooks/useTheme";
import "../styles/GlassNav.css";

export function GlassNav() {
  const { theme, toggle } = useTheme();

  return (
    <nav className="glass-nav">
      <div className="glass-nav__inner">
        <div className="glass-nav__brand">
          <span className="glass-nav__logo">⌘</span>
          <span className="glass-nav__brand-name">Wiki-RAG</span>
        </div>

        <ul className="glass-nav__tabs">
          <li>
            <NavLink to="/" end className={({ isActive }) =>
              "glass-nav__link" + (isActive ? " is-active" : "")
            }>
              Chat
            </NavLink>
          </li>
          <li>
            <NavLink to="/library" className={({ isActive }) =>
              "glass-nav__link" + (isActive ? " is-active" : "")
            }>
              Library
            </NavLink>
          </li>
          <li>
            <NavLink to="/debug" className={({ isActive }) =>
              "glass-nav__link" + (isActive ? " is-active" : "")
            }>
              Debug
            </NavLink>
          </li>
          <li>
            <NavLink to="/settings" className={({ isActive }) =>
              "glass-nav__link" + (isActive ? " is-active" : "")
            }>
              Settings
            </NavLink>
          </li>
        </ul>

        <button
          className="glass-nav__theme"
          onClick={toggle}
          aria-label="切换主题"
          title={theme === "light" ? "切到深色" : "切到浅色"}
        >
          {theme === "light" ? "🌙" : "☀"}
        </button>
      </div>
    </nav>
  );
}
