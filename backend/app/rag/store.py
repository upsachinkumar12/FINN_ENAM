"""Hybrid retrieval over primary documents: SQLite FTS5 (exact terms and figures) + Chroma (meaning),
merged with reciprocal-rank fusion. If the vector index is unavailable, keyword search still works."""
import logging
import re
import threading

from app.config import settings
from app.database import db

log = logging.getLogger(__name__)
_collection = None
_lock = threading.Lock()
_vector_error: str | None = None


def _vectors():
    """Chroma with its built-in local ONNX embedding model: no API key, no per-call cost."""
    global _collection, _vector_error
    if not settings.vector_search:
        _vector_error = "switched off on this host (VECTOR_SEARCH=false); keyword search only"
    if _collection is not None or _vector_error:
        return _collection
    with _lock:
        if _collection is None and not _vector_error:
            try:
                import chromadb
                client = chromadb.PersistentClient(path=str(settings.chroma_dir))
                _collection = client.get_or_create_collection("chunks", metadata={"hnsw:space": "cosine"})
            except Exception as e:  # missing model download, disk, platform issues
                _vector_error = str(e)
                log.warning("Vector index unavailable, keyword retrieval only: %s", e)
    return _collection


def vector_status() -> dict:
    return {"available": _vectors() is not None, "error": _vector_error}


def add_chunks(doc_id: str, symbol: str, chunks: list[tuple[int, str]]) -> int:
    rows = [(f"{doc_id}:{i}", doc_id, symbol, page, i, text) for i, (page, text) in enumerate(chunks)]
    with db.tx() as c:
        c.executemany("INSERT OR IGNORE INTO chunks(id, doc_id, symbol, page, seq, text) VALUES (?, ?, ?, ?, ?, ?)",
                      rows)
    col = _vectors()
    if col is not None and rows:
        try:
            for i in range(0, len(rows), 64):  # small batches keep peak memory low
                batch = rows[i:i + 64]
                col.upsert(ids=[r[0] for r in batch], documents=[r[5] for r in batch],
                           metadatas=[{"doc_id": r[1], "symbol": r[2], "page": r[3]} for r in batch])
        except Exception as e:
            log.warning("Embedding failed for %s; keyword search still covers it: %s", doc_id, e)
    return len(rows)


def _fts_query(q: str) -> str:
    terms = [t for t in re.findall(r"[A-Za-z0-9]{2,}", q.lower()) if t not in _STOP]
    return " OR ".join(f'"{t}"' for t in terms[:24])


_STOP = set("the a an and or of to in on for with is are was were be by at as it its this that what which how did "
            "does do has have had from their they them company management about over last four quarters year".split())


def search(query: str, symbol: str, k: int = 8, doc_ids: list[str] | None = None,
           doc_types: list[str] | None = None) -> list[dict]:
    where = ["c.symbol = ?"]
    params: list = [symbol]
    if doc_ids:
        where.append(f"c.doc_id IN ({','.join('?' * len(doc_ids))})")
        params += doc_ids
    if doc_types:
        where.append(f"d.doc_type IN ({','.join('?' * len(doc_types))})")
        params += doc_types
    allowed_sql = " AND ".join(where)

    ranked: dict[str, float] = {}
    fq = _fts_query(query)
    if fq:
        rows = db.query(
            f"SELECT c.id FROM chunks_fts f JOIN chunks c ON c.rowid = f.rowid JOIN documents d ON d.id = c.doc_id "
            f"WHERE chunks_fts MATCH ? AND {allowed_sql} ORDER BY bm25(chunks_fts) LIMIT 30", (fq, *params))
        for rank, r in enumerate(rows):
            ranked[r["id"]] = ranked.get(r["id"], 0) + 1 / (60 + rank)

    col = _vectors()
    if col is not None:
        try:
            filt: dict = {"symbol": symbol}
            if doc_ids:
                filt = {"$and": [{"symbol": symbol}, {"doc_id": {"$in": doc_ids}}]}
            res = col.query(query_texts=[query], n_results=30, where=filt)
            allowed = None
            if doc_types:
                allowed = {r["id"] for r in db.query(
                    f"SELECT d.id FROM documents d WHERE d.symbol = ? AND d.doc_type IN "
                    f"({','.join('?' * len(doc_types))})", (symbol, *doc_types))}
            for rank, cid in enumerate(res["ids"][0]):
                if allowed is not None and cid.rsplit(":", 1)[0] not in allowed:
                    continue
                ranked[cid] = ranked.get(cid, 0) + 1 / (60 + rank)
        except Exception as e:
            log.warning("Vector query failed: %s", e)

    top = sorted(ranked, key=ranked.get, reverse=True)[:k]
    if not top:
        return []
    rows = {r["id"]: r for r in db.query(
        f"SELECT c.id, c.doc_id, c.page, c.text, d.title, d.doc_type, d.period, d.source_url "
        f"FROM chunks c JOIN documents d ON d.id = c.doc_id WHERE c.id IN ({','.join('?' * len(top))})", tuple(top))}
    return [rows[i] for i in top if i in rows]
