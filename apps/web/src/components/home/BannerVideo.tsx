"use client";
import { Pause, Play } from "lucide-react";
import { useEffect, useRef, useState } from "react";

/** Decorative muted loop behind the banner. Honours reduced motion and can always be paused (WCAG 2.2.2). */
export function BannerVideo() {
  const ref = useRef<HTMLVideoElement>(null);
  const [playing, setPlaying] = useState(false);
  useEffect(() => {
    if (!matchMedia("(prefers-reduced-motion: reduce)").matches) ref.current?.play().catch(() => undefined);
  }, []);
  return (
    <>
      <video
        ref={ref}
        data-testid="banner-video"
        src="/home/banner.mp4"
        poster="/home/banner-poster.jpg"
        muted
        loop
        playsInline
        preload="metadata"
        aria-hidden
        onPlay={() => setPlaying(true)}
        onPause={() => setPlaying(false)}
        className="absolute inset-0 h-full w-full object-cover"
      />
      <button
        type="button"
        aria-label={playing ? "Pause background video" : "Play background video"}
        onClick={() => (playing ? ref.current?.pause() : ref.current?.play())}
        className="absolute bottom-3 right-3 z-10 flex h-11 w-11 items-center justify-center rounded-full bg-black/50 text-white hover:bg-black/70"
      >
        {playing ? <Pause className="h-5 w-5" /> : <Play className="h-5 w-5" />}
      </button>
    </>
  );
}
