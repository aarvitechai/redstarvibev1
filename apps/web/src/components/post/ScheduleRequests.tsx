"use client";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Button, ErrorNote } from "@/components/ui";
import { api, errorMessage } from "@/lib/api/client";
import type { ScheduleRequest } from "@/lib/api/types";

/** An AI app connected through MCP can only ask to schedule. Nothing goes out until the person approves it here. */
export function ScheduleRequests() {
  const qc = useQueryClient();
  const requests = useQuery({ queryKey: ["schedule-requests"], queryFn: () => api<ScheduleRequest[]>("/posts/schedule-requests") });
  const answer = useMutation({
    mutationFn: ({ id, approve }: { id: string; approve: boolean }) => api(`/posts/${id}/schedule-request`, { method: approve ? "POST" : "DELETE" }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["schedule-requests"] });
      qc.invalidateQueries({ queryKey: ["drafts"] });
    },
  });
  if (!requests.data?.length) return null;
  return (
    <section aria-label="Schedule requests" data-testid="schedule-requests" className="space-y-2 rounded-lg border border-brand/40 p-3">
      <h2 className="text-sm font-semibold">A connected AI app wants to schedule these</h2>
      <ErrorNote message={answer.error ? errorMessage(answer.error) : null} />
      <ul className="space-y-2">
        {requests.data.map((r) => (
          <li key={r.post_id} className="space-y-1 text-sm">
            <p className="truncate">{r.caption || "Untitled"} <span className="text-muted">({new Date(r.publish_at).toLocaleString()})</span></p>
            <div className="flex gap-2">
              <Button disabled={answer.isPending} onClick={() => answer.mutate({ id: r.post_id, approve: true })}>Approve</Button>
              <Button variant="ghost" disabled={answer.isPending} onClick={() => answer.mutate({ id: r.post_id, approve: false })}>Decline</Button>
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}
