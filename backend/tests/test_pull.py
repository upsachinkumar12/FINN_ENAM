import pytest

from app.announcements import results
from app.document_ingestion import pdf
from app.research import chat, ledger, synthesis


# ---------- results card ----------

def test_parse_figure_handles_indian_formats():
    assert results.parse_figure("332,861") == 332861
    assert results.parse_figure("(17,539)") == -17539
    assert results.parse_figure("-4.5") == -4.5
    assert results.parse_figure("") is None
    assert results.parse_figure("--") is None


def test_figures_must_appear_verbatim_on_page():
    page = "Revenue from Operations 332,861 311,850 Profit Before Tax 38,613 30,630"
    assert results._in_text("332,861", page)
    assert results._in_text("38613", page)
    assert not results._in_text("332,816", page)  # transposed digits: a hallucinated figure
    assert not results._in_text("38,61", page)    # a fragment of a real number doesn't count


def _llm_out(rows, unit="crore", bank=False):
    return {"found": True, "basis": "consolidated", "unit": unit, "is_bank": bank, "period_end": "2026-09-30",
            "rows": {f: dict(zip(("current", "prev_quarter", "year_ago"), rows.get(f, ("", "", ""))))
                     for f in results.FIELDS}}


def test_results_card_math_and_derived_ebitda(monkeypatch):
    monkeypatch.setattr(results, "_cross_check", lambda *a: [])
    rows = {"revenue": ("1,100", "1,000", "880"), "other_income": ("10", "10", "8"),
            "finance_costs": ("20", "20", "20"), "depreciation": ("50", "45", "40"),
            "pbt": ("200", "180", "160"), "pat": ("150", "135", "(20)")}
    page = " ".join(v for t in rows.values() for v in t)
    card = results.build_card(_llm_out(rows), 4, page, "TEST")
    m = card["metrics"]
    assert m["Revenue"]["qoq"] == pytest.approx(10.0)
    assert m["Revenue"]["yoy"] == pytest.approx(25.0)
    assert m["EBITDA"]["current"] == pytest.approx(260.0)  # 200 + 20 + 50 - 10
    assert m["PAT"]["yoy"] == pytest.approx(850.0)         # from a loss of 20 to a profit of 150
    assert card["period_label"] == "Q2 FY27" and card["page"] == 4


def test_unverifiable_figures_are_dropped_not_shown(monkeypatch):
    monkeypatch.setattr(results, "_cross_check", lambda *a: [])
    rows = {"revenue": ("1,100", "1,000", "880"), "pbt": ("200", "180", "160"), "pat": ("150", "135", "120")}
    page = "1,100 1,000 880 200 180 160 150 135"  # year-ago PAT (120) missing from the page
    card = results.build_card(_llm_out(rows), 2, page, "TEST")
    assert card["metrics"]["PAT"]["year_ago"] is None and card["metrics"]["PAT"]["yoy"] is None
    assert any("dropped" in c for c in card["checks"])


def test_lakh_units_convert_to_crore_and_banks_skip_ebitda(monkeypatch):
    monkeypatch.setattr(results, "_cross_check", lambda *a: [])
    rows = {"revenue": ("50,000", "40,000", "25,000"), "pbt": ("1,000", "800", "500"), "pat": ("750", "600", "400")}
    page = " ".join(v for t in rows.values() for v in t)
    card = results.build_card(_llm_out(rows, unit="lakh", bank=True), 1, page, "TEST")
    assert card["metrics"]["Revenue"]["current"] == pytest.approx(500.0)
    assert "EBITDA" not in card["metrics"]
    assert any("banks" in c for c in card["checks"])


# ---------- documents ----------

def test_chunks_keep_true_page_numbers():
    pages = [pdf.Page(1, "Cover"), pdf.Page(2, "word " * 600), pdf.Page(3, "Revenue grew strongly this year " * 10)]
    chunks = pdf.chunk_pages(pages)
    assert {p for p, _ in chunks} == {2, 3}  # the near-empty cover is skipped
    assert all(len(t) <= pdf.CHUNK_CHARS for _, t in chunks)


def test_ocr_layer_is_detected():
    good = [pdf.Page(1, "ICICI Bank Limited Corporate Office " * 10)]
    bad = [pdf.Page(1, "ICICI Bonk Tower. Corpornte Office Operotinq expenses " * 10)]
    assert pdf.text_quality(good) == "good"
    assert pdf.text_quality(bad) == "ocr"
    assert pdf.text_quality([pdf.Page(1, "")]) == "none"


# ---------- promise ledger ----------

def test_fabricated_quote_is_rejected():
    page = "We expect revenue growth of 18 to 20 percent in FY27, driven by new capacity."
    assert ledger.verify_quote("We expect revenue growth of 18 to 20 percent in FY27", page) == 1.0
    assert ledger.verify_quote("We guarantee revenue growth of 35 percent next year", page) < 0.6


