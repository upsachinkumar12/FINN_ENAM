"""Deterministic research sections from the standardised statements (screener.in, compiled from filings).

Nothing here touches a model: every number is read or computed, and every observation is a rule over
those numbers. EBITDA uses screener's "Operating Profit" (sales minus operating expenses, excluding other
income); banks have no EBITDA, so their equivalent rows are labelled for what they are.
"""
from app.market_data.metrics import pct_change
from app.sources import screener


def _row(table: dict, *names: str) -> list[float | None]:
    for n in names:
        if n in table["rows"]:
            return table["rows"][n]
    return [None] * len(table["periods"])


def _at(xs: list, i: int):
    return xs[i] if -len(xs) <= i < len(xs) else None


def _cagr(first, last, years) -> float | None:
    if first is None or last is None or first <= 0 or last <= 0 or years <= 0:
        return None
    return ((last / first) ** (1 / years) - 1) * 100


def _ratio(a, b) -> float | None:
    return None if a is None or b in (None, 0) else a / b


def build(symbol: str) -> dict:
    co = screener.fetch_company(symbol)
    q, a, bs, cf, rt = co["quarters"], co["annual"], co["balance_sheet"], co["cash_flow"], co["ratios"]
    is_bank = "Financing Profit" in q["rows"] or "Financing Profit" in a["rows"]

    # ---- latest quarter vs previous quarter and the same quarter last year ----
    q_rev = _row(q, "Sales", "Revenue")
    q_ebitda = _row(q, "Operating Profit", "Financing Profit")
    q_pbt = _row(q, "Profit before tax")
    q_pat = _row(q, "Net Profit")
    q_margin = _row(q, "OPM %", "Financing Margin %")
    n = len(q["periods"])
    cur = n - 1
    while cur >= 0 and q_rev[cur] is None:  # skip trailing empty columns
        cur -= 1

    def snap(series, label, note=None):
        c, p, y = _at(series, cur), _at(series, cur - 1) if cur >= 1 else None, _at(series, cur - 4) if cur >= 4 else None
        return {"metric": label, "current": c, "prev_q": p, "year_ago": y,
                "qoq": pct_change(c, p), "yoy": pct_change(c, y), "note": note}

    if is_bank:
        # Banks have no EBITDA; asset quality (bad-loan ratios) is the operating lens instead.
        rows = [snap(q_rev, "Revenue", "Total revenue: interest earned plus other operating income"),
                snap(q_pbt, "PBT"), snap(q_pat, "PAT")]
        npa = [snap(_row(q, "Gross NPA %"), "Gross NPA %", "Share of loans not being repaid, before provisions"),
               snap(_row(q, "Net NPA %"), "Net NPA %", "Bad loans net of provisions already set aside")]
        rows += [r for r in npa if r["current"] is not None]
        if len(rows) == 3:
            rows[-1]["note"] = "Bad-loan (NPA) ratios are published on the standalone basis only"
        margin = None
    else:
        rows = [snap(q_rev, "Revenue"),
                snap(q_ebitda, "EBITDA", "Operating profit before other income, depreciation, interest and tax"),
                snap(q_pbt, "PBT"), snap(q_pat, "PAT")]
        margin = {"label": "EBITDA margin", "current": _at(q_margin, cur),
                  "prev_q": _at(q_margin, cur - 1) if cur >= 1 else None,
                  "year_ago": _at(q_margin, cur - 4) if cur >= 4 else None}
    snapshot = {
        "period": q["periods"][cur] if cur >= 0 else None,
        "period_label": screener.fiscal_label(screener.period_key(q["periods"][cur])) if cur >= 0 else None,
        "prev_label": q["periods"][cur - 1] if cur >= 1 else None,
        "year_ago_label": q["periods"][cur - 4] if cur >= 4 else None,
        "rows": rows,
        "margin": margin,
    }

    quarterly = [{"period": q["periods"][i], "label": screener.fiscal_label(screener.period_key(q["periods"][i]) or ""),
                  "revenue": q_rev[i], "ebitda": None if is_bank else q_ebitda[i], "pat": q_pat[i],
                  "margin": None if is_bank else q_margin[i]}
                 for i in range(max(0, cur - 11), cur + 1)]

    # ---- multi-year ----
    years = [p for p in a["periods"] if p != "TTM"]
    ny = len(years)
    a_rev, a_ebitda, a_pat = _row(a, "Sales", "Revenue")[:ny], _row(a, "Operating Profit", "Financing Profit")[:ny], _row(a, "Net Profit")[:ny]
    a_margin = _row(a, "OPM %", "Financing Margin %")[:ny]

    def by_year(table, *names):
        vals = dict(zip(table["periods"], _row(table, *names)))
        return [vals.get(y) for y in years]

    cfo = by_year(cf, "Cash from Operating Activity")
    fcf = by_year(cf, "Free Cash Flow")
    borrow = by_year(bs, "Borrowings", "Borrowing")
    eq_cap, reserves = by_year(bs, "Equity Capital"), by_year(bs, "Reserves")
    equity = [None if c is None or r is None else c + r for c, r in zip(eq_cap, reserves)]
    roce = by_year(rt, "ROCE %")
    wc_days = by_year(rt, "Working Capital Days")
    ccc = by_year(rt, "Cash Conversion Cycle")

    annual = []
    for i, y in enumerate(years):
        annual.append({
            "year": y, "label": "FY" + y[-2:], "revenue": a_rev[i], "ebitda": None if is_bank else a_ebitda[i],
            "pat": a_pat[i], "margin": None if is_bank else a_margin[i], "cfo": cfo[i], "fcf": fcf[i],
            "borrowings": borrow[i], "equity": equity[i],
            "de": None if is_bank else _ratio(borrow[i], equity[i]), "roce": roce[i], "wc_days": wc_days[i],
            "ccc": ccc[i], "cfo_to_pat": _ratio(cfo[i], a_pat[i]),
        })

    return {
        "symbol": symbol,
        "name": co["name"],
        "basis": co["basis"],
        "is_bank": is_bank,
        "source": {"name": "screener.in (standardised from company filings)", "url": co["source_url"],
                   "fetched_at": co["fetched_at"], "unit": "₹ crore"},
        "key_ratios": {k: co["top_ratios"].get(k) for k in ("Market Cap", "Current Price", "Stock P/E", "ROCE", "ROE",
                                                             "Dividend Yield", "Book Value")},
        "snapshot": snapshot,
        "quarterly": quarterly,
        "annual": annual[-10:],
        "observations": observations(annual, is_bank),
        "documents": co["documents"],
        "bse_code": co["bse_code"],
    }


