"use client";
import { useQuery } from "@tanstack/react-query";
import { Clock } from "lucide-react";
import { api } from "@/lib/api/client";
import type { BestTimes as BestTimesData } from "@/lib/api/types";

const label = (hour: number) => new Date(2000, 0, 1, hour).toLocaleTimeString([], { hour: "numeric" });

/** The next time this hour comes round, in the format a datetime-local input expects. */
export function nextAt(hour: number, now = new Date()): string {
  const when = new Date(now);
  when.setHours(hour, 0, 0, 0);
  if (when <= now) when.setDate(when.getDate() + 1);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${when.getFullYear()}-${pad(when.getMonth() + 1)}-${pad(when.getDate())}T${pad(hour)}:00`;
}

export function BestTimes({ onPick }: { onPick: (value: string) => void }) {
  const tz = Intl.DateTimeFormat().resolvedOptions().timeZone;
  const q = useQuery({
    queryKey: ["best-times", tz],
    staleTime: 3_600_000,
    queryFn: () => api<BestTimesData>(`/posts/best-times?tz=${encodeURIComponent(tz)}`),
  });
  if (!q.data) return null;
  if (!q.data.enough_data) return <p className="text-xs text-muted">Best time to post appears once your posts have 20 likes from others.</p>;
  return (
    <div data-testid="best-times" className="flex flex-wrap items-center gap-1 text-xs">
      <span className="flex items-center gap-1 font-semibold text-muted"><Clock aria-hidden className="h-3.5 w-3.5" /> Your people are most active at:</span>
      {q.data.hours.map((h) => (
        <button key={h.hour} type="button" onClick={() => onPick(nextAt(h.hour))} className="min-h-9 rounded-full border border-line px-3 hover:bg-surface">
          {label(h.hour)}
        </button>
      ))}
    </div>
  );
}
