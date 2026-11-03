"""The only module that talks to the model API.

Routing: "cheap" (Haiku) for bulk reading and extraction, "strong" (Sonnet) for multi-document reasoning.
Every call is cached by a hash of its full input, and logged with real token usage and cost.
"""
import hashlib
import json
import threading
from dataclasses import dataclass
from typing import Any, Literal

import anthropic

from app.config import settings
from app.database import db

Tier = Literal["cheap", "strong"]

# USD per million tokens: (input, output). Cache writes bill at 1.25x input, cache reads at 0.1x.
PRICES = {
    "claude-haiku-5-5": (0.10, 0.50),
    "claude-sonnet-5-5": (2.00, 10.00),
    "claude-opus-5-5": (4.00, 20.00),
}
# Server-side refusal fallback for the strong tier (reroutes a declined request to another model).
FALLBACK_BETA = "server-side-fallback-2026-07-01"


class LLMUnavailable(RuntimeError):
    """No key configured, or the model API refused / failed. Callers show this honestly."""


_client: anthropic.Anthropic | None = None
_lock = threading.Lock()


def available() -> bool:
    return bool(settings.llm_enabled and settings.anthropic_api_key)


def _get() -> anthropic.Anthropic:
    global _client
    if not available():
        raise LLMUnavailable("No Anthropic API key configured, so AI reading is switched off")
    with _lock:
        if _client is None:
            _client = anthropic.Anthropic(api_key=settings.anthropic_api_key, max_retries=3, timeout=180.0)
    return _client


def model_for(tier: Tier) -> str:
    return settings.model_cheap if tier == "cheap" else settings.model_strong


def _cost(model: str, u) -> float:
    pin, pout = PRICES.get(model, (0.0, 0.0))
    cache_w = getattr(u, "cache_creation_input_tokens", 0) or 0
    cache_r = getattr(u, "cache_read_input_tokens", 0) or 0
    return (u.input_tokens * pin + cache_w * pin * 1.25 + cache_r * pin * 0.1 + u.output_tokens * pout) / 1e6


def _log(purpose: str, model: str, usage, cache_hit: bool = False) -> None:
    if cache_hit:
        db.execute("INSERT INTO llm_calls(ts, purpose, model, cache_hit) VALUES (?, ?, ?, 1)",
                   (db.now_iso(), purpose, model))
        return
    db.execute(
        "INSERT INTO llm_calls(ts, purpose, model, input_tokens, output_tokens, cache_read_tokens, "
        "cache_write_tokens, cost_usd) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (db.now_iso(), purpose, model, usage.input_tokens, usage.output_tokens,
         getattr(usage, "cache_read_input_tokens", 0) or 0, getattr(usage, "cache_creation_input_tokens", 0) or 0,
         _cost(model, usage)),
    )


def _cache_key(*parts: Any) -> str:
    return hashlib.sha256(json.dumps(parts, sort_keys=True, default=str).encode()).hexdigest()


def _cache_get(key: str) -> Any | None:
    row = db.query_one("SELECT response_json FROM llm_cache WHERE key = ?", (key,))
    return json.loads(row["response_json"]) if row else None


def _cache_put(key: str, purpose: str, value: Any) -> None:
    db.execute("INSERT OR REPLACE INTO llm_cache(key, purpose, response_json, created_at) VALUES (?, ?, ?, ?)",
               (key, purpose, json.dumps(value), db.now_iso()))


def _check_stop(resp) -> None:
    if resp.stop_reason == "refusal":
        cat = getattr(getattr(resp, "stop_details", None), "category", None)
        raise LLMUnavailable(f"The model declined this request ({cat or 'no category'})")
    if resp.stop_reason == "max_tokens":
        raise LLMUnavailable("The model's answer was cut off (max_tokens)")


def _create(tier: Tier, **kw):
    client = _get()
    model = model_for(tier)
    try:
        if tier == "strong":
            return model, client.beta.messages.create(model=model, betas=[FALLBACK_BETA],
                                                      extra_body={"fallbacks": "default"}, **kw)
        return model, client.messages.create(model=model, **kw)
    except anthropic.AuthenticationError as e:
        raise LLMUnavailable("The Anthropic API key was rejected") from e
    except anthropic.RateLimitError as e:
        raise LLMUnavailable("Rate-limited by the model API; try again shortly") from e
    except anthropic.APIStatusError as e:
        raise LLMUnavailable(f"Model API error {e.status_code}: {e.message}") from e
    except anthropic.APIConnectionError as e:
        raise LLMUnavailable("Couldn't reach the model API") from e


