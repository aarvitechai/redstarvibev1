"""Calls to Cloudflare Workers AI, so no model runs on this machine. Every failure returns None, so callers can fall back."""
from typing import Any

import httpx
import structlog

from app.core.config import settings

log = structlog.get_logger()


async def _run(model: str, body: dict[str, Any], seconds: float) -> dict[str, Any] | None:
    url = f"https://api.cloudflare.com/client/v4/accounts/{settings.cloudflare_account_id}/ai/run/{model}"
    headers = {"Authorization": f"Bearer {settings.cloudflare_ai_token}"}
    try:
        async with httpx.AsyncClient(timeout=seconds) as client:
            res = await client.post(url, json=body, headers=headers)
            res.raise_for_status()
            result = res.json().get("result")
    except (httpx.HTTPError, ValueError) as exc:  # includes the free daily limit running out
        log.warning("workers_ai_failed", model=model, error=type(exc).__name__)
        return None
    return result if isinstance(result, dict) else None


async def embed(model: str, texts: list[str], seconds: float) -> list[list[float]] | None:
    result = await _run(model, {"text": texts}, seconds)
    vectors = (result.get("data") or result.get("response")) if result else None
    return vectors if isinstance(vectors, list) and len(vectors) == len(texts) else None


async def chat(model: str, system: str, user: str, seconds: float, image_b64: str | None = None) -> str | None:
    body: dict[str, Any] = {"messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
    if image_b64:
        body["image"] = image_b64
    result = await _run(model, body, seconds)
    reply = result.get("response") if result else None
    return reply.strip() or None if isinstance(reply, str) else None
