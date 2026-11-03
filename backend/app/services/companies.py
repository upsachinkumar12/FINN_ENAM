"""Company registry. Any NSE ticker can be added: Yahoo validates the ticker, Screener supplies the BSE code."""
from app.database import db
from app.market_data import yahoo
from app.portfolio_seed import PORTFOLIO, RESEARCH_PICKS
from app.sources import screener
from app.utils.http import SourceError


def seed_defaults() -> None:
    if db.query_one("SELECT 1 FROM companies LIMIT 1"):
        return
    with db.tx() as c:
        for rows, in_pf, pick in ((PORTFOLIO, 1, 0), (RESEARCH_PICKS, 0, 1)):
            for sym, name, sector, size in rows:
                c.execute(
                    "INSERT OR IGNORE INTO companies(symbol, name, sector, size_bucket, in_portfolio, "
                    "is_research_pick, added_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (sym, name, sector, size, in_pf, pick, db.now_iso()),
                )


def resolve_bse(symbol: str) -> dict:
    """Fill in BSE code and page from Screener. Failure is recorded, never guessed."""
    try:
        info = screener.fetch_company(symbol)
    except SourceError as e:
        db.log_fetch("screener", symbol, False, str(e))
        return {"symbol": symbol, "ok": False, "error": str(e)}
    db.execute("UPDATE companies SET bse_code = ?, bse_url = ? WHERE symbol = ?",
               (info["bse_code"], info["bse_url"], symbol))
    db.log_fetch("screener", symbol, True, info["basis"])
    return {"symbol": symbol, "ok": True, "bse_code": info["bse_code"], "name": info["name"]}


def validate_ticker(symbol: str) -> dict:
    """A ticker is valid when Yahoo has NSE price data for it."""
    symbol = symbol.strip().upper()
    if not symbol.replace("-", "").replace("&", "").isalnum() or len(symbol) > 20:
        return {"symbol": symbol, "valid": False, "error": "Not a well-formed NSE symbol"}
    try:
        data = yahoo.fetch_eod(symbol, "5d")
    except SourceError as e:
        return {"symbol": symbol, "valid": False, "error": str(e)}
    return {"symbol": symbol, "valid": True, "name": data["name"]}


def add_company(symbol: str, in_portfolio: bool = True, sector: str | None = None) -> dict:
    v = validate_ticker(symbol)
    if not v["valid"]:
        return {"ok": False, **v}
    sym = v["symbol"]
    existing = db.query_one("SELECT * FROM companies WHERE symbol = ?", (sym,))
    if existing:
        if in_portfolio and not existing["in_portfolio"]:
            db.execute("UPDATE companies SET in_portfolio = 1 WHERE symbol = ?", (sym,))
    else:
        db.execute(
            "INSERT INTO companies(symbol, name, sector, size_bucket, in_portfolio, is_research_pick, added_at) "
            "VALUES (?, ?, ?, NULL, ?, 0, ?)",
            (sym, v["name"] or sym, sector, int(in_portfolio), db.now_iso()),
        )
    resolve_bse(sym)
    return {"ok": True, "company": db.query_one("SELECT * FROM companies WHERE symbol = ?", (sym,))}


def remove_from_portfolio(symbol: str) -> bool:
    return db.execute("UPDATE companies SET in_portfolio = 0 WHERE symbol = ?", (symbol.upper(),)) > 0


def search(q: str) -> list[dict]:
    """Local companies first, then Screener's search for anything else listed."""
    q = q.strip()
    if not q:
        return []
    like = f"%{q}%"
    local = db.query("SELECT symbol, name, in_portfolio, is_research_pick FROM companies "
                     "WHERE symbol LIKE ? OR name LIKE ? ORDER BY in_portfolio DESC, symbol LIMIT 8", (like, like))
    seen = {r["symbol"] for r in local}
    try:
        remote = [r for r in screener.search(q) if r["symbol"] not in seen and not r["symbol"].isdigit()]
    except SourceError:
        remote = []
    return [{**r, "known": True} for r in local] + [{**r, "known": False} for r in remote[:8]]
