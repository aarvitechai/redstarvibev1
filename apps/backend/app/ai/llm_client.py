"""Single entry point to the Claude API. Everything sent here has already been PII redacted."""
from typing import Any

import anthropic
import structlog

from app.core.config import settings

log = structlog.get_logger()
_client: anthropic.AsyncAnthropic | None = None


def is_configured() -> bool:
    return bool(settings.anthropic_api_key)


def _get() -> anthropic.AsyncAnthropic:
    global _client
    if _client is None:
        _client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key, timeout=60.0)
    return _client


async def complete(
    system: str, user_text: str, images_b64: list[tuple[str, str]] | None = None,
    max_tokens: int = 4000, effort: str = "low",
) -> str | None:
    """Returns the text answer, or None when Claude is unavailable or declined. Callers must degrade gracefully."""
    if not is_configured():
        return None
    content: list[dict[str, Any]] = [
        {"type": "image", "source": {"type": "base64", "media_type": media, "data": data}}
        for data, media in (images_b64 or [])
    ]
    content.append({"type": "text", "text": user_text})
    try:
        response = await _get().beta.messages.create(  # type: ignore[call-overload]
            model=settings.anthropic_model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": content}],
            output_config={"effort": effort},
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",  # refusals retry on a suitable fallback model
        )
    except anthropic.RateLimitError:
        log.warning("claude_rate_limited")
        return None
    except anthropic.APIStatusError as exc:
        log.error("claude_api_error", status=exc.status_code)
        return None
    except anthropic.APIConnectionError:
        log.warning("claude_unreachable")
        return None
    if response.stop_reason == "refusal":
        log.info("claude_refusal")
        return None
    return "".join(block.text for block in response.content if block.type == "text").strip() or None
