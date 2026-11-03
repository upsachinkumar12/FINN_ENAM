from app.announcements import bse, service
from app.announcements.classify import triage
from app.sources import screener

PAGE = """<div id="company-announcements-tab"><ul>
<li><a href="https://www.bseindia.com/stockinfo/AnnPdfOpen.aspx?Pname=abc-123.pdf">
  Announcement under Regulation 30 (LODR)-Credit Rating
  <div class="ink-600 smaller"><time datetime="2026-10-30T18:26:40+05:30">30 Oct</time> - A summary we must not use.</div></a></li>
<li><a href="https://www.bseindia.com/stockinfo/AnnPdfOpen.aspx?Pname=def-456.pdf">
  Board Meeting Outcome for Outcome Of The Board Meeting Dated 29Th October 2026
  <div class="ink-600 smaller"><time datetime="2026-10-29T16:01:00+05:30">29 Oct</time></div></a></li>
</ul></div>"""


def test_screener_index_gives_title_time_and_bse_link_only(monkeypatch):
    monkeypatch.setattr(screener, "_cached_get", lambda url, max_age_h=None: PAGE)
    items = screener.recent_announcements("SUZLON")
    assert items[0] == {"title": "Announcement under Regulation 30 (LODR)-Credit Rating",
                        "published_at": "2026-10-30T18:26:40+05:30",
                        "pdf_url": "https://www.bseindia.com/stockinfo/AnnPdfOpen.aspx?Pname=abc-123.pdf"}
    assert all("summary" not in i["title"].lower() for i in items)


def test_index_items_recover_bse_subcategory_for_the_same_triage():
    a = bse.from_index({"title": "Announcement under Regulation 30 (LODR)-Credit Rating",
                        "published_at": "2026-10-30T18:26:40+05:30",
                        "pdf_url": "https://www.bseindia.com/stockinfo/AnnPdfOpen.aspx?Pname=abc-123.pdf"}, "SUZLON", None)
    assert a["bse_subcategory"] == "Credit Rating" and a["id"] == "bse-att:abc-123.pdf"
    assert triage(a["bse_category"], a["bse_subcategory"], a["title"]).category == "credit_rating"


def test_bse_refusal_falls_back_and_never_duplicates(fresh_db, monkeypatch):
    from app.utils.http import SourceError
    fresh_db.execute("INSERT INTO companies(symbol, name, bse_code, in_portfolio, added_at) "
                     "VALUES ('SUZLON', 'Suzlon', '532667', 1, 'x')")

    def refused(*a, **k):
        raise SourceError("api.bseindia.com returned HTTP 403")
    monkeypatch.setattr(bse, "fetch", refused)
    monkeypatch.setattr(screener, "_cached_get", lambda url, max_age_h=None: PAGE)
    r = service.ingest("SUZLON")
    assert r["ok"] and r["new"] == 2 and "screener" in r["via"]
    assert service.ingest("SUZLON")["new"] == 0
    f = service.freshness()
    assert f["last_success"] and "screener" in f["via"]


def test_a_failure_does_not_erase_the_last_success(fresh_db):
    fresh_db.log_fetch("bse", "TCS", True, "10 filings via BSE, 2 new")
    ok_at = fresh_db.last_fetch("bse", "TCS")["last_ok_at"]
    fresh_db.log_fetch("bse", "TCS", False, "HTTP 403")
    row = fresh_db.last_fetch("bse", "TCS")
    assert row["ok"] == 0 and row["last_ok_at"] == ok_at
    assert service.freshness()["last_success"] == ok_at
