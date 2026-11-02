"use client";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Download } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { Button, CenterSpinner, Empty, ErrorNote, Modal } from "@/components/ui";
import { useInfinite } from "@/hooks/useInfinite";
import { useMe } from "@/hooks/useMe";
import { api, errorMessage } from "@/lib/api/client";
import type { AdminReport, ReportCounts } from "@/lib/api/types";
import { cn, timeAgo } from "@/lib/utils";

const STATUSES = [
  ["open", "Open"],
  ["actioned", "Actioned"],
  ["dismissed", "Dismissed"],
  ["all", "All"],
] as const;
const REASONS = ["spam", "harassment", "hate", "violence", "nudity", "child_safety", "self_harm", "other"];
const TYPES = ["post", "comment", "user", "story", "message", "community"];
const ACTIONS = {
  dismiss: { label: "Dismiss", confirm: "Close this report without changing anything?" },
  remove_content: { label: "Remove content", confirm: "Remove this content? Other open reports on it will close too." },
  suspend_user: { label: "Suspend user", confirm: "Suspend this account? They will not be able to log in." },
} as const;
type Action = keyof typeof ACTIONS;

const inputClass = "min-h-11 w-full rounded-lg border border-line bg-surface px-2 text-[16px] sm:text-sm";

function ReportRow({ report, onAct, onEscalate }: { report: AdminReport; onAct: (action: Action) => void; onEscalate: () => void }) {
  const t = report.target;
  const { data: me } = useMe();
  const canAct = !!me?.permissions.includes("remove_reported");
  return (
    <li className="rounded-lg border border-line p-3 text-sm" data-testid="report">
      <div className="flex gap-3">
        {t.thumbnail && <img src={t.thumbnail} alt="" className="h-16 w-16 shrink-0 rounded object-cover" />}
        <div className="min-w-0 flex-1">
          <p className="font-semibold capitalize">{report.reason.replace(/_/g, " ")} <span className="font-normal normal-case text-muted">on {report.entity_type}</span></p>
          <p className="text-xs text-muted">
            {report.source === "ai" ? `Flagged by AI${report.score != null ? `, score ${report.score.toFixed(2)}` : ""}` : `Reported by ${report.reporter ?? "a deleted account"}`}, {timeAgo(report.created_at)}
          </p>
          {report.details && <p className="mt-1 whitespace-pre-wrap break-words">&ldquo;{report.details}&rdquo;</p>}
        </div>
        <span className="h-fit shrink-0 rounded bg-surface px-2 py-0.5 text-xs font-semibold capitalize">{report.status}</span>
      </div>
      {report.escalated_by_name && <p className="mt-1 text-xs font-semibold text-brand">Escalated by {report.escalated_by_name}</p>}
      <div className="mt-2 rounded bg-surface p-2 text-xs">
        {t.available ? (
          <>
            {t.author && <p className="font-semibold">{t.author}</p>}
            {t.text && <p className="whitespace-pre-wrap break-words">{t.text}</p>}
            {t.link && <Link href={t.link} className="inline-flex min-h-8 items-center font-semibold text-brand">Open</Link>}
          </>
        ) : (
          <p className="text-muted">This content no longer exists.</p>
        )}
      </div>
      {report.status === "open" ? (
        <div className="mt-2 flex flex-wrap gap-2">
          <Button variant="secondary" onClick={() => onAct("dismiss")}>Dismiss</Button>
          {canAct && ["post", "comment", "story", "community"].includes(report.entity_type) && t.available && <Button variant="danger" onClick={() => onAct("remove_content")}>Remove content</Button>}
          {canAct && t.author && <Button variant="danger" onClick={() => onAct("suspend_user")}>Suspend user</Button>}
          {me?.permissions.includes("escalate") && !report.escalated_by_name && <Button variant="secondary" onClick={onEscalate}>Escalate to admin</Button>}
        </div>
      ) : (
        report.resolved_at && <p className="mt-2 text-xs text-muted">Resolved by {report.resolved_by_name ?? "unknown"}, {timeAgo(report.resolved_at)}</p>
      )}
    </li>
  );
}

