import json
from datetime import date, datetime, timedelta

from app.alerts import engine as alerts
from app.announcements import bse
from app.announcements.classify import triage
from app.config import IST
from app.database import db
from app.utils.http import SourceError

PRIORITY_ORDER = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}


def ingest(symbol: str, days: int = 30) -> dict:
    company = db.query_one("SELECT * FROM companies WHERE symbol = ?", (symbol,))
    if not company or not company.get("bse_code"):
        db.log_fetch("bse", symbol, False, "No BSE code known for this company")
        return {"symbol": symbol, "ok": False, "error": "No BSE code known; filings unavailable from BSE"}
    to = datetime.now(IST).date()
    try:
        raw = bse.fetch(company["bse_code"], to - timedelta(days=days), to)
    except SourceError as e:
        db.log_fetch("bse", symbol, False, str(e))
        return {"symbol": symbol, "ok": False, "error": str(e)}

    new = 0
    for row in raw:
        a = bse.normalise(row, symbol, company.get("bse_url"))
        t = triage(a["bse_category"], a["bse_subcategory"], a["title"], a["critical"])
        inserted = db.execute(
            "INSERT OR IGNORE INTO announcements(id, symbol, title, detail, bse_category, bse_subcategory, "
            "published_at, source, filing_page_url, pdf_url, category, category_confidence, category_method, "
            "priority, priority_score, priority_reason, card_json, ingested_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (a["id"], symbol, a["title"], a["detail"], a["bse_category"], a["bse_subcategory"], a["published_at"],
             a["source"], a["filing_page_url"], a["pdf_url"], t.category, t.confidence, t.method, t.priority,
             t.score, t.reason,
             json.dumps({"needs_reading": t.needs_reading, "tags": t.tags, "critical": a["critical"]}),
             db.now_iso()),
        )
        if inserted:
            new += 1
            alerts.raise_announcement_alert({**a, "category": t.category, "priority": t.priority})
    db.log_fetch("bse", symbol, True, f"{len(raw)} filings in {days}d, {new} new")
    return {"symbol": symbol, "ok": True, "fetched": len(raw), "new": new}


def _hydrate(r: dict) -> dict:
    r["card"] = json.loads(r.pop("card_json") or "{}")
    r["summary"] = json.loads(r.pop("summary_json") or "null")
    r["low_confidence"] = (r.get("category_confidence") or 0) < 0.6
    return r


def get(ann_id: str) -> dict | None:
    r = db.query_one("SELECT a.*, c.name AS company_name FROM announcements a "
                     "LEFT JOIN companies c ON c.symbol = a.symbol WHERE a.id = ?", (ann_id,))
    return _hydrate(r) if r else None


def list_window(hours: float | None = None, since: str | None = None, until: str | None = None,
                symbols: list[str] | None = None, categories: list[str] | None = None,
                priorities: list[str] | None = None, portfolio_only: bool = True, limit: int = 500) -> list[dict]:
    where, params = [], []
    if hours is not None:
        where.append("a.published_at >= ?")
        params.append((datetime.now(IST) - timedelta(hours=hours)).isoformat(timespec="seconds"))
    if since:
        where.append("a.published_at >= ?")
        params.append(since)
    if until:
        where.append("a.published_at <= ?")
        params.append(until)
    for col, vals in (("a.symbol", symbols), ("a.category", categories), ("a.priority", priorities)):
        if vals:
            where.append(f"{col} IN ({','.join('?' * len(vals))})")
            params.extend(vals)
    if portfolio_only:
        where.append("c.in_portfolio = 1")
    sql = ("SELECT a.*, c.name AS company_name FROM announcements a JOIN companies c ON c.symbol = a.symbol "
           + (("WHERE " + " AND ".join(where)) if where else "")
           + " ORDER BY a.published_at DESC LIMIT ?")
    return [_hydrate(r) for r in db.query(sql, (*params, limit))]


def group_related(items: list[dict]) -> list[dict]:
    """One event often produces several filings (board outcome + results + press release + deck).
    Fold same-company, same-category filings within 36 hours under the most important one."""
    items = sorted(items, key=lambda a: (PRIORITY_ORDER[a["priority"]], -a["priority_score"], a["published_at"]))
    leaders: list[dict] = []
    for a in items:
        t = datetime.fromisoformat(a["published_at"])
        for lead in leaders:
            if (lead["symbol"] == a["symbol"] and lead["category"] == a["category"]
                    and a["category"] != "unclassified"
                    and abs((datetime.fromisoformat(lead["published_at"]) - t).total_seconds()) < 36 * 3600):
                lead["related"].append({k: a[k] for k in ("id", "title", "published_at", "pdf_url", "priority")})
                break
        else:
            leaders.append({**a, "related": []})
    return leaders


def digest(hours: float = 24, **filters) -> dict:
    items = list_window(hours=hours, **filters)
    grouped = group_related(items)
    bands = {p: [g for g in grouped if g["priority"] == p] for p in ("HIGH", "MEDIUM", "LOW")}
    return {
        "window_hours": hours,
        "generated_at": db.now_iso(),
        "counts": {"filings": len(items), "events": len(grouped),
                   **{p.lower(): len(v) for p, v in bands.items()}},
        "must_read": bands["HIGH"],
        "worth_a_look": bands["MEDIUM"],
        "buried": bands["LOW"],
    }


def freshness() -> dict:
    rows = db.query("SELECT key, fetched_at, ok, detail FROM fetch_log WHERE source = 'bse' ORDER BY fetched_at DESC")
    return {
        "last_success": next((r["fetched_at"] for r in rows if r["ok"]), None),
        "failures": [r for r in rows if not r["ok"]],
    }


def window_bounds(days: int) -> tuple[date, date]:
    to = datetime.now(IST).date()
    return to - timedelta(days=days), to
