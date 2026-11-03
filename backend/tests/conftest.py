import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import db  # noqa: E402


@pytest.fixture()
def fresh_db(tmp_path):
    db._conn = None
    db.connect(tmp_path / "test.sqlite3")
    yield db
    db._conn.close()
    db._conn = None


def make_bars(closes, volumes, start="2026-09-01"):
    from datetime import date, timedelta
    d0 = date.fromisoformat(start)
    return [{"date": (d0 + timedelta(days=i)).isoformat(), "open": c, "high": c, "low": c, "close": c,
             "adj_close": c, "volume": v} for i, (c, v) in enumerate(zip(closes, volumes))]
