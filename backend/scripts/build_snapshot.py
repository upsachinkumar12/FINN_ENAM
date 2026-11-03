"""Refresh everything locally, read pending filings, then write backend/seed/snapshot.json.gz.

    python scripts/build_snapshot.py               # prices, 30 days of filings, AI reading if a key is set
    python scripts/build_snapshot.py --research HAL BEL   # also build full research for these symbols
"""
import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.announcements import enrich  # noqa: E402
from app.database import db  # noqa: E402
from app.llm import client as llm  # noqa: E402
from app.research import jobs  # noqa: E402
from app.services import companies, refresh, snapshot  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=30)
    ap.add_argument("--research", nargs="*", default=[])
    a = ap.parse_args()

    db.connect()
    companies.seed_defaults()
    print("refresh:", refresh.run(days=a.days, enrich=False)["state"])
    if llm.available():
        print("enrich:", enrich.enrich_pending(days=a.days, limit=400))
    for sym in a.research:
        j = jobs.start(sym)
        while (j := jobs.job(j["id"]))["status"] == "running":
            time.sleep(3)
        print(f"research {sym}:", j["status"], [(s["name"], s["state"]) for s in j["steps"]])
    print("snapshot:", snapshot.export())
    print("llm spend so far:", llm.cost_summary()["total"])


if __name__ == "__main__":
    main()
