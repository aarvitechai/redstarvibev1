"use client";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Users } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Button, CenterSpinner, Empty, ErrorNote, Field, Input, Modal } from "@/components/ui";
import { api, errorMessage } from "@/lib/api/client";
import type { Community } from "@/lib/api/types";

export default function CommunitiesPage() {
  const router = useRouter();
  const [text, setText] = useState("");
  const [q, setQ] = useState("");
  const [creating, setCreating] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  useEffect(() => {
    const t = setTimeout(() => setQ(text.trim()), 250);
    return () => clearTimeout(t);
  }, [text]);
  const list = useQuery({ queryKey: ["communities", q], queryFn: () => api<Community[]>(`/communities?q=${encodeURIComponent(q)}`) });
  const create = useMutation({
    mutationFn: () => api<Community>("/communities", { json: { name, description } }),
    onSuccess: (c) => router.push(`/communities/${c.slug}`),
  });
  return (
    <div className="mx-auto max-w-xl space-y-3 p-3 sm:p-4">
      <div className="flex items-center justify-between gap-2">
        <h1 className="text-xl font-bold">Communities</h1>
        <Button variant="secondary" onClick={() => setCreating(true)}>Create</Button>
      </div>
      <Input aria-label="Search communities" placeholder="Search communities" value={text} onChange={(e) => setText(e.target.value)} />
      {list.isLoading ? <CenterSpinner /> : !list.data?.length ? <Empty title="No communities found" hint="Start one for your city, trade or hobby." /> : (
        <ul className="divide-y divide-line">
          {list.data.map((c) => (
            <li key={c.id}>
              <Link href={`/communities/${c.slug}`} className="flex min-h-16 items-center gap-3 py-2">
                <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-surface"><Users aria-hidden className="h-5 w-5" /></span>
                <span className="min-w-0 flex-1">
                  <span className="block truncate font-semibold">{c.name}</span>
                  <span className="block truncate text-xs text-muted">{c.member_count} {c.member_count === 1 ? "member" : "members"}{c.description ? `, ${c.description}` : ""}</span>
                </span>
              </Link>
            </li>
          ))}
        </ul>
      )}
      <Modal open={creating} onClose={() => setCreating(false)} title="New community">
        <div className="space-y-3">
          <Field label="Name"><Input value={name} maxLength={80} onChange={(e) => setName(e.target.value)} /></Field>
          <Field label="What is it about?"><Input value={description} maxLength={500} onChange={(e) => setDescription(e.target.value)} /></Field>
          <p className="text-xs text-muted">Communities are public. Anyone can read and join.</p>
          <ErrorNote message={create.error ? errorMessage(create.error) : null} />
          <Button className="w-full" disabled={name.trim().length < 3} loading={create.isPending} onClick={() => create.mutate()}>Create community</Button>
        </div>
      </Modal>
    </div>
  );
}
