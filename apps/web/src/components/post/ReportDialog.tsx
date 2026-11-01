"use client";
import { useState } from "react";
import { Button, ErrorNote, Modal } from "@/components/ui";
import { api, errorMessage } from "@/lib/api/client";
import { useUi } from "@/stores/ui";

const REASONS: [string, string][] = [
  ["spam", "Spam"],
  ["harassment", "Harassment or bullying"],
  ["hate", "Hate speech"],
  ["violence", "Violence"],
  ["nudity", "Nudity or sexual content"],
  ["child_safety", "Child safety"],
  ["self_harm", "Self harm"],
  ["other", "Something else"],
];

export function ReportDialog({ open, onClose, entityType, entityId }: { open: boolean; onClose: () => void; entityType: string; entityId: string }) {
  const [reason, setReason] = useState("spam");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const toast = useUi((s) => s.showToast);
  return (
    <Modal open={open} onClose={onClose} title="Report">
      <fieldset className="space-y-1">
        <legend className="mb-2 text-sm text-muted">Why are you reporting this?</legend>
        {REASONS.map(([value, label]) => (
          <label key={value} className="flex min-h-11 items-center gap-3">
            <input type="radio" name="reason" checked={reason === value} onChange={() => setReason(value)} className="h-4 w-4 accent-[#C8102E]" />
            {label}
          </label>
        ))}
      </fieldset>
      <ErrorNote message={error} />
      <Button
        className="mt-3 w-full"
        loading={busy}
        onClick={async () => {
          setBusy(true);
          try {
            await api("/reports", { json: { entity_type: entityType, entity_id: entityId, reason } });
            toast("Thanks. Our team will review this.");
            onClose();
          } catch (e) {
            setError(errorMessage(e));
          } finally {
            setBusy(false);
          }
        }}
      >
        Submit report
      </Button>
    </Modal>
  );
}
