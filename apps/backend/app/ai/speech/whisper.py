"""Reel subtitles with faster-whisper (CPU in Phase 1). Enabled with WHISPER_ENABLED and the ai extra."""
from functools import lru_cache
from typing import Any

from app.core.config import settings


@lru_cache
def _model() -> Any:
    from faster_whisper import WhisperModel

    return WhisperModel(settings.whisper_model, device="cpu", compute_type="int8")


def _ts(seconds: float) -> str:
    ms = int(seconds * 1000)
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02}:{m:02}:{s:02}.{ms:03}"


def segments_to_vtt(segments: list[tuple[float, float, str]]) -> str:
    lines = ["WEBVTT", ""]
    for start, end, text in segments:
        lines += [f"{_ts(start)} --> {_ts(end)}", text.strip(), ""]
    return "\n".join(lines)


def transcribe_to_vtt(path: str) -> str | None:
    if not settings.whisper_enabled:
        return None
    segments, _ = _model().transcribe(path, vad_filter=True)
    rows = [(s.start, s.end, s.text) for s in segments]
    return segments_to_vtt(rows) if rows else None
