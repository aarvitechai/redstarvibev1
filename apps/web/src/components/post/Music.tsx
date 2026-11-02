"use client";
import { Music2, Pause, Play, Volume2, VolumeX } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { cn } from "@/lib/utils";
import { useUi } from "@/stores/ui";

/** Original tracks made by scripts/generate_music.py. Ids match MusicTrack in the backend. */
export const TRACKS = [
  { id: "golden-hour", title: "Golden Hour", mood: "Warm" },
  { id: "city-lights", title: "City Lights", mood: "Lo-fi" },
  { id: "monsoon", title: "Monsoon", mood: "Dreamy" },
  { id: "festival", title: "Festival", mood: "Dhol beat" },
  { id: "road-trip", title: "Road Trip", mood: "Upbeat" },
  { id: "sunrise", title: "Sunrise", mood: "Calm" },
] as const;
export type TrackId = (typeof TRACKS)[number]["id"];

const trackSrc = (id: string) => `/music/${id}.mp3`;
const trackTitle = (id: string) => TRACKS.find((t) => t.id === id)?.title;

/** Plays only while on screen. Sound follows the same mute choice as videos, and starts muted as browsers require. */
export function PostMusic({ track, className }: { track: string; className?: string }) {
  const audio = useRef<HTMLAudioElement>(null);
  const chip = useRef<HTMLButtonElement>(null);
  const muted = useUi((s) => s.videoMuted);
  const setMuted = useUi((s) => s.setVideoMuted);
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const el = chip.current;
    if (!el) return;
    const io = new IntersectionObserver(([entry]) => setVisible(!!entry?.isIntersecting), { threshold: 0.5 });
    io.observe(el);
    return () => io.disconnect();
  }, []);

  useEffect(() => {
    const el = audio.current;
    if (!el) return;
    if (visible && !muted) el.play().catch(() => undefined);
    else el.pause();
  }, [visible, muted]);

  const title = trackTitle(track);
  if (!title) return null;
  return (
    <>
      <audio ref={audio} src={trackSrc(track)} loop preload="none" />
      <button
        ref={chip}
        type="button"
        data-testid="post-music"
        aria-label={`${muted ? "Play" : "Mute"} music: ${title}`}
        onClick={() => setMuted(!muted)}
        className={cn("absolute z-10 flex min-h-11 max-w-[70%] items-center", className)}
      >
        <span className="flex h-7 items-center gap-1 truncate rounded-full bg-black/60 px-2.5 text-[11px] font-medium text-white">
          <Music2 aria-hidden className="h-3 w-3 shrink-0" />
          <span className="truncate">{title}</span>
          {muted ? <VolumeX aria-hidden className="h-3 w-3 shrink-0" /> : <Volume2 aria-hidden className="h-3 w-3 shrink-0" />}
        </span>
      </button>
    </>
  );
}

export function MusicPicker({ value, onChange }: { value: TrackId | null; onChange: (track: TrackId | null) => void }) {
  const audio = useRef<HTMLAudioElement>(null);
  const [previewing, setPreviewing] = useState<TrackId | null>(null);

  const preview = (id: TrackId) => {
    const el = audio.current;
    if (!el) return;
    if (previewing === id) {
      el.pause();
      setPreviewing(null);
      return;
    }
    el.src = trackSrc(id);
    el.play().catch(() => undefined);
    setPreviewing(id);
  };

  return (
    <section aria-label="Music" className="space-y-2 rounded-lg border border-line p-3">
      <h2 className="flex items-center gap-1.5 text-sm font-semibold"><Music2 aria-hidden className="h-4 w-4 text-brand" /> Music</h2>
      <audio ref={audio} loop />
      <ul className="grid gap-1 sm:grid-cols-2">
        <li>
          <button type="button" aria-pressed={value === null} onClick={() => onChange(null)} className={cn("flex min-h-11 w-full items-center rounded-lg border px-3 text-left text-sm", value === null ? "border-brand font-semibold text-brand" : "border-line")}>
            No music
          </button>
        </li>
        {TRACKS.map((t) => (
          <li key={t.id} className={cn("flex min-h-11 items-center rounded-lg border", value === t.id ? "border-brand" : "border-line")}>
            <button type="button" aria-pressed={value === t.id} onClick={() => onChange(t.id)} className={cn("flex min-h-11 min-w-0 flex-1 items-center gap-1 px-3 text-left text-sm", value === t.id && "font-semibold text-brand")}>
              <span className="truncate">{t.title}</span> <span className="truncate text-xs font-normal text-muted">{t.mood}</span>
            </button>
            <button type="button" aria-label={`${previewing === t.id ? "Stop" : "Preview"} ${t.title}`} onClick={() => preview(t.id)} className="flex h-11 w-11 shrink-0 items-center justify-center">
              {previewing === t.id ? <Pause aria-hidden className="h-4 w-4" /> : <Play aria-hidden className="h-4 w-4" />}
            </button>
          </li>
        ))}
      </ul>
      <p className="text-xs text-muted">Original tracks, free to use. When a video has music, the music replaces its own sound.</p>
    </section>
  );
}
