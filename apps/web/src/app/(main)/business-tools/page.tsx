"use client";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Button, ErrorNote, Field, Input, UserRow, CenterSpinner, Empty } from "@/components/ui";
import { useMe } from "@/hooks/useMe";
import { api, errorMessage } from "@/lib/api/client";
import type { AdRequest, Page, Post, UserBrief } from "@/lib/api/types";

function Staff() {
  const qc = useQueryClient();
  const [username, setUsername] = useState("");
  const list = useQuery({ queryKey: ["business-staff"], queryFn: () => api<UserBrief[]>("/business/staff") });
  const add = useMutation({
    mutationFn: () => api("/business/staff", { json: { username } }),
    onSuccess: () => {
      setUsername("");
      qc.invalidateQueries({ queryKey: ["business-staff"] });
    },
  });
  return (
    <section className="space-y-2">
      <h2 className="font-semibold">Staff accounts</h2>
      <p className="text-xs text-muted">This keeps your staff list. They get no extra access yet, because bookings and services are not built.</p>
      <div className="flex gap-2">
        <Input aria-label="Staff username" placeholder="Username" value={username} onChange={(e) => setUsername(e.target.value)} />
        <Button variant="secondary" disabled={!username.trim()} loading={add.isPending} onClick={() => add.mutate()}>Add</Button>
      </div>
      <ErrorNote message={add.error ? errorMessage(add.error) : null} />
      {list.data?.map((u) => (
        <UserRow key={u.id} user={u} action={<Button variant="secondary" onClick={async () => { await api(`/business/staff/${u.id}`, { method: "DELETE" }); list.refetch(); }}>Remove</Button>} />
      ))}
    </section>
  );
}

function Ads({ username }: { username: string }) {
  const qc = useQueryClient();
  const [postId, setPostId] = useState("");
  const [headline, setHeadline] = useState("");
  const [city, setCity] = useState("");
  const [budget, setBudget] = useState("");
  const posts = useQuery({ queryKey: ["user-posts", username, "for-ads"], queryFn: () => api<Page<Post>>(`/users/${username}/posts?limit=48`) });
  const ads = useQuery({ queryKey: ["business-ads"], queryFn: () => api<AdRequest[]>("/business/ads") });
  const send = useMutation({
    mutationFn: () => api("/business/ads", { json: { post_id: postId, headline, city: city || null, daily_budget_paise: Math.round(Number(budget) * 100) } }),
    onSuccess: () => {
      setHeadline("");
      qc.invalidateQueries({ queryKey: ["business-ads"] });
    },
  });
  return (
    <section className="space-y-2">
      <h2 className="font-semibold">Promote a post</h2>
      <p className="text-xs text-muted">An admin reviews each request. Nothing is charged and approved ads do not run yet, because ad delivery and payments are not built.</p>
      <Field label="Post">
        <select value={postId} onChange={(e) => setPostId(e.target.value)} className="min-h-11 w-full rounded-lg border border-line bg-surface px-3 text-[16px] sm:text-sm">
          <option value="">Choose a post</option>
          {posts.data?.items.map((p) => <option key={p.id} value={p.id}>{p.caption.slice(0, 60) || "No caption"}</option>)}
        </select>
      </Field>
      <Field label="Headline"><Input value={headline} maxLength={80} onChange={(e) => setHeadline(e.target.value)} /></Field>
      <Field label="City (optional)"><Input value={city} maxLength={80} onChange={(e) => setCity(e.target.value)} /></Field>
      <Field label="Daily budget in rupees"><Input type="number" min={1} value={budget} onChange={(e) => setBudget(e.target.value)} /></Field>
      <ErrorNote message={send.error ? errorMessage(send.error) : null} />
      <Button disabled={!postId || headline.trim().length < 3 || !(Number(budget) >= 1)} loading={send.isPending} onClick={() => send.mutate()}>Send for review</Button>
      <ul className="divide-y divide-line">
        {ads.data?.map((ad) => (
          <li key={ad.id} className="py-2 text-sm">
            <p className="font-medium">{ad.headline}</p>
            <p className="text-xs capitalize text-muted">{ad.status}{ad.reason ? `: ${ad.reason}` : ""}</p>
          </li>
        ))}
      </ul>
    </section>
  );
}

export default function BusinessToolsPage() {
  const { data: me } = useMe();
  if (!me) return <CenterSpinner />;
  if (!me.permissions.includes("manage_business")) return <Empty title="For business accounts" hint="Ask for business verification from the Support page." />;
  return (
    <div className="mx-auto max-w-xl space-y-6 p-3 sm:p-4">
      <h1 className="text-xl font-bold">Business tools</h1>
      <Ads username={me.username} />
      <Staff />
    </div>
  );
}
