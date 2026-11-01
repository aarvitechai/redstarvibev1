"use client";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";
import { PostCard } from "@/components/post/PostCard";
import { StoryBar } from "@/components/story/StoryBar";
import { Button, CenterSpinner, Empty, UserRow } from "@/components/ui";
import { useInfinite, useSentinel } from "@/hooks/useInfinite";
import { api, errorMessage } from "@/lib/api/client";
import type { Post, UserBrief } from "@/lib/api/types";

function FollowButton({ user }: { user: UserBrief }) {
  const [state, setState] = useState<"idle" | "busy" | "done">("idle");
  const qc = useQueryClient();
  return (
    <Button
      variant="ghost"
      className="!text-brand"
      loading={state === "busy"}
      disabled={state === "done"}
      onClick={async () => {
        setState("busy");
        await api(`/users/${user.username}/follow`, { method: "POST" });
        setState("done");
        setTimeout(() => qc.invalidateQueries({ queryKey: ["feed"] }), 800);
      }}
    >
      {state === "done" ? "Following" : "Follow"}
    </Button>
  );
}

function Suggestions() {
  const q = useQuery({ queryKey: ["suggestions"], queryFn: () => api<UserBrief[]>("/users/suggestions?limit=6") });
  if (!q.data?.length) return null;
  return (
    <section aria-label="Suggested for you">
      <h2 className="mb-1 text-sm font-semibold text-muted">Suggested for you</h2>
      {q.data.map((u) => (
        <UserRow key={u.id} user={u} action={<FollowButton user={u} />} />
      ))}
    </section>
  );
}

export default function FeedPage() {
  const feed = useInfinite<Post>(["feed"], "/feed");
  const sentinel = useSentinel(() => feed.fetchNextPage(), !!feed.hasNextPage && !feed.isFetchingNextPage);
  return (
    <div className="mx-auto flex max-w-[960px] justify-center gap-10 sm:px-4 sm:pt-4">
      <div className="w-full min-w-0 max-w-[470px] space-y-0 sm:space-y-4">
        <StoryBar />
        {feed.isLoading ? (
          <CenterSpinner />
        ) : feed.isError ? (
          <Empty title="Could not load your feed" hint={errorMessage(feed.error)} action={<Button onClick={() => feed.refetch()}>Try again</Button>} />
        ) : feed.items.length === 0 ? (
          <div>
            <Empty title="Your feed is empty" hint="Follow people to see their posts here." action={<Link href="/explore" className="font-semibold text-brand">Explore posts</Link>} />
            <div className="px-3 lg:hidden">
              <Suggestions />
            </div>
          </div>
        ) : (
          feed.items.map((p, i) => <PostCard key={p.id} post={p} priority={i === 0} onRemoved={() => feed.refetch()} />)
        )}
        <div ref={sentinel} />
        {feed.isFetchingNextPage && <CenterSpinner />}
      </div>
      <aside className="sticky top-4 hidden h-fit w-72 shrink-0 lg:block">
        <Suggestions />
      </aside>
    </div>
  );
}