def test_call_month_maps_to_quarter_discussed():
    assert ledger.quarter_discussed("2026-10") == "2026-09"
    assert ledger.quarter_discussed("2026-06") == "2026-03"
    assert ledger.quarter_discussed("2026-02") == "2025-12"


def test_period_parsing():
    assert ledger.parse_period("FY27") == ("annual", ["2027-03"])
    assert ledger.parse_period("Q3 FY27") == ("quarters", ["2026-12"])
    assert ledger.parse_period("H2FY27") == ("quarters", ["2026-12", "2027-03"])
    assert ledger.parse_period("multi-year") is None


FIN = {
    "annual": [{"year": "Mar 2025", "revenue": 1000, "ebitda": 200, "pat": 100, "borrowings": 500},
               {"year": "Mar 2026", "revenue": 1150, "ebitda": 207, "pat": 120, "borrowings": 400}],
    "quarterly": [{"period": "Sep 2025", "revenue": 250, "ebitda": 50, "pat": 25},
                  {"period": "Sep 2026", "revenue": 300, "ebitda": 54, "pat": 30}],
}


def test_actuals_and_scoring():
    v, _, status = ledger.actual_for("revenue_growth", "FY26", FIN)
    assert status == "ok" and v == pytest.approx(15.0)
    assert ledger.score(18, 20, v, "pct") == "Missed"
    assert ledger.score(12, 15, v, "pct") == "Met"
    assert ledger.score(10, 12, v, "pct") == "Exceeded"
    m, _, _ = ledger.actual_for("ebitda_margin", "FY26", FIN)
    assert m == pytest.approx(18.0)
    assert ledger.actual_for("revenue_growth", "FY28", FIN)[2] == "not_yet_due"
    assert ledger.actual_for("order_book", "FY26", FIN)[2] == "unverifiable"
    q, _, _ = ledger.actual_for("revenue_growth", "Q2 FY27", FIN)
    assert q == pytest.approx(20.0)


def test_open_ended_floor():
    assert ledger.score(15, None, 15.2, "pct") == "Met"
    assert ledger.score(15, None, 30.0, "pct") == "Exceeded"
    assert ledger.score(15, None, 12.0, "pct") == "Missed"


# ---------- synthesis guards ----------

def test_uncited_bull_bear_points_are_dropped():
    cite = [{"doc_id": "d", "doc_title": "AR", "doc_type": "annual_report", "period": "FY26", "page": 12,
             "url": "u", "quote": "q"}]
    out = {"model": "m", "segments": [
        {"text": "BULL: Revenue compounded 6% a year", "citations": cite},
        {"text": "\nBULL: The brand is beloved", "citations": []},
        {"text": "\nBEAR: Debt rose", "citations": cite},
        {"text": "\nLEDGER: Promised 20%, delivered 15%.", "citations": []},
    ]}
    p = synthesis.parse_labelled(out)
    assert [b["text"] for b in p["bull"]] == ["Revenue compounded 6% a year"]
    assert p["dropped_uncited"] == 1
    assert p["bear"][0]["citations"][0]["page"] == 12
    assert p["ledger_conclusion"]["text"].startswith("Promised")


# ---------- chat routing ----------

def test_chat_routes_without_a_model(fresh_db, monkeypatch):
    fresh_db.execute("INSERT INTO companies(symbol, name, in_portfolio, added_at) VALUES ('TCS', 'Tata Consultancy Services', 1, 'x')")
    fresh_db.execute("INSERT INTO companies(symbol, name, in_portfolio, added_at) VALUES ('TMPV', 'Tata Motors Passenger Vehicles', 1, 'x')")
    fresh_db.execute("INSERT INTO companies(symbol, name, in_portfolio, added_at) VALUES ('SUZLON', 'Suzlon Energy', 1, 'x')")
    assert chat.resolve_symbol("what did suzlon promise?", None) == "SUZLON"
    assert chat.resolve_symbol("how is tata doing", None) is None  # ambiguous: two Tata companies
    assert chat.resolve_symbol("TCS margins", None) == "TCS"
    assert chat.answer("What are the most important developments in my portfolio today?")["intent"] == "portfolio"
    called = {}
    monkeypatch.setattr(chat, "_move", lambda s: called.setdefault("move", s) and {"intent": "move"})
    monkeypatch.setattr(chat, "_numbers", lambda s: called.setdefault("numbers", s) and {"intent": "numbers"})
    monkeypatch.setattr(chat, "_documents", lambda s, m: called.setdefault("docs", s) and {"intent": "documents"})
    chat.answer("Why did TCS volume spike?")
    chat.answer("Compare the last four quarters of revenue", "SUZLON")
    chat.answer("What did management promise in the last earnings call?", "SUZLON")
    assert called == {"move": "TCS", "numbers": "SUZLON", "docs": "SUZLON"}
