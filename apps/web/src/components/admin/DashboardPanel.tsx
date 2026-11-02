"use client";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";
import { CenterSpinner, ErrorNote } from "@/components/ui";
import { api, errorMessage } from "@/lib/api/client";
import type { AdminDashboard } from "@/lib/api/types";
import { cn, compactNumber } from "@/lib/utils";
import { DailyBars, RankedBars, StatTile } from "./charts";

export const PERIODS = [7, 30, 90] as const;

export function PeriodPicker({ days, onChange }: { days: number; onChange: (days: number) => void }) {
  return (
    <div className="flex gap-1" role="group" aria-label="Period">
      {PERIODS.map((value) => (
        <button key={value} aria-pressed={days === value} onClick={() => onChange(value)} className={cn("min-h-11 rounded-lg px-3 text-sm font-semibold", days === value ? "bg-fg text-bg" : "bg-surface")}>
          {value} days
        </button>
      ))}
    </div>
  );
}

export function DashboardPanel({ onOpenReports }: { onOpenReports: () => void }) {
  const [days, setDays] = useState<number>(30);
  const q = useQuery({ queryKey: ["admin-dashboard", days], queryFn: () => api<AdminDashboard>(`/admin/dashboard?days=${days}`), refetchInterval: 60_000 });
  if (q.error) return <ErrorNote message={errorMessage(q.error)} />;
  if (!q.data) return <CenterSpinner />;
  const d = q.data;
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <PeriodPicker days={days} onChange={setDays} />
        {d.test_accounts > 0 && <p className="text-xs text-muted">Leaves out {d.test_accounts} test accounts.</p>}
      </div>

      {d.open_reports > 0 && (
        <button onClick={onOpenReports} className="flex min-h-11 w-full items-center justify-between gap-2 rounded-lg border border-brand px-3 py-2 text-left text-sm">
          <span><b>{d.open_reports}</b> {d.open_reports === 1 ? "report needs" : "reports need"} review</span>
          <span className="font-semibold text-brand">Review now</span>
        </button>
      )}

      <dl className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-4">
        <StatTile label="People" value={compactNumber(d.users)} note={`+${d.new_users} in ${d.days} days`} />
        <StatTile label="Published posts" value={compactNumber(d.posts)} note={`+${d.new_posts} in ${d.days} days`} />
        <StatTile label="Comments" value={compactNumber(d.comments)} note={`+${d.new_comments} in ${d.days} days`} />
        <StatTile label="Likes" value={compactNumber(d.likes)} note="All time" />
        <StatTile label="Views" value={compactNumber(d.views)} note="All time" />
        <StatTile label="Open reports" value={compactNumber(d.open_reports)} note={`+${d.new_reports} in ${d.days} days`} />
        <StatTile label="Reports resolved" value={compactNumber(d.resolved_reports)} note={`In ${d.days} days`} />
        <StatTile label="Median time to resolve" value={d.median_resolve_hours == null ? "No data" : `${d.median_resolve_hours} h`} note={`In ${d.days} days`} />
      </dl>

      <div className="grid gap-2 sm:grid-cols-2">
        <DailyBars title="New people per day" data={d.users_by_day} />
        <DailyBars title="New posts per day" data={d.posts_by_day} />
        <DailyBars title="New comments per day" data={d.comments_by_day} />
        <DailyBars title="New reports per day" data={d.reports_by_day} />
        <RankedBars title="Reports by reason" data={d.reports_by_reason} empty="No reports in this period" />
        <RankedBars title="Reports by content type" data={d.reports_by_type} empty="No reports in this period" />
      </div>

      <section className="rounded-lg border border-line p-3">
        <h3 className="text-sm font-semibold">Top posts in this period</h3>
        {d.top_posts.length === 0 ? (
          <p className="py-4 text-center text-sm text-muted">No posts in this period</p>
        ) : (
          <ol className="mt-1 divide-y divide-line">
            {d.top_posts.map((p) => (
              <li key={p.id}>
                <Link href={`/p/${p.id}`} className="flex min-h-14 items-center gap-3 py-2 text-sm">
                  <span className="h-10 w-10 shrink-0 overflow-hidden rounded bg-surface">{p.thumbnail && <img src={p.thumbnail} alt="" className="h-full w-full object-cover" />}</span>
                  <span className="min-w-0 flex-1">
                    <span className="block truncate font-semibold">{p.author}</span>
                    <span className="block truncate text-xs text-muted">{p.caption || "No caption"}</span>
                  </span>
                  <span className="shrink-0 text-right text-xs text-muted tabular-nums">
                    {compactNumber(p.likes)} {p.likes === 1 ? "like" : "likes"}<br />{compactNumber(p.views)} {p.views === 1 ? "view" : "views"}
                  </span>
                </Link>
              </li>
            ))}
          </ol>
        )}
      </section>
      <p className="text-xs text-muted">Days are in UTC. Refreshes every minute.</p>
    </div>
  );
}
