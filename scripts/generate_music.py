#!/usr/bin/env python3
"""Generates original background music with no licence attached, so posts never carry someone else's song.

Each track is synthesized here from chords, bass, melody and drums. It needs numpy and ffmpeg, which the backend image has:

    docker compose --env-file .env -f infra/docker/docker-compose.yml exec -T worker python - < scripts/generate_music.py
    docker cp redstarvibe-worker-1:/tmp/music/. apps/web/public/music/
"""
import subprocess
import wave
from pathlib import Path

import numpy as np

OUT = Path("/tmp/music")  # noqa: S108
RATE = 32000
A4 = 440.0
MAJOR = (0, 4, 7)
MINOR = (0, 3, 7)

# name: beats per minute, chords as (semitones from A4, shape), melody as scale steps, drum feel
TRACKS = {
    "golden-hour": (84, [(-9, MAJOR), (-5, MAJOR), (-7, MINOR), (-2, MAJOR)], [0, 2, 4, 7, 4, 2], "soft"),
    "city-lights": (76, [(-12, MINOR), (-4, MAJOR), (-7, MAJOR), (-5, MINOR)], [0, 3, 5, 7, 10, 7], "lofi"),
    "monsoon": (60, [(-9, MINOR), (-4, MAJOR), (-2, MAJOR), (-7, MINOR)], [0, 2, 3, 7, 3, 0], "none"),
    "festival": (118, [(-7, MAJOR), (-2, MAJOR), (-4, MINOR), (-9, MAJOR)], [0, 4, 5, 7, 5, 4, 2, 0], "dhol"),
    "road-trip": (104, [(-5, MAJOR), (0, MAJOR), (-3, MINOR), (-7, MAJOR)], [0, 2, 4, 5, 7, 5, 4, 2], "drive"),
    "sunrise": (68, [(-12, MAJOR), (-5, MAJOR), (-9, MINOR), (-7, MAJOR)], [0, 4, 7, 12, 7, 4], "none"),
}


def hz(semitones: float) -> float:
    return A4 * 2 ** (semitones / 12)


def tone(freq: float, seconds: float, attack: float, decay: float, bright: float) -> np.ndarray:
    t = np.arange(int(seconds * RATE)) / RATE
    wave_shape = np.sin(2 * np.pi * freq * t) + bright * np.sin(4 * np.pi * freq * t) + bright / 3 * np.sin(6 * np.pi * freq * t)
    envelope = np.minimum(t / attack, 1) * np.exp(-t * decay)
    return wave_shape * envelope


def drum(kind: str, rng: np.random.Generator) -> np.ndarray:
    t = np.arange(int(0.25 * RATE)) / RATE
    if kind == "kick":
        return np.sin(2 * np.pi * (45 + 90 * np.exp(-t * 40)) * t) * np.exp(-t * 14)
    if kind == "dhol":
        return np.sin(2 * np.pi * (80 + 70 * np.exp(-t * 30)) * t) * np.exp(-t * 10) + 0.15 * rng.normal(size=t.size) * np.exp(-t * 35)
    return rng.normal(size=t.size) * np.exp(-t * (70 if kind == "hat" else 22))


def place(track: np.ndarray, sound: np.ndarray, at: float, gain: float) -> None:
    start = int(at * RATE)
    end = min(track.size, start + sound.size)
    if start < track.size:
        track[start:end] += gain * sound[: end - start]


def add_drums(track: np.ndarray, feel: str, beat: float, beats: int, rng: np.random.Generator) -> None:
    patterns = {
        "soft": {"kick": (0, 2.5), "hat": (1, 3), "gain": 0.28},
        "lofi": {"kick": (0, 2.5), "snare": (1, 3), "hat": (0, 0.5, 1, 1.5, 2, 2.5, 3, 3.5), "gain": 0.3},
        "drive": {"kick": (0, 1, 2, 3), "snare": (1, 3), "hat": (0.5, 1.5, 2.5, 3.5), "gain": 0.36},
        "dhol": {"dhol": (0, 0.75, 1.5, 2, 2.75, 3.5), "hat": (1, 3), "gain": 0.46},
    }
    pattern = patterns.get(feel)
    if not pattern:
        return
    for bar in range(0, beats, 4):
        for kind, hits in pattern.items():
            if kind != "gain":
                for hit in hits:
                    place(track, drum(kind, rng), (bar + hit) * beat, pattern["gain"] * (0.35 if kind == "hat" else 1))


def compose(name: str, bpm: int, chords: list, melody: list, feel: str) -> np.ndarray:
    rng = np.random.default_rng(sum(name.encode()))
    beat = 60 / bpm
    bars = max(8, round(24 / (4 * beat)))
    track = np.zeros(int((bars * 4 * beat + 2) * RATE))
    for bar in range(bars):
        root, shape = chords[bar % len(chords)]
        start = bar * 4 * beat
        for interval in shape:
            place(track, tone(hz(root + interval), 4.4 * beat, 0.25, 0.5, 0.15), start, 0.13)
        for hit in (0, 2):
            place(track, tone(hz(root - 12), 1.8 * beat, 0.01, 1.6, 0.3), start + hit * beat, 0.3)
        for step in range(8):  # a melody that follows the chord, resting now and then so it can breathe
            if rng.random() < 0.3:
                continue
            note = root + 12 + melody[int(rng.integers(len(melody)))]
            place(track, tone(hz(note), beat, 0.008, 3.2, 0.25), start + step * beat / 2, 0.16)
    add_drums(track, feel, beat, bars * 4, rng)
    track = track[: int(bars * 4 * beat * RATE)]
    fade = np.linspace(0, 1, int(1.2 * RATE))
    track[: fade.size] *= fade
    track[-fade.size:] *= fade[::-1]
    return track / np.max(np.abs(track)) * 0.85


def main() -> None:
    OUT.mkdir(exist_ok=True)
    for name, (bpm, chords, melody, feel) in TRACKS.items():
        audio = compose(name, bpm, chords, melody, feel)
        raw = OUT / f"{name}.wav"
        with wave.open(str(raw), "wb") as f:
            f.setnchannels(1)
            f.setsampwidth(2)
            f.setframerate(RATE)
            f.writeframes((audio * 32767).astype(np.int16).tobytes())
        subprocess.run(  # noqa: S603
            ["ffmpeg", "-y", "-v", "error", "-i", str(raw), "-c:a", "libmp3lame", "-b:a", "96k", str(OUT / f"{name}.mp3")],  # noqa: S607
            check=True,
        )
        raw.unlink()
        print(name, round(audio.size / RATE), "seconds")


main()
