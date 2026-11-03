To: assessment@enam.com
Subject: ENAM - IIT screening - 2027

Dear ENAM team,

Please find my submission for the FINN build challenge.

- Prototype (open on a phone): [DEPLOYED_URL]
- Repository: [GITHUB_URL]
- AI build history: [BUILD_HISTORY_LINK_OR_ATTACHMENT]

**What I built**

FINN is a mobile web app for an investor holding 20 NSE companies (your suggested large caps plus a mid cap and a small cap for size diversity). Its point of view is that the product should remove information, not add it.

- **Today** is a brief with an end: "12 filings → 8 worth a look → 2 must read". You clear each item and FINN tells you when you're done. Routine filings are buried, but each one still says why. Unusual price or volume moves appear next to the filings made around them, with an explicit note that exchange data can't establish cause.
- **Alerts** let the investor define "unusual": price up and down, volume against the previous 20 sessions, and which filing types matter. Saving re-checks history immediately, and duplicates are impossible by construction.
- **Research** works on any NSE ticker. It covers snapshot (QoQ/YoY), multi-year trajectory, balance sheet and cash quality from reported statements, plus a cited bull/bear case built only from the annual report and call transcripts.
- **Promise Ledger** is my answer to "narrative vs numbers". Every explicit quantitative promise from the last four calls is stored with its verbatim quote and page, then scored Met, Exceeded, Missed, Not yet due or Can't verify against reported figures. Results filings in the Push feed are checked against the promises due that quarter.
- **Ask** answers portfolio, "why did it move" and comparison questions from data without any model call, and document questions with citations to the page. It supports voice input and a spoken 60-second brief.

**Key decisions**

1. **Rules before models.** BSE's own metadata classifies 62% of filings for free (tested on 751 real filings). Haiku 5.5 reads only the filings whose content decides their importance. Sonnet 5.5 is used only for multi-document reasoning. Prices, alerts, QoQ/YoY and ledger scoring are plain Python. Every model call is cached and costed: [COST_FIGURE from GET /api/costs].
2. **Grounding enforced in code.** Citations map to FINN's own stored pages, so page numbers can't be invented. Results figures must appear verbatim on the filing page. Ledger quotes must match the transcript. Uncited bull/bear points are deleted. Scanned filings (ICICI Bank's results are an OCR layer) are read visually instead of trusting garbled text.
3. **Honest data handling.** NSE's API refuses non-browser clients, so filings come from BSE. TATAMOTORS.NS is dead after the demerger, so TMPV stands in. Everything is end-of-day and labelled that way. A seed snapshot keeps the deployed demo working, with original timestamps, if a source blocks the host.

**What I left out on purpose**

Device push notifications (the data is end of day), intraday prices, LinkedIn scraping (bios come from the appointment filing, with a LinkedIn search link), news or broker views on the Pull side, and buy/sell recommendations.

**Where I'd take it next**

Score management's promises across years to build a credibility index per company. Measure segment-level guidance against segment results. Push results cards within minutes of filing, using a BSE poller on an always-on host. Add an evaluation set of hand-checked results cards and ledger rows to tune extraction prompts against.

Thank you for the interesting problem.

[YOUR NAME]
[PHONE] · [LINKEDIN]
