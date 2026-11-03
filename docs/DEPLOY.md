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

Free Render instances sleep after inactivity; the first request after a sleep takes 30–60 s, and the app shows a "waking up" retry state. If Chroma plus the embedding model exceed the free memory limit, use any Docker host with ≥1 GB RAM (the same image runs unchanged, for example on Hugging Face Spaces or Fly.io).

**Check after deploying:** press refresh in the app. If BSE or Yahoo refuse the host's IP, the header and Feed say so, and the snapshot data stays visible with its original dates.

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
| `VITE_API_URL` | Web | API base URL |
