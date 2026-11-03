from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.alerts import engine as alerts
from app.announcements import service as announcements
from app.database import db
from app.market_data import service as market
from app.market_data.yahoo import quote_page_url
from app.services import companies, refresh

router = APIRouter(prefix="/api")


@router.get("/portfolio")
def portfolio():
    rows = db.query("SELECT * FROM companies WHERE in_portfolio = 1 ORDER BY sector, symbol")
    high = {r["symbol"]: r["n"] for r in db.query(
        "SELECT symbol, COUNT(*) n FROM announcements WHERE priority = 'HIGH' "
        "AND published_at >= datetime('now', '-7 days') GROUP BY symbol")}
    for r in rows:
        r["market"] = market.latest_stats(r["symbol"])
        r["high_priority_7d"] = high.get(r["symbol"], 0)
    return {"companies": rows, "refresh": refresh.status()}


class AddCompany(BaseModel):
    symbol: str
    in_portfolio: bool = True


@router.post("/portfolio")
def add_company(body: AddCompany):
    res = companies.add_company(body.symbol, body.in_portfolio)
    if not res["ok"]:
        raise HTTPException(422, res["error"])
    sym = res["company"]["symbol"]
    market.refresh_prices(sym)
    if body.in_portfolio:
        announcements.ingest(sym, 7)
        alerts.scan([sym])
    return res


@router.delete("/portfolio/{symbol}")
def remove_company(symbol: str):
    if not companies.remove_from_portfolio(symbol):
        raise HTTPException(404, "Not in portfolio")
    return {"ok": True}


@router.get("/companies/search")
def search(q: str = Query(..., min_length=1, max_length=60)):
    return {"results": companies.search(q)}


@router.get("/market-data/{symbol}")
def market_data(symbol: str, sessions: int = Query(130, ge=5, le=500)):
    symbol = symbol.upper()
    bars = market.bars(symbol, sessions)
    if not bars:
        r = market.refresh_prices(symbol)
        if not r["ok"]:
            raise HTTPException(404, r["error"])
        bars = market.bars(symbol, sessions)
    return {"symbol": symbol, "bars": bars, "latest": market.latest_stats(symbol),
            "source": "Yahoo Finance (end of day)", "source_url": quote_page_url(symbol)}


@router.post("/market-data/refresh")
def refresh_all(days: int = Query(7, ge=1, le=120), enrich: bool = True):
    return refresh.run_in_background(days=days, enrich=enrich)


@router.get("/refresh/status")
def refresh_status():
    return refresh.status()


def _csv(v: str | None) -> list[str] | None:
    return [x.strip() for x in v.split(",") if x.strip()] if v else None


@router.get("/announcements")
def list_announcements(hours: float | None = Query(None, gt=0, le=24 * 365), since: str | None = None,
                       until: str | None = None, symbols: str | None = None, categories: str | None = None,
                       priorities: str | None = None, limit: int = Query(300, le=1000)):
    items = announcements.list_window(hours, since, until, _csv(symbols), _csv(categories), _csv(priorities),
                                      limit=limit)
    return {"items": items, "freshness": announcements.freshness()}


@router.get("/announcements/{ann_id}")
def get_announcement(ann_id: str):
    a = announcements.get(ann_id)
    if not a:
        raise HTTPException(404, "Unknown announcement")
    return a


@router.get("/intelligence/digest")
def digest(hours: float = Query(24, gt=0, le=24 * 365), symbols: str | None = None,
           categories: str | None = None, priorities: str | None = None):
    d = announcements.digest(hours, symbols=_csv(symbols), categories=_csv(categories),
                             priorities=_csv(priorities))
    d["freshness"] = announcements.freshness()
    return d


@router.get("/alerts")
def list_alerts(limit: int = Query(200, le=1000), symbol: str | None = None):
    return {"alerts": alerts.list_alerts(limit, symbol), "settings": alerts.get_settings()}


@router.get("/alerts/settings")
def get_alert_settings():
    return alerts.get_settings()


@router.post("/alerts/settings")
def save_alert_settings(body: dict):
    try:
        s = alerts.save_settings(body)
    except (ValueError, TypeError) as e:
        raise HTTPException(422, str(e))
    scan = alerts.scan()
    return {"settings": s, "scan": scan}


@router.post("/alerts/{alert_id}/ack")
def ack_alert(alert_id: int):
    if not db.execute("UPDATE alerts SET acknowledged = 1 WHERE id = ?", (alert_id,)):
        raise HTTPException(404, "Unknown alert")
    return {"ok": True}
