To: assessment@enam.com
Subject: ENAM - IIT screening - 2027

Dear ENAM team,

Please find my submission for the FINN build challenge.

- Prototype (open on a phone): https://finn-enam-smoky.vercel.app
  The API runs on a free host that sleeps, so the first load can take 30–60 seconds.
- Repository: https://github.com/upsachinkumar12/FINN_ENAM
- AI build history: [BUILD_HISTORY_LINK_OR_ATTACHMENT]

**What I built**

FINN is a mobile web app for an investor holding 20 NSE companies: your suggested large caps, plus Suzlon and MTAR Technologies for size diversity. Its point of view is that the product should remove information, not add it.

- **Today** is a brief with an end: "13 filings → 8 worth a look → 2 must read". You clear each item and FINN tells you when you're done. Routine filings are buried, but each one still says why it was buried. Unusual price or volume moves sit next to the filings made around them, with an explicit note that exchange data can't establish cause.
- **Alerts** let the investor define "unusual": price up and down, volume against the previous 20 sessions, and which filing types matter. Saving re-checks history immediately, and duplicates are impossible by construction.
- **Research** works on any NSE ticker. It covers snapshot (QoQ/YoY), multi-year trajectory, balance sheet and cash quality from reported statements, and indexes the company's annual report and last four call transcripts.
- **Promise Ledger** is my answer to "narrative vs numbers". Every explicit quantitative promise from the last four calls is stored with its verbatim quote and page, then scored Met, Exceeded, Missed, Not yet due or Can't verify by arithmetic on reported figures; the model finds promises but never judges them. A cited bull/bear case and document Q&A are built on the same retrieval.
- **Ask** answers portfolio, "why did it move" and comparison questions from data, with no model call. It supports voice input and a spoken brief.

**Please note:** the public demo runs without a model API key. Everything above works except the AI layer: filing summaries, results cards, management bios, the Promise Ledger, the bull/bear case and document Q&A. The app labels these as switched off. The code for them is in the repository and covered by unit tests (quote verification, figure verification, period alignment, uncited-point removal), but I haven't run them against a live model in this deployment. Setting one environment variable switches them on.

**Key decisions**

1. **Rules before models.** BSE's own metadata classifies 62% of filings at no cost (tested on 751 real filings). The model would read only filings whose content decides their importance: Haiku 5.5 for bulk reading, Sonnet 5.5 only for multi-document reasoning. Prices, alerts, QoQ/YoY and ledger scoring are plain Python. Model calls are cached by input and logged with their real cost.
2. **Grounding enforced in code.** Citations map to FINN's own stored pages, so page numbers can't be invented. Results figures must appear verbatim on the filing page. Ledger quotes must match the transcript. Uncited bull/bear points are deleted. Scanned filings (ICICI Bank's results are an OCR layer) are read visually instead of trusting garbled text.
3. **Honest data handling, tested in production.** NSE's API refuses non-browser clients, so filings come from BSE. TATAMOTORS.NS is dead after the demerger, so TMPV stands in. BSE's API refuses the cloud host, so the deployed app falls back to the same BSE filings listed on screener.in and says so in the Feed. A seed snapshot keeps every original timestamp, so old data never looks new. Everything is end-of-day and labelled that way.

**What I left out on purpose**

Device push notifications (the data is end of day), intraday prices, LinkedIn scraping (bios come from the appointment filing, with a LinkedIn search link), news or broker views on the Pull side, and buy/sell recommendations.

**Where I'd take it next**

Run the AI layer live and build an evaluation set of hand-checked results cards and ledger rows to tune extraction against. Score management's promises across years into a credibility index per company. Push results cards within minutes of filing, using a BSE poller on an always-on host in India.

Thank you for the interesting problem.

[YOUR NAME]
[PHONE] · [LINKEDIN]
