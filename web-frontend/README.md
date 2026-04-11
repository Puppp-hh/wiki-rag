# Wiki-RAG Frontend

Apple-style React + TypeScript UI for the local wiki-rag project.
Strictly follows `design/DESIGN.md`.

## Run

```bash
# 1. install
cd web-frontend
npm install

# 2. dev server
npm run dev          # http://localhost:5173

# 3. backend (in another shell, from project root)
pip install fastapi uvicorn
uvicorn web.api:app --reload --port 8000
```

`vite.config.ts` already proxies `/api/*` to `http://localhost:8000`.

## Pages

| Route | What |
|------|------|
| `/`         | Chat (RAG 问答 + 可折叠检索结果) |
| `/library`  | 文件管理 + Rebuild Index |
| `/debug`    | 检索调试面板 |
| `/settings` | Light / Dark 主题切换 |

## Theming

Uses CSS Variables only. Toggle in Settings or via the moon/sun
button in the top nav. Persists to `localStorage`. Falls back to
`prefers-color-scheme` when unset.
