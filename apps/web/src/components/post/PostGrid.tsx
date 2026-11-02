"use client";
import { Copy, Eye, Pin, Play } from "lucide-react";
import Link from "next/link";
import type { Post } from "@/lib/api/types";
import { compactNumber } from "@/lib/utils";
import { editStyle } from "./mediaEdit";
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
            <div className="h-full w-full" style={editStyle(media.edit)}>
              <MediaImage asset={media} sizes="(max-width: 640px) 33vw, 300px" className="h-full w-full object-cover" alt="" />
            </div>
            {post.pinned && <Pin aria-label="Pinned" className="absolute left-1.5 top-1.5 h-5 w-5 fill-white text-white drop-shadow" />}
            <TextOverlayView overlay={media.text_overlay} />
            {media.kind === "video" && <Play className="absolute right-1.5 top-1.5 h-5 w-5 fill-white text-white drop-shadow" />}
            <span className="absolute bottom-1 left-1.5 flex items-center gap-1 text-xs font-semibold text-white drop-shadow">
              <Eye aria-hidden className="h-3.5 w-3.5" /> {compactNumber(post.view_count)}
            </span>
            {post.media.length > 1 && <Copy className="absolute right-1.5 top-1.5 h-5 w-5 text-white drop-shadow" />}
          </Link>
        );
      })}
    </div>
  );
}
