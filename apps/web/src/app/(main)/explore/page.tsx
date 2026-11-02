"use client";
import { useState } from "react";
import { InterestPicker } from "@/components/feed/InterestPicker";
import { InfiniteGrid } from "@/components/post/InfiniteGrid";
import { cn } from "@/lib/utils";

const TABS = [
  { id: "for-you", label: "For You", path: "/feed/for-you", hint: "Like a few posts or choose interests, and this page starts to fit you." },
  { id: "latest", label: "Latest", path: "/explore", hint: "New posts from people you do not follow will show up here." },
] as const;

export default function ExplorePage() {
  const [tab, setTab] = useState<(typeof TABS)[number]["id"]>("for-you");
  const current = TABS.find((t) => t.id === tab) ?? TABS[0];
  return (
    <div className="mx-auto max-w-4xl space-y-2 sm:p-4">
      <h1 className="sr-only">Explore</h1>
      <div role="tablist" className="grid grid-cols-2 gap-1 p-2 sm:p-0">
        {TABS.map((t) => (
          <button key={t.id} role="tab" aria-selected={tab === t.id} onClick={() => setTab(t.id)} className={cn("min-h-11 rounded-lg text-sm font-semibold", tab === t.id ? "bg-brand text-white" : "bg-surface")}>
            {t.label}
          </button>
        ))}
      </div>
      {tab === "for-you" && <InterestPicker />}
      <InfiniteGrid key={current.id} queryKey={[current.id === "for-you" ? "for-you" : "explore"]} path={current.path} emptyTitle="Nothing to explore yet" emptyHint={current.hint} />
    </div>
  );
}
