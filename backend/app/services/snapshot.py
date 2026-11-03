"""Seed snapshot: derived data a fresh server can boot from.

Free hosts lose local files on restart, and exchange or price sources may refuse cloud IPs. A snapshot built
locally (prices, triaged filings with FINN's readings, alerts, research sections, the promise ledger) lets
the deployed demo show real, dated data immediately. It never contains downloaded PDFs or document text,
and every timestamp in it is preserved, so the UI shows exactly how old the data is.
"""
import gzip
import json

from app.config import settings
from app.database import db

TABLES = ["companies", "prices", "fetch_log", "announcements", "alerts", "kv", "research", "promises", "llm_calls"]
PATH = settings.seed_dir / "snapshot.json.gz"


def export(price_sessions: int = 140) -> dict:
    data = {"exported_at": db.now_iso(), "tables": {}}
    for t in TABLES:
        if t == "prices":
            rows = db.query("SELECT * FROM (SELECT p.*, ROW_NUMBER() OVER (PARTITION BY symbol ORDER BY date DESC) rn "
                            "FROM prices p) WHERE rn <= ?", (price_sessions,))
            for r in rows:
                r.pop("rn")
        elif t == "kv":
            rows = db.query("SELECT * FROM kv WHERE key != 'refresh_status'")
        else:
            rows = db.query(f"SELECT * FROM {t}")
        data["tables"][t] = rows
    settings.seed_dir.mkdir(parents=True, exist_ok=True)
    with gzip.open(PATH, "wt", encoding="utf-8") as f:
        json.dump(data, f, separators=(",", ":"))
    return {"path": str(PATH), "bytes": PATH.stat().st_size, **{t: len(r) for t, r in data["tables"].items()}}


def load_if_empty() -> dict | None:
    """Import the snapshot only into an empty database; never overwrite live data."""
    if not PATH.exists() or db.query_one("SELECT 1 FROM prices LIMIT 1"):
        return None
    with gzip.open(PATH, "rt", encoding="utf-8") as f:
        data = json.load(f)
    counts = {}
    with db.tx() as c:
        for t, rows in data["tables"].items():
            if t not in TABLES or not rows:
                continue
            cols = list(rows[0].keys())
            c.executemany(f"INSERT OR IGNORE INTO {t}({','.join(cols)}) VALUES ({','.join('?' * len(cols))})",
                          [tuple(r[k] for k in cols) for r in rows])
            counts[t] = len(rows)
    db.kv_set("snapshot_loaded", {"exported_at": data["exported_at"], "loaded_at": db.now_iso()})
    return counts
