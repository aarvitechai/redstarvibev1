"use client";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { TicketThread } from "@/components/admin/TicketsPanel";
import { Button, CenterSpinner, ErrorNote, Field, Input, Modal } from "@/components/ui";
import { useMe } from "@/hooks/useMe";
import { api, errorMessage } from "@/lib/api/client";
import type { Ticket, Verification } from "@/lib/api/types";
import { timeAgo } from "@/lib/utils";
import { useUi } from "@/stores/ui";

const areaClass = "w-full rounded-lg border border-line bg-surface p-3 text-[16px] focus:border-brand focus:outline-none sm:text-sm";

function VerifySection() {
  const { data: me } = useMe();
  const qc = useQueryClient();
  const toast = useUi((s) => s.showToast);
  const [kind, setKind] = useState("person");
  const [details, setDetails] = useState("");
  const current = useQuery({ queryKey: ["my-verification"], queryFn: () => api<Verification | null>("/verification") });
  const send = useMutation({
    mutationFn: () => api("/verification", { json: { kind, details } }),
    onSuccess: () => {
      setDetails("");
      qc.invalidateQueries({ queryKey: ["my-verification"] });
      toast("Request sent");
    },
  });
  if (me?.verified) return <p className="text-sm">Your account is verified.</p>;
  if (current.data?.status === "pending") return <p className="text-sm">Your {current.data.kind} verification request is being reviewed.</p>;
  return (
    <div className="space-y-2">
      {current.data?.status === "rejected" && <p className="text-sm text-brand">Your last request was not approved{current.data.reason ? `: ${current.data.reason}` : "."}</p>}
      <Field label="Verify as">
        <select value={kind} onChange={(e) => setKind(e.target.value)} className="min-h-11 w-full rounded-lg border border-line bg-surface px-3 text-[16px] sm:text-sm">
          <option value="person">A person</option>
          <option value="business">A business</option>
        </select>
      </Field>
      <Field label="Details that prove who you are">
        <textarea value={details} maxLength={1000} rows={3} onChange={(e) => setDetails(e.target.value)} placeholder="For example your business name, GST number and website" className={areaClass} />
      </Field>
      <ErrorNote message={send.error ? errorMessage(send.error) : null} />
      <Button variant="secondary" disabled={details.trim().length < 10} loading={send.isPending} onClick={() => send.mutate()}>Request verification</Button>
    </div>
  );
}

export default function SupportPage() {
  const qc = useQueryClient();
  const [subject, setSubject] = useState("");
  const [body, setBody] = useState("");
  const [open, setOpen] = useState<string | null>(null);
  const tickets = useQuery({ queryKey: ["my-tickets"], queryFn: () => api<Ticket[]>("/support/tickets") });
  const create = useMutation({
    mutationFn: () => api<Ticket>("/support/tickets", { json: { subject, body } }),
    onSuccess: (t) => {
      setSubject("");
      setBody("");
      qc.invalidateQueries({ queryKey: ["my-tickets"] });
      setOpen(t.id);
    },
  });
  return (
    <div className="mx-auto max-w-xl space-y-6 p-3 sm:p-4">
      <h1 className="text-xl font-bold">Support</h1>
      <section className="space-y-2">
        <h2 className="font-semibold">Ask for help</h2>
        <Field label="Subject"><Input value={subject} maxLength={120} onChange={(e) => setSubject(e.target.value)} /></Field>
        <Field label="How can we help?"><textarea value={body} maxLength={4000} rows={4} onChange={(e) => setBody(e.target.value)} className={areaClass} /></Field>
        <ErrorNote message={create.error ? errorMessage(create.error) : null} />
        <Button disabled={subject.trim().length < 3 || !body.trim()} loading={create.isPending} onClick={() => create.mutate()}>Send</Button>
      </section>
      <section>
        <h2 className="font-semibold">Your tickets</h2>
        {tickets.isLoading ? <CenterSpinner /> : !tickets.data?.length ? <p className="py-2 text-sm text-muted">No tickets yet.</p> : (
          <ul className="mt-1 divide-y divide-line">
            {tickets.data.map((t) => (
              <li key={t.id}>
                <button className="flex min-h-12 w-full items-center justify-between gap-3 text-left text-sm" onClick={() => setOpen(t.id)}>
                  <span className="min-w-0 truncate font-medium">{t.subject}</span>
                  <span className="shrink-0 text-xs capitalize text-muted">{t.status}, {timeAgo(t.updated_at)}</span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>
      <section className="space-y-2">
        <h2 className="font-semibold">Verification</h2>
        <VerifySection />
      </section>
      <Modal open={!!open} onClose={() => setOpen(null)} title="Ticket">{open && <TicketThread id={open} />}</Modal>
    </div>
  );
}
