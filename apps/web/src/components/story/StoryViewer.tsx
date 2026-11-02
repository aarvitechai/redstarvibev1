"use client";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ChevronLeft, ChevronRight, Eye, Trash2, X } from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { MediaImage } from "@/components/post/MediaImage";
import { VideoPlayer } from "@/components/post/VideoPlayer";
import { Avatar, Modal, UserRow } from "@/components/ui";
import { api, errorMessage } from "@/lib/api/client";
import type { Story, StoryActivity, UserBrief } from "@/lib/api/types";
import { cn, timeAgo } from "@/lib/utils";
import { useUi } from "@/stores/ui";
import { StoryFrame } from "./frames";

const IMAGE_MS = 5000;
const STICKER_MS = 15000;
const EMOJIS = ["❤️", "🔥", "😂", "😮", "😢", "👏"];

function Sticker({ story, ownerIsMe, onChange }: { story: Story; ownerIsMe: boolean; onChange: (s: Story) => void }) {
  const toast = useUi((s) => s.showToast);
  const sticker = story.sticker;
  if (!sticker) return null;
  const total = (sticker.counts ?? []).reduce((a, b) => a + b, 0);
  const answered = sticker.counts != null;
  return (
    <div data-testid="story-sticker" className="absolute inset-x-12 top-1/2 z-10 -translate-y-1/2 rounded-xl bg-white p-3 text-sm text-black shadow-lg">
      <p className="pb-2 text-center font-bold">{sticker.question}</p>
      <div className="space-y-1">
        {sticker.options.map((option, i) => {
          const share = total ? Math.round(((sticker.counts?.[i] ?? 0) / total) * 100) : 0;
          const isCorrect = sticker.correct === i;
          return (
            <button
              key={i}
              disabled={answered || ownerIsMe}
              aria-pressed={sticker.my_answer === i}
              className={cn("relative block min-h-11 w-full overflow-hidden rounded-lg border border-black/20 px-3 text-left", sticker.my_answer === i && "font-bold")}
              onClick={async () => {
                try {
                  onChange(await api<Story>(`/stories/${story.id}/answer`, { json: { option: i } }));
                } catch (e) {
                  toast(errorMessage(e));
                }
              }}
            >
              {answered && <span aria-hidden className="absolute inset-y-0 left-0 bg-black/10" style={{ width: `${share}%` }} />}
              <span className="relative flex items-center justify-between gap-2">
                <span>{option}{sticker.kind === "quiz" && answered && isCorrect ? " (correct)" : ""}</span>
                {answered && <span className="tabular-nums">{share}%</span>}
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
}

export function StoryViewer({ stories, ownerIsMe, onClose, onDone }: { stories: Story[]; ownerIsMe: boolean; onClose: () => void; onDone?: () => void }) {
  const [index, setIndex] = useState(0);
  const [progress, setProgress] = useState(0);
  const [viewersOpen, setViewersOpen] = useState(false);
  const [changed, setChanged] = useState<Record<string, Story>>({});
  const qc = useQueryClient();
  const toast = useUi((s) => s.showToast);
  const touchX = useRef<number | null>(null);
  const original = stories[index];
  const story = original ? (changed[original.id] ?? original) : undefined;
  const durationMs = story?.media.kind === "video" ? Math.min(60_000, (story.media.duration ?? 15) * 1000) : story?.sticker ? STICKER_MS : IMAGE_MS;

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
    if (original && !ownerIsMe) {
      api(`/stories/${original.id}/view`, { method: "POST" }).catch(() => undefined);
    }
  }, [original?.id, ownerIsMe]); // eslint-disable-line react-hooks/exhaustive-deps

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
  const activity = useQuery({
    queryKey: ["story-activity", story?.id],
    enabled: viewersOpen && !!story,
    queryFn: () => api<StoryActivity[]>(`/stories/${story!.id}/activity`),
  });
  const react = async (emoji: string) => {
    if (!story) return;
    const removing = story.my_reaction === emoji;
    try {
      await api(`/stories/${story.id}/react`, removing ? { method: "DELETE" } : { json: { emoji } });
      setChanged((c) => ({ ...c, [story.id]: { ...story, my_reaction: removing ? null : emoji } }));
    } catch (e) {
      toast(errorMessage(e));
    }
  };

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
        <StoryFrame frame={story.frame} />
        {story.audience === "close_friends" && <p className="absolute right-3 top-16 z-10 rounded-full bg-green-700 px-2 py-0.5 text-xs font-semibold text-white">Close friends</p>}
        <Sticker story={story} ownerIsMe={ownerIsMe} onChange={(s) => setChanged((c) => ({ ...c, [s.id]: s }))} />
        <button aria-label="Previous story" onClick={prev} className="absolute left-0 top-1/2 flex h-16 w-11 -translate-y-1/2 items-center justify-center text-white/80">
          <ChevronLeft className="h-7 w-7" />
        </button>
        <button aria-label="Next story" onClick={next} className="absolute right-0 top-1/2 flex h-16 w-11 -translate-y-1/2 items-center justify-center text-white/80">
          <ChevronRight className="h-7 w-7" />
        </button>
        {!ownerIsMe && (
          <div role="group" aria-label="React to this story" className="absolute inset-x-0 bottom-0 z-10 flex justify-center gap-1 p-2 pb-[max(0.5rem,env(safe-area-inset-bottom))]">
            {EMOJIS.map((emoji) => (
              <button key={emoji} aria-label={`React ${emoji}`} aria-pressed={story.my_reaction === emoji} onClick={() => react(emoji)} className={cn("flex h-11 w-11 items-center justify-center rounded-full text-xl", story.my_reaction === emoji && "bg-white/30")}>
                {emoji}
              </button>
            ))}
          </div>
        )}
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
        {!!activity.data?.length && <h3 className="pt-3 text-sm font-semibold">Reactions and answers</h3>}
        {activity.data?.map((a) => (
          <p key={a.user.id} className="flex min-h-9 items-center justify-between gap-2 text-sm">
            <span className="truncate font-medium">{a.user.username}</span>
            <span className="shrink-0">{a.reaction}{a.answer != null && story.sticker ? ` ${story.sticker.options[a.answer]}` : ""}</span>
          </p>
        ))}
      </Modal>
    </div>
  );
}
