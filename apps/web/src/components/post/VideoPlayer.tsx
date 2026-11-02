"use client";
import { Play, Volume2, VolumeX } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import type { Asset } from "@/lib/api/types";
import { useUi } from "@/stores/ui";

const SPEEDS = [1, 1.5, 2];
const CONTROL = "flex h-11 w-11 items-center justify-center";
const CONTROL_FACE = "flex h-7 min-w-7 items-center justify-center rounded-full bg-black/60 px-1 text-[11px] font-semibold text-white";

/** HLS adaptive playback. hls.js is imported only when a video actually comes into view. */
export function VideoPlayer({ asset, className, loop = true, onView, silent }: { asset: Asset; className?: string; loop?: boolean; onView?: () => void; silent?: boolean }) {
  const ref = useRef<HTMLVideoElement>(null);
  const soundOff = useUi((s) => s.videoMuted);
  const muted = silent || soundOff; // when the post has music, the music replaces the video's own sound
  const setMuted = useUi((s) => s.setVideoMuted);
  const [playing, setPlaying] = useState(false);
  const [started, setStarted] = useState(false);
  const [progress, setProgress] = useState(0);
  const [speed, setSpeed] = useState(SPEEDS[0] as number);
  const counted = useRef(false);

  useEffect(() => {
    const video = ref.current;
    if (!video || !asset.hls) return;
    let hls: { destroy: () => void } | null = null;
    let attached = false;
    const attach = async () => {
      if (attached) return;
      attached = true;
      if (video.canPlayType("application/vnd.apple.mpegurl")) {
        video.src = asset.hls!;
      } else {
        const { default: Hls } = await import("hls.js");
        if (Hls.isSupported()) {
          const instance = new Hls({ capLevelToPlayerSize: true });
          instance.loadSource(asset.hls!);
          instance.attachMedia(video);
          hls = instance;
        }
      }
    };
    const io = new IntersectionObserver(
      ([entry]) => {
        if (entry?.isIntersecting) {
          attach().then(() => video.play().catch(() => undefined));
          if (!counted.current) {
            counted.current = true;
            onView?.();
          }
        } else video.pause();
      },
      { threshold: 0.6 },
    );
    io.observe(video);
    return () => {
      io.disconnect();
      hls?.destroy();
    };
  }, [asset.hls, onView]);

  const togglePlay = () => {
    const video = ref.current;
    if (!video) return;
    if (video.paused) video.play().catch(() => undefined);
    else video.pause();
  };
  const nextSpeed = () => {
    const next = SPEEDS[(SPEEDS.indexOf(speed) + 1) % SPEEDS.length] as number;
    setSpeed(next);
    if (ref.current) ref.current.playbackRate = next;
  };
  const seek = (fraction: number) => {
    const video = ref.current;
    if (video && Number.isFinite(video.duration)) video.currentTime = fraction * video.duration;
    setProgress(fraction);
  };

  return (
    <div className="relative h-full w-full bg-black">
      <video
        ref={ref}
        poster={asset.poster ?? undefined}
        muted={muted}
        loop={loop}
        playsInline
        crossOrigin="anonymous"
        className={className}
        onPlay={() => { setPlaying(true); setStarted(true); }}
        onPause={() => setPlaying(false)}
        onTimeUpdate={(e) => {
          const { currentTime, duration } = e.currentTarget;
          if (Number.isFinite(duration) && duration > 0) setProgress(currentTime / duration);
        }}
      >
        {asset.subtitles && <track kind="subtitles" src={asset.subtitles} srcLang="en" label="Subtitles" default />}
      </video>
      <button type="button" data-surface aria-label={playing ? "Pause" : "Play"} onClick={togglePlay} className="absolute inset-0 flex items-center justify-center">
        {started && !playing && (
          <span className="flex h-11 w-11 items-center justify-center rounded-full bg-black/60 text-white">
            <Play aria-hidden className="h-5 w-5 fill-white" />
          </span>
        )}
      </button>
      <div className="absolute bottom-1 right-1 flex">
        <button type="button" aria-label={`Playback speed ${speed}x`} onClick={nextSpeed} className={CONTROL}>
          <span className={CONTROL_FACE}>{speed}x</span>
        </button>
        {!silent && (
          <button type="button" aria-label={muted ? "Unmute" : "Mute"} onClick={() => setMuted(!muted)} className={CONTROL}>
            <span className={CONTROL_FACE}>{muted ? <VolumeX className="h-3.5 w-3.5" /> : <Volume2 className="h-3.5 w-3.5" />}</span>
          </button>
        )}
      </div>
      <input
        type="range"
        aria-label="Seek"
        min={0}
        max={1}
        step={0.001}
        value={progress}
        onChange={(e) => seek(Number(e.target.value))}
        className="absolute inset-x-0 bottom-0 h-1 w-full cursor-pointer accent-[#C8102E]"
      />
    </div>
  );
}
