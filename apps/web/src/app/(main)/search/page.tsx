"use client";
import { Hash, MapPin, Search } from "lucide-react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { PostGrid } from "@/components/post/PostGrid";
import { useDebounced } from "@/components/search/SearchBox";
import { Button, CenterSpinner, Empty, Input, UserRow } from "@/components/ui";
import { useInfinite, useSentinel } from "@/hooks/useInfinite";
import type { HashtagOut, PlaceOut, Post, UserBrief } from "@/lib/api/types";
import { cn } from "@/lib/utils";

const TABS = [
  ["posts", "Posts"],
  ["users", "People"],
  ["tags", "Tags"],
  ["places", "Places"],
] as const;
type Tab = (typeof TABS)[number][0];

function Row({ href, icon, title, count }: { href: string; icon: React.ReactNode; title: string; count: number }) {
  return (
    <Link href={href} className="flex min-h-14 items-center gap-3">
      <span className="flex h-11 w-11 items-center justify-center rounded-full bg-surface">{icon}</span>
      <span className="text-sm"><b>{title}</b><span className="block text-muted">{count} posts</span></span>
    </Link>
  );
}

function Results({ q, tab }: { q: string; tab: Tab }) {
  const list = useInfinite<Post | UserBrief | HashtagOut | PlaceOut>(["search", tab, q], `/search?q=${encodeURIComponent(q)}&type=${tab}`);
  const sentinel = useSentinel(() => list.fetchNextPage(), !!list.hasNextPage && !list.isFetchingNextPage);
  if (list.isLoading) return <CenterSpinner />;
  if (!list.items.length) return <Empty title="No results" hint={`Nothing matched "${q}"`} />;
  return (
    <>
      {tab === "posts" && <PostGrid posts={list.items as Post[]} />}
      {tab === "users" && (list.items as UserBrief[]).map((u) => <UserRow key={u.id} user={u} />)}
      {tab === "tags" && (list.items as HashtagOut[]).map((t) => (
        <Row key={t.tag} href={`/tag/${encodeURIComponent(t.tag)}`} icon={<Hash className="h-5 w-5" />} title={`#${t.tag}`} count={t.post_count} />
      ))}
      {tab === "places" && (list.items as PlaceOut[]).map((p) => (
        <Row key={p.name} href={`/place/${encodeURIComponent(p.name)}`} icon={<MapPin className="h-5 w-5" />} title={p.name} count={p.post_count} />
      ))}
      <div ref={sentinel} />
      {list.hasNextPage && <Button variant="ghost" className="w-full" loading={list.isFetchingNextPage} onClick={() => list.fetchNextPage()}>Load more</Button>}
    </>
  );
}

function SearchInner() {
  const [text, setText] = useState(useSearchParams().get("q") ?? "");
  const [tab, setTab] = useState<Tab>("posts");
  const q = useDebounced(text.trim());
  return (
    <div className="mx-auto max-w-4xl p-3 sm:p-4">
      <h1 className="sr-only">Search</h1>
      <div className="relative">
        <Search aria-hidden className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" />
        <Input aria-label="Search" placeholder="Try: goa ki shaam" className="!pl-9" value={text} onChange={(e) => setText(e.target.value)} autoFocus />
      </div>
      <div role="tablist" className="my-3 grid grid-cols-4 gap-1">
        {TABS.map(([value, label]) => (
          <button key={value} role="tab" aria-selected={tab === value} onClick={() => setTab(value)} className={cn("min-h-11 rounded-lg text-sm font-semibold", tab === value ? "bg-brand text-white" : "bg-surface")}>
            {label}
          </button>
        ))}
      </div>
      {q ? <Results q={q} tab={tab} /> : <Empty title="Search RedStarVibe" hint="Find posts, people, tags and places." />}
    </div>
  );
}

export default function SearchPage() {
  return (
    <Suspense>
      <SearchInner />
    </Suspense>
  );
}
