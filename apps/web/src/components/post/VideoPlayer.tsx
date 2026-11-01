"use client";
import { Volume2, VolumeX } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import type { Asset } from "@/lib/api/types";

/** HLS adaptive playback. hls.js is imported only when a video actually comes into view. */
export function VideoPlayer({ asset, className, loop = true, onView }: { asset: Asset; className?: string; loop?: boolean; onView?: () => void }) {
  const ref = useRef<HTMLVideoElement>(null);
  const [muted, setMuted] = useState(true);
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

  return (
    <div className="relative h-full w-full bg-black">
      <video ref={ref} poster={asset.poster ?? undefined} muted={muted} loop={loop} playsInline crossOrigin="anonymous" className={className}>
        {asset.subtitles && <track kind="subtitles" src={asset.subtitles} srcLang="en" label="Subtitles" default />}
      </video>
      <button
        aria-label={muted ? "Unmute" : "Mute"}
        onClick={() => setMuted(!muted)}
        className="absolute bottom-3 right-3 flex h-11 w-11 items-center justify-center rounded-full bg-black/60 text-white"
      >
        {muted ? <VolumeX className="h-5 w-5" /> : <Volume2 className="h-5 w-5" />}
      </button>
    </div>
  );
}
