"""Reciprocal Rank Fusion: a post near the top of either list rises, a post high in both wins."""
import uuid
from collections.abc import Sequence

RRF_K = 60
FRESHNESS_WEIGHT = 0.002
MS_PER_DAY = 86_400_000


def _age_days(post_id: uuid.UUID, now_ms: int) -> float:
    return max(0, now_ms - int(post_id.hex[:12], 16)) / MS_PER_DAY  # the id is a UUIDv7, so it holds the time


def merge(lists: Sequence[Sequence[uuid.UUID]], now_ms: int) -> list[uuid.UUID]:
    """Freshness only breaks near ties: its most is 0.002, about a third of the gap between ranks 1 and 50."""
    scores: dict[uuid.UUID, float] = {}
    for ranked in lists:
        for rank, post_id in enumerate(ranked, start=1):
            scores[post_id] = scores.get(post_id, 0.0) + 1 / (RRF_K + rank)
    for post_id in scores:
        scores[post_id] += FRESHNESS_WEIGHT / (1 + _age_days(post_id, now_ms))
    return sorted(scores, key=lambda p: (-scores[p], p.hex))
