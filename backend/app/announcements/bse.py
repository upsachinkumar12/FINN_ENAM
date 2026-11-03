"""BSE corporate-announcement adapter (the API behind bseindia.com's announcements page).

NSE's equivalent endpoint returns 403 to non-browser clients, so BSE is the primary filings feed.
BSE only answers per-company queries; the all-company query returns nothing.
"""
from datetime import date, datetime

from app.config import IST
from app.utils.http import get

API = ("https://api.bseindia.com/BseIndiaAPI/api/AnnSubCategoryGetData/w?pageno={page}&strCat=-1"
       "&strPrevDate={frm}&strScrip={code}&strSearch=P&strToDate={to}&strType=C&subcategory=-1")
HEADERS = {"Referer": "https://www.bseindia.com/", "Origin": "https://www.bseindia.com"}
MAX_PAGES = 40  # 10 rows a page; 400 filings is far beyond any company's quarterly volume


def pdf_url(attachment: str) -> str:
    return f"https://www.bseindia.com/stockinfo/AnnPdfOpen.aspx?Pname={attachment}"


def fetch(bse_code: str, frm: date, to: date) -> list[dict]:
    rows: list[dict] = []
    for page in range(1, MAX_PAGES + 1):
        r = get(API.format(page=page, frm=f"{frm:%Y%m%d}", to=f"{to:%Y%m%d}", code=bse_code), headers=HEADERS)
        table = r.json().get("Table") or []
        if not table:
            break
        rows.extend(table)
    return rows


def normalise(row: dict, symbol: str, company_bse_url: str | None) -> dict:
    ts = row.get("DissemDT") or row.get("NEWS_DT")
    published = datetime.fromisoformat(ts.split(".")[0]).replace(tzinfo=IST).isoformat()
    attachment = (row.get("ATTACHMENTNAME") or "").strip()
    return {
        "id": f"bse:{row['NEWSID']}",
        "symbol": symbol,
        "title": (row.get("NEWSSUB") or row.get("HEADLINE") or "").strip(),
        "detail": (row.get("HEADLINE") or "").strip() or None,
        "bse_category": (row.get("CATEGORYNAME") or "").strip() or None,
        "bse_subcategory": (row.get("SUBCATNAME") or "").strip() or None,
        "critical": str(row.get("CRITICALNEWS")) == "1",
        "published_at": published,
        "source": "BSE",
        "filing_page_url": (company_bse_url.rstrip("/") + "/corp-announcements/") if company_bse_url else None,
        "pdf_url": pdf_url(attachment) if attachment else None,
    }
