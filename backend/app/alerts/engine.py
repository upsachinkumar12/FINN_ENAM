"""Deterministic EOD alert rules. The investor decides what "unusual" means; this module only checks it."""
import json
from dataclasses import dataclass

from app.database import db
from app.market_data import service as market
from app.market_data.metrics import SessionStats, session_stats
from app.market_data.yahoo import quote_page_url

DEFAULT_SETTINGS = {
    "price_up_pct": 5.0,
    "price_down_pct": 5.0,  # stored as a positive magnitude; fires on return <= -price_down_pct
    "volume_multiple": 2.0,
    "enabled": {"price_up": True, "price_down": True, "volume": True, "announcement": True},
    "symbols": None,  # None = every portfolio company
    "announcement_categories": ["results", "M&A", "management_change", "litigation",
                                "fund_raise", "pledging", "credit_rating"],
    "announcement_min_priority": "HIGH",
    "scan_sessions": 30,
}
PRIORITY_RANK = {"LOW": 0, "MEDIUM": 1, "HIGH": 2}


def get_settings() -> dict:
    stored = db.kv_get("alert_settings", {})
    merged = {**DEFAULT_SETTINGS, **stored}
    merged["enabled"] = {**DEFAULT_SETTINGS["enabled"], **stored.get("enabled", {})}
    return merged


def validate_settings(s: dict) -> dict:
    out = {**get_settings(), **{k: v for k, v in s.items() if k in DEFAULT_SETTINGS}}
    for k, lo, hi in (("price_up_pct", 0.1, 50), ("price_down_pct", 0.1, 50), ("volume_multiple", 1.05, 20)):
        v = float(out[k])
        if not lo <= v <= hi:
            raise ValueError(f"{k} must be between {lo} and {hi}")
        out[k] = v
    if out["announcement_min_priority"] not in PRIORITY_RANK:
        raise ValueError("announcement_min_priority must be LOW, MEDIUM or HIGH")
    out["scan_sessions"] = max(1, min(int(out["scan_sessions"]), 120))
    return out


def save_settings(s: dict) -> dict:
    s = validate_settings(s)
    db.kv_set("alert_settings", s)
    return s


@dataclass(frozen=True)
class Trigger:
    rule: str
    value: float
    threshold: float
    reason: str


def evaluate_session(stats: SessionStats, settings: dict) -> list[Trigger]:
    out: list[Trigger] = []
    en = settings["enabled"]
    r = stats.return_pct
    if r is not None:
        if en.get("price_up") and r >= settings["price_up_pct"]:
            out.append(Trigger("price_up", r, settings["price_up_pct"],
                               f"Closed {r:+.2f}% vs previous close, above your +{settings['price_up_pct']:g}% threshold"))
        if en.get("price_down") and r <= -settings["price_down_pct"]:
            out.append(Trigger("price_down", r, -settings["price_down_pct"],
                               f"Closed {r:+.2f}% vs previous close, below your -{settings['price_down_pct']:g}% threshold"))
    m = stats.volume_multiple
    if en.get("volume") and m is not None and m >= settings["volume_multiple"]:
        out.append(Trigger("volume", m, settings["volume_multiple"],
                           f"Traded {m:.1f}x its {stats.lookback_sessions}-session average volume "
                           f"(threshold {settings['volume_multiple']:g}x)"))
    return out


def monitored_symbols(settings: dict) -> list[str]:
    portfolio = [r["symbol"] for r in db.query("SELECT symbol FROM companies WHERE in_portfolio = 1 ORDER BY symbol")]
    chosen = settings.get("symbols")
    return [s for s in portfolio if chosen is None or s in chosen]


def scan(symbols: list[str] | None = None) -> dict:
    """Evaluate the most recent sessions. INSERT OR IGNORE on (symbol, trade_date, rule) prevents duplicates."""
    settings = get_settings()
    symbols = symbols or monitored_symbols(settings)
    created = 0
    for sym in symbols:
        bars = market.bars(sym, settings["scan_sessions"] + 25)
        start = max(1, len(bars) - settings["scan_sessions"])
        for i in range(start, len(bars)):
            stats = session_stats(bars, i)
            for t in evaluate_session(stats, settings):
                details = {
                    "reason": t.reason,
                    "close": stats.close,
                    "prev_close": stats.prev_close,
                    "return_pct": stats.return_pct,
                    "volume": stats.volume,
                    "avg_volume": stats.avg_volume,
                    "volume_multiple": stats.volume_multiple,
                    "lookback_sessions": stats.lookback_sessions,
                    "source_url": quote_page_url(sym),
                    "basis": "End-of-day data (Yahoo Finance). Not an intraday signal.",
                }
                created += db.execute(
                    "INSERT OR IGNORE INTO alerts(symbol, trade_date, rule, value, threshold, details_json, created_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (sym, stats.date, t.rule, t.value, t.threshold, json.dumps(details), db.now_iso()),
                )
    return {"symbols": len(symbols), "new_alerts": created}


def raise_announcement_alert(ann: dict) -> bool:
    """Called by the announcement pipeline after a filing is classified and prioritised."""
    s = get_settings()
    if not s["enabled"].get("announcement") or ann["symbol"] not in monitored_symbols(s):
        return False
    if ann["category"] not in s["announcement_categories"]:
        return False
    if PRIORITY_RANK.get(ann["priority"], 0) < PRIORITY_RANK[s["announcement_min_priority"]]:
        return False
    details = {
        "reason": f"{ann['category'].replace('_', ' ')} filing rated {ann['priority']}: {ann['title'][:140]}",
        "announcement_id": ann["id"],
        "source_url": ann.get("pdf_url") or ann.get("filing_page_url"),
    }
    return bool(db.execute(
        "INSERT OR IGNORE INTO alerts(symbol, trade_date, rule, value, threshold, details_json, created_at) "
        "VALUES (?, ?, ?, NULL, NULL, ?, ?)",
        (ann["symbol"], ann["published_at"][:10], f"announcement:{ann['id']}", json.dumps(details), db.now_iso()),
    ))


def list_alerts(limit: int = 200, symbol: str | None = None) -> list[dict]:
    sql = ("SELECT a.*, c.name FROM alerts a LEFT JOIN companies c ON c.symbol = a.symbol "
           + ("WHERE a.symbol = ? " if symbol else "")
           + "ORDER BY a.trade_date DESC, a.id DESC LIMIT ?")
    rows = db.query(sql, (symbol, limit) if symbol else (limit,))
    for r in rows:
        r["details"] = json.loads(r.pop("details_json") or "{}")
        r["kind"] = "announcement" if r["rule"].startswith("announcement:") else r["rule"]
    return rows
