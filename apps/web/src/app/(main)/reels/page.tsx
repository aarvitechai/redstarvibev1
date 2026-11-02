"use client";
import { ArrowDown, ArrowUp, Eye, Heart, MessageCircle } from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { editStyle } from "@/components/post/mediaEdit";
import { TextOverlayView } from "@/components/post/TextOverlay";
import { VideoPlayer } from "@/components/post/VideoPlayer";
import { Avatar, CenterSpinner, Empty } from "@/components/ui";
import { useInfinite, useSentinel } from "@/hooks/useInfinite";
import { api } from "@/lib/api/client";
import type { Post } from "@/lib/api/types";
import { cn, compactNumber } from "@/lib/utils";

const ARROW = "flex h-11 w-11 items-center justify-center rounded-full border border-line bg-surface hover:bg-line disabled:opacity-40";

function Reel({ post }: { post: Post }) {
  const [liked, setLiked] = useState(post.liked);
  const [likes, setLikes] = useState(post.like_count);
  const [views, setViews] = useState(post.view_count);
  const media = post.media[0];
  const onView = useCallback(() => {
    api<{ view_count: number }>(`/posts/${post.id}/view`, { method: "POST" })
      .then((r) => setViews(r.view_count))
      .catch(() => undefined);
  }, [post.id]);
  if (!media) return null;
  return (
    <section className="relative h-[calc(100dvh-7rem)] snap-start snap-always bg-black sm:h-dvh">
      <div className="h-full w-full" style={editStyle(media.edit)}>
        <VideoPlayer asset={media} onView={onView} className="h-full w-full object-contain" />
      </div>
      <TextOverlayView overlay={media.text_overlay} />
      <div className="absolute bottom-16 left-3 right-16 text-white drop-shadow">
        <Link href={`/${post.author.username}`} className="flex items-center gap-2 font-semibold">
          <Avatar user={post.author} size={32} /> {post.author.username}
        </Link>
        <p className="mt-1 line-clamp-2 text-sm">{post.caption}</p>
      </div>
      <div className="absolute bottom-20 right-1 flex flex-col items-center gap-2 text-white">
        <button
          aria-label={liked ? "Unlike" : "Like"}
          className="flex h-11 w-11 items-center justify-center"
          onClick={async () => {
            const next = !liked;
            setLiked(next);
            const res = await api<{ like_count: number }>(`/posts/${post.id}/like`, { method: next ? "POST" : "DELETE" });
            setLikes(res.like_count);
          }}
        >
          <Heart className={cn("h-7 w-7", liked && "fill-brand stroke-brand")} />
        </button>
        <span className="text-xs">{compactNumber(likes)}</span>
        <Link href={`/p/${post.id}`} aria-label="Comments" className="flex h-11 w-11 items-center justify-center">
          <MessageCircle className="h-7 w-7" />
        </Link>
        <span className="text-xs">{compactNumber(post.comment_count)}</span>
        <Eye aria-hidden className="mt-2 h-6 w-6" />
        <span className="text-xs" aria-label={`${views} views`}>{compactNumber(views)}</span>
      </div>
    </section>
  );
}

export default function ReelsPage() {
  const q = useInfinite<Post>(["reels"], "/reels");
  const sentinel = useSentinel(() => q.fetchNextPage(), !!q.hasNextPage && !q.isFetchingNextPage);
  const list = useRef<HTMLDivElement>(null);
  const [ends, setEnds] = useState({ top: true, bottom: false });
  const move = useCallback((direction: 1 | -1) => {
    const el = list.current;
    if (el) el.scrollBy({ top: direction * el.clientHeight, behavior: "smooth" });
  }, []);
  const onScroll = () => {
    const el = list.current;
    if (el) setEnds({ top: el.scrollTop < 8, bottom: el.scrollTop + el.clientHeight >= el.scrollHeight - 8 });
  };
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== "ArrowDown" && e.key !== "ArrowUp") return;
      if ((e.target as HTMLElement).closest("input, textarea, select, [contenteditable=true]")) return;
      e.preventDefault();
      move(e.key === "ArrowDown" ? 1 : -1);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [move]);
  if (q.isLoading) return <CenterSpinner />;
  if (!q.items.length) return <Empty title="No reels yet" hint="Share a short vertical video from Create." action={<Link href="/new?reel=1" className="font-semibold text-brand">Create a reel</Link>} />;
  return (
    <div className="relative mx-auto max-w-md">
      <div ref={list} onScroll={onScroll} className="no-scrollbar h-[calc(100dvh-7rem)] snap-y snap-mandatory overflow-y-auto sm:h-dvh">
        {q.items.map((p) => (
          <Reel key={p.id} post={p} />
        ))}
        <div ref={sentinel} className="h-1" />
      </div>
      <div className="absolute left-full top-1/2 ml-3 hidden -translate-y-1/2 flex-col gap-3 lg:flex">
        <button type="button" aria-label="Previous reel" disabled={ends.top} onClick={() => move(-1)} className={ARROW}>
          <ArrowUp aria-hidden className="h-5 w-5" />
        </button>
        <button type="button" aria-label="Next reel" disabled={ends.bottom} onClick={() => move(1)} className={ARROW}>
          <ArrowDown aria-hidden className="h-5 w-5" />
        </button>
      </div>
    </div>
  );
}
