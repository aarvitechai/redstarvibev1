"use client";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Button, ErrorNote } from "@/components/ui";
import { api, errorMessage } from "@/lib/api/client";
import type { Interests } from "@/lib/api/types";
import { cn } from "@/lib/utils";

const DISMISSED = "rsv-interests-dismissed";
const OPTIONS = ["travel", "food", "nature", "mountains", "beach", "street", "city", "photography", "monsoon", "india", "fitness", "music", "cricket", "fashion", "art", "tech"];
const MAX = 10;

function wasDismissed(): boolean {
  try {
    return localStorage.getItem(DISMISSED) === "1";
  } catch {
    return false;
  }
}

function remember(): void {
  try {
    localStorage.setItem(DISMISSED, "1");
  } catch {} // private windows can block storage, and the card just shows again next time
}

/** A first feed for new accounts. Shown until the person chooses or says not now. */
export function InterestPicker() {
  const qc = useQueryClient();
  const [dismissed, setDismissed] = useState(wasDismissed);
  const [chosen, setChosen] = useState<string[]>([]);
  const current = useQuery({ queryKey: ["interests"], queryFn: () => api<Interests>("/users/me/interests"), enabled: !dismissed });
  const save = useMutation({
    mutationFn: () => api<Interests>("/users/me/interests", { method: "PUT", json: { interests: chosen } }),
    onSuccess: (data) => {
      qc.setQueryData(["interests"], data);
      qc.invalidateQueries({ queryKey: ["for-you"] });
    },
  });
  if (dismissed || !current.data || current.data.interests.length > 0) return null;
  const toggle = (tag: string) =>
    setChosen((list) => (list.includes(tag) ? list.filter((t) => t !== tag) : list.length < MAX ? [...list, tag] : list));
  return (
    <section aria-label="Choose your interests" data-testid="interest-picker" className="space-y-2 border-b border-line bg-bg p-3 sm:rounded-lg sm:border">
      <h2 className="text-sm font-semibold">What do you like to see?</h2>
      <p className="text-xs text-muted">Pick a few, and For You in Explore starts with them.</p>
      <div className="flex flex-wrap gap-1">
        {OPTIONS.map((tag) => (
          <button key={tag} type="button" aria-pressed={chosen.includes(tag)} onClick={() => toggle(tag)} className={cn("min-h-9 rounded-full border px-3 text-xs", chosen.includes(tag) ? "border-brand font-semibold text-brand" : "border-line")}>
            {tag}
          </button>
        ))}
      </div>
      <ErrorNote message={save.error ? errorMessage(save.error) : null} />
      <div className="flex gap-2">
        <Button disabled={!chosen.length} loading={save.isPending} onClick={() => save.mutate()}>Done</Button>
        <Button variant="ghost" onClick={() => { remember(); setDismissed(true); }}>Not now</Button>
      </div>
    </section>
  );
}
