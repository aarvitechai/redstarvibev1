"""30 real queries against the real model. Skipped unless real Cloudflare keys are set in GOLDEN_ACCOUNT and GOLDEN_TOKEN."""
import os
import uuid
from unittest.mock import patch

import pytest

from app.core.config import settings
from app.workers.ai_tasks import index_posts

ACCOUNT, TOKEN = os.environ.get("GOLDEN_ACCOUNT"), os.environ.get("GOLDEN_TOKEN")
pytestmark = pytest.mark.skipif(not (ACCOUNT and TOKEN), reason="Cloudflare keys are not set")

POSTS = {
    "beach": "Sunset over the beach in Goa, orange sky and calm waves",
    "mountain": "Snow on the mountains in Spiti, cold wind and clear blue sky",
    "food": "Spicy street food in Old Delhi, hot jalebi and chole bhature",
    "rain": "Heavy monsoon rain on the streets of Mumbai, everyone running with umbrellas",
    "wedding": "My sister's wedding, bride in a red lehenga and the whole family dancing",
    "cricket": "Playing cricket with friends in the park, I took two wickets today",
    "temple": "Evening prayer at the old temple in Varanasi, diyas on the Ganga",
    "coffee": "Quiet morning with a cup of filter coffee and a good book",
    "gym": "Leg day at the gym, new personal record on squats",
    "puppy": "Adopted this tiny puppy today, he sleeps all day on my lap",
}
QUERIES = [
    ("beach sunset", "beach"), ("goa ki shaam", "beach"), ("samundar ke kinare", "beach"), ("समुद्र तट पर सूर्यास्त", "beach"),
    ("கடற்கரை", "beach"), ("waves and orange sky", "beach"),
    ("snow mountains", "mountain"), ("pahadon mein barf", "mountain"), ("पहाड़ों पर बर्फ", "mountain"),
    ("himalaya trek cold", "mountain"),
    ("street food", "food"), ("delhi ka khana", "food"), ("दिल्ली का स्ट्रीट फूड", "food"), ("spicy snacks", "food"),
    ("rainy day", "rain"), ("baarish mumbai", "rain"), ("बारिश का मौसम", "rain"),
    ("marriage ceremony", "wedding"), ("shaadi ka dance", "wedding"), ("शादी की तस्वीरें", "wedding"),
    ("cricket match", "cricket"), ("dosto ke saath cricket", "cricket"), ("क्रिकेट खेलना", "cricket"),
    ("hindu worship by the river", "temple"), ("mandir ki aarti", "temple"), ("गंगा आरती", "temple"),
    ("morning coffee", "coffee"), ("workout fitness", "gym"), ("cute dog", "puppy"), ("chhota kutta", "puppy"),
]
TOP = 5
MIN_HITS = 24  # 80 percent. Printed in full, so a change in quality is visible.


async def test_golden_queries(make_user, make_post):
    author = await make_user()
    marker = uuid.uuid4().hex[:8]
    ids = {}
    with (
        patch.object(settings, "ai_provider", "cloudflare"), patch.object(settings, "cloudflare_account_id", ACCOUNT),
        patch.object(settings, "cloudflare_ai_token", TOKEN),
    ):
        for name, caption in POSTS.items():
            ids[await make_post(author, caption=f"{caption} {marker}")] = name
        assert await index_posts([uuid.UUID(i) for i in ids])
        hits, misses = 0, []
        for query, expected in QUERIES:
            res = await author.get("/search", params={"q": query, "limit": 48})
            top = [ids[p["id"]] for p in res.json()["items"] if p["id"] in ids][:TOP]
            if top and expected == top[0]:
                hits += 1
            else:
                misses.append((query, expected, top))
    print(f"\nGOLDEN first place {hits}/{len(QUERIES)} misses: {misses}")
    assert hits >= MIN_HITS
