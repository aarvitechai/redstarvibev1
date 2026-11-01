"use client";
import { InfiniteGrid } from "@/components/post/InfiniteGrid";

export default function ExplorePage() {
  return (
    <div className="mx-auto max-w-4xl sm:p-4">
      <h1 className="sr-only">Explore</h1>
      <InfiniteGrid queryKey={["explore"]} path="/explore" emptyTitle="Nothing to explore yet" emptyHint="New posts from people you do not follow will show up here." />
    </div>
  );
}