def structured(purpose: str, tier: Tier, system: str, content: list[dict] | str, schema: dict,
               max_tokens: int = 4000, effort: str = "low") -> dict:
    """JSON that is guaranteed to match `schema`. Cached on the full input."""
    model = model_for(tier)
    key = _cache_key("structured", model, system, content, schema)
    if (hit := _cache_get(key)) is not None:
        _log(purpose, model, None, cache_hit=True)
        return hit
    model, resp = _create(
        tier,
        max_tokens=max_tokens,
        system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": content}],
        output_config={"format": {"type": "json_schema", "schema": schema}, "effort": effort},
    )
    _log(purpose, model, resp.usage)
    _check_stop(resp)
    text = next((b.text for b in resp.content if b.type == "text"), None)
    if text is None:
        raise LLMUnavailable("The model returned no structured output")
    data = json.loads(text)
    _cache_put(key, purpose, data)
    return data


@dataclass
class Source:
    """One retrieved passage. Passages are grouped into documents; a citation points at a passage."""
    doc_id: str
    doc_title: str
    doc_type: str
    period: str | None
    page: int | None
    url: str | None
    text: str


def cited(purpose: str, tier: Tier, system: str, sources: list[Source], question: str,
          max_tokens: int = 3000, effort: str = "medium") -> dict:
    """Prose answer whose citations resolve to our own stored passages (document, page, URL).

    Each passage is sent as one block of a custom-content document, so the API's
    content_block_location (document_index, start_block_index) maps straight back to a Source.
    The model never supplies page numbers itself.
    """
    model = model_for(tier)
    docs: list[tuple[str, list[Source]]] = []
    index: dict[str, int] = {}
    for s in sources:
        if s.doc_id not in index:
            index[s.doc_id] = len(docs)
            docs.append((s.doc_id, []))
        docs[index[s.doc_id]][1].append(s)

    content: list[dict] = []
    for _, group in docs:
        first = group[0]
        content.append({
            "type": "document",
            "source": {"type": "content", "content": [{"type": "text", "text": g.text} for g in group]},
            "title": first.doc_title[:250],
            "context": f"{first.doc_type}{' · ' + first.period if first.period else ''}. Published by the company.",
            "citations": {"enabled": True},
        })
    content.append({"type": "text", "text": question})

    key = _cache_key("cited", model, system, [(s.doc_id, s.page, s.text) for s in sources], question)
    if (hit := _cache_get(key)) is not None:
        _log(purpose, model, None, cache_hit=True)
        return hit

    model, resp = _create(tier, max_tokens=max_tokens, system=system,
                          messages=[{"role": "user", "content": content}],
                          output_config={"effort": effort})
    _log(purpose, model, resp.usage)
    _check_stop(resp)

    segments = []
    for b in resp.content:
        if b.type != "text":
            continue
        cites = []
        for c in getattr(b, "citations", None) or []:
            if getattr(c, "type", "") != "content_block_location":
                continue
            _, group = docs[c.document_index]
            for blk in range(c.start_block_index, max(c.end_block_index, c.start_block_index + 1)):
                if blk < len(group):
                    s = group[blk]
                    cites.append({"doc_id": s.doc_id, "doc_title": s.doc_title, "doc_type": s.doc_type,
                                  "period": s.period, "page": s.page, "url": s.url, "quote": c.cited_text})
        segments.append({"text": b.text, "citations": cites})
    out = {"segments": segments, "model": model}
    _cache_put(key, purpose, out)
    return out


def cost_summary() -> dict:
    rows = db.query(
        "SELECT purpose, model, COUNT(*) calls, SUM(cache_hit) cache_hits, SUM(input_tokens) input_tokens, "
        "SUM(output_tokens) output_tokens, SUM(cache_read_tokens) cache_read, ROUND(SUM(cost_usd), 4) cost_usd "
        "FROM llm_calls GROUP BY purpose, model ORDER BY cost_usd DESC")
    total = db.query_one("SELECT ROUND(COALESCE(SUM(cost_usd),0), 4) usd, COUNT(*) calls, "
                         "COALESCE(SUM(cache_hit),0) hits FROM llm_calls")
    ann = db.query_one("SELECT COUNT(*) total, SUM(CASE WHEN category_method = 'rules' AND enriched_at IS NULL "
                       "THEN 1 ELSE 0 END) rules_only FROM announcements")
    return {"by_purpose": rows, "total": total, "filings": ann, "llm_configured": available(),
            "models": {"cheap": settings.model_cheap, "strong": settings.model_strong}}
