"""On-demand research for any NSE ticker. Instant sections first, document work in a background job."""
import json
import threading
import traceback
import uuid

from app.database import db
from app.document_ingestion import service as docs
from app.llm import client as llm
from app.research import financials, ledger, synthesis
from app.sources import screener
from app.utils.http import SourceError

TRANSCRIPTS = 4
STEPS = ["Reading financial statements", "Finding annual report and transcripts", "Indexing annual report",
         "Indexing transcripts", "Extracting management promises", "Describing the business",
         "Weighing bull and bear case"]
_running: dict[str, str] = {}
_lock = threading.Lock()


def save_section(symbol: str, section: str, payload) -> None:
    db.execute("INSERT OR REPLACE INTO research(symbol, section, payload_json, updated_at) VALUES (?, ?, ?, ?)",
               (symbol, section, json.dumps(payload), db.now_iso()))


def sections(symbol: str) -> dict:
    return {r["section"]: {"data": json.loads(r["payload_json"]), "updated_at": r["updated_at"]}
            for r in db.query("SELECT * FROM research WHERE symbol = ?", (symbol,))}


def job(job_id: str) -> dict | None:
    r = db.query_one("SELECT * FROM jobs WHERE id = ?", (job_id,))
    if r:
        r["steps"] = json.loads(r.pop("steps_json"))
    return r


def latest_job(symbol: str) -> dict | None:
    r = db.query_one("SELECT id FROM jobs WHERE symbol = ? ORDER BY created_at DESC LIMIT 1", (symbol,))
    return job(r["id"]) if r else None


def _update(job_id: str, steps: list[dict], status: str = "running", error: str | None = None) -> None:
    db.execute("UPDATE jobs SET steps_json = ?, status = ?, error = ?, updated_at = ? WHERE id = ?",
               (json.dumps(steps), status, error, db.now_iso(), job_id))


def start(symbol: str, force: bool = False) -> dict:
    symbol = symbol.upper()
    with _lock:
        if symbol in _running:
            return job(_running[symbol])
        job_id = uuid.uuid4().hex[:12]
        steps = [{"name": s, "state": "pending", "detail": None} for s in STEPS]
        db.execute("INSERT INTO jobs(id, symbol, kind, status, steps_json, created_at, updated_at) "
                   "VALUES (?, ?, 'research', 'running', ?, ?, ?)",
                   (job_id, symbol, json.dumps(steps), db.now_iso(), db.now_iso()))
        _running[symbol] = job_id
    threading.Thread(target=_run, args=(job_id, symbol, force), daemon=True).start()
    return job(job_id)


def _run(job_id: str, symbol: str, force: bool) -> None:
    steps = job(job_id)["steps"]

    def step(i, state, detail=None):
        steps[i].update(state=state, detail=detail)
        _update(job_id, steps)

    try:
        step(0, "running")
        fin = financials.build(symbol)
        save_section(symbol, "financials", fin)
        step(0, "done", f"{fin['basis'].title()} statements, latest quarter {fin['snapshot']['period_label']}")

        step(1, "running")
        ars = [a for a in fin["documents"]["annual_reports"] if a["url"].lower().split("?")[0].endswith(".pdf")
               or "bseindia" in a["url"]]
        calls = [c for c in fin["documents"]["concalls"] if c["transcript_url"]][:TRANSCRIPTS]
        step(1, "done", f"{min(1, len(ars))} annual report, {len(calls)} transcripts")

        step(2, "running")
        ar_ids = []
        if ars:
            ar = ars[0]
            d = docs.ingest(symbol, "annual_report", f"{fin['name']} {ar['title']}", ar["url"],
                            period=f"FY{str(ar['fy'])[-2:]}" if ar["fy"] else None)
            if d["status"] == "ready":
                ar_ids.append(d["id"])
            step(2, "done" if ar_ids else "failed",
                 f"{d.get('pages') or 0} pages" if ar_ids else (d.get("error") or "Not readable"))
        else:
            step(2, "skipped", "No annual report link found")

        step(3, "running")
        transcripts = []
        for c in calls:
            label = screener.fiscal_label(ledger.quarter_discussed(c["period_key"])) if c["period_key"] else c["month"]
            d = docs.ingest(symbol, "transcript", f"{fin['name']} earnings call, {c['month']}", c["transcript_url"],
                            period=label)
            if d["status"] == "ready":
                transcripts.append((d, c["period_key"]))
        step(3, "done" if transcripts else "failed", f"{len(transcripts)} of {len(calls)} readable")

        doc_ids = ar_ids + [d["id"] for d, _ in transcripts]
        if not llm.available():
            for i in range(4, 7):
                step(i, "skipped", "AI reading is off: no API key configured")
            _update(job_id, steps, "done")
            return

        step(4, "running")
        led = ledger.build(symbol, fin, transcripts)
        save_section(symbol, "ledger", led)
        step(4, "done", f"{len(led['rows'])} verifiable promises from {len(transcripts)} calls")

        step(5, "running")
        try:
            biz = synthesis.business(symbol, ar_ids)
            if biz:
                save_section(symbol, "business", biz)
            step(5, "done" if biz else "skipped", None if biz else "No annual report text to describe")
        except llm.LLMUnavailable as e:
            step(5, "failed", str(e))

        step(6, "running")
        try:
            bb = synthesis.bull_bear(symbol, fin, led["rows"], doc_ids)
            save_section(symbol, "bull_bear", bb)
            step(6, "done", f"{len(bb['bull'])} bull, {len(bb['bear'])} bear points"
                            + (f"; {bb['dropped_uncited']} uncited point(s) removed" if bb["dropped_uncited"] else ""))
        except llm.LLMUnavailable as e:
            step(6, "failed", str(e))
        _update(job_id, steps, "done")
    except (SourceError, llm.LLMUnavailable) as e:
        for s in steps:
            if s["state"] == "running":
                s.update(state="failed", detail=str(e))
        _update(job_id, steps, "failed", str(e))
    except Exception as e:
        for s in steps:
            if s["state"] == "running":
                s.update(state="failed", detail="Unexpected error")
        _update(job_id, steps, "failed", f"{e}\n{traceback.format_exc()[-600:]}")
    finally:
        with _lock:
            _running.pop(symbol, None)
