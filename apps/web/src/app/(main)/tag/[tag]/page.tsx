"use client";
import { useParams } from "next/navigation";
import { useState } from "react";
import { cn } from "@/lib/utils";
import { InfiniteGrid } from "@/components/post/InfiniteGrid";

export default function TagPage() {
  const tag = decodeURIComponent(useParams<{ tag: string }>().tag);
  const [sort, setSort] = useState<"top" | "recent">("top");
  return (
    <div className="mx-auto max-w-4xl sm:p-4">
      <h1 className="p-3 text-xl font-bold">#{tag}</h1>
      <div role="tablist" className="flex border-b border-line">
        {(["top", "recent"] as const).map((value) => (
          <button key={value} role="tab" aria-selected={sort === value} onClick={() => setSort(value)} className={cn("min-h-11 flex-1 text-sm font-semibold capitalize", sort === value ? "border-b-2 border-brand text-brand" : "text-muted")}>
            {value}
          </button>
        ))}
      </div>
      <InfiniteGrid key={sort} queryKey={["tag", tag, sort]} path={`/hashtags/${encodeURIComponent(tag)}/posts?sort=${sort}`} emptyTitle="No posts with this hashtag" />
    </div>
  );
}
