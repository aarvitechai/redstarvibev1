"use client";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { InfiniteGrid } from "@/components/post/InfiniteGrid";
import { Button, Input } from "@/components/ui";
import { api } from "@/lib/api/client";
import type { Collection } from "@/lib/api/types";
import { cn } from "@/lib/utils";

export default function SavedPage() {
  const qc = useQueryClient();
  const [active, setActive] = useState<string | null>(null);
  const [name, setName] = useState("");
  const collections = useQuery({ queryKey: ["collections"], queryFn: () => api<Collection[]>("/collections") });
  const create = useMutation({
    mutationFn: () => api("/collections", { json: { name } }),
    onSuccess: () => {
      setName("");
      qc.invalidateQueries({ queryKey: ["collections"] });
    },
  });
  return (
    <div className="mx-auto max-w-4xl sm:p-4">
      <h1 className="p-3 text-xl font-bold">Saved</h1>
      <div className="no-scrollbar flex gap-2 overflow-x-auto px-3 pb-3">
        <button onClick={() => setActive(null)} className={cn("min-h-11 shrink-0 rounded-full px-4 text-sm font-semibold", !active ? "bg-brand text-white" : "bg-surface")}>All</button>
        {collections.data?.map((c) => (
          <button key={c.id} onClick={() => setActive(c.id)} className={cn("min-h-11 shrink-0 rounded-full px-4 text-sm font-semibold", active === c.id ? "bg-brand text-white" : "bg-surface")}>{c.name}</button>
        ))}
      </div>
      <form className="flex gap-2 px-3 pb-3" onSubmit={(e) => { e.preventDefault(); if (name.trim()) create.mutate(); }}>
        <Input aria-label="New collection name" placeholder="New collection name" value={name} maxLength={80} onChange={(e) => setName(e.target.value)} />
        <Button type="submit" variant="secondary" disabled={!name.trim()}>Add</Button>
      </form>
      <InfiniteGrid key={active ?? "all"} queryKey={["saved", active]} path={active ? `/saved?collection_id=${active}` : "/saved"} emptyTitle="Nothing saved yet" emptyHint="Tap the bookmark on any post to keep it here." />
    </div>
  );
}
