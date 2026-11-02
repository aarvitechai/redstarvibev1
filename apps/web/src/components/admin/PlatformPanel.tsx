"use client";
import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, CheckCircle2, XCircle } from "lucide-react";
import { useState } from "react";
import { Button, CenterSpinner, Empty, ErrorNote } from "@/components/ui";
import { useInfinite } from "@/hooks/useInfinite";
import { api, errorMessage } from "@/lib/api/client";
import type { AuditRow, Platform } from "@/lib/api/types";
import { timeAgo } from "@/lib/utils";
import { RankedBars, StatTile } from "./charts";
import { PeriodPicker } from "./DashboardPanel";

function Health({ label, ok }: { label: string; ok: boolean }) {
  const Icon = ok ? CheckCircle2 : XCircle;
  return (
    <li className="flex min-h-9 items-center gap-2 text-sm">
      <Icon aria-hidden className={ok ? "h-4 w-4" : "h-4 w-4 text-brand"} />
      {label}: <b>{ok ? "OK" : "Down"}</b>
    </li>
  );
}

export function PlatformPanel() {
  const [days, setDays] = useState(30);
  const q = useQuery({ queryKey: ["admin-platform", days], queryFn: () => api<Platform>(`/admin/platform?days=${days}`), refetchInterval: 60_000 });
  if (q.error) return <ErrorNote message={errorMessage(q.error)} />;
  if (!q.data) return <CenterSpinner />;
  const p = q.data;
  const warnings = [
    p.staff_without_mfa > 0 && `${p.staff_without_mfa} staff ${p.staff_without_mfa === 1 ? "account has" : "accounts have"} no authenticator app. Production will block them.`,
    p.live_test_batches > 0 && `${p.live_test_batches} test data ${p.live_test_batches === 1 ? "batch is" : "batches are"} live. Remove before launch.`,
    p.token_reuse_7d > 0 && `${p.token_reuse_7d} possible stolen ${p.token_reuse_7d === 1 ? "session" : "sessions"} in 7 days, ended automatically. Check auth.refresh_reuse in the audit log.`,
  ].filter(Boolean) as string[];
  return (
    <div className="space-y-4">
      <PeriodPicker days={days} onChange={setDays} />
      {warnings.length > 0 && (
        <ul className="space-y-1 rounded-lg border border-brand p-3 text-sm" data-testid="platform-warnings">
          {warnings.map((w) => (
            <li key={w} className="flex gap-2"><AlertTriangle aria-hidden className="mt-0.5 h-4 w-4 shrink-0 text-brand" /> {w}</li>
          ))}
        </ul>
      )}
      <dl className="grid grid-cols-2 gap-2 sm:grid-cols-4">
        <StatTile label="Failed logins" value={String(p.failed_logins_24h)} note="Last 24 hours" />
        <StatTile label="Possible stolen sessions" value={String(p.token_reuse_7d)} note="Last 7 days" />
        <StatTile label="Staff without authenticator" value={String(p.staff_without_mfa)} />
        <StatTile label="Live test batches" value={String(p.live_test_batches)} />
      </dl>
      <div className="grid gap-2 sm:grid-cols-3">
        <section className="rounded-lg border border-line p-3">
          <h3 className="text-sm font-semibold">Service health</h3>
          <ul className="mt-1">
            <Health label="Database" ok={p.database_ok} />
            <Health label="Redis" ok={p.redis_ok} />
          </ul>
          <p className="mt-2 text-xs text-muted">Jobs waiting</p>
          <ul className="text-sm tabular-nums">
            {p.queue_depth.map((queue) => <li key={queue.name} className="flex justify-between"><span>{queue.name === "ai" ? "AI" : queue.name === "media" ? "Media" : "Default"}</span><b>{queue.count}</b></li>)}
          </ul>
        </section>
        <RankedBars title="Accounts by status" data={p.users_by_status} empty="No accounts" />
        <RankedBars title="Accounts by role" data={p.users_by_role} empty="No accounts" />
      </div>
      <section className="rounded-lg border border-line p-3">
        <h3 className="text-sm font-semibold">Staff activity in {p.days} days</h3>
        <div className="overflow-x-auto">
          <table className="mt-2 w-full min-w-[440px] text-left text-sm">
            <thead className="text-xs text-muted">
              <tr><th className="py-1 font-medium">Name</th><th className="font-medium">Role</th><th className="font-medium">Authenticator</th><th className="text-right font-medium">Actions</th><th className="text-right font-medium">Last action</th></tr>
            </thead>
            <tbody className="divide-y divide-line">
              {p.staff.map((row) => (
                <tr key={row.username}>
                  <td className="py-2 font-semibold">{row.username}{row.status !== "active" && <span className="font-normal text-muted"> ({row.status})</span>}</td>
                  <td>{row.role === "superadmin" ? "Super admin" : "Admin"}</td>
                  <td>{row.mfa ? "On" : "Off"}</td>
                  <td className="text-right tabular-nums">{row.actions}</td>
                  <td className="text-right text-muted">{row.last_action_at ? timeAgo(row.last_action_at) : "None"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}

const CATEGORIES = [
  ["", "Everything"],
  ["admin", "Admin actions"],
  ["auth", "Logins and security"],
  ["account", "Account changes"],
  ["mcp", "MCP tools"],
] as const;

export function AuditPanel() {
  const [category, setCategory] = useState("");
  const log = useInfinite<AuditRow>(["admin-audit", category], `/admin/audit${category ? `?category=${category}` : ""}`);
  return (
    <div className="space-y-3">
      <select aria-label="Audit category" value={category} onChange={(e) => setCategory(e.target.value)} className="min-h-11 w-full rounded-lg border border-line bg-surface px-2 text-[16px] sm:w-64 sm:text-sm">
        {CATEGORIES.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
      </select>
      {log.isLoading ? <CenterSpinner /> : !log.items.length ? <Empty title="Nothing logged yet" /> : (
        <ul className="divide-y divide-line rounded-lg border border-line px-3">
          {log.items.map((row) => (
            <li key={row.id} className="py-2 text-sm" data-testid="audit-row">
              <div className="flex flex-wrap items-baseline justify-between gap-x-2">
                <code className="break-all text-xs font-semibold">{row.action}</code>
                <span className="text-xs text-muted">{timeAgo(row.created_at)}</span>
              </div>
              <p className="break-all text-xs text-muted">
                By {row.actor ?? "system or unknown"}{row.ip ? ` from ${row.ip}` : ""}{row.target ? `. Target: ${row.target}` : ""}
              </p>
              {row.meta && <p className="break-all text-xs text-muted">{JSON.stringify(row.meta)}</p>}
            </li>
          ))}
        </ul>
      )}
      {log.hasNextPage && <Button variant="ghost" className="w-full" onClick={() => log.fetchNextPage()}>Load more</Button>}
      <p className="text-xs text-muted">The target of a failed login is whatever was typed as the username.</p>
    </div>
  );
}
