"""Rules-first classification and triage.

Most filings announce what they are in BSE's own category, subcategory and title. Rules handle
those for free. Only filings whose metadata can't tell us what happened (or whose importance
depends on what the document says) are marked for the cheap model to read.

Categories follow the reference document. Priority is HIGH / MEDIUM / LOW with a 0-100 score
for ordering inside each band.
"""
import re
from dataclasses import dataclass, field

CATEGORIES = [
    "results", "M&A", "fund_raise", "management_change", "litigation", "insider_trading", "earnings_call",
    "investor_meetings", "credit_rating", "dividend", "bonus_split", "capex", "press_release",
    "postal_ballot", "agm_egm", "pledging", "unclassified",
]


@dataclass
class Triage:
    category: str
    confidence: float
    priority: str
    score: float
    reason: str
    method: str = "rules"
    needs_reading: bool = False  # the filing's content decides importance; send to the cheap model
    tags: list[str] = field(default_factory=list)


def _t(category, confidence, priority, score, reason, needs_reading=False, tags=None):
    return Triage(category, confidence, priority, score, reason, "rules", needs_reading, tags or [])


# (subcategory regex, title regex or None) -> triage. First match wins, so specific rules come first.
RULES: list[tuple[str, str | None, Triage]] = [
    # Results and their paperwork
    (r"^Financial Results$", None,
     _t("results", 0.97, "HIGH", 92, "Quarterly results filed", needs_reading=True, tags=["results_card"])),
    (r"^Outcome of Board Meeting$", r"result",
     _t("results", 0.9, "HIGH", 88, "Board approved results", needs_reading=True, tags=["results_card"])),
    (r"^Board Meeting$", r"result",
     _t("results", 0.9, "LOW", 30, "Results date scheduled. The numbers come later")),
    (r"^Newspaper Publication$", None,
     _t("results", 0.6, "LOW", 8, "Newspaper ad of an earlier disclosure. Nothing new")),
    (r".*", r"^(Report of Auditors|Auditor'*s'* Report) on Financial",
     _t("results", 0.85, "LOW", 25, "Auditor's report on results already filed")),
    # Management
    (r"^(Change in Management|Change in Directorate|Cessation|Resignation of Director|Appointment.*Director)", None,
     _t("management_change", 0.9, "MEDIUM", 60, "Change at the top. Seniority decides importance",
        needs_reading=True, tags=["people"])),
    (r"^Appointment of Statutory Auditor", None,
     _t("unclassified", 0.85, "LOW", 12, "Auditor appointment. Routine")),
    # Deals and capital
    (r"^(Acquisition|Scheme of Arrangement|Amalgamation|Merger|Demerger|Diversification / Disinvestment|Restructuring)",
     None, _t("M&A", 0.9, "HIGH", 80, "Deal or restructuring. Size decides importance", needs_reading=True)),
    (r"^Allotment of ESOP", None, _t("unclassified", 0.95, "LOW", 5, "Employee stock option allotment. Routine")),
    (r"^Allotment of Equity Shares$", None,
     _t("fund_raise", 0.6, "LOW", 30, "Share allotment. Could be ESOP or fresh capital", needs_reading=True)),
    (r"(Commercial Paper|Non.?Convertible|NCD|Debenture)", None,
     _t("fund_raise", 0.85, "LOW", 18, "Routine debt servicing or issuance")),
    (r"(QIP|Qualified Institution|Rights Issue|Preferential|Buy.?back)", None,
     _t("fund_raise", 0.9, "HIGH", 82, "Equity raise or buyback")),
    (r"^Reg\. 32 \(1\), \(3\) - Statement of Deviation", None,
     _t("fund_raise", 0.8, "LOW", 22, "Use-of-proceeds statement")),
    (r"^Monitoring Agency Report", None, _t("fund_raise", 0.8, "LOW", 15, "Use-of-proceeds monitoring")),
    # Credit, dividends, corporate actions
    (r"^Credit Rating", None,
     _t("credit_rating", 0.95, "MEDIUM", 50, "Rating action. Upgrade/downgrade matters, reaffirmation doesn't",
        needs_reading=True)),
    (r"^(Dividend|Date of payment of Dividend)", None, _t("dividend", 0.95, "MEDIUM", 45, "Dividend declared")),
    (r"^Record Date", None, _t("dividend", 0.7, "LOW", 25, "Record date set for a corporate action")),
    (r"(Bonus|Split|Sub-division)", None, _t("bonus_split", 0.9, "MEDIUM", 55, "Share count change")),
    # Insider and promoter activity
    (r"Reg\. 31\(1\) and 31\(2\)", None,
     _t("pledging", 0.85, "HIGH", 75, "Promoter encumbrance (pledge) disclosure", needs_reading=True)),
    (r"(Reg\. 29\(|Reg\. 7\(|Insider)", None,
     _t("insider_trading", 0.85, "MEDIUM", 50, "Promoter or large-holder stake change", needs_reading=True)),
    (r"^Closure of Trading Window", None, _t("unclassified", 0.97, "LOW", 2, "Trading window closure. Routine")),
    # Investor communication
    (r"^Earnings Call Transcript", None,
     _t("earnings_call", 0.97, "MEDIUM", 40, "Transcript is out. Feeds the Promise Ledger", tags=["transcript"])),
    (r"^Investor Presentation", None, _t("results", 0.8, "MEDIUM", 38, "Results deck. Management's framing")),
    (r"^Analyst / Investor Meet", r"intimation",
     _t("investor_meetings", 0.95, "LOW", 10, "Investor meeting scheduled")),
    (r"^Analyst / Investor Meet", None,
     _t("investor_meetings", 0.9, "LOW", 18, "Investor meeting outcome or recording")),
    (r".*", r"(audio|video) recording|conference call|earnings call",
     _t("earnings_call", 0.85, "LOW", 15, "Call logistics or recording")),
    (r".*", r"investors?'*\s*(conference|meet|day|forum)|analyst meet|^presentation:",
     _t("investor_meetings", 0.8, "LOW", 10, "Investor meeting or conference")),
    # Business news
    (r"^Award of Order|Receipt of Order", None,
     _t("press_release", 0.9, "MEDIUM", 52, "Order win. Size relative to revenue decides importance",
        needs_reading=True)),
    (r"^Press Release", None,
     _t("press_release", 0.85, "LOW", 28, "Company press release", needs_reading=True)),
    (r"^Clarification$", None,
     _t("litigation", 0.5, "MEDIUM", 55, "Exchange sought a clarification", needs_reading=True)),
    (r".*", r"rumou?r verification",
     _t("press_release", 0.8, "MEDIUM", 45, "Company responding to a market rumour", needs_reading=True)),
    (r".*", r"(penalt|show cause|order of|tribunal|NCLT|SEBI order|tax demand|litigation|lawsuit)",
     _t("litigation", 0.75, "HIGH", 70, "Regulatory or legal matter", needs_reading=True)),
    (r".*", r"(capex|capacity expansion|new plant|greenfield|brownfield)",
     _t("capex", 0.8, "MEDIUM", 50, "Capacity investment", needs_reading=True)),
    # Meetings and compliance paperwork
    (r"^Postal Ballot", None, _t("postal_ballot", 0.95, "LOW", 12, "Postal ballot paperwork")),
    (r"^(AGM|EGM)", None, _t("agm_egm", 0.95, "LOW", 12, "Shareholder meeting paperwork")),
    (r"^(Certificate under Reg\. 74|Half Yearly Report|Business Responsibility|Reg\. 34 \(1\) Annual Report|"
     r"Amendments to Memorandum|Outcome without intimation)", None,
     _t("unclassified", 0.9, "LOW", 4, "Compliance filing. Routine")),
]

