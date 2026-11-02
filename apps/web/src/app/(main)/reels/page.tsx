"use client";
import { Heart, MessageCircle } from "lucide-react";
import Link from "next/link";
import { useCallback, useState } from "react";
import { TextOverlayView } from "@/components/post/TextOverlay";
import { VideoPlayer } from "@/components/post/VideoPlayer";
import { Avatar, CenterSpinner, Empty } from "@/components/ui";
import { useInfinite, useSentinel } from "@/hooks/useInfinite";
import { api } from "@/lib/api/client";
import type { Post } from "@/lib/api/types";
import { cn, compactNumber } from "@/lib/utils";

function Reel({ post }: { post: Post }) {
  const [liked, setLiked] = useState(post.liked);
  const [likes, setLikes] = useState(post.like_count);
  const media = post.media[0];
  const onView = useCallback(() => {
    api(`/posts/${post.id}/view`, { method: "POST" }).catch(() => undefined);
  }, [post.id]);
  if (!media) return null;
  return (
    <section className="relative h-[calc(100dvh-7rem)] snap-start snap-always bg-black sm:h-dvh">
      <VideoPlayer asset={media} onView={onView} className="h-full w-full object-contain" />
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
      </div>
    </section>
  );
}

export default function ReelsPage() {
  const q = useInfinite<Post>(["reels"], "/reels");
  const sentinel = useSentinel(() => q.fetchNextPage(), !!q.hasNextPage && !q.isFetchingNextPage);
  if (q.isLoading) return <CenterSpinner />;
  if (!q.items.length) return <Empty title="No reels yet" hint="Share a short vertical video from Create." action={<Link href="/new?reel=1" className="font-semibold text-brand">Create a reel</Link>} />;
  return (
    <div className="no-scrollbar mx-auto h-[calc(100dvh-7rem)] max-w-md snap-y snap-mandatory overflow-y-auto sm:h-dvh">
      {q.items.map((p) => (
        <Reel key={p.id} post={p} />
      ))}
      <div ref={sentinel} className="h-1" />
    </div>
  );
}
