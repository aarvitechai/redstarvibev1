"use client";
import { Copy, Play } from "lucide-react";
import Link from "next/link";
import type { Post } from "@/lib/api/types";
import { MediaImage } from "./MediaImage";
import { TextOverlayView } from "./TextOverlay";

export function PostGrid({ posts }: { posts: Post[] }) {
  return (
    <div className="grid grid-cols-3 gap-0.5 sm:gap-1">
      {posts.map((post) => {
        const media = post.media[0];
        if (!media) return null;
        return (
          <Link key={post.id} href={`/p/${post.id}`} className="grid-item relative block aspect-square overflow-hidden bg-surface" aria-label={post.caption || `Post by ${post.author.username}`}>
            <MediaImage asset={media} sizes="(max-width: 640px) 33vw, 300px" className="h-full w-full object-cover" alt="" />
            <TextOverlayView overlay={media.text_overlay} />
            {media.kind === "video" && <Play className="absolute right-1.5 top-1.5 h-5 w-5 fill-white text-white drop-shadow" />}
            {post.media.length > 1 && <Copy className="absolute right-1.5 top-1.5 h-5 w-5 text-white drop-shadow" />}
          </Link>
        );
      })}
    </div>
  );
}
