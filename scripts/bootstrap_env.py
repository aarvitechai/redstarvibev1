#!/usr/bin/env python3
"""Creates .env from .env.example with freshly generated secrets. Never overwrites an existing file."""
import base64
import secrets
import sys
from pathlib import Path

root = Path(__file__).resolve().parent.parent
env = root / ".env"
if env.exists():
    sys.exit(".env already exists; leaving it untouched")

try:
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives.serialization import Encoding, NoEncryption, PrivateFormat, PublicFormat

    key = ec.generate_private_key(ec.SECP256R1())
    b64 = lambda raw: base64.urlsafe_b64encode(raw).rstrip(b"=").decode()  # noqa: E731
    vapid_public = b64(key.public_key().public_bytes(Encoding.X962, PublicFormat.UncompressedPoint))
    vapid_private = b64(key.private_numbers().private_value.to_bytes(32, "big"))
except ImportError:
    vapid_public = vapid_private = ""
    print("cryptography is not installed: web push stays off until VAPID keys are set")

values = {
    "POSTGRES_PASSWORD": secrets.token_urlsafe(24),
    "JWT_SECRET": secrets.token_urlsafe(48),
    "FIELD_ENCRYPTION_KEY": base64.urlsafe_b64encode(secrets.token_bytes(32)).decode(),
    "S3_ACCESS_KEY": "rsv" + secrets.token_hex(8),
    "S3_SECRET_KEY": secrets.token_urlsafe(32),
    "VAPID_PUBLIC_KEY": vapid_public,
    "VAPID_PRIVATE_KEY": vapid_private,
}
lines = []
for line in (root / ".env.example").read_text(encoding="utf8").splitlines():
    name = line.split("=", 1)[0]
    lines.append(f"{name}={values[name]}" if name in values and "=" in line else line)
env.write_text("\n".join(lines) + "\n", encoding="utf8")
print("wrote .env")