def observations(annual: list[dict], is_bank: bool) -> dict[str, list[str]]:
    """Rule-based statements over the numbers, grouped by research section."""
    out: dict[str, list[str]] = {"trajectory": [], "balance_sheet": [], "cash_quality": []}
    rows = [r for r in annual if r["revenue"] is not None]
    if len(rows) >= 4:
        last, base3 = rows[-1], rows[-4]
        c3 = _cagr(base3["revenue"], last["revenue"], 3)
        if c3 is not None:
            out["trajectory"].append(f"Revenue compounded {c3:.1f}% a year over {base3['label']}–{last['label']}.")
        p3 = _cagr(base3["pat"], last["pat"], 3)
        if p3 is not None and p3 < 0:
            out["trajectory"].append(f"Profit after tax shrank {abs(p3):.1f}% a year over the same period"
                                     f"{' even as revenue grew' if c3 and c3 > 0 else ''}.")
        elif p3 is not None:
            faster = "faster" if c3 is not None and p3 > c3 else "slower"
            out["trajectory"].append(f"Profit after tax compounded {p3:.1f}% a year, {faster} than revenue.")
        elif base3["pat"] is not None and last["pat"] is not None:
            out["trajectory"].append(f"PAT moved from ₹{base3['pat']:,.0f} cr to ₹{last['pat']:,.0f} cr over {base3['label']}–{last['label']}.")
        if base3["margin"] is not None and last["margin"] is not None:
            d = last["margin"] - base3["margin"]
            word = "expanded" if d > 0.5 else "compressed" if d < -0.5 else "held roughly flat"
            out["trajectory"].append(f"Operating margin {word}: {base3['margin']:.0f}% in {base3['label']} → {last['margin']:.0f}% in {last['label']}.")
        ups = sum(1 for x, y in zip(rows[-6:], rows[-5:]) if x["revenue"] and y["revenue"] and y["revenue"] > x["revenue"])
        out["trajectory"].append(f"Revenue rose in {ups} of the last {min(5, len(rows) - 1)} years.")

    if not is_bank:
        bs = [r for r in annual if r["borrowings"] is not None and r["equity"]]
        if len(bs) >= 2:
            f, l = bs[-4] if len(bs) >= 4 else bs[0], bs[-1]
            out["balance_sheet"].append(
                f"Borrowings ₹{f['borrowings']:,.0f} cr ({f['label']}) → ₹{l['borrowings']:,.0f} cr ({l['label']}); "
                f"debt-to-equity {f['de']:.2f} → {l['de']:.2f}.")
        wc = [r for r in annual if r["wc_days"] is not None]
        if len(wc) >= 3:
            f, l = wc[-3], wc[-1]
            trend = "lengthened" if l["wc_days"] > f["wc_days"] + 5 else "shortened" if l["wc_days"] < f["wc_days"] - 5 else "was stable"
            out["balance_sheet"].append(f"Working-capital cycle {trend}: {f['wc_days']:.0f} → {l['wc_days']:.0f} days.")

    cash = [r for r in annual if r["cfo"] is not None and r["pat"] not in (None, 0)][-5:]
    if len(cash) >= 3:
        conv = sum(r["cfo"] for r in cash) / sum(r["pat"] for r in cash)
        verdict = ("profits are turning into cash" if conv >= 0.9 else
                   "a meaningful share of profit isn't showing up as cash" if conv < 0.7 else "conversion is middling")
        out["cash_quality"].append(f"Over {cash[0]['label']}–{cash[-1]['label']}, operating cash flow was "
                                   f"{conv * 100:.0f}% of reported profit: {verdict}.")
        neg = [r["label"] for r in cash if r["fcf"] is not None and r["fcf"] < 0]
        if neg:
            out["cash_quality"].append(f"Free cash flow was negative in {', '.join(neg)}.")
    if is_bank:
        out["cash_quality"].append("Cash-flow conversion isn't a meaningful lens for a bank; deposits and lending dominate its cash flows.")
    return out
