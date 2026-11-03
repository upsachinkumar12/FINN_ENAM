from app.database import db
from app.market_data import yahoo
from app.market_data.metrics import session_stats
from app.utils.http import SourceError


def refresh_prices(symbol: str, range_: str = "6mo") -> dict:
    try:
        data = yahoo.fetch_eod(symbol, range_)
    except SourceError as e:
        db.log_fetch("yahoo", symbol, False, str(e))
        return {"symbol": symbol, "ok": False, "error": str(e)}
    with db.tx() as c:
        c.executemany(
            "INSERT INTO prices(symbol, date, open, high, low, close, adj_close, volume) "
            "VALUES (:symbol, :date, :open, :high, :low, :close, :adj_close, :volume) "
            "ON CONFLICT(symbol, date) DO UPDATE SET open=excluded.open, high=excluded.high, low=excluded.low, "
            "close=excluded.close, adj_close=excluded.adj_close, volume=excluded.volume",
            [{"symbol": symbol, **b} for b in data["bars"]],
        )
    db.log_fetch("yahoo", symbol, True, f"{len(data['bars'])} sessions")
    return {"symbol": symbol, "ok": True, "sessions": len(data["bars"]), "name": data["name"]}


def bars(symbol: str, limit: int = 130) -> list[dict]:
    rows = db.query(
        "SELECT date, open, high, low, close, adj_close, volume FROM prices WHERE symbol = ? "
        "ORDER BY date DESC LIMIT ?",
        (symbol, limit),
    )
    return rows[::-1]


def latest_stats(symbol: str) -> dict | None:
    b = bars(symbol, 40)
    if not b:
        return None
    s = session_stats(b, len(b) - 1)
    fetched = db.last_fetch("yahoo", symbol)
    return {
        **s.__dict__,
        "spark": [x["close"] for x in b[-20:]],
        "fetched_at": fetched["fetched_at"] if fetched else None,
        "fetch_ok": bool(fetched["ok"]) if fetched else None,
        "fetch_error": fetched["detail"] if fetched and not fetched["ok"] else None,
        "source_url": yahoo.quote_page_url(symbol),
    }
