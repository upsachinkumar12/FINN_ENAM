# FINN — Financial Investment Agent

**Live demo:** https://finn-enam-smoky.vercel.app (open on a phone; the API may take 30–60 s to wake on first visit)

A mobile-first investment agent for an investor holding 20 NSE companies. FINN reads the exchange feed, prices and primary documents so the investor doesn't have to, and shows only what matters, with the source one tap away.

- **Push:** a daily brief you can finish, ranked filing digest, configurable price/volume/filing alerts, results cards with QoQ/YoY, management-change bios from the filing itself.
- **Pull:** research on any NSE ticker from its annual report and earnings-call transcripts: financial snapshot, multi-year trajectory, balance sheet, cash quality, a **Promise Ledger** (what management guided vs what it delivered), and a cited bull/bear case.

## The point of view

Most investor tools add information. FINN removes it.

1. **A brief with an end.** Today shows the funnel ("12 filed → 8 worth a look → 2 must read"), the must-reads, and the unusual moves. You clear each one; when they're gone FINN says you're done. Routine filings are buried, but every buried item still says why.
2. **Narrative vs numbers is a ledger, not a summary.** Every explicit, quantitative promise from the last four earnings calls is stored with its verbatim quote and page, then scored Met / Exceeded / Missed / Not yet due / Can't verify by arithmetic on reported numbers. The model finds promises; it never decides whether one was kept.
3. **Every claim opens its source.** Numbers link to the statement they come from; model-written sentences carry citation markers that open the exact passage, page and PDF. A point without a source is deleted in code, not discouraged in a prompt.

## Run it locally

Requirements: Python 3.12, Node 20+.

```bash
# backend
cd backend
python -m venv .venv && .venv\Scripts\activate      # macOS/Linux: source .venv/bin/activate
pip install -r requirements-dev.txt
copy .env.example .env                               # add ANTHROPIC_API_KEY (optional, see below)
uvicorn app.main:app --reload --port 8000

# frontend (second terminal)
cd frontend
npm install
npm run dev                                          # http://localhost:5173
```

Press the refresh icon in the app header for the first data load (about 45 s: prices for 25 companies and 7 days of filings).

**On a phone:** `npm run dev` listens on your network. Open `http://<your-PC-IP>:5173` on a phone on the same Wi-Fi.

**Without an API key** FINN still runs: prices, alerts, rule-based filing triage, the deterministic research sections and the number/move/portfolio questions in Ask all work. AI readings, the Promise Ledger and the bull/bear case are switched off and labelled as such.

## Tests

```bash
cd backend && pytest -q
```

39 tests cover the things that would be embarrassing to get wrong: return and 20-session volume maths (the current day excluded from its own baseline), threshold boundaries, duplicate-alert prevention, holiday gaps, provisional-session handling, the dead `TATAMOTORS.NS` ticker, classification and priority rules, QoQ/YoY including loss-to-profit swings, unit conversion, figures that must appear verbatim on the filing page, fabricated-quote rejection, period alignment for guidance, removal of uncited bull/bear points, chat routing, and the seed snapshot round-trip.

## Deploy

See [docs/DEPLOY.md](docs/DEPLOY.md). Backend: Docker on Render (blueprint in `render.yaml`). Frontend: Vercel (`frontend/vercel.json`, set `VITE_API_URL`).

The public demo runs **without a model API key**, so it shows everything except the AI readings, the Promise Ledger and the cited bull/bear case, which are labelled as switched off. Set `ANTHROPIC_API_KEY` on the API service to turn them on; no code change is needed.

## Docs

- [Architecture, API and model routing](docs/ARCHITECTURE.md)
- [Data sources and their limits](docs/DATA_SOURCES.md)
- [Deployment](docs/DEPLOY.md)

## What is deliberately left out

- **Real device push notifications.** The data is end-of-day; an in-app brief is honest about that, a 3 a.m. phone buzz is not.
- **Intraday prices.** EOD only, labelled everywhere.
- **LinkedIn scraping.** Bios come from the appointment filing itself (SEBI requires a profile for appointed directors); FINN links a LinkedIn search instead of scraping it.
- **NSE as a live source.** Its API refuses non-browser clients; BSE carries the same filings.
- **News, broker notes or the model's own knowledge on the Pull side.** Primary documents only, as the brief asks.
- **Buy/sell calls, user accounts, multiple portfolios.**
