"use client";
import { useParams } from "next/navigation";
import { InfiniteGrid } from "@/components/post/InfiniteGrid";

export default function TagPage() {
  const tag = decodeURIComponent(useParams<{ tag: string }>().tag);
  return (
    <div className="mx-auto max-w-4xl sm:p-4">
      <h1 className="p-3 text-xl font-bold">#{tag}</h1>
      <InfiniteGrid queryKey={["tag", tag]} path={`/hashtags/${encodeURIComponent(tag)}/posts`} emptyTitle="No posts with this hashtag" />
    </div>
  );
}
