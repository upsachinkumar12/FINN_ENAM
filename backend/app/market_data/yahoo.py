"""End-of-day prices from Yahoo Finance's public chart endpoint (the same data yfinance wraps)."""
from datetime import datetime, time

from app.config import IST, settings
from app.utils.http import SourceError, get

CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?range={range}&interval=1d&events=div,splits"


def yahoo_ticker(symbol: str) -> str:
    return symbol if "." in symbol else f"{symbol}.NS"


def quote_page_url(symbol: str) -> str:
    return f"https://finance.yahoo.com/quote/{yahoo_ticker(symbol)}/history/"


def fetch_eod(symbol: str, range_: str = "6mo", now: datetime | None = None) -> dict:
    """Daily bars, ascending. Today's bar is dropped until after the configured post-close time,
    so an in-progress session is never treated as an end-of-day value.

    `close` is split-adjusted but not dividend-adjusted (Yahoo's convention), so returns across a
    bonus or split date don't show as fake crashes. `adj_close` additionally adjusts for dividends.
    """
    try:
        payload = get(CHART_URL.format(ticker=yahoo_ticker(symbol), range=range_)).json()
    except SourceError as e:
        if "HTTP 404" in str(e):
            raise SourceError(f"{symbol}: not a valid NSE ticker on Yahoo Finance") from e
        raise
    chart = payload.get("chart") or {}
    result = (chart.get("result") or [None])[0]
    if not result or not result.get("timestamp"):
        raise SourceError(f"{symbol}: Yahoo returned no price data")

    meta = result["meta"]
    q = result["indicators"]["quote"][0]
    adj = (result["indicators"].get("adjclose") or [{}])[0].get("adjclose") or [None] * len(result["timestamp"])
    bars: dict[str, dict] = {}
    for i, ts in enumerate(result["timestamp"]):
        if q["close"][i] is None:  # holiday or suspended session rows come back null
            continue
        d = datetime.fromtimestamp(ts, IST).date().isoformat()
        bars[d] = {
            "date": d,
            "open": q["open"][i],
            "high": q["high"][i],
            "low": q["low"][i],
            "close": q["close"][i],
            "adj_close": adj[i],
            "volume": q["volume"][i],
        }

    now = now or datetime.now(IST)
    cutoff = time.fromisoformat(settings.eod_final_after_ist)
    today = now.date().isoformat()
    provisional = today in bars and now.time() < cutoff
    if provisional:
        bars.pop(today)

    return {
        "symbol": symbol,
        "name": meta.get("longName") or meta.get("shortName"),
        "currency": meta.get("currency"),
        "bars": [bars[k] for k in sorted(bars)],
        "dropped_provisional_session": today if provisional else None,
    }
