"""screener.in as an index of primary documents and a table of reported financials.

Used for: company lookup (name, BSE code), the standardised financial tables (which are compiled from
the company's own filings), and links to annual reports and concall transcripts hosted on BSE or the
company's site. Deliberately NOT used: Screener's AI summaries of concalls and annual reports, its
"about" blurb, and credit-rating agency pages. Those are secondary commentary, which the Pull side
must not rely on. `/company/source/quarter/*` is disallowed by robots.txt, so it is never fetched.
"""
import hashlib
import json
import re
import time
from datetime import datetime

from bs4 import BeautifulSoup

from app.config import settings
from app.utils.http import SourceError, get

BASE = "https://www.screener.in"
MONTHS = {m: i for i, m in enumerate(
    ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], 1)}


def _cached_get(url: str, max_age_h: float | None = None) -> str:
    max_age_h = settings.screener_cache_hours if max_age_h is None else max_age_h
    path = settings.cache_dir / "screener" / (hashlib.sha1(url.encode()).hexdigest() + ".html")
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and (time.time() - path.stat().st_mtime) < max_age_h * 3600:
        return path.read_text(encoding="utf-8")
    try:
        html = get(url).text
    except SourceError:
        if path.exists():  # stale cache beats no data; the caller still sees fetched_at
            return path.read_text(encoding="utf-8")
        raise
    path.write_text(html, encoding="utf-8")
    return html


def search(q: str) -> list[dict]:
    q = q.strip()
    if not q:
        return []
    data = json.loads(_cached_get(f"{BASE}/api/company/search/?q={q}", max_age_h=24))
    out = []
    for d in data:
        m = re.match(r"/company/([^/]+)/", d.get("url", ""))
        if m:
            out.append({"symbol": m.group(1).upper(), "name": d["name"]})
    return out


def parse_number(s: str) -> float | None:
    s = s.replace(",", "").replace("%", "").replace("₹", "").strip()
    if s in ("", "-", "--"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def period_key(label: str) -> str | None:
    """'Sep 2026' -> '2026-09'. Indian quarters end Jun/Sep/Dec/Mar; fiscal years end in March."""
    m = re.match(r"([A-Z][a-z]{2}) (\d{4})", label.strip())
    if not m or m.group(1) not in MONTHS:
        return None
    return f"{m.group(2)}-{MONTHS[m.group(1)]:02d}"


def fiscal_label(key: str) -> str:
    """'2026-09' -> 'Q2 FY27'; '2026-03' -> 'Q4 FY26'. Indian FY runs April-March."""
    y, mth = int(key[:4]), int(key[5:])
    fy = y + 1 if mth > 3 else y
    q = {6: 1, 9: 2, 12: 3, 3: 4}.get(mth)
    return f"Q{q} FY{fy % 100:02d}" if q else key


def _clean_label(s: str) -> str:
    return re.sub(r"\s*\+\s*$", "", s).strip()


def _parse_table(section) -> dict:
    table = section.select_one("table") if section else None
    if table is None:
        return {"periods": [], "rows": {}}
    headers = [th.get_text(strip=True) for th in table.select("thead th")][1:]
    rows: dict[str, list[float | None]] = {}
    for tr in table.select("tbody tr"):
        tds = tr.select("td")
        if not tds:
            continue
        label = _clean_label(tds[0].get_text(" ", strip=True))
        if label in ("Raw PDF",):
            continue
        rows[label] = [parse_number(td.get_text(strip=True)) for td in tds[1:]]
    return {"periods": headers, "rows": rows}


def _company_url(symbol: str, consolidated: bool) -> str:
    return f"{BASE}/company/{symbol}/" + ("consolidated/" if consolidated else "")


def fetch_company(symbol: str) -> dict:
    """Everything FINN needs from one company page. Prefers consolidated figures and falls back to
    standalone when the consolidated tables are empty (common for companies without subsidiaries)."""
    symbol = symbol.upper()
    basis = "consolidated"
    try:
        html = _cached_get(_company_url(symbol, True))
    except SourceError as e:
        if "HTTP 404" in str(e):
            raise SourceError(f"{symbol}: no company page found on screener.in") from e
        raise
    soup = BeautifulSoup(html, "lxml")
    quarters = _parse_table(soup.select_one("section#quarters"))
    if not any(v for vals in quarters["rows"].values() for v in vals if v is not None):
        basis = "standalone"
        html = _cached_get(_company_url(symbol, False))
        soup = BeautifulSoup(html, "lxml")
        quarters = _parse_table(soup.select_one("section#quarters"))

    name_el = soup.select_one("h1")
    bse = soup.select_one("a[href*='bseindia.com/stock-share-price']")
    bse_code = None
    if bse:
        m = re.search(r"/(\d{6})/?$", bse["href"].rstrip("/") + "/")
        bse_code = m.group(1) if m else None

    top = {}
    for li in soup.select("#top-ratios li"):
        n, v = li.select_one(".name"), li.select_one(".value")
        if n and v:
            top[n.get_text(strip=True)] = v.get_text(" ", strip=True)

    return {
        "symbol": symbol,
        "name": name_el.get_text(strip=True) if name_el else symbol,
        "basis": basis,
        "bse_code": bse_code,
        "bse_url": bse["href"] if bse else None,
        "source_url": _company_url(symbol, basis == "consolidated"),
        "fetched_at": datetime.now().isoformat(timespec="seconds"),
        "top_ratios": top,
        "quarters": quarters,
        "annual": _parse_table(soup.select_one("section#profit-loss")),
        "balance_sheet": _parse_table(soup.select_one("section#balance-sheet")),
        "cash_flow": _parse_table(soup.select_one("section#cash-flow")),
        "ratios": _parse_table(soup.select_one("section#ratios")),
        "documents": _parse_documents(soup),
    }


def _parse_documents(soup) -> dict:
    """Primary-document links only: annual reports and concall transcripts / decks."""
    annual_reports = []
    for a in soup.select(".documents.annual-reports li a"):
        m = re.search(r"(\d{4})", a.get_text())
        annual_reports.append({"title": a.get_text(strip=True), "fy": int(m.group(1)) if m else None,
                               "url": a["href"]})
    concalls = []
    for li in soup.select(".documents.concalls li"):
        when = li.select_one("div")
        label = when.get_text(strip=True) if when else ""
        links = {a.get_text(strip=True): a.get("href") for a in li.select("a[href]")}
        concalls.append({
            "month": label,
            "period_key": period_key(label),
            "transcript_url": links.get("Transcript"),
            "presentation_url": links.get("PPT"),
        })
    return {"annual_reports": annual_reports, "concalls": concalls}
