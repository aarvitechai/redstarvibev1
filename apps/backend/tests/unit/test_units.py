import time
import uuid

from app.ai.embeddings.provider import hash_embed
from app.ai.rag.chunking import chunk_text
from app.ai.ranking.ranker import score_post
from app.ai.safety.moderation import check_rules
from app.ai.safety.pii import redact
from app.ai.safety.spam import spam_score
from app.ai.speech.whisper import segments_to_vtt
from app.core.ids import uuid7
from app.core.pagination import decode_cursor, encode_cursor
from app.modules.auth.service import is_old_enough
from app.modules.posts.service import extract_hashtags, extract_mentions
from app.workers.media_tasks import sniff


def test_uuid7_is_time_ordered_v7():
    a, b = uuid7(), uuid7()
    assert a.version == 7 and a.hex[:8] <= b.hex[:8]
    assert isinstance(a, uuid.UUID)


def test_chunking_overlap():
    words = [str(i) for i in range(1200)]
    chunks = chunk_text(" ".join(words))
    assert len(chunks) == 3
    assert chunks[0].split()[-50:] == chunks[1].split()[:50]


def test_hash_embedding_is_normalised_and_lexical():
    a, b, c = hash_embed("sunset at the beach"), hash_embed("beach sunset"), hash_embed("database migration")
    dot = lambda x, y: sum(p * q for p, q in zip(x, y, strict=True))  # noqa: E731
    assert abs(dot(a, a) - 1) < 1e-5
    assert dot(a, b) > dot(a, c)


def test_pii_redaction():
    out = redact("mail me at a.b@example.com or +91 98765 43210")
    assert "example.com" not in out and "98765" not in out


def test_hashtags_and_mentions():
    assert extract_hashtags("Hi #Sunset and #sunset #beach2") == ["beach2", "sunset"]
    assert extract_mentions("thanks @asha and a@b.com") == ["asha"]


def test_magic_bytes_not_extension():
    assert sniff(b"\xff\xd8\xff\xe0" + b"\0" * 28) == "image"
    assert sniff(b"\0\0\0\x20ftypisom" + b"\0" * 20) == "video"
    assert sniff(b"MZ\x90\0" + b"\0" * 28) is None
    assert sniff(b"<html><script>" + b"\0" * 18) is None


def test_age_gate():
    assert is_old_enough(__import__("datetime").date(2000, 1, 1))
    assert not is_old_enough(__import__("datetime").date.today())


def test_rrf_merges_duplicates_in_a_stable_order():
    from app.modules.search.ranking import merge

    now = int(time.time() * 1000)
    a, b, c = uuid7(), uuid7(), uuid7()
    assert merge([[a, b], [c, a]], now)[0] == a  # high in both lists wins
    assert len(merge([[a, b], [c, a]], now)) == 3
    assert merge([[a, b], [c, a]], now) == merge([[a, b], [c, a]], now)
    assert merge([[], []], now) == []


def test_caption_parser_rejects_bad_model_output():
    from app.ai.writing import parse_suggestions

    for bad in (None, "", "no json", "[1, 2]", '{"captions": []}', '{"captions": "text"}', '{"captions": [1, " "]}'):
        assert parse_suggestions(bad) is None
    raw = '{"captions": ["One", "Two", "Three", "Four"], "tagline": "Go", "hashtags": ["#Beach", "a b", "x"]}'
    good = parse_suggestions(f"Sure! {raw}")
    assert good == {"captions": ["One", "Two", "Three"], "tagline": "Go", "hashtags": ["beach", "x"]}


def test_query_normalized():
    from app.modules.search.service import normalize

    assert normalize("  #Goa Beach ") == "goa beach"
    assert normalize("@" + "x" * 200) == "x" * 100
    assert normalize(" # ") == ""


def test_rules_moderation():
    assert check_rules("buy followers cheap").blocked
    assert not check_rules("lovely sunset").needs_review


def test_ranking_prefers_fresh_and_engaged():
    assert score_post(100, 10, 5, 1, 0, 0) > score_post(1, 0, 0, 1, 0, 0)
    assert score_post(10, 0, 0, 1, 0, 0) > score_post(10, 0, 0, 200, 0, 0)


def test_spam_score_bounds():
    assert spam_score("asha", "a@gmail.com", "hi") < 0.2
    assert spam_score("xk7829341", "a@mailinator.com", "http://x") > 0.5


def test_cursor_round_trip():
    assert decode_cursor(encode_cursor("abc", 12)) == ["abc", "12"]


def test_vtt():
    assert "00:00:01.500 --> 00:00:02.000" in segments_to_vtt([(1.5, 2.0, " hi ")])
