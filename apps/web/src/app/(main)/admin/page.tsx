"use client";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { RolesPanel } from "@/components/admin/RolesPanel";
import { TestDataPanel } from "@/components/admin/TestDataPanel";
import { Button, CenterSpinner, Empty, ErrorNote } from "@/components/ui";
import { useInfinite } from "@/hooks/useInfinite";
import { useMe } from "@/hooks/useMe";
import { api, errorMessage } from "@/lib/api/client";
import type { Report, Stats } from "@/lib/api/types";
import { cn, timeAgo } from "@/lib/utils";

function Moderation() {
  const qc = useQueryClient();
  const stats = useQuery({ queryKey: ["admin-stats"], queryFn: () => api<Stats>("/admin/stats") });
  const reports = useInfinite<Report>(["admin-reports"], "/admin/reports");
  const resolve = useMutation({
    mutationFn: ({ id, action }: { id: string; action: string }) => api(`/admin/reports/${id}/resolve`, { json: { action } }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["admin-reports"] });
      qc.invalidateQueries({ queryKey: ["admin-stats"] });
    },
  });
  return (
    <div className="space-y-4">
      {stats.data && (
        <dl className="grid grid-cols-3 gap-2 text-center">
          {[["Users", stats.data.users], ["Posts", stats.data.posts], ["Open reports", stats.data.open_reports]].map(([label, value]) => (
            <div key={label} className="rounded-lg bg-surface p-3"><dd className="text-2xl font-bold">{value}</dd><dt className="text-xs text-muted">{label}</dt></div>
          ))}
        </dl>
      )}
      <ErrorNote message={resolve.error ? errorMessage(resolve.error) : null} />
      {reports.isLoading ? <CenterSpinner /> : !reports.items.length ? <Empty title="The queue is clear" /> : (
        <ul className="space-y-2">
          {reports.items.map((r) => (
            <li key={r.id} className="rounded-lg border border-line p-3 text-sm">
              <p><b>{r.reason}</b> on {r.entity_type} <span className="text-muted">({r.source}{r.score != null ? `, score ${r.score}` : ""}, {timeAgo(r.created_at)})</span></p>
              {r.details && <p className="mt-1">{r.details}</p>}
              {r.entity_type === "post" && <a className="text-brand underline" href={`/p/${r.entity_id}`}>Open post</a>}
              <div className="mt-2 flex flex-wrap gap-2">
                <Button variant="secondary" onClick={() => resolve.mutate({ id: r.id, action: "dismiss" })}>Dismiss</Button>
                <Button variant="danger" onClick={() => resolve.mutate({ id: r.id, action: "remove_content" })}>Remove content</Button>
                <Button variant="danger" onClick={() => resolve.mutate({ id: r.id, action: "suspend_user" })}>Suspend user</Button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export default function AdminPage() {
  const { data: me } = useMe();
  const [tab, setTab] = useState("moderation");
  if (!me) return <CenterSpinner />;
  const superAdmin = me.role === "superadmin";
  if (!superAdmin && me.role !== "admin") return <Empty title="Admins only" />;
  const tabs = [["moderation", "Moderation"], ["test-data", "Test data"], ...(superAdmin ? [["roles", "Admins"]] : [])] as const;
  return (
    <div className="mx-auto max-w-3xl space-y-4 p-3 sm:p-4">
      <h1 className="text-xl font-bold">{superAdmin ? "Super admin" : "Admin"}</h1>
      <div role="tablist" className="flex gap-2">
        {tabs.map(([value, label]) => (
          <button key={value} role="tab" aria-selected={tab === value} onClick={() => setTab(value)} className={cn("min-h-11 flex-1 rounded-lg text-sm font-semibold", tab === value ? "bg-brand text-white" : "bg-surface")}>
            {label}
          </button>
        ))}
      </div>
      {tab === "moderation" && <Moderation />}
      {tab === "test-data" && <TestDataPanel />}
      {tab === "roles" && superAdmin && <RolesPanel />}
    </div>
  );
}
