"use client";
import { useQuery } from "@tanstack/react-query";
import { Hash, Search } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Avatar, Input } from "@/components/ui";
import { api } from "@/lib/api/client";
import type { SearchSuggest } from "@/lib/api/types";

const DEBOUNCE_MS = 300;

export function useDebounced(value: string) {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setDebounced(value), DEBOUNCE_MS);
    return () => clearTimeout(t);
  }, [value]);
  return debounced;
}

export function SearchBox() {
  const router = useRouter();
  const [text, setText] = useState("");
  const [open, setOpen] = useState(false);
  const q = useDebounced(text.trim());
  const suggest = useQuery({
    queryKey: ["search-suggest", q],
    enabled: open && q.length > 0,
    queryFn: () => api<SearchSuggest>(`/search/suggest?q=${encodeURIComponent(q)}`),
  });
  const close = () => {
    setOpen(false);
    setText("");
  };
  const hasResults = !!suggest.data && suggest.data.users.length + suggest.data.tags.length > 0;
  return (
    <form
      role="search"
      className="relative"
      onBlur={(e) => !e.currentTarget.contains(e.relatedTarget) && setOpen(false)}
      onSubmit={(e) => {
        e.preventDefault();
        if (!text.trim()) return;
        router.push(`/search?q=${encodeURIComponent(text.trim())}`);
        close();
      }}
    >
      <Search aria-hidden className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" />
      <Input aria-label="Quick search" placeholder="Search" className="!pl-9" value={text} onFocus={() => setOpen(true)} onChange={(e) => { setText(e.target.value); setOpen(true); }} />
      {open && hasResults && (
        <div data-testid="search-suggestions" className="absolute inset-x-0 top-full z-40 mt-1 w-64 rounded-lg border border-line bg-bg p-1 shadow-lg">
          {suggest.data.users.map((u) => (
            <Link key={u.id} href={`/${u.username}`} onClick={close} className="flex min-h-11 items-center gap-2 rounded-lg px-2 text-sm hover:bg-surface">
              <Avatar user={u} size={28} /> <span className="truncate">{u.username}</span>
            </Link>
          ))}
          {suggest.data.tags.map((t) => (
            <Link key={t.tag} href={`/tag/${encodeURIComponent(t.tag)}`} onClick={close} className="flex min-h-11 items-center gap-2 rounded-lg px-2 text-sm hover:bg-surface">
              <Hash aria-hidden className="h-4 w-4 text-muted" /> <span className="truncate">{t.tag}</span>
              <span className="ml-auto text-xs text-muted">{t.post_count}</span>
            </Link>
          ))}
        </div>
      )}
    </form>
  );
}
