from app.announcements import service
from app.announcements.classify import CATEGORIES, triage
from app.sources.screener import _parse_table, fiscal_label, parse_number, period_key


def test_results_filing_is_high_and_gets_read():
    t = triage("Result", "Financial Results", "Financial Results For The Quarter Ended September 30, 2026")
    assert (t.category, t.priority, t.needs_reading) == ("results", "HIGH", True)
    assert "results_card" in t.tags


def test_results_date_notice_is_low():
    t = triage("Board Meeting", "Board Meeting", "Board Meeting Intimation for Approval Of The Financial Results")
    assert (t.category, t.priority) == ("results", "LOW")


def test_routine_paperwork_never_needs_the_model():
    for sub, title in [("Allotment of ESOP / ESPS", "Allotment of ESOP"),
                       ("Closure of Trading Window", "Closure of Trading Window"),
                       ("Certificate under Reg. 74 (5) of SEBI (DP) Regulations, 2018", "Compliances-Certificate"),
                       ("Newspaper Publication", "Newspaper Publication")]:
        t = triage("Company Update", sub, title)
        assert t.priority == "LOW" and not t.needs_reading, sub


def test_management_change_and_pledge_are_read_for_detail():
    t = triage("Company Update", "Change in Management", "Change in Management")
    assert t.category == "management_change" and t.needs_reading and "people" in t.tags
    p = triage("Insider Trading / SAST", "Disclosures under Reg. 31(1) and 31(2) of SEBI (SAST) Regulations, 2011", "x")
    assert (p.category, p.priority) == ("pledging", "HIGH")


def test_descriptive_general_headlines():
    routine = triage("Company Update", "General", "Infosys Foundation Collaborates With Madras Medical College")
    assert (routine.category, routine.priority, routine.needs_reading) == ("press_release", "LOW", False)
    material = triage("Company Update", "General", "Press Release - TCS Wins Rs 122 Crore Bid For Odisha Platform")
    assert (material.priority, material.needs_reading) == ("MEDIUM", True)


def test_opaque_titles_are_flagged_low_confidence():
    t = triage("Company Update", "General", "Intimation Under Regulation 30 Of The SEBI (LODR) Regulations, 2015")
    assert t.category == "unclassified" and t.confidence < 0.6 and t.needs_reading


def test_bse_critical_flag_lifts_low_items_only():
    t = triage("Company Update", "Analyst / Investor Meet", "Analyst / Investor Meet - Intimation", critical=True)
    assert t.priority == "MEDIUM"
    hi = triage("Result", "Financial Results", "Financial Results", critical=True)
    assert hi.priority == "HIGH"


def test_every_rule_emits_a_reference_category():
    from app.announcements.classify import RULES
    assert all(r[2].category in CATEGORIES for r in RULES)


def _ann(i, sym, cat, prio, score, ts):
    return {"id": str(i), "symbol": sym, "category": cat, "priority": prio, "priority_score": score,
            "published_at": ts, "title": f"t{i}", "pdf_url": None}


def test_related_filings_fold_under_the_most_important():
    items = [
        _ann(1, "TCS", "results", "LOW", 30, "2026-10-09T10:00:00+05:30"),
        _ann(2, "TCS", "results", "HIGH", 92, "2026-10-09T16:00:00+05:30"),
        _ann(3, "TCS", "results", "HIGH", 88, "2026-10-09T16:05:00+05:30"),
        _ann(4, "INFY", "results", "HIGH", 92, "2026-10-09T16:00:00+05:30"),
        _ann(5, "TCS", "unclassified", "LOW", 5, "2026-10-09T16:00:00+05:30"),
        _ann(6, "TCS", "unclassified", "LOW", 5, "2026-10-09T16:01:00+05:30"),
    ]
    g = service.group_related(items)
    tcs = next(x for x in g if x["symbol"] == "TCS" and x["category"] == "results")
    assert tcs["id"] == "2" and {r["id"] for r in tcs["related"]} == {"1", "3"}
    assert sum(1 for x in g if x["category"] == "unclassified") == 2  # routine items are never folded


def test_screener_number_and_period_parsing():
    assert parse_number("1,421") == 1421
    assert parse_number("-29%") == -29
    assert parse_number("") is None
    assert period_key("Sep 2026") == "2026-09"
    assert fiscal_label("2026-09") == "Q2 FY27"
    assert fiscal_label("2026-03") == "Q4 FY26"
    assert fiscal_label("2026-12") == "Q3 FY27"


def test_screener_table_parse():
    from bs4 import BeautifulSoup
    html = """<section id="quarters"><table><thead><tr><th></th><th>Jun 2026</th><th>Sep 2026</th></tr></thead>
    <tbody><tr><td class="text">Sales +</td><td>1,000</td><td>1,100</td></tr>
    <tr><td class="text">OPM %</td><td>20%</td><td></td></tr>
    <tr><td class="text">Raw PDF</td><td><a href="/x"></a></td><td></td></tr></tbody></table></section>"""
    t = _parse_table(BeautifulSoup(html, "lxml").select_one("section"))
    assert t["periods"] == ["Jun 2026", "Sep 2026"]
    assert t["rows"] == {"Sales": [1000, 1100], "OPM %": [20, None]}
