"use client";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Radio } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Avatar, Button, CenterSpinner, Empty, ErrorNote, Input } from "@/components/ui";
import { api, errorMessage } from "@/lib/api/client";
import type { CallJoin, LiveOut } from "@/lib/api/types";

export default function LivePage() {
  const [title, setTitle] = useState("");
  const router = useRouter();
  const list = useQuery({ queryKey: ["live"], queryFn: () => api<LiveOut[]>("/live"), refetchInterval: 15_000 });
  const start = useMutation({
    mutationFn: () => api<CallJoin>("/live", { json: { title } }),
    onSuccess: (join) => router.push(`/call/${join.room}`),
  });
  return (
    <div className="mx-auto max-w-xl space-y-4 p-3 sm:p-4">
      <h1 className="text-xl font-bold">Live</h1>
      <form className="flex gap-2" onSubmit={(e) => { e.preventDefault(); if (title.trim()) start.mutate(); }}>
        <Input aria-label="Live title" placeholder="What is your live about?" value={title} maxLength={120} onChange={(e) => setTitle(e.target.value)} />
        <Button type="submit" disabled={!title.trim()} loading={start.isPending}><Radio className="h-4 w-4" /> Go live</Button>
      </form>
      <ErrorNote message={start.error ? errorMessage(start.error) : null} />
      {list.isLoading ? <CenterSpinner /> : !list.data?.length ? <Empty title="Nobody is live right now" hint="Live videos from people you follow show up here." /> : (
        <ul>
          {list.data.map((l) => (
            <li key={l.id}>
              <Link href={`/call/${l.room}`} className="flex min-h-16 items-center gap-3 rounded-lg px-2 hover:bg-surface">
                <Avatar user={l.host} size={48} ring />
                <span className="min-w-0"><b className="block truncate text-sm">{l.host.username}</b><span className="block truncate text-sm text-muted">{l.title}</span></span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
