#!/usr/bin/env python3
"""Generates the original homepage artwork into apps/web/public/home: 8 SVG scenes, 2 MP4 videos and their posters.

Needs Pillow locally and Docker (ffmpeg runs from the backend image). To use real photos or footage instead, replace
the files in public/home and keep the names, or change the paths in src/components/home/businesses.ts.
"""
import math
import random
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "apps/web/public/home"
OUT.mkdir(parents=True, exist_ok=True)
W, H, FPS = 1280, 720, 24
RED = (200, 16, 46)
FONT = "C:/Windows/Fonts/segoeuib.ttf"
FONT_REG = "C:/Windows/Fonts/segoeui.ttf"


def svg(name: str, top: str, bottom: str, glow: str, body: str) -> None:
    (OUT / f"{name}.svg").write_text(
        f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 600" role="img">
<defs><linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{top}"/><stop offset="1" stop-color="{bottom}"/></linearGradient>
<radialGradient id="glow"><stop offset="0" stop-color="{glow}" stop-opacity=".75"/><stop offset="1" stop-color="{glow}" stop-opacity="0"/></radialGradient>
<filter id="s" x="-20%" y="-20%" width="140%" height="150%"><feDropShadow dx="0" dy="14" stdDeviation="14" flood-color="#000" flood-opacity=".28"/></filter></defs>
<rect width="800" height="600" fill="url(#bg)"/><circle cx="610" cy="130" r="300" fill="url(#glow)"/><circle cx="120" cy="520" r="240" fill="url(#glow)" opacity=".55"/>
{body}</svg>''',
        encoding="utf8",
    )


def scenes() -> None:
    svg("food", "#ff8a3c", "#b3261e", "#ffd166", '''
<rect y="430" width="800" height="170" fill="#5b2412"/><rect y="430" width="800" height="14" fill="#7a3419"/>
<g filter="url(#s)"><ellipse cx="370" cy="420" rx="210" ry="62" fill="#fff"/><ellipse cx="370" cy="412" rx="170" ry="48" fill="#f4e3c8"/>
<ellipse cx="370" cy="400" rx="158" ry="44" fill="#e0a03f"/><ellipse cx="370" cy="396" rx="140" ry="37" fill="#d9482b"/></g>
<g fill="#fff4d6"><circle cx="300" cy="388" r="15"/><circle cx="375" cy="376" r="15"/><circle cx="440" cy="396" r="15"/><circle cx="350" cy="412" r="13"/></g>
<g fill="#3f8f3a"><ellipse cx="335" cy="384" rx="11" ry="5" transform="rotate(30 335 384)"/><ellipse cx="410" cy="406" rx="11" ry="5" transform="rotate(-25 410 406)"/><ellipse cx="400" cy="372" rx="10" ry="5"/></g>
<g fill="none" stroke="#fff" stroke-width="9" stroke-linecap="round" opacity=".65"><path d="M310 300c-22-30 22-48 0-82"/><path d="M380 285c-24-34 24-54 0-92"/><path d="M450 300c-22-30 22-48 0-82"/></g>
<g filter="url(#s)"><path d="M610 330h110l-13 130a22 22 0 0 1-22 20h-40a22 22 0 0 1-22-20z" fill="#fff"/><path d="M720 352c50-4 50 66-8 66" fill="none" stroke="#fff" stroke-width="13"/><ellipse cx="665" cy="334" rx="55" ry="12" fill="#5a2d14"/></g>''')
    svg("fashion", "#ec4899", "#5b21b6", "#fbcfe8", '''
<g filter="url(#s)"><rect x="110" y="90" width="580" height="16" rx="8" fill="#fff"/><rect x="130" y="100" width="14" height="430" fill="#fff"/><rect x="656" y="100" width="14" height="430" fill="#fff"/><rect x="90" y="522" width="94" height="14" rx="7" fill="#fff"/><rect x="616" y="522" width="94" height="14" rx="7" fill="#fff"/></g>
<g fill="none" stroke="#f3f4f6" stroke-width="6"><path d="M250 106v26l-58 34M250 132l58 34"/><path d="M400 106v26l-58 34M400 132l58 34"/><path d="M550 106v26l-58 34M550 132l58 34"/></g>
<g filter="url(#s)"><path d="M192 166l58-14 58 14 28 70-34 14-14-30v190H212V220l-14 30-34-14z" fill="#fde047"/>
<path d="M342 166h116l-16 108 66 196H292l66-196z" fill="#f43f5e"/><path d="M365 166h70l-6 36h-58z" fill="#be123c"/>
<path d="M492 166l58-14 58 14 28 88-34 12-14-34v178H462V232l-14 34-34-12z" fill="#22d3ee"/><path d="M550 152v292" stroke="#0e7490" stroke-width="5"/></g>''')
    svg("beauty", "#2dd4bf", "#be185d", "#fff1f2", '''
<g filter="url(#s)"><circle cx="400" cy="240" r="150" fill="#fff"/><circle cx="400" cy="240" r="128" fill="#bfe9f2"/><path d="M320 180l90-48M312 240l150-88" stroke="#fff" stroke-width="14" stroke-linecap="round" opacity=".8"/><rect x="386" y="388" width="28" height="96" fill="#fff"/><rect x="310" y="478" width="180" height="24" rx="12" fill="#fff"/></g>
<g filter="url(#s)"><rect x="150" y="368" width="62" height="132" rx="8" fill="#1f2937"/><rect x="158" y="310" width="46" height="62" fill="#fbbf24"/><path d="M162 310v-52l38 24v28z" fill="#e11d48"/></g>
<g filter="url(#s)"><rect x="575" y="330" width="96" height="170" rx="18" fill="#fff"/><rect x="600" y="280" width="46" height="52" rx="6" fill="#f9a8d4"/><rect x="590" y="395" width="66" height="50" rx="6" fill="#ec4899"/></g>
<g fill="#fff"><path d="M675 150l13 34 34 13-34 13-13 34-13-34-34-13 34-13z"/><path d="M125 170l9 24 24 9-24 9-9 24-9-24-24-9 24-9z"/><path d="M710 280l6 16 16 6-16 6-6 16-6-16-16-6 16-6z"/></g>''')
    svg("fitness", "#111827", "#15803d", "#a3e635", '''
<path d="M60 170h170l36-80 56 170 46-120 28 30h344" fill="none" stroke="#a3e635" stroke-width="13" stroke-linejoin="round" stroke-linecap="round"/>
<g filter="url(#s)"><rect x="210" y="375" width="380" height="36" rx="10" fill="#e5e7eb"/><rect x="130" y="300" width="56" height="186" rx="14" fill="#ef4444"/><rect x="190" y="326" width="42" height="134" rx="12" fill="#f97316"/><rect x="614" y="300" width="56" height="186" rx="14" fill="#ef4444"/><rect x="568" y="326" width="42" height="134" rx="12" fill="#f97316"/><rect x="92" y="352" width="36" height="82" rx="10" fill="#9ca3af"/><rect x="672" y="352" width="36" height="82" rx="10" fill="#9ca3af"/></g>
<g filter="url(#s)"><path d="M400 318c-36-32-68-14-68 16 0 34 42 56 68 78 26-22 68-44 68-78 0-30-32-48-68-16z" fill="#f43f5e" transform="translate(0 -160) "/></g>''')
    svg("travel", "#38bdf8", "#f97316", "#fef08a", '''
<circle cx="610" cy="150" r="72" fill="#fde68a"/><path d="M0 470l190-240 130 150 120-190 360 280v130H0z" fill="#1e3a5f"/><path d="M440 190l66 96-44-16-34 34-30-30z" fill="#fff"/><path d="M190 230l52 66-34-12-24 24-28-26z" fill="#fff"/>
<path d="M0 500c180-60 330 30 480-10s220-40 320-10v120H0z" fill="#0f766e"/>
<g filter="url(#s)" transform="rotate(-14 230 120)"><path d="M120 120l180-14c36-3 36 26 2 30l-182 14z" fill="#fff"/><path d="M215 112l-58-58h28l80 54zM220 138l-44 54h26l66-60zM130 118l-30-38h20l36 34z" fill="#e5e7eb"/></g>
<path d="M100 110q70 60 130 12" fill="none" stroke="#fff" stroke-width="5" stroke-dasharray="12 12" opacity=".8"/>
<g filter="url(#s)"><rect x="520" y="370" width="160" height="186" rx="20" fill="#c8102e"/><path d="M566 370v-44a18 18 0 0 1 18-18h32a18 18 0 0 1 18 18v44" fill="none" stroke="#fff" stroke-width="12"/><path d="M560 402v120M640 402v120" stroke="#7f0a1e" stroke-width="12"/></g>''')
    svg("realestate", "#1e3a8a", "#f59e0b", "#fde68a", '''
<g fill="#fff" opacity=".85"><circle cx="110" cy="80" r="3"/><circle cx="240" cy="50" r="2"/><circle cx="420" cy="90" r="3"/><circle cx="700" cy="60" r="2"/></g><path d="M0 500h800v100H0z" fill="#14532d"/>
<g filter="url(#s)"><rect x="70" y="190" width="170" height="320" fill="#334155"/><rect x="540" y="130" width="190" height="380" fill="#475569"/></g>
<g fill="#fde047"><rect x="95" y="220" width="40" height="40"/><rect x="175" y="220" width="40" height="40"/><rect x="95" y="290" width="40" height="40"/><rect x="175" y="360" width="40" height="40"/><rect x="570" y="165" width="48" height="44"/><rect x="655" y="165" width="48" height="44"/><rect x="655" y="250" width="48" height="44"/><rect x="570" y="335" width="48" height="44"/><rect x="655" y="420" width="48" height="44"/></g>
<g filter="url(#s)"><path d="M230 330L400 190l170 140z" fill="#c8102e"/><rect x="262" y="330" width="276" height="180" fill="#fff"/><rect x="370" y="400" width="62" height="110" fill="#7c2d12"/><rect x="290" y="365" width="56" height="56" fill="#7dd3fc"/><rect x="455" y="365" width="56" height="56" fill="#7dd3fc"/></g>
<g filter="url(#s)"><path d="M400 150c-44 0-72-32-72-68s32-66 72-66 72 30 72 66-28 68-72 68z" fill="#fff" transform="translate(0 16)"/><path d="M366 150l34 56 34-56z" fill="#fff"/><circle cx="400" cy="98" r="26" fill="#c8102e"/></g>''')
    svg("education", "#4338ca", "#0ea5e9", "#c7d2fe", '''
<g filter="url(#s)"><rect x="170" y="430" width="460" height="62" rx="10" fill="#f43f5e"/><rect x="200" y="368" width="400" height="62" rx="10" fill="#fbbf24"/><rect x="150" y="306" width="440" height="62" rx="10" fill="#34d399"/><path d="M182 322h300M232 384h290M202 446h330" stroke="#fff" stroke-width="7" opacity=".7"/></g>
<g filter="url(#s)"><path d="M400 110l230 92-230 92-230-92z" fill="#111827"/><path d="M280 244v62c70 44 170 44 240 0v-62l-120 50z" fill="#1f2937"/><path d="M610 200v110" stroke="#fbbf24" stroke-width="9"/><circle cx="610" cy="322" r="17" fill="#fbbf24"/></g>
<g filter="url(#s)"><circle cx="135" cy="150" r="56" fill="#fef08a"/><rect x="112" y="204" width="46" height="34" rx="7" fill="#e5e7eb"/></g><g stroke="#fef08a" stroke-width="8" stroke-linecap="round"><path d="M135 62v-24M58 150H34M212 150h24M80 95L62 77M190 95l18-18"/></g>''')
    svg("creators", "#c8102e", "#3b0764", "#fda4af", '''
<circle cx="400" cy="285" r="205" fill="none" stroke="#fff" stroke-width="30" opacity=".95"/><circle cx="400" cy="285" r="228" fill="none" stroke="#fff" stroke-width="10" opacity=".25"/>
<g filter="url(#s)"><rect x="285" y="150" width="230" height="270" rx="30" fill="#111827"/><rect x="305" y="176" width="190" height="218" rx="12" fill="url(#bg)"/><path d="M372 240l78 45-78 45z" fill="#fff"/></g><rect x="388" y="480" width="24" height="86" fill="#e5e7eb"/><rect x="320" y="556" width="160" height="18" rx="9" fill="#e5e7eb"/>
<g fill="#fff"><path id="h" d="M650 170c-18-16-34-7-34 8 0 17 21 28 34 39 13-11 34-22 34-39 0-15-16-24-34-8z"/><path d="M120 300c-14-12-27-5-27 6 0 14 17 22 27 31 10-9 27-17 27-31 0-11-13-18-27-6z"/></g>
<g fill="#fde047"><path d="M685 360l12 26 28 4-20 20 5 28-25-13-25 13 5-28-20-20 28-4z"/><path d="M120 120l9 20 22 3-16 15 4 22-19-10-19 10 4-22-16-15 22-3z"/></g>''')


def background() -> Image.Image:
    grad = Image.linear_gradient("L").resize((W, H)).rotate(0)
    top, bottom = Image.new("RGB", (W, H), (70, 8, 24)), Image.new("RGB", (W, H), (9, 9, 14))
    return Image.composite(bottom, top, grad)


class Network:
    def __init__(self, seconds: int, count: int = 34) -> None:
        rng = random.Random(7)
        self.seconds = seconds
        self.nodes = [
            (rng.uniform(0, W), rng.uniform(0, H), rng.uniform(25, 70), rng.uniform(25, 70), rng.uniform(0, 6.28), rng.choice([1, 2]))
            for _ in range(count)
        ]
        self.base = background()

    def frame(self, t: float) -> Image.Image:
        """Motion is periodic in the clip length, so the video loops without a jump."""
        points = []
        for x, y, ax, ay, phase, cycles in self.nodes:
            a = 2 * math.pi * cycles * t / self.seconds + phase
            points.append((x + ax * math.sin(a), y + ay * math.cos(a)))
        layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        draw = ImageDraw.Draw(layer)
        for i, p in enumerate(points):
            for q in points[i + 1:]:
                dist = math.dist(p, q)
                if dist < 240:
                    draw.line([p, q], fill=(255, 255, 255, int(70 * (1 - dist / 240))), width=2)
        for i, (x, y) in enumerate(points):
            pulse = 1 + 0.35 * math.sin(2 * math.pi * t / self.seconds * 2 + i)
            r = (5 if i % 4 else 9) * pulse
            draw.ellipse([x - r, y - r, x + r, y + r], fill=(255, 255, 255, 190) if i % 3 else (232, 40, 70, 240))
        out = self.base.convert("RGBA")
        out.alpha_composite(layer)
        return out


def encode(name: str, seconds: int, render, crf: int = 27) -> None:  # noqa: ANN001
    cmd = [
        "docker", "run", "--rm", "-i", "-e", "MSYS_NO_PATHCONV=1", "-v", f"{OUT}:/out", "--entrypoint", "ffmpeg",
        "redstarvibe/backend:local", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
        "-i", "-", "-an", "-c:v", "libx264", "-preset", "slow", "-crf", str(crf), "-pix_fmt", "yuv420p", "-movflags", "+faststart",
        f"/out/{name}.mp4",
    ]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    total = seconds * FPS
    for n in range(total):
        frame = render(n / FPS).convert("RGB")
        proc.stdin.write(frame.tobytes())
        if n == min(total - 1, FPS * 2):
            frame.save(OUT / f"{name}-poster.jpg", quality=82)
    proc.stdin.close()
    if proc.wait():
        raise SystemExit(f"ffmpeg failed for {name}")


def font(size: int, bold: bool = True) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(FONT if bold else FONT_REG, size)


def ease(x: float) -> float:
    x = max(0.0, min(1.0, x))
    return 1 - (1 - x) ** 3


def phone(content) -> Image.Image:  # noqa: ANN001
    pw, ph = 300, 560
    img = Image.new("RGBA", (pw, ph), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, pw - 1, ph - 1], 40, fill=(20, 20, 26, 255))
    d.rounded_rectangle([10, 10, pw - 11, ph - 11], 32, fill=(255, 255, 255, 255))
    content(img, d)
    return img


def explainer() -> None:
    net = Network(16)
    logo = Image.open(ROOT / "apps/web/public/brand/logo.png").convert("RGBA")
    small = logo.resize((30, 30), Image.LANCZOS)
    colours = [(255, 138, 60), (236, 72, 153), (45, 212, 191), (56, 189, 248), (250, 204, 21), (99, 102, 241), (34, 197, 94), (200, 16, 46), (244, 63, 94)]
    steps = [
        ("Show what you do", "Photos, reels and stories in one place."),
        ("Get discovered", "Hashtags, places and Explore bring in new people."),
        ("Talk to customers", "Messages, audio and video calls, right in the app."),
    ]

    def screen(step: int, local: float):  # noqa: ANN202
        def draw_it(img: Image.Image, d: ImageDraw.ImageDraw) -> None:
            img.alpha_composite(small, (28, 26))
            d.text((66, 30), "RedStarVibe", font=font(19), fill=(17, 17, 17))
            if step == 0:
                d.rounded_rectangle([24, 72, 276, 356], 14, fill=colours[0])
                d.ellipse([90, 140, 210, 260], fill=(255, 225, 170))
                d.ellipse([112, 162, 188, 238], fill=(217, 72, 43))
                s = 1 + 0.5 * max(0.0, 1 - abs(local - 1.6) * 3)
                x, y, r = 48, 392, 15 * s
                d.ellipse([x - r, y - r, x, y], fill=RED)
                d.ellipse([x, y - r, x + r, y], fill=RED)
                d.polygon([(x - r, y - r * 0.4), (x + r, y - r * 0.4), (x, y + r)], fill=RED)
                d.text((28, 422), "Fresh from our kitchen", font=font(18, False), fill=(40, 40, 40))
                d.text((28, 450), "#food #local", font=font(18), fill=RED)
            elif step == 1:
                for i, colour in enumerate(colours):
                    if local * 5 > i * 0.6:
                        x, y = 24 + (i % 3) * 86, 76 + (i // 3) * 86
                        d.rounded_rectangle([x, y, x + 80, y + 80], 8, fill=colour)
                d.rounded_rectangle([24, 350, 276, 396], 22, fill=(240, 240, 243))
                d.text((44, 360), "#food near Pune", font=font(18, False), fill=(90, 90, 90))
            else:
                bubbles = [(False, "Are you open today?"), (True, "Yes, until 10 pm!"), (False, "Can I call you?"), (True, "Of course")]
                y = 86
                for i, (mine, text) in enumerate(bubbles):
                    if local > 0.3 + i * 0.7:
                        width = d.textlength(text, font=font(17, False)) + 28
                        x = 276 - width if mine else 24
                        d.rounded_rectangle([x, y, x + width, y + 44], 18, fill=RED if mine else (240, 240, 243))
                        d.text((x + 14, y + 10), text, font=font(17, False), fill=(255, 255, 255) if mine else (20, 20, 20))
                        y += 58
                d.ellipse([120, 410, 180, 470], fill=(34, 197, 94))
                d.text((134, 422), "Call", font=font(15), fill=(255, 255, 255))

        return draw_it

    # Dark across the caption side, fading out to the right. Dims the centre for the closing logo too.
    scrim = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    scrim.putalpha(Image.linear_gradient("L").rotate(90, expand=True).resize((W, H)).point(lambda v: int(v * 0.8)))

    def render(t: float) -> Image.Image:
        out = net.frame(t)
        out.alpha_composite(scrim)  # keeps captions readable over the moving network
        if t < 12:
            step = int(t // 4)
            local = t - step * 4
            alpha = ease(local / 0.5) * ease((4 - local) / 0.4)
            slide = int((1 - ease(local / 0.6)) * 50)
            layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            d = ImageDraw.Draw(layer)
            title, sub = steps[step]
            d.text((96, 250 + slide), title, font=font(58), fill=(255, 255, 255, 255))
            d.text((96, 336 + slide), sub, font=font(28, False), fill=(235, 235, 240, 255))
            layer.alpha_composite(phone(screen(step, local)), (880, 80 + slide))
            layer.putalpha(layer.getchannel("A").point(lambda v: int(v * alpha)))
            out.alpha_composite(layer)
        else:
            local = t - 12
            alpha = ease(local / 0.6) * ease((4 - local) / 0.3)
            layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            size = int(230 + 20 * ease(local / 1.5))
            mark = logo.resize((size, size), Image.LANCZOS)
            layer.alpha_composite(mark, ((W - size) // 2, 120))
            d = ImageDraw.Draw(layer)
            d.text((W / 2, 430), "RedStarVibe", font=font(64), fill=(255, 255, 255, 255), anchor="mm")
            d.text((W / 2, 500), "Bring your business to where people connect.", font=font(30, False), fill=(235, 235, 240, 255), anchor="mm")
            layer.putalpha(layer.getchannel("A").point(lambda v: int(v * alpha)))
            out.alpha_composite(layer)
        return out

    encode("explainer", 16, render, crf=25)


if __name__ == "__main__":
    scenes()
    banner = Network(8, 46)
    encode("banner", 8, banner.frame, crf=30)
    explainer()
    Image.open(ROOT / "apps/web/public/brand/logo.png")
    for f in sorted(OUT.iterdir()):
        print(f.name, f.stat().st_size)
