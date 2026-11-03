"""Ask FINN. Routing is rules-first so most questions never need a model:
portfolio questions -> database, "why did it move" -> prices + filings, number comparisons -> computed
tables, anything about what management or the documents say -> retrieval with cited answers."""
import re
from datetime import datetime, timedelta

from app.alerts import engine as alerts
from app.announcements import service as announcements
from app.config import IST
from app.database import db
from app.llm import client as llm
from app.llm.client import Source
from app.market_data import service as market
from app.rag import store
from app.research import jobs
from app.research.synthesis import GROUNDING

PORTFOLIO = re.compile(r"\b(my portfolio|portfolio|today|this week|developments|what (?:changed|happened)|"
                       r"anything important|brief me)\b", re.I)
MOVE = re.compile(r"\b(why|what).{0,40}\b(volume|price|stock|shares?)\b.{0,30}\b(jump|spike|move|moved|fall|fell|"
                  r"rise|rose|drop|dropped|increase|increased|surge|crash|up|down)|\bunusual\b", re.I)
NUMBERS = re.compile(r"\b(compare|last (?:four|4|eight|8) quarters|quarter(?:ly)? (?:revenue|profit|numbers)|"
                     r"revenue trend|margin trend|qoq|yoy)\b", re.I)
DOC_HINT = re.compile(r"management|promise|guid|said|call|transcript|annual report|risk|strategy|why|explain|"
                      r"segment|capex|plan|disclos|auditor|contingent|related party", re.I)


def resolve_symbol(message: str, context: str | None) -> str | None:
    companies = db.query("SELECT symbol, name FROM companies")
    text = message.upper()
    for c in sorted(companies, key=lambda c: -len(c["symbol"])):
        if re.search(rf"\b{re.escape(c['symbol'])}\b", text):
            return c["symbol"]
    low = message.lower()
    firsts: dict[str, list[str]] = {}
    for c in companies:
        firsts.setdefault(c["name"].lower().split()[0], []).append(c["symbol"])
    for word, syms in firsts.items():
        # "Tata" or "Hindustan" names several companies; only unambiguous first words identify one
        if len(syms) == 1 and len(word) > 3 and re.search(rf"\b{re.escape(word)}\b", low):
            return syms[0]
    return context.upper() if context else None


def answer(message: str, context_symbol: str | None = None) -> dict:
    if re.search(r"\bportfolio\b|\bbrief me\b", message, re.I):
        return _portfolio()
    sym = resolve_symbol(message, context_symbol)
    if MOVE.search(message) and sym:
        return _move(sym)
    if NUMBERS.search(message) and sym and not DOC_HINT.search(message.replace("quarter", "")):
        return _numbers(sym)
    if sym:
        return _documents(sym, message)
    return _portfolio()


def _text(t: str) -> list[dict]:
    return [{"text": t, "citations": []}]


def _portfolio() -> dict:
    d = announcements.digest(24)
    hours = 24
    if not d["must_read"] and not d["worth_a_look"]:
        d, hours = announcements.digest(72), 72
    lines = []
    if d["must_read"]:
        lines.append(f"{len(d['must_read'])} must-read item(s) across your portfolio in the last {hours} hours:")
    elif d["worth_a_look"]:
        lines.append(f"Nothing must-read in the last {hours} hours; {len(d['worth_a_look'])} item(s) worth a look:")
    else:
        lines.append(f"Nothing material in the last {hours} hours.")
    s = alerts.get_settings()
    last = db.query_one("SELECT MAX(trade_date) d FROM alerts WHERE rule NOT LIKE 'announcement:%'")
    moves = [a for a in alerts.list_alerts(300) if a["kind"] != "announcement" and a["trade_date"] == (last or {}).get("d")]
    if moves:
        lines.append(f"{len({m['symbol'] for m in moves})} stock(s) crossed your price/volume thresholds "
                     f"(±{s['price_up_pct']:g}% / {s['volume_multiple']:g}× volume) at the {last['d']} close.")
    return {"intent": "portfolio", "symbol": None, "segments": _text(" ".join(lines)),
            "cards": [a["id"] for a in (d["must_read"] or d["worth_a_look"])[:5]],
            "moves": [m["id"] for m in moves[:6]], "basis": "FINN's filing triage and your alert rules. No model call."}


