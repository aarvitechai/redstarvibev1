"use client";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Button, CenterSpinner, Empty, ErrorNote, Field, Modal } from "@/components/ui";
import { useInfinite } from "@/hooks/useInfinite";
import { useMe } from "@/hooks/useMe";
import { api, errorMessage } from "@/lib/api/client";
import type { Ticket } from "@/lib/api/types";
import { cn, timeAgo } from "@/lib/utils";

export function TicketThread({ id }: { id: string }) {
  const qc = useQueryClient();
  const { data: me } = useMe();
  const [body, setBody] = useState("");
  const ticket = useQuery({ queryKey: ["ticket", id], queryFn: () => api<Ticket>(`/support/tickets/${id}`) });
  const refresh = () => {
    qc.invalidateQueries({ queryKey: ["ticket", id] });
    qc.invalidateQueries({ queryKey: ["admin-tickets"] });
    qc.invalidateQueries({ queryKey: ["my-tickets"] });
  };
  const reply = useMutation({
    mutationFn: () => api(`/support/tickets/${id}/messages`, { json: { body } }),
    onSuccess: () => {
      setBody("");
      refresh();
    },
  });
  const act = useMutation({ mutationFn: (verb: string) => api(`/admin/tickets/${id}/${verb}`, { method: "POST" }), onSettled: refresh });
  if (!ticket.data) return <CenterSpinner />;
  const t = ticket.data;
  const canResolve = t.status !== "resolved" && me?.permissions.includes("resolve_tickets") && !(t.status === "escalated" && me.role === "staff");
  return (
    <div className="space-y-3">
      <p className="text-xs text-muted">From {t.user}. Status: <b className="capitalize">{t.status}</b></p>
      <ul className="max-h-[50dvh] space-y-2 overflow-y-auto">
        {(t.messages ?? []).map((m) => (
          <li key={m.id} className={cn("rounded-lg p-2 text-sm", m.is_staff ? "bg-surface" : "border border-line")}>
            <p className="text-xs text-muted"><b>{m.author ?? "Deleted account"}</b>, {timeAgo(m.created_at)}</p>
            <p className="whitespace-pre-wrap break-words">{m.body}</p>
          </li>
        ))}
      </ul>
      <Field label="Reply">
        <textarea value={body} maxLength={4000} rows={3} onChange={(e) => setBody(e.target.value)} className="w-full rounded-lg border border-line bg-surface p-3 text-[16px] focus:border-brand focus:outline-none sm:text-sm" />
      </Field>
      <ErrorNote message={reply.error || act.error ? errorMessage(reply.error ?? act.error) : null} />
      <div className="flex flex-wrap gap-2">
        <Button disabled={!body.trim()} loading={reply.isPending} onClick={() => reply.mutate()}>Send reply</Button>
        {me?.permissions.includes("escalate") && t.status === "open" && <Button variant="secondary" onClick={() => act.mutate("escalate")}>Escalate to admin</Button>}
        {canResolve && <Button variant="secondary" onClick={() => act.mutate("resolve")}>Mark resolved</Button>}
      </div>
    </div>
  );
}

export function TicketsPanel() {
  const [status, setStatus] = useState("open");
  const [open, setOpen] = useState<string | null>(null);
  const list = useInfinite<Ticket>(["admin-tickets", status], `/admin/tickets?status=${status}`);
  return (
    <div className="space-y-3">
      <div role="tablist" aria-label="Ticket status" className="grid grid-cols-3 gap-1">
        {["open", "escalated", "resolved"].map((value) => (
          <button key={value} role="tab" aria-selected={status === value} onClick={() => setStatus(value)} className={cn("min-h-11 rounded-lg text-sm font-semibold capitalize", status === value ? "bg-fg text-bg" : "bg-surface")}>{value}</button>
        ))}
      </div>
      {list.isLoading ? <CenterSpinner /> : !list.items.length ? <Empty title="No tickets here" /> : (
        <ul className="divide-y divide-line rounded-lg border border-line">
          {list.items.map((t) => (
            <li key={t.id}>
              <button className="flex min-h-14 w-full items-center justify-between gap-3 px-3 py-2 text-left text-sm hover:bg-surface" onClick={() => setOpen(t.id)}>
                <span className="min-w-0"><span className="block truncate font-semibold">{t.subject}</span><span className="block truncate text-xs text-muted">{t.user}</span></span>
                <span className="shrink-0 text-xs text-muted">{timeAgo(t.updated_at)}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
      {list.hasNextPage && <Button variant="ghost" className="w-full" onClick={() => list.fetchNextPage()}>Load more</Button>}
      <Modal open={!!open} onClose={() => setOpen(null)} title="Ticket">{open && <TicketThread id={open} />}</Modal>
    </div>
  );
}
