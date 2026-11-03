"""Shared HTTP access to public sources: one client, browser-like headers, per-host throttling."""
import threading
import time
from urllib.parse import urlparse

import httpx

from app.config import settings

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)
# BSE's CDN rejects requests without Accept-Language (verified during the data spike).
BASE_HEADERS = {
    "User-Agent": UA,
    "Accept": "application/json, text/html, application/pdf, */*",
    "Accept-Language": "en-US,en;q=0.9",
}


class SourceError(RuntimeError):
    """A public source failed or refused us. Callers surface this honestly instead of inventing data."""


_client = httpx.Client(headers=BASE_HEADERS, timeout=30, follow_redirects=True)
_last_hit: dict[str, float] = {}
_lock = threading.Lock()


def _throttle(host: str) -> None:
    with _lock:
        wait = _last_hit.get(host, 0) + settings.http_min_interval_s - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        _last_hit[host] = time.monotonic()


def get(url: str, *, headers: dict | None = None, retries: int = 2) -> httpx.Response:
    host = urlparse(url).netloc
    last_exc: Exception | None = None
    for attempt in range(retries + 1):
        _throttle(host)
        try:
            r = _client.get(url, headers=headers)
        except httpx.HTTPError as e:
            last_exc = e
        else:
            if r.status_code == 200:
                return r
            if r.status_code not in (429, 500, 502, 503, 504):
                raise SourceError(f"{host} returned HTTP {r.status_code}")
            last_exc = SourceError(f"{host} returned HTTP {r.status_code}")
        time.sleep(1.5 * (attempt + 1))
    raise SourceError(f"{host} unreachable: {last_exc}")
