# Deploying FINN

Two pieces: the API (Docker) and the web app (static). Each step that creates an account or pushes code is yours to run.

## 1. Build a seed snapshot (local)

Free hosts lose files when they restart, and BSE or Yahoo may refuse cloud IP addresses. A snapshot lets the deployed app show real, dated data immediately:

```bash
cd backend
python scripts/build_snapshot.py --days 30 --research MTARTECH HAL SUZLON
```

This writes `backend/seed/snapshot.json.gz` (prices, triaged filings with FINN's readings, alerts, research sections, the ledger). It contains no PDFs or document text. Commit it with the code.

## 2. API on Render

1. Push the repository to GitHub.
2. Render dashboard → **New → Blueprint** → pick the repo. It reads `render.yaml`.
3. Set `ANTHROPIC_API_KEY` and `CORS_ORIGINS` (your Vercel URL) in the service's environment.
4. Wait for `/api/health` to return `{"ok": true}`.

Free Render instances sleep after inactivity; the first request after a sleep takes 30–60 s, and the app shows a "waking up" retry state. Their disk is wiped on restart, so the app re-boots from the seed snapshot each time.

**Memory.** Indexing a 300–400 page annual report with the local embedding model needs about 1 GB RAM and crashed the free 512 MB instance in testing. `render.yaml` therefore sets `VECTOR_SEARCH=false` (keyword retrieval only); with that setting a 414-page annual report indexes without trouble. On a host with ≥1 GB RAM, remove it to get hybrid retrieval back.

**What was verified on Render (3 Nov 2026):** Yahoo prices refresh; BSE's API refuses the host (403) and the filing feed falls back to the screener.in index automatically; screener.in statements and BSE-hosted PDFs download; research indexing completes.

## 3. Web app on Vercel

1. Vercel → **Add New Project** → the repo → root directory `frontend`.
2. Environment variable `VITE_API_URL` = your Render URL (e.g. `https://finn-api.onrender.com`).
3. Deploy. `vercel.json` handles client-side routes.

## Environment variables

| Variable | Where | Purpose |
|---|---|---|
| `ANTHROPIC_API_KEY` | API | Enables AI reading, ledger, bull/bear, document Q&A |
| `MODEL_CHEAP` / `MODEL_STRONG` | API | Model routing (defaults: `claude-haiku-5-5`, `claude-sonnet-5-5`) |
| `CORS_ORIGINS` | API | Comma-separated allowed web origins |
| `AUTO_REFRESH_MINUTES` | API | Periodic refresh on hosts that stay awake; `0` = on demand |
| `DATA_DIR` | API | SQLite, PDF cache and vector index location (`/data` in Docker) |
| `VECTOR_SEARCH` | API | `false` on hosts under ~1 GB RAM: keyword retrieval only |
| `VITE_API_URL` | Web | API base URL |
