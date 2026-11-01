"use client";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { useRef, useState } from "react";
import type { Asset } from "@/lib/api/types";
import { cn } from "@/lib/utils";
import { MediaImage } from "./MediaImage";
import { VideoPlayer } from "./VideoPlayer";

const SIZES = "(max-width: 640px) 100vw, 470px";

export function MediaCarousel({ media, priority, onView }: { media: Asset[]; priority?: boolean; onView?: () => void }) {
  const [index, setIndex] = useState(0);
  const track = useRef<HTMLDivElement>(null);
  const first = media[0];
  const ratio = first?.width && first?.height ? Math.max(0.8, Math.min(1.91, first.width / first.height)) : 1;
  const go = (i: number) => {
    const el = track.current;
    if (el) el.scrollTo({ left: el.clientWidth * i, behavior: "smooth" });
  };
  return (
    <div className="relative bg-surface" style={{ aspectRatio: ratio }}>
      <div
        ref={track}
        onScroll={(e) => setIndex(Math.round(e.currentTarget.scrollLeft / Math.max(1, e.currentTarget.clientWidth)))}
        className="no-scrollbar flex h-full snap-x snap-mandatory overflow-x-auto"
      >
        {media.map((asset, i) => (
          <div key={asset.id} className="h-full w-full shrink-0 snap-center">
            {asset.kind === "video" ? (
              <VideoPlayer asset={asset} onView={onView} className="h-full w-full object-contain" />
            ) : (
              <MediaImage asset={asset} sizes={SIZES} priority={priority && i === 0} className="h-full w-full object-cover" />
            )}
          </div>
        ))}
      </div>
      {media.length > 1 && (
        <>
          {index > 0 && (
            <button aria-label="Previous" onClick={() => go(index - 1)} className="absolute left-1 top-1/2 flex h-11 w-11 -translate-y-1/2 items-center justify-center rounded-full bg-black/40 text-white">
              <ChevronLeft className="h-5 w-5" />
            </button>
          )}
          {index < media.length - 1 && (
            <button aria-label="Next" onClick={() => go(index + 1)} className="absolute right-1 top-1/2 flex h-11 w-11 -translate-y-1/2 items-center justify-center rounded-full bg-black/40 text-white">
              <ChevronRight className="h-5 w-5" />
            </button>
          )}
          <div className="absolute bottom-2 left-1/2 flex -translate-x-1/2 gap-1">
            {media.map((asset, i) => (
              <span key={asset.id} className={cn("h-1.5 w-1.5 rounded-full", i === index ? "bg-brand" : "bg-white/70")} />
            ))}
          </div>
        </>
      )}
    </div>
  );
}
