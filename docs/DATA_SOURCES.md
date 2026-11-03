# Data sources

All checked from a residential connection in India on 3 November 2026.

| Need | Source | Status | Notes |
|---|---|---|---|
| EOD price & volume | Yahoo Finance chart endpoint (`query1.finance.yahoo.com/v8/finance/chart/{SYMBOL}.NS`) | Works | Same data `yfinance` wraps, called directly to avoid a dependency. `close` is split-adjusted, not dividend-adjusted, so bonus/split dates don't fire false alerts. Today's bar is ignored until 16:00 IST. |
| Corporate announcements | BSE `AnnSubCategoryGetData` API | Works per company | Rejects requests without an `Accept-Language` header. The all-company query returns nothing, so FINN queries each company. |
| Corporate announcements | NSE `corporate-announcements` API | **403** | Refuses non-browser clients even with a cookie session. Not used; BSE carries the same filings. |
| Filing PDFs | `bseindia.com/stockinfo/AnnPdfOpen.aspx` | Works | Some results filings are scans with an OCR text layer (e.g. ICICI Bank). FINN detects this and reads the page visually. |
| BSE code for any NSE ticker | screener.in company page | Works | Lets research generalise to tickers FINN has never seen. |
| Reported financials | screener.in (quarterly, annual P&L, balance sheet, cash flow, ratios) | Works | Standardised from company filings. Consolidated preferred, standalone fallback, always labelled. Banks have no EBITDA; NPA ratios are published standalone only. |
| Annual reports, concall transcripts | Links on screener.in (hosted on BSE or the company's site) | Works | Primary documents. |
| Manual fallback | PDF upload or https link | Works | For companies or documents the automatic path misses. |

## Primary-source discipline (Pull side)

Used: the company's filings, annual reports, earnings-call transcripts, and reported statements.

Deliberately not used, although available on the same pages: screener.in's AI summaries of concalls and annual reports, its company "about" text, credit-agency pages, and any news. `robots.txt` disallows `/company/source/quarter/*`, so FINN never fetches it; results PDFs come from BSE instead.

## Demo universe

Portfolio (20): TCS, INFY, WIPRO, HDFCBANK, ICICIBANK, SBIN, RELIANCE, ONGC, NTPC, TMPV, MARUTI, ITC, HINDUNILVR, SUNPHARMA, CIPLA, LT, BHARTIARTL, TITAN, plus SUZLON (mid cap) and MTARTECH (small cap) for size diversity.

`TATAMOTORS.NS` no longer resolves after the Tata Motors demerger; TMPV (Tata Motors Passenger Vehicles) kept BSE code 500570 and stands in.

Research picks: HAL, BEL, ASIANPAINT, COALINDIA, POWERGRID. Nothing in the code depends on either list; any NSE ticker with a screener.in page works.

## Freshness labels

Prices show "close of <date> (end of day, not live)". Filings show when the exchange feed was last checked. Research shows when statements were fetched. A server booted from the seed snapshot keeps every original timestamp, so old data never looks new.
