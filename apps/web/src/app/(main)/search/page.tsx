"use client";
import { useQuery } from "@tanstack/react-query";
import { Hash, MapPin, Search } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";
import { PostGrid } from "@/components/post/PostGrid";
import { CenterSpinner, Empty, Input, UserRow } from "@/components/ui";
import { api } from "@/lib/api/client";
import type { Post, SearchResults } from "@/lib/api/types";
import { cn } from "@/lib/utils";

export default function SearchPage() {
  const [text, setText] = useState("");
  const [q, setQ] = useState("");
  const [tab, setTab] = useState<"accounts" | "photos">("accounts");
  useEffect(() => {
    const t = setTimeout(() => setQ(text.trim()), 250);
    return () => clearTimeout(t);
  }, [text]);
  const results = useQuery({
    queryKey: ["search", q],
    enabled: q.length > 0 && tab === "accounts",
    queryFn: () => api<SearchResults>(`/search?q=${encodeURIComponent(q)}`),
  });
  const photos = useQuery({
    queryKey: ["search-images", q],
    enabled: q.length > 1 && tab === "photos",
    queryFn: () => api<Post[]>(`/search/images?q=${encodeURIComponent(q)}`),
  });
  const data = results.data;
  const none = data && !data.users?.length && !data.hashtags?.length && !data.places?.length;
  return (
    <div className="mx-auto max-w-2xl p-3 sm:p-4">
      <h1 className="sr-only">Search</h1>
      <div className="relative">
        <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" />
        <Input aria-label="Search" placeholder={tab === "photos" ? "Try: sunset at beach" : "Search people, hashtags and places"} className="!pl-9" value={text} onChange={(e) => setText(e.target.value)} autoFocus />
      </div>
      <div role="tablist" className="my-3 flex gap-2">
        {(["accounts", "photos"] as const).map((t) => (
          <button key={t} role="tab" aria-selected={tab === t} onClick={() => setTab(t)} className={cn("min-h-11 flex-1 rounded-lg text-sm font-semibold", tab === t ? "bg-brand text-white" : "bg-surface")}>
            {t === "accounts" ? "People, tags, places" : "Photo search"}
          </button>
        ))}
      </div>
      {tab === "accounts" && (
        <>
          {results.isFetching && <CenterSpinner />}
          {none && <Empty title="No results" hint={`Nothing matched "${q}"`} />}
          {data?.users?.map((u) => <UserRow key={u.id} user={u} />)}
          {data?.hashtags?.map((h) => (
            <Link key={h.tag} href={`/tag/${encodeURIComponent(h.tag)}`} className="flex min-h-14 items-center gap-3">
              <span className="flex h-11 w-11 items-center justify-center rounded-full bg-surface"><Hash className="h-5 w-5" /></span>
              <span className="text-sm"><b>#{h.tag}</b><span className="block text-muted">{h.post_count} posts</span></span>
            </Link>
          ))}
          {data?.places?.map((p) => (
            <Link key={p.name} href={`/place/${encodeURIComponent(p.name)}`} className="flex min-h-14 items-center gap-3">
              <span className="flex h-11 w-11 items-center justify-center rounded-full bg-surface"><MapPin className="h-5 w-5" /></span>
              <span className="text-sm"><b>{p.name}</b><span className="block text-muted">{p.post_count} posts</span></span>
            </Link>
          ))}
        </>
      )}
      {tab === "photos" && (
        <>
          {photos.isFetching && <CenterSpinner />}
          {photos.data && (photos.data.length ? <PostGrid posts={photos.data} /> : <Empty title="No matching photos" />)}
        </>
      )}
    </div>
  );
}
