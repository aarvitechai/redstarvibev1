"""UUIDv7 generation (time ordered primary keys, RFC 9562)."""
import os
import time
import uuid


def uuid7() -> uuid.UUID:
    ms = time.time_ns() // 1_000_000
    rand = bytearray(os.urandom(10))
    rand[0] = (rand[0] & 0x0F) | 0x70
    rand[2] = (rand[2] & 0x3F) | 0x80
    return uuid.UUID(bytes=ms.to_bytes(6, "big") + bytes(rand))
