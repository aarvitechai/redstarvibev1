"use client";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Button, CenterSpinner, Empty, ErrorNote } from "@/components/ui";
import { useInfinite } from "@/hooks/useInfinite";
import { api, errorMessage } from "@/lib/api/client";
import type { Report, Stats } from "@/lib/api/types";
import { timeAgo } from "@/lib/utils";

export default function AdminPage() {
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
  if (stats.isError) return <Empty title="Admins only" hint={errorMessage(stats.error)} />;
  return (
    <div className="mx-auto max-w-3xl space-y-4 p-3 sm:p-4">
      <h1 className="text-xl font-bold">Moderation</h1>
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
