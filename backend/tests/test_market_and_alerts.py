from datetime import datetime

import pytest

from app.alerts import engine
from app.config import IST
from app.market_data import yahoo
from app.market_data.metrics import pct_change, session_stats
from app.utils.http import SourceError
from tests.conftest import make_bars


def test_pct_change_basic_and_edge_cases():
    assert pct_change(110, 100) == pytest.approx(10.0)
    assert pct_change(95, 100) == pytest.approx(-5.0)
    assert pct_change(5, 0) is None
    assert pct_change(None, 100) is None
    # a loss narrowing from -100 to -50 is an improvement, so the change must be positive
    assert pct_change(-50, -100) == pytest.approx(50.0)


def test_daily_return_uses_previous_close():
    bars = make_bars([100, 104.5], [1, 1])
    assert session_stats(bars, 1).return_pct == pytest.approx(4.5)
    assert session_stats(bars, 0).return_pct is None


def test_average_volume_excludes_current_session():
    vols = [100] * 20 + [500]
    bars = make_bars([10] * 21, vols)
    s = session_stats(bars, 20)
    assert s.avg_volume == pytest.approx(100)  # the 500 spike must not dilute its own baseline
    assert s.volume_multiple == pytest.approx(5.0)
    assert s.lookback_sessions == 20


def test_no_volume_baseline_with_short_history():
    bars = make_bars([10] * 10, [100] * 9 + [900])
    s = session_stats(bars, 9)
    assert s.avg_volume is None and s.volume_multiple is None


SETTINGS = {**engine.DEFAULT_SETTINGS}


def stats_for(closes, vols):
    bars = make_bars(closes, vols)
    return session_stats(bars, len(bars) - 1)


def test_price_thresholds_trigger_at_boundaries():
    rules = lambda s: {t.rule for t in engine.evaluate_session(s, SETTINGS)}  # noqa: E731
    assert rules(stats_for([100] * 20 + [105], [1] * 21)) == {"price_up"}  # exactly +5% fires
    assert rules(stats_for([100] * 20 + [104.9], [1] * 21)) == set()
    assert rules(stats_for([100] * 20 + [95], [1] * 21)) == {"price_down"}
    assert rules(stats_for([100] * 20 + [95.1], [1] * 21)) == set()


def test_volume_threshold_and_disable_switch():
    s = stats_for([100] * 21, [100] * 20 + [250])
    assert [t.rule for t in engine.evaluate_session(s, SETTINGS)] == ["volume"]
    off = {**SETTINGS, "enabled": {**SETTINGS["enabled"], "volume": False}}
    assert engine.evaluate_session(s, off) == []


def test_custom_threshold_changes_outcome():
    s = stats_for([100] * 20 + [103], [1] * 21)
    assert engine.evaluate_session(s, SETTINGS) == []
    assert [t.rule for t in engine.evaluate_session(s, {**SETTINGS, "price_up_pct": 2.5})] == ["price_up"]


def test_settings_validation_rejects_nonsense():
    with pytest.raises(ValueError):
        engine.validate_settings({"volume_multiple": 0.5})
    with pytest.raises(ValueError):
        engine.validate_settings({"announcement_min_priority": "URGENT"})


def _seed_prices(fresh_db, symbol, closes, vols):
    fresh_db.execute("INSERT INTO companies(symbol, name, in_portfolio, added_at) VALUES (?, ?, 1, 'x')",
                     (symbol, symbol))
    for b in make_bars(closes, vols):
        fresh_db.execute("INSERT INTO prices(symbol, date, close, volume) VALUES (?, ?, ?, ?)",
                         (symbol, b["date"], b["close"], b["volume"]))


def test_scan_creates_alert_once_no_duplicates(fresh_db):
    _seed_prices(fresh_db, "AAA", [100] * 22 + [108], [100] * 22 + [300])
    first = engine.scan(["AAA"])
    assert first["new_alerts"] == 2  # price_up and volume on the last session
    again = engine.scan(["AAA"])
    assert again["new_alerts"] == 0
    rows = engine.list_alerts(symbol="AAA")
    assert sorted(r["rule"] for r in rows) == ["price_up", "volume"]
    up = next(r for r in rows if r["rule"] == "price_up")
    assert up["details"]["avg_volume"] == pytest.approx(100)
    assert "End-of-day" in up["details"]["basis"]


def test_announcement_alert_respects_category_and_priority(fresh_db):
    fresh_db.execute("INSERT INTO companies(symbol, name, in_portfolio, added_at) VALUES ('BBB', 'B', 1, 'x')")
    base = {"symbol": "BBB", "title": "t", "published_at": "2026-11-01T10:00:00+05:30", "pdf_url": "u"}
    assert engine.raise_announcement_alert({**base, "id": "1", "category": "results", "priority": "HIGH"})
    assert not engine.raise_announcement_alert({**base, "id": "1", "category": "results", "priority": "HIGH"})
    assert not engine.raise_announcement_alert({**base, "id": "2", "category": "dividend", "priority": "HIGH"})
    assert not engine.raise_announcement_alert({**base, "id": "3", "category": "results", "priority": "LOW"})


def _chart_payload(timestamps, closes, vols):
    return {"chart": {"result": [{
        "meta": {"longName": "Test Ltd", "currency": "INR"},
        "timestamp": timestamps,
        "indicators": {"quote": [{"open": closes, "high": closes, "low": closes, "close": closes,
                                  "volume": vols}],
                       "adjclose": [{"adjclose": closes}]},
    }]}}


class _Resp:
    def __init__(self, payload):
        self._p = payload

    def json(self):
        return self._p


def test_yahoo_drops_provisional_session_and_null_rows(monkeypatch):
    ts = [int(datetime(2026, 10, 30, 9, 15, tzinfo=IST).timestamp()),
          int(datetime(2026, 10, 31, 9, 15, tzinfo=IST).timestamp()),
          int(datetime(2026, 11, 2, 9, 15, tzinfo=IST).timestamp())]
    payload = _chart_payload(ts, [100.0, None, 101.0], [10, None, 20])
    monkeypatch.setattr(yahoo, "get", lambda url: _Resp(payload))
    during = yahoo.fetch_eod("TEST", now=datetime(2026, 11, 2, 11, 0, tzinfo=IST))
    assert [b["date"] for b in during["bars"]] == ["2026-10-30"]
    assert during["dropped_provisional_session"] == "2026-11-02"
    after = yahoo.fetch_eod("TEST", now=datetime(2026, 11, 2, 17, 0, tzinfo=IST))
    assert [b["date"] for b in after["bars"]] == ["2026-10-30", "2026-11-02"]


def test_yahoo_invalid_ticker_is_reported(monkeypatch):
    def boom(url):
        raise SourceError("query1.finance.yahoo.com returned HTTP 404")
    monkeypatch.setattr(yahoo, "get", boom)
    with pytest.raises(SourceError, match="not a valid NSE ticker"):
        yahoo.fetch_eod("TATAMOTORS")


def test_ticker_suffix():
    assert yahoo.yahoo_ticker("RELIANCE") == "RELIANCE.NS"
    assert yahoo.yahoo_ticker("RELIANCE.BO") == "RELIANCE.BO"