def _move(sym: str) -> dict:
    stats = market.latest_stats(sym)
    if not stats:
        market.refresh_prices(sym)
        stats = market.latest_stats(sym)
    if not stats:
        return {"intent": "move", "symbol": sym, "segments": _text(f"No price data available for {sym}.")}
    since = (datetime.fromisoformat(stats["date"]) - timedelta(days=4)).replace(tzinfo=IST).isoformat()
    filings = [a for a in announcements.list_window(since=since, symbols=[sym], portfolio_only=False)
               if a["priority"] in ("HIGH", "MEDIUM")]
    vm = stats["volume_multiple"]
    t = (f"{sym} closed at ₹{stats['close']:,.2f} on {stats['date']}, "
         f"{stats['return_pct']:+.2f}% on the day" if stats["return_pct"] is not None else f"{sym} closed {stats['date']}")
    if vm is not None:
        t += f", on {vm:.1f}× its 20-session average volume"
    t += ". "
    if filings:
        t += (f"FINN found {len(filings)} filing(s) from the days around this move, listed below. "
              "They are possibly related, but exchange data alone can't establish why a stock moved.")
    else:
        t += ("There's no material filing from the company in the days around it, so the move isn't explained "
              "by anything it disclosed. FINN doesn't use news or broker commentary to guess.")
    return {"intent": "move", "symbol": sym, "segments": _text(t), "cards": [f["id"] for f in filings[:4]],
            "basis": "End-of-day prices (Yahoo Finance) and exchange filings. No model call."}


def _numbers(sym: str) -> dict:
    sec = jobs.sections(sym).get("financials")
    if not sec:
        from app.research import financials
        fin = financials.build(sym)
        jobs.save_section(sym, "financials", fin)
    else:
        fin = sec["data"]
    q = fin["quarterly"][-4:]
    table = {"columns": ["Quarter", "Revenue", "EBITDA" if not fin["is_bank"] else "—", "PAT", "Margin"],
             "rows": [[r["label"], r["revenue"], r["ebitda"], r["pat"], r["margin"]] for r in q]}
    first, last = q[0], q[-1]
    t = f"{fin['name']}, last four reported quarters ({fin['basis']}, ₹ crore)."
    if first["revenue"] and last["revenue"]:
        t += f" Revenue went from ₹{first['revenue']:,.0f} cr in {first['label']} to ₹{last['revenue']:,.0f} cr in {last['label']}."
    return {"intent": "numbers", "symbol": sym, "segments": _text(t), "table": table,
            "basis": f"Reported statements via screener.in ({fin['source']['url']}). Calculated, no model call."}


def _documents(sym: str, message: str) -> dict:
    have = db.query_one("SELECT COUNT(*) n FROM documents WHERE symbol = ? AND status = 'ready'", (sym,))["n"]
    if not have:
        j = jobs.start(sym)
        return {"intent": "documents", "symbol": sym, "job_id": j["id"],
                "segments": _text(f"FINN hasn't read {sym}'s annual report and earnings calls yet. It's fetching and "
                                  "indexing them now (about a minute). Ask again once Research shows them as ready.")}
    if not llm.available():
        return {"intent": "documents", "symbol": sym, "segments": _text(
            "Answering from documents needs the AI model, which is switched off (no API key configured).")}
    rows = store.search(message, sym, k=10)
    if not rows:
        return {"intent": "documents", "symbol": sym, "segments": _text(
            "Nothing in the indexed annual report or transcripts addresses that, so FINN can't answer it from primary sources.")}
    sources = [Source(r["doc_id"], r["title"], r["doc_type"], r.get("period"), r["page"], r["source_url"], r["text"])
               for r in rows]
    try:
        out = llm.cited("chat", "strong", GROUNDING + """
Answer the investor's question in at most 150 words, plain sentences, most important point first.
Cite the passages you rely on. If the documents don't answer the question, say exactly what is missing rather than guessing.""",
                        sources, message, max_tokens=1200, effort="low")
    except llm.LLMUnavailable as e:
        return {"intent": "documents", "symbol": sym, "segments": _text(f"FINN couldn't answer: {e}")}
    cited = sum(1 for s in out["segments"] if s["citations"])
    return {"intent": "documents", "symbol": sym, "segments": out["segments"], "model": out["model"],
            "basis": f"Retrieved {len(rows)} passages from {sym}'s annual report and call transcripts; "
                     f"{cited} cited statement(s).", "grounded": cited > 0}
