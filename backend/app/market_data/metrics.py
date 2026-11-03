"""Deterministic EOD calculations. No LLM is ever involved in these numbers."""
from dataclasses import dataclass

VOLUME_LOOKBACK = 20


def pct_change(current: float | None, previous: float | None) -> float | None:
    """(current - previous) / |previous| * 100. None when the base is missing or zero.

    abs() keeps the sign meaningful when the base is negative (e.g. a loss narrowing from -100 to -50
    is +50%, an improvement), which matters for PAT comparisons in results.
    """
    if current is None or previous is None or previous == 0:
        return None
    return (current - previous) / abs(previous) * 100


@dataclass(frozen=True)
class SessionStats:
    date: str
    close: float
    prev_close: float | None
    return_pct: float | None
    volume: int | None
    avg_volume: float | None  # mean of the previous VOLUME_LOOKBACK sessions, excluding this one
    volume_multiple: float | None
    lookback_sessions: int


def session_stats(bars: list[dict], index: int, lookback: int = VOLUME_LOOKBACK) -> SessionStats:
    """Stats for bars[index]; bars must be sorted ascending by date with one bar per trading session."""
    bar = bars[index]
    prev = bars[index - 1] if index > 0 else None
    prior_vols = [b["volume"] for b in bars[max(0, index - lookback):index] if b.get("volume") is not None]
    full_window = len(prior_vols) == lookback
    avg = sum(prior_vols) / lookback if full_window else None
    vol = bar.get("volume")
    return SessionStats(
        date=bar["date"],
        close=bar["close"],
        prev_close=prev["close"] if prev else None,
        return_pct=pct_change(bar["close"], prev["close"] if prev else None),
        volume=vol,
        avg_volume=avg,
        volume_multiple=(vol / avg) if (avg and vol is not None) else None,
        lookback_sessions=len(prior_vols),
    )
