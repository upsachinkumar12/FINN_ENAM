from app.database import db
from app.document_ingestion import pdf
from app.rag import store
from app.utils.http import SourceError

DOC_TYPES = ("annual_report", "transcript", "results", "presentation", "filing", "upload")


def ingest(symbol: str, doc_type: str, title: str, url: str, period: str | None = None,
           published_at: str | None = None, data: bytes | None = None) -> dict:
    """Idempotent: the same URL, or the same bytes under another URL, is processed once."""
    existing = db.query_one("SELECT * FROM documents WHERE source_url = ? AND symbol = ?", (url, symbol))
    if existing and existing["status"] == "ready":
        return existing
    try:
        data = data if data is not None else pdf.download(url)
    except SourceError as e:
        return _record_failure(symbol, doc_type, title, url, period, published_at, str(e))

    doc_id = pdf.sha256(data)[:24]
    same = db.query_one("SELECT * FROM documents WHERE id = ?", (doc_id,))
    if same and same["status"] == "ready":
        return same

    try:
        pages = pdf.extract_pages(data)
    except Exception as e:
        return _record_failure(symbol, doc_type, title, url, period, published_at, f"Unreadable PDF: {e}")
    quality = pdf.text_quality(pages)
    chunks = pdf.chunk_pages(pages)
    db.execute(
        "INSERT OR REPLACE INTO documents(id, symbol, doc_type, period, title, source_url, published_at, pages, "
        "chars, text_quality, status, error, ingested_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'indexing', NULL, ?)",
        (doc_id, symbol, doc_type, period, title, url, published_at, len(pages), sum(len(p.text) for p in pages),
         quality, db.now_iso()),
    )
    store.add_chunks(doc_id, symbol, chunks)
    status = "ready" if chunks else "no_text"
    db.execute("UPDATE documents SET status = ?, error = ? WHERE id = ?",
               (status, None if chunks else "No extractable text (image-only scan)", doc_id))
    return db.query_one("SELECT * FROM documents WHERE id = ?", (doc_id,))


def _record_failure(symbol, doc_type, title, url, period, published_at, error) -> dict:
    fake_id = "failed:" + pdf.sha256(url.encode())[:20]
    db.execute(
        "INSERT OR REPLACE INTO documents(id, symbol, doc_type, period, title, source_url, published_at, status, "
        "error, ingested_at) VALUES (?, ?, ?, ?, ?, ?, ?, 'failed', ?, ?)",
        (fake_id, symbol, doc_type, period, title, url, published_at, error, db.now_iso()))
    return db.query_one("SELECT * FROM documents WHERE id = ?", (fake_id,))


def page_text(doc_id: str, page: int) -> str:
    rows = db.query("SELECT text FROM chunks WHERE doc_id = ? AND page = ? ORDER BY seq", (doc_id, page))
    return "\n".join(r["text"] for r in rows)


def list_for(symbol: str) -> list[dict]:
    return db.query("SELECT id, doc_type, period, title, source_url, published_at, pages, text_quality, status, "
                    "error, ingested_at FROM documents WHERE symbol = ? ORDER BY published_at DESC, ingested_at DESC",
                    (symbol,))
