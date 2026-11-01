"""PII redaction before any text is sent to an external API."""
import re

EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
PHONE = re.compile(r"(?<!\d)(?:\+?\d[\s-]?){10,14}(?!\d)")
CARD = re.compile(r"(?<!\d)(?:\d[ -]?){13,19}(?!\d)")


def redact(text: str) -> str:
    text = EMAIL.sub("[email]", text)
    text = CARD.sub("[number]", text)
    return PHONE.sub("[phone]", text)
