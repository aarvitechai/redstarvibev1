"""Original placeholder pictures, so test data needs no third party photos."""
import io
import math
import random

from PIL import Image, ImageDraw, ImageFilter

THEMES = {
    "sunset": ((252, 110, 60), (60, 30, 90)),
    "city": ((120, 150, 180), (40, 45, 60)),
    "hills": ((150, 210, 170), (20, 90, 70)),
    "night": ((25, 30, 70), (5, 5, 20)),
    "snow": ((225, 235, 245), (120, 150, 190)),
}


def artwork(theme: str, seed: int, size: tuple[int, int] = (1080, 1350)) -> bytes:
    rng = random.Random(seed)
    w, h = size
    top, bottom = THEMES[theme]
    image = Image.new("RGB", size)
    draw = ImageDraw.Draw(image)
    for y in range(h):
        t = y / h
        draw.line([(0, y), (w, y)], fill=tuple(int(a + (b - a) * t) for a, b in zip(top, bottom, strict=True)))
    if theme in {"sunset", "snow"}:
        cx, cy, r = rng.randint(250, 830), rng.randint(350, 650), rng.randint(90, 170)
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(255, 225, 150))
    if theme == "night":
        for _ in range(180):
            draw.point((rng.randint(0, w), rng.randint(0, h // 2)), fill=(255, 255, 255))
    for layer in range(3):
        base = int(h * (0.62 + layer * 0.12))
        shade = tuple(max(0, int(c * (0.6 - layer * 0.18))) for c in bottom)
        phase, amp = rng.random() * 6, rng.randint(40, 110)
        points = [(0, h)] + [(x, base + int(amp * math.sin(x / 150 + phase))) for x in range(0, w + 20, 20)] + [(w, h)]
        draw.polygon(points, fill=shade)
    buffer = io.BytesIO()
    image.filter(ImageFilter.GaussianBlur(0.6)).save(buffer, "JPEG", quality=88)
    return buffer.getvalue()


def avatar(seed: int) -> bytes:
    rng = random.Random(seed)
    image = Image.new("RGB", (400, 400), (rng.randint(40, 220), rng.randint(40, 220), rng.randint(40, 220)))
    draw = ImageDraw.Draw(image)
    draw.ellipse([130, 90, 270, 230], fill=(255, 255, 255))
    draw.ellipse([70, 250, 330, 520], fill=(255, 255, 255))
    buffer = io.BytesIO()
    image.save(buffer, "JPEG", quality=90)
    return buffer.getvalue()
