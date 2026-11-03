from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field

from app.database import db
from app.document_ingestion import service as docs
from app.llm import client as llm
from app.rag import store
from app.research import chat, financials, jobs
from app.services import companies
from app.utils.http import SourceError

router = APIRouter(prefix="/api")


def _stale(updated_at: str, hours: float = 12) -> bool:
    from datetime import datetime, timedelta
    from app.config import IST
    return datetime.fromisoformat(updated_at) < datetime.now(IST) - timedelta(hours=hours)


@router.get("/company/{symbol}")
def company(symbol: str):
    symbol = symbol.upper()
    known = db.query_one("SELECT * FROM companies WHERE symbol = ?", (symbol,))
    if not known:
        v = companies.validate_ticker(symbol)
        if not v["valid"]:
            raise HTTPException(404, v["error"])
        res = companies.add_company(symbol, in_portfolio=False)
        known = res.get("company")
    secs = jobs.sections(symbol)
    if "financials" not in secs or _stale(secs["financials"]["updated_at"]):
        try:
            jobs.save_section(symbol, "financials", financials.build(symbol))
        except SourceError as e:
            raise HTTPException(502, f"Couldn't load reported financials: {e}")
        secs = jobs.sections(symbol)
    return {"company": known, "sections": secs, "job": jobs.latest_job(symbol), "documents": docs.list_for(symbol),
            "llm_configured": llm.available()}


@router.post("/research/{symbol}/generate")
def generate(symbol: str, force: bool = False):
    return jobs.start(symbol.upper(), force)


@router.get("/research/jobs/{job_id}")
def research_job(job_id: str):
    j = jobs.job(job_id)
    if not j:
        raise HTTPException(404, "Unknown job")
    return j


@router.get("/research/{symbol}")
def research_sections(symbol: str):
    return {"sections": jobs.sections(symbol.upper()), "job": jobs.latest_job(symbol.upper())}


class Ask(BaseModel):
    message: str = Field(min_length=2, max_length=600)
    symbol: str | None = None


@router.post("/research/chat")
def ask(body: Ask):
    out = chat.answer(body.message, body.symbol)
    ids = out.get("cards") or []
    from app.announcements import service as ann
    out["cards"] = [a for a in (ann.get(i) for i in ids) if a]
    if out.get("moves"):
        from app.alerts import engine
        wanted = set(out["moves"])
        out["moves"] = [a for a in engine.list_alerts(300) if a["id"] in wanted]
    return out


@router.post("/documents/upload")
async def upload(symbol: str = Form(...), doc_type: str = Form("upload"), title: str = Form(...),
                 period: str | None = Form(None), file: UploadFile = File(...)):
    if doc_type not in docs.DOC_TYPES:
        raise HTTPException(422, f"doc_type must be one of {', '.join(docs.DOC_TYPES)}")
    data = await file.read()
    if not data.startswith(b"%PDF"):
        raise HTTPException(422, "Only PDF files are accepted")
    if len(data) > 60 * 1024 * 1024:
        raise HTTPException(413, "PDF larger than 60 MB")
    d = docs.ingest(symbol.upper(), doc_type, title, f"upload://{file.filename}", period=period, data=data)
    return d


class ImportUrl(BaseModel):
    symbol: str
    url: str
    title: str
    doc_type: str = "filing"
    period: str | None = None


@router.post("/documents/import")
def import_url(body: ImportUrl):
    if not body.url.startswith("https://"):
        raise HTTPException(422, "Only https links are accepted")
    if body.doc_type not in docs.DOC_TYPES:
        raise HTTPException(422, f"doc_type must be one of {', '.join(docs.DOC_TYPES)}")
    return docs.ingest(body.symbol.upper(), body.doc_type, body.title, body.url, period=body.period)


@router.get("/documents/{symbol}")
def documents(symbol: str):
    return {"documents": docs.list_for(symbol.upper()), "vector_index": store.vector_status()}


@router.get("/costs")
def costs():
    return llm.cost_summary()