export function ReportsPanel() {
  const qc = useQueryClient();
  const { data: me } = useMe();
  const canExport = me?.role === "admin" || me?.role === "superadmin";
  const [status, setStatus] = useState("open");
  const [reason, setReason] = useState("");
  const [type, setType] = useState("");
  const [source, setSource] = useState("");
  const [pending, setPending] = useState<{ report: AdminReport; action: Action } | null>(null);
  const params = new URLSearchParams({ status });
  if (reason) params.set("reason", reason);
  if (type) params.set("entity_type", type);
  if (source) params.set("source", source);
  const query = params.toString();
  const counts = useQuery({ queryKey: ["admin-report-counts"], queryFn: () => api<ReportCounts>("/admin/reports/counts") });
  const reports = useInfinite<AdminReport>(["admin-reports", query], `/admin/reports?${query}`);
  const resolve = useMutation({
    mutationFn: ({ report, action }: { report: AdminReport; action: Action }) => api(`/admin/reports/${report.id}/resolve`, { json: { action } }),
    onSettled: () => {
      setPending(null);
      for (const key of ["admin-reports", "admin-report-counts", "admin-dashboard"]) qc.invalidateQueries({ queryKey: [key] });
    },
  });
  const escalate = useMutation({
    mutationFn: (reportId: string) => api(`/admin/reports/${reportId}/escalate`, { method: "POST" }),
    onSettled: () => qc.invalidateQueries({ queryKey: ["admin-reports"] }),
  });
  const total = counts.data ? counts.data.open + counts.data.actioned + counts.data.dismissed : null;
  const countOf = (value: string) => (!counts.data ? null : value === "all" ? total : counts.data[value as "open" | "actioned" | "dismissed"]);
  return (
    <div className="space-y-3">
      <div role="tablist" aria-label="Report status" className="grid grid-cols-2 gap-1 sm:grid-cols-4">
        {STATUSES.map(([value, label]) => (
          <button key={value} role="tab" aria-selected={status === value} onClick={() => setStatus(value)} className={cn("min-h-11 rounded-lg text-sm font-semibold", status === value ? "bg-fg text-bg" : "bg-surface")}>
            {label} {countOf(value) != null && <span className="font-normal tabular-nums">({countOf(value)})</span>}
          </button>
        ))}
      </div>
      <div className="grid grid-cols-2 items-end gap-2 sm:grid-cols-4">
        <select aria-label="Reason" value={reason} onChange={(e) => setReason(e.target.value)} className={inputClass}>
          <option value="">All reasons</option>
          {REASONS.map((r) => <option key={r} value={r}>{r.replace(/_/g, " ")}</option>)}
        </select>
        <select aria-label="Content type" value={type} onChange={(e) => setType(e.target.value)} className={inputClass}>
          <option value="">All content</option>
          {TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
        </select>
        <select aria-label="Source" value={source} onChange={(e) => setSource(e.target.value)} className={inputClass}>
          <option value="">People and AI</option>
          <option value="user">People</option>
          <option value="ai">AI</option>
        </select>
        {canExport && <a href={`/api/v1/admin/reports/export?${query}`} download className="flex min-h-11 items-center justify-center gap-2 rounded-lg bg-surface text-sm font-semibold hover:bg-line">
          <Download className="h-4 w-4" /> Export CSV
        </a>}
      </div>
      <ErrorNote message={resolve.error || escalate.error ? errorMessage(resolve.error ?? escalate.error) : null} />
      {reports.isLoading ? <CenterSpinner /> : !reports.items.length ? (
        <Empty title={status === "open" ? "The queue is clear" : "No reports found"} hint={reason || type || source ? "Try removing a filter." : undefined} />
      ) : (
        <ul className="space-y-2">
          {reports.items.map((r) => <ReportRow key={r.id} report={r} onAct={(action) => setPending({ report: r, action })} onEscalate={() => escalate.mutate(r.id)} />)}
        </ul>
      )}
      {reports.hasNextPage && <Button variant="ghost" className="w-full" onClick={() => reports.fetchNextPage()}>Load more</Button>}
      <Modal open={!!pending} onClose={() => setPending(null)} title={pending ? ACTIONS[pending.action].label : ""}>
        {pending && (
          <>
            <p className="text-sm">{ACTIONS[pending.action].confirm}</p>
            <Button variant={pending.action === "dismiss" ? "primary" : "danger"} className="mt-3 w-full" loading={resolve.isPending} onClick={() => resolve.mutate(pending)}>
              Yes, {ACTIONS[pending.action].label.toLowerCase()}
            </Button>
          </>
        )}
      </Modal>
    </div>
  );
}
