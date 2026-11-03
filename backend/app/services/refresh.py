"""One refresh = prices -> price/volume alerts -> filings (which raise announcement alerts) -> enrichment.

Runs in a background thread; a lock makes concurrent requests join the running refresh instead
of hammering public sources twice.
"""
import threading
import traceback

from app.alerts import engine as alerts
from app.announcements import service as announcements
from app.database import db
from app.market_data import service as market
from app.services import companies

_lock = threading.Lock()


def status() -> dict:
    return db.kv_get("refresh_status", {"state": "never", "started_at": None, "finished_at": None})


def _set(**kw) -> None:
    db.kv_set("refresh_status", {**status(), **kw})


def run(days: int = 7, enrich: bool = True) -> dict:
    if not _lock.acquire(blocking=False):
        return {"state": "already_running"}
    try:
        _set(state="running", started_at=db.now_iso(), finished_at=None, step="prices", errors=[])
        errors: list[str] = []
        symbols = [r["symbol"] for r in db.query(
            "SELECT symbol FROM companies WHERE in_portfolio = 1 OR is_research_pick = 1 ORDER BY symbol")]
        for s in symbols:
            r = market.refresh_prices(s)
            if not r["ok"]:
                errors.append(r["error"])
        _set(step="alerts")
        alerts.scan()

        _set(step="filings")
        portfolio = [r for r in db.query("SELECT symbol, bse_code FROM companies WHERE in_portfolio = 1")]
        for c in portfolio:
            if not c["bse_code"]:
                res = companies.resolve_bse(c["symbol"])
                if not res["ok"]:
                    errors.append(res["error"])
                    continue
            r = announcements.ingest(c["symbol"], days)
            if not r["ok"]:
                errors.append(f"{c['symbol']}: {r['error']}")

        if enrich:
            _set(step="reading filings")
            try:
                from app.announcements import enrich as enricher
                enricher.enrich_pending()
            except Exception as e:  # enrichment is additive; rule-based triage already stands
                errors.append(f"enrichment: {e}")

        _set(state="done", finished_at=db.now_iso(), step=None, errors=errors[:30])
        return status()
    except Exception as e:
        _set(state="failed", finished_at=db.now_iso(), step=None, errors=[str(e), traceback.format_exc()[-800:]])
        raise
    finally:
        _lock.release()


def run_in_background(**kw) -> dict:
    if _lock.locked():
        return {"state": "already_running"}
    threading.Thread(target=run, kwargs=kw, daemon=True).start()
    return {"state": "started"}
