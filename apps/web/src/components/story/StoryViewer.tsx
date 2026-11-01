"use client";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ChevronLeft, ChevronRight, Eye, Trash2, X } from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { MediaImage } from "@/components/post/MediaImage";
import { VideoPlayer } from "@/components/post/VideoPlayer";
import { Avatar, Modal, UserRow } from "@/components/ui";
import { api } from "@/lib/api/client";
import type { Story, UserBrief } from "@/lib/api/types";
import { cn, timeAgo } from "@/lib/utils";

const IMAGE_MS = 5000;

export function StoryViewer({ stories, ownerIsMe, onClose, onDone }: { stories: Story[]; ownerIsMe: boolean; onClose: () => void; onDone?: () => void }) {
  const [index, setIndex] = useState(0);
  const [progress, setProgress] = useState(0);
  const [viewersOpen, setViewersOpen] = useState(false);
  const qc = useQueryClient();
  const touchX = useRef<number | null>(null);
  const story = stories[index];
  const durationMs = story?.media.kind === "video" ? Math.min(60_000, (story.media.duration ?? 15) * 1000) : IMAGE_MS;

  const next = useCallback(() => {
    if (index + 1 < stories.length) {
      setIndex(index + 1);
      setProgress(0);
    } else {
      onDone?.();
      onClose();
    }
  }, [index, stories.length, onClose, onDone]);
  const prev = () => {
    setIndex(Math.max(0, index - 1));
    setProgress(0);
  };

  useEffect(() => {
    if (story && !ownerIsMe) {
      api(`/stories/${story.id}/view`, { method: "POST" }).catch(() => undefined);
    }
  }, [story, ownerIsMe]);

  useEffect(() => {
    if (viewersOpen) return;
    const startedAt = Date.now() - progress * durationMs;
    const timer = setInterval(() => {
      const value = (Date.now() - startedAt) / durationMs;
      if (value >= 1) next();
      else setProgress(value);
    }, 80);
    return () => clearInterval(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [index, durationMs, next, viewersOpen]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "ArrowRight") next();
      else if (e.key === "ArrowLeft") prev();
      else if (e.key === "Escape") onClose();
    };
    addEventListener("keydown", onKey);
    return () => removeEventListener("keydown", onKey);
  });

  const viewers = useQuery({
    queryKey: ["story-viewers", story?.id],
    enabled: viewersOpen && !!story,
    queryFn: () => api<UserBrief[]>(`/stories/${story!.id}/viewers`),
  });

  if (!story) return null;
  return (
    <div
      role="dialog"
      aria-label={`Story by ${story.author.username}`}
      className="fixed inset-0 z-50 flex items-center justify-center bg-black"
      onTouchStart={(e) => (touchX.current = e.touches[0]?.clientX ?? null)}
      onTouchEnd={(e) => {
        const start = touchX.current;
        const end = e.changedTouches[0]?.clientX;
        if (start != null && end != null && Math.abs(end - start) > 50) {
          if (end < start) next();
          else prev();
        }
      }}
    >
      <div className="relative h-full w-full max-w-md">
        <div className="absolute inset-x-2 top-2 z-10 flex gap-1 pt-[env(safe-area-inset-top)]">
          {stories.map((s, i) => (
            <span key={s.id} className="h-0.5 flex-1 overflow-hidden rounded bg-white/40">
              <span className={cn("block h-full bg-white")} style={{ width: i < index ? "100%" : i === index ? `${progress * 100}%` : 0 }} />
            </span>
          ))}
        </div>
        <div className="absolute inset-x-2 top-5 z-10 flex items-center gap-2 pt-[env(safe-area-inset-top)] text-white">
          <Link href={`/${story.author.username}`} className="flex min-w-0 items-center gap-2">
            <Avatar user={story.author} size={32} />
            <span className="truncate text-sm font-semibold">{story.author.username}</span>
          </Link>
          <span className="text-xs opacity-80">{timeAgo(story.created_at)}</span>
          <button aria-label="Close" onClick={onClose} className="ml-auto flex h-11 w-11 items-center justify-center">
            <X className="h-6 w-6" />
          </button>
        </div>
        {story.media.kind === "video" ? (
          <VideoPlayer key={story.id} asset={story.media} loop={false} className="h-full w-full object-contain" />
        ) : (
          <MediaImage key={story.id} asset={story.media} sizes="448px" priority className="h-full w-full object-contain" />
        )}
        <button aria-label="Previous story" onClick={prev} className="absolute left-0 top-1/2 flex h-16 w-11 -translate-y-1/2 items-center justify-center text-white/80">
          <ChevronLeft className="h-7 w-7" />
        </button>
        <button aria-label="Next story" onClick={next} className="absolute right-0 top-1/2 flex h-16 w-11 -translate-y-1/2 items-center justify-center text-white/80">
          <ChevronRight className="h-7 w-7" />
        </button>
        {ownerIsMe && (
          <div className="absolute inset-x-0 bottom-0 flex items-center justify-between p-3 pb-[max(0.75rem,env(safe-area-inset-bottom))] text-white">
            <button className="flex min-h-11 items-center gap-2 text-sm" onClick={() => setViewersOpen(true)}>
              <Eye className="h-5 w-5" /> {story.view_count} viewers
            </button>
            <button
              aria-label="Delete story"
              className="flex h-11 w-11 items-center justify-center"
              onClick={async () => {
                await api(`/stories/${story.id}`, { method: "DELETE" });
                qc.invalidateQueries({ queryKey: ["stories"] });
                onClose();
              }}
            >
              <Trash2 className="h-5 w-5" />
            </button>
          </div>
        )}
      </div>
      <Modal open={viewersOpen} onClose={() => setViewersOpen(false)} title="Viewers">
        {(viewers.data ?? []).map((u) => (
          <UserRow key={u.id} user={u} />
        ))}
        {viewers.data?.length === 0 && <p className="text-sm text-muted">No viewers yet.</p>}
      </Modal>
    </div>
  );
}
