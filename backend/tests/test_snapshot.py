from app.services import snapshot
from tests.conftest import make_bars


def test_snapshot_roundtrip_keeps_recent_prices_and_never_overwrites(fresh_db, tmp_path, monkeypatch):
    monkeypatch.setattr(snapshot, "PATH", tmp_path / "snap.json.gz")
    fresh_db.execute("INSERT INTO companies(symbol, name, in_portfolio, added_at) VALUES ('AAA', 'A', 1, 'x')")
    for b in make_bars([10.0] * 200, [1] * 200, start="2026-01-01"):
        fresh_db.execute("INSERT INTO prices(symbol, date, close, volume) VALUES ('AAA', ?, ?, ?)",
                         (b["date"], b["close"], b["volume"]))
    out = snapshot.export(price_sessions=140)
    assert out["prices"] == 140 and out["companies"] == 1

    fresh_db.execute("DELETE FROM prices")
    fresh_db.execute("DELETE FROM companies")
    loaded = snapshot.load_if_empty()
    assert loaded["prices"] == 140
    assert fresh_db.query_one("SELECT MAX(date) d FROM prices")["d"] == "2026-07-19"
    assert snapshot.load_if_empty() is None  # a database with data is never overwritten