# Titles too generic to classify; the document has to be read.
OPAQUE_TITLE = re.compile(
    r"^(intimation|disclosure|announcement)s? under regulation 30|^general$|^updates?$|^media statement$|"
    r"^(intimation|disclosure)\b.{0,40}(regulation|SEBI|LODR|securities and exchange)", re.I)
PRESS_PREFIX = re.compile(r"^press release\s*(titled)?\s*[-:]?\s*", re.I)
RESULTS_DATE = re.compile(r"(to announce|announce).{0,40}results|board meeting.{0,60}(notice|intimation)", re.I)
# Words in a descriptive headline that suggest money, control or risk is involved
MATERIAL = re.compile(
    r"acqui|merger|amalgamat|demerg|stake|joint venture|\bJV\b|order|contract|crore|\bcr\b|million|billion|"
    r"\bdeal\b|penalt|fine\b|statement|clarif|regulat|government|tariff|ban\b|recall|fire|strike|shutdown|"
    r"capacity|plant|invest", re.I)
LOW_SIGNAL = re.compile(r"foundation|award|recogni|csr|webinar|research:|report:|launches|sponsor|partner", re.I)


def _triage_descriptive(title: str) -> Triage:
    """A 'General' filing whose headline says what it is (typical of company press desks)."""
    if RESULTS_DATE.search(title):
        return _t("results", 0.75, "LOW", 22, "Results date or board meeting notice. The numbers come later")
    if MATERIAL.search(title) and not LOW_SIGNAL.search(title):
        return _t("press_release", 0.6, "MEDIUM", 42, "Headline mentions money, deals or regulation. Worth a read",
                  needs_reading=True)
    return _t("press_release", 0.6, "LOW", 15, "Company news release. Headline says it all")


def triage(bse_category: str | None, bse_subcategory: str | None, title: str, critical: bool = False) -> Triage:
    sub = bse_subcategory or ""
    for sub_re, title_re, result in RULES:
        if re.search(sub_re, sub, re.I) and (title_re is None or re.search(title_re, title, re.I)):
            t = Triage(**{**result.__dict__, "tags": list(result.tags)})
            break
    else:
        headline = PRESS_PREFIX.sub("", title.strip())
        if not headline or OPAQUE_TITLE.search(headline):
            t = Triage("unclassified", 0.3, "LOW", 20,
                       "Generic filing. Its content decides what it is", "rules", needs_reading=True)
        else:
            t = _triage_descriptive(headline)
    if critical and t.priority == "LOW" and t.category != "unclassified":
        # BSE's own materiality flag lifts routine-looking items one level, never the reverse
        t.priority, t.score = "MEDIUM", max(t.score, 40)
        t.reason += " (BSE flagged it as critical)"
    return t
