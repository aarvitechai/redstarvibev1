"use client";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";
import { Button, CenterSpinner, Empty, ErrorNote, Field, Input } from "@/components/ui";
import { api, errorMessage } from "@/lib/api/client";
import type { AdRequest, Plan, Verification } from "@/lib/api/types";
import { timeAgo } from "@/lib/utils";

const rupees = (paise: number) => `₹${(paise / 100).toLocaleString("en-IN")}`;

function Review({ onReview, busy }: { onReview: (approve: boolean, reason: string | null) => void; busy: boolean }) {
  const [reason, setReason] = useState("");
  return (
    <div className="mt-2 flex flex-wrap items-center gap-2">
      <Input aria-label="Reason, shown to the person" placeholder="Reason, if rejecting" maxLength={300} value={reason} onChange={(e) => setReason(e.target.value)} />
      <Button loading={busy} onClick={() => onReview(true, null)}>Approve</Button>
      <Button variant="danger" disabled={busy || !reason.trim()} onClick={() => onReview(false, reason.trim())}>Reject</Button>
    </div>
  );
}

export function VerificationPanel() {
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["admin-verification"], queryFn: () => api<Verification[]>("/admin/verification") });
  const review = useMutation({
    mutationFn: ({ id, approve, reason }: { id: string; approve: boolean; reason: string | null }) => api(`/admin/verification/${id}/review`, { json: { approve, reason } }),
    onSettled: () => qc.invalidateQueries({ queryKey: ["admin-verification"] }),
  });
  if (q.isLoading) return <CenterSpinner />;
  if (!q.data?.length) return <Empty title="No verification requests" hint="People ask for this from the Support page." />;
  return (
    <div className="space-y-2">
      <ErrorNote message={review.error ? errorMessage(review.error) : null} />
      <p className="text-xs text-muted">Check the details yourself before approving. The site does not verify documents. Approving a business also gives it the business role.</p>
      <ul className="space-y-2">
        {q.data.map((r) => (
          <li key={r.id} data-testid="verification" className="rounded-lg border border-line p-3 text-sm">
            <p><Link href={`/${r.username}`} className="font-semibold">{r.username}</Link> <span className="text-muted">asks to verify a {r.kind}, {timeAgo(r.created_at)}</span></p>
            <p className="mt-1 whitespace-pre-wrap break-words">{r.details}</p>
            <Review busy={review.isPending} onReview={(approve, reason) => review.mutate({ id: r.id, approve, reason })} />
          </li>
        ))}
      </ul>
    </div>
  );
}

export function AdsPanel() {
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["admin-ads"], queryFn: () => api<AdRequest[]>("/admin/ads") });
  const review = useMutation({
    mutationFn: ({ id, approve, reason }: { id: string; approve: boolean; reason: string | null }) => api(`/admin/ads/${id}/review`, { json: { approve, reason } }),
    onSettled: () => qc.invalidateQueries({ queryKey: ["admin-ads"] }),
  });
  if (q.isLoading) return <CenterSpinner />;
  return (
    <div className="space-y-2">
      <p className="text-xs text-muted">Approving records the decision. Approved ads do not show in the feed yet, because ad delivery and payments are not built.</p>
      <ErrorNote message={review.error ? errorMessage(review.error) : null} />
      {!q.data?.length ? <Empty title="No ads waiting" /> : (
        <ul className="space-y-2">
          {q.data.map((ad) => (
            <li key={ad.id} data-testid="ad-request" className="rounded-lg border border-line p-3 text-sm">
              <p className="font-semibold">{ad.headline}</p>
              <p className="text-xs text-muted">{ad.business}, {rupees(ad.daily_budget_paise)} a day{ad.city ? `, ${ad.city}` : ""}</p>
              <Link href={`/p/${ad.post_id}`} className="inline-flex min-h-8 items-center text-xs font-semibold text-brand">Open post</Link>
              <Review busy={review.isPending} onReview={(approve, reason) => review.mutate({ id: ad.id, approve, reason })} />
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function PlanRow({ plan }: { plan: Plan }) {
  const qc = useQueryClient();
  const [price, setPrice] = useState(plan.price_paise == null ? "" : String(plan.price_paise / 100));
  const [includes, setIncludes] = useState(plan.includes);
  const [active, setActive] = useState(plan.active);
  const save = useMutation({
    mutationFn: () => api(`/admin/plans/${plan.code}`, {
      method: "PUT",
      json: { price_paise: price.trim() === "" ? null : Math.round(Number(price) * 100), includes, active },
    }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin-plans"] }),
  });
  return (
    <li data-testid="plan" className="space-y-2 rounded-lg border border-line p-3 text-sm">
      <p className="font-semibold">{plan.name}</p>
      <Field label={`${plan.name} price, rupees a month`}>
        <Input type="number" min={0} step="0.01" placeholder="Not set" value={price} onChange={(e) => setPrice(e.target.value)} />
      </Field>
      <Field label={`${plan.name} includes`}><Input maxLength={300} value={includes} onChange={(e) => setIncludes(e.target.value)} /></Field>
      <label className="flex min-h-11 items-center gap-2">
        <input type="checkbox" checked={active} onChange={(e) => setActive(e.target.checked)} className="h-5 w-5 accent-[#C8102E]" /> Show this plan
      </label>
      <ErrorNote message={save.error ? errorMessage(save.error) : null} />
      <Button variant="secondary" loading={save.isPending} onClick={() => save.mutate()}>Save {plan.name}</Button>
    </li>
  );
}

export function PlansPanel() {
  const q = useQuery({ queryKey: ["admin-plans"], queryFn: () => api<Plan[]>("/admin/plans") });
  if (!q.data) return <CenterSpinner />;
  return (
    <div className="space-y-3">
      <section className="rounded-lg border border-line p-3 text-sm" data-testid="revenue">
        <h2 className="font-semibold">Revenue</h2>
        <p className="mt-1 text-muted">No revenue to show. Payments are not connected yet, so nobody can subscribe and these prices are not charged.</p>
      </section>
      <ul className="grid gap-2 sm:grid-cols-2">{q.data.map((plan) => <PlanRow key={plan.code} plan={plan} />)}</ul>
    </div>
  );
}
