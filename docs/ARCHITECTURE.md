# Architecture

```
React PWA (Vite, Tailwind, Recharts)  ──HTTPS──▶  FastAPI
                                                   ├── SQLite: companies, prices, filings, alerts, research, ledger, LLM cache + cost log
                                                   ├── SQLite FTS5 + Chroma (local ONNX embeddings): hybrid retrieval over primary documents
                                                   ├── Anthropic API: Haiku 5.5 (bulk reading), Sonnet 5.5 (multi-document reasoning)
                                                   └── Adapters: Yahoo Finance (EOD) · BSE announcements · screener.in (statements + document index) · PDF upload/URL import
```

## Backend layout

| Module | Job |
|---|---|
| `market_data/` | Yahoo chart endpoint → daily bars; deterministic return and 20-session volume metrics |
| `alerts/engine.py` | User thresholds, per-company monitoring, per-rule switches; `UNIQUE(symbol, trade_date, rule)` prevents duplicates |
| `announcements/bse.py` | Per-company BSE announcement feed (paginated) |
| `announcements/classify.py` | Rules over BSE category/subcategory/headline → reference category, priority, confidence, "needs reading" |
| `announcements/enrich.py` | Reads only filings whose content decides their importance; 4-part summary; people from the filing |
| `announcements/results.py` | Results table transcription → Python QoQ/YoY/derived EBITDA; figure verification; screener.in cross-check |
| `document_ingestion/` | Cached download, page-level extraction, OCR-layer detection, page-bounded chunks, SHA-256 dedup |
| `rag/store.py` | FTS5 (exact terms, figures) + Chroma (meaning), reciprocal-rank fusion; keyword-only fallback |
| `research/financials.py` | Snapshot, trajectory, balance sheet, cash quality from reported statements. No model |
| `research/ledger.py` | Promise extraction → quote verification → period alignment → arithmetic scoring |
| `research/synthesis.py` | Business snapshot (Haiku) and bull/bear + ledger conclusion (Sonnet), both through the Citations API |
| `research/chat.py` | Ask routing: portfolio → DB, "why did it move" → prices + filings, comparisons → tables, everything else → cited retrieval |
| `llm/client.py` | The only module that calls the model: tiers, response cache, cost log, refusal handling |

## Model routing and cost

| Step | Handled by | Why |
|---|---|---|
| Prices, returns, volume multiples, alert firing | Python | Arithmetic should never be probabilistic |
| Classifying filings | Rules first (62% of 751 real filings settled without a model) | BSE metadata already says what most filings are |
| Reading ambiguous filings, 4-part summaries, people | Haiku 5.5, structured JSON output, effort `low` | Bulk, cheap, schema-guaranteed |
| Results numbers | Haiku transcribes; Python computes | The model copies; it doesn't do maths |
| Scanned filings (OCR'd text layer) | Haiku reads the single page as a PDF image | Avoids trusting garbled OCR numbers |
| Guidance extraction | Haiku over keyword-filtered pages only | ~12 of 20+ pages per transcript |
| Bull/bear, ledger conclusion, document Q&A | Sonnet 5.5 with the Citations API | Multi-document reasoning; citations are machine-checkable |
| Embeddings | Chroma's local ONNX model | No API cost, no key |

Every call is cached by a hash of its full input (`llm_cache`) and logged with real token usage and cost (`llm_calls`, exposed at `GET /api/costs`). System prompts carry a cache breakpoint for prompt caching. The strong tier sends the server-side refusal fallback so a declined request is retried on another model inside the same call.

## Anti-fabrication guards (code, not prompts)

- **Pages can't be invented.** Retrieved passages go to the model as blocks of custom-content documents; a citation comes back as (document index, block index), which FINN maps to its own stored page and URL.
- **Figures must be on the page.** A transcribed results figure that isn't a whole token on the source page is dropped, not shown.
- **Quotes must be on the page.** Ledger quotes are matched against the transcript page (or its neighbours across a page break); unmatched promises are discarded.
- **Scores are arithmetic.** Met/Missed is computed from reported figures for the stated period; unverifiable metrics say so.
- **Uncited points are removed.** Bull/bear points without a citation are deleted and the count is shown.
- **Filing text is data.** Every prompt marks documents as untrusted and the output is schema-constrained.

## API

| Method & path | Purpose |
|---|---|
| `GET /api/health` | Liveness, whether AI is configured, snapshot info |
| `GET /api/portfolio` · `POST /api/portfolio` · `DELETE /api/portfolio/{symbol}` | Portfolio with latest EOD stats; add (validated) / remove |
| `GET /api/companies/search?q=` | Local + any listed company |
| `GET /api/market-data/{symbol}` | Daily bars and latest stats |
| `POST /api/market-data/refresh` · `GET /api/refresh/status` | Background refresh: prices → alerts → filings → reading |
| `GET /api/intelligence/digest?hours=&symbols=&categories=&priorities=` | Windowed, ranked, de-duplicated digest |
| `GET /api/announcements` · `GET /api/announcements/{id}` | Filings with triage, summaries, cards |
| `GET /api/alerts` · `GET/POST /api/alerts/settings` · `POST /api/alerts/{id}/ack` | Alert history and rules (saving re-scans) |
| `GET /api/company/{symbol}` | Research sections, documents, latest job (any valid NSE ticker) |
| `POST /api/research/{symbol}/generate` · `GET /api/research/jobs/{id}` | Background document reading + ledger + synthesis |
| `POST /api/research/chat` | Ask FINN |
| `POST /api/documents/upload` · `POST /api/documents/import` · `GET /api/documents/{symbol}` | Manual primary-source fallback |
| `GET /api/costs` | Model spend by purpose, cache hits, filings settled by rules |

## Storage

SQLite with plain SQL behind small repository functions; only the FTS5 index is SQLite-specific. Moving to Postgres means swapping `database/db.py` and replacing FTS5 with `tsvector`.
