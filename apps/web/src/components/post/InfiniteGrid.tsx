"use client";
import { CenterSpinner, Empty } from "@/components/ui";
import { useInfinite, useSentinel } from "@/hooks/useInfinite";
import type { Post } from "@/lib/api/types";
import { PostGrid } from "./PostGrid";

export function InfiniteGrid({ queryKey, path, emptyTitle, emptyHint }: { queryKey: unknown[]; path: string; emptyTitle: string; emptyHint?: string }) {
  const q = useInfinite<Post>(queryKey, path);
  const sentinel = useSentinel(() => q.fetchNextPage(), !!q.hasNextPage && !q.isFetchingNextPage);
  if (q.isLoading) return <CenterSpinner />;
  if (q.isError) return <Empty title="Could not load posts" hint={(q.error as Error).message} />;
  if (q.items.length === 0) return <Empty title={emptyTitle} hint={emptyHint} />;
  return (
    <>
      <PostGrid posts={q.items} />
      <div ref={sentinel} />
      {q.isFetchingNextPage && <CenterSpinner />}
    </>
  );
}
