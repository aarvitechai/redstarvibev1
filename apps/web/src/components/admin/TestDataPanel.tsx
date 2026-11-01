"use client";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Button, CenterSpinner, Empty, ErrorNote, Field, Input, Modal } from "@/components/ui";
import { api, errorMessage } from "@/lib/api/client";
import type { TestBatch } from "@/lib/api/types";
import { timeAgo } from "@/lib/utils";

const BUSY = new Set(["creating", "removing"]);
const STATUS: Record<string, string> = {
  creating: "Creating...",
  ready: "Live",
  failed: "Failed",
  removing: "Removing...",
  removed: "Removed",
};

export function TestDataPanel() {
  const qc = useQueryClient();
  const [form, setForm] = useState({ label: "Test data", users: 10, posts_per_user: 3, reels: 2, stories: 3 });
  const [confirm, setConfirm] = useState<TestBatch | "all" | null>(null);
  const batches = useQuery({
    queryKey: ["test-data"],
    queryFn: () => api<TestBatch[]>("/admin/test-data"),
    refetchInterval: (q) => (q.state.data?.some((b) => BUSY.has(b.status)) ? 2000 : false),
  });
  const refresh = () => qc.invalidateQueries({ queryKey: ["test-data"] });
  const create = useMutation({ mutationFn: () => api("/admin/test-data", { json: form }), onSuccess: refresh });
  const remove = useMutation({
    mutationFn: (target: TestBatch | "all") =>
      target === "all"
        ? api("/admin/test-data/remove-all", { method: "POST" })
        : api(`/admin/test-data/${target.id}`, { method: "DELETE" }),
    onSuccess: refresh,
    onSettled: () => setConfirm(null),
  });
  const number = (key: "users" | "posts_per_user" | "reels" | "stories", label: string, min: number, max: number) => (
    <Field label={`${label} (${min} to ${max})`}>
      <Input type="number" min={min} max={max} value={form[key]} onChange={(e) => setForm({ ...form, [key]: Number(e.target.value) })} />
    </Field>
  );
  const live = batches.data?.filter((b) => b.status === "ready" || b.status === "failed") ?? [];
  return (
    <div className="space-y-4">
      <p className="text-sm text-muted">
        Test accounts are named <code>test_...</code>, marked as test in their bio, and cannot log in. They appear in Explore,
        search and reels like real content, so remove them before real users arrive.
      </p>
      <form
        className="grid grid-cols-2 gap-3 rounded-lg border border-line p-3"
        onSubmit={(e) => {
          e.preventDefault();
          create.mutate();
        }}
      >
        <div className="col-span-2">
          <Field label="Name for this batch">
            <Input value={form.label} maxLength={80} required onChange={(e) => setForm({ ...form, label: e.target.value })} />
          </Field>
        </div>
        {number("users", "Accounts", 2, 50)}
        {number("posts_per_user", "Posts per account", 0, 10)}
        {number("reels", "Reels", 0, 5)}
        {number("stories", "Stories", 0, 20)}
        <div className="col-span-2">
          <ErrorNote message={create.error ? errorMessage(create.error) : null} />
          <Button type="submit" className="mt-1 w-full" loading={create.isPending}>
            Add test data
          </Button>
        </div>
      </form>
      <div className="flex items-center justify-between">
        <h2 className="font-semibold">Batches</h2>
        {live.length > 0 && (
          <Button variant="danger" onClick={() => setConfirm("all")}>
            Remove all test data
          </Button>
        )}
      </div>
      <ErrorNote message={remove.error ? errorMessage(remove.error) : null} />
      {batches.isLoading ? (
        <CenterSpinner />
      ) : !batches.data?.length ? (
        <Empty title="No test data yet" />
      ) : (
        <ul className="space-y-2">
          {batches.data.map((b) => (
            <li key={b.id} data-testid="batch" className="flex items-center gap-3 rounded-lg border border-line p-3 text-sm">
              <div className="min-w-0 flex-1">
                <p className="truncate font-semibold">{b.label}</p>
                <p className="text-muted">
                  {STATUS[b.status] ?? b.status} · {b.user_count} accounts · {b.post_count} posts · {timeAgo(b.created_at)}
                </p>
                {b.error && <p className="text-brand">{b.error}</p>}
              </div>
              {(b.status === "ready" || b.status === "failed") && (
                <Button variant="danger" onClick={() => setConfirm(b)}>
                  Remove
                </Button>
              )}
            </li>
          ))}
        </ul>
      )}
      <Modal open={confirm !== null} onClose={() => setConfirm(null)} title="Remove test data?">
        <p className="text-sm">
          {confirm === "all" ? `This permanently deletes all ${live.length} live batches` : "This permanently deletes this batch"}: its
          test accounts, posts, media, comments and likes. Comments and likes real people left on those posts go too. Real accounts
          and their posts are not touched.
        </p>
        <Button variant="danger" className="mt-3 w-full" loading={remove.isPending} onClick={() => confirm && remove.mutate(confirm)}>
          Yes, remove
        </Button>
      </Modal>
    </div>
  );
}
