"use client";
import { compactNumber } from "@/lib/utils";

const shortDay = (day: string) => new Date(`${day}T00:00:00Z`).toLocaleDateString(undefined, { month: "short", day: "numeric", timeZone: "UTC" });

export function StatTile({ label, value, note }: { label: string; value: string; note?: string }) {
  return (
    <div className="rounded-lg border border-line p-3">
      <dt className="text-xs text-muted">{label}</dt>
      <dd className="mt-1 text-2xl font-bold tabular-nums">{value}</dd>
      {note && <dd className="mt-0.5 text-xs text-muted">{note}</dd>}
    </div>
  );
}

/** One measure per chart, one colour. Every bar has a hover and tap tooltip, and the numbers are in a table below. */
export function DailyBars({ title, data }: { title: string; data: { day: string; count: number }[] }) {
  const max = Math.max(1, ...data.map((d) => d.count));
  const total = data.reduce((sum, d) => sum + d.count, 0);
  return (
    <figure className="rounded-lg border border-line p-3" data-testid="daily-chart">
      <figcaption className="flex items-baseline justify-between gap-2">
        <span className="text-sm font-semibold">{title}</span>
        <span className="text-xs text-muted tabular-nums">{compactNumber(total)} total</span>
      </figcaption>
      <div className="relative mt-3 border-b border-line">
        <span className="absolute right-0 top-0 text-[11px] text-muted tabular-nums">{max}</span>
        <div className="flex h-28 items-end gap-0.5" role="img" aria-label={`${title}: ${total} in ${data.length} days. Peak ${max} a day.`}>
          {data.map((d) => (
            <div key={d.day} tabIndex={0} className="group relative flex h-full min-w-0 flex-1 items-end outline-none" aria-label={`${shortDay(d.day)}: ${d.count}`}>
              <div className="w-full max-w-5 rounded-t bg-[var(--chart)] group-hover:opacity-80 group-focus:opacity-80" style={{ height: d.count ? `${Math.max(3, (d.count / max) * 100)}%` : "1px" }} />
              <div className="pointer-events-none absolute bottom-full left-1/2 z-10 mb-1 hidden -translate-x-1/2 whitespace-nowrap rounded bg-fg px-2 py-1 text-xs text-bg group-hover:block group-focus:block">
                {shortDay(d.day)}: <b>{d.count}</b>
              </div>
            </div>
          ))}
        </div>
      </div>
      <div className="mt-1 flex justify-between text-[11px] text-muted">
        <span>{data[0] && shortDay(data[0].day)}</span>
        <span>{data.at(-1) && shortDay(data.at(-1)!.day)}</span>
      </div>
      <details className="mt-1 text-xs">
        <summary className="flex min-h-8 cursor-pointer items-center text-muted">Show numbers</summary>
        <table className="w-full tabular-nums">
          <tbody>
            {data.filter((d) => d.count > 0).map((d) => (
              <tr key={d.day}><td className="py-0.5">{shortDay(d.day)}</td><td className="text-right">{d.count}</td></tr>
            ))}
            {total === 0 && <tr><td className="py-0.5 text-muted">Nothing in this period</td></tr>}
          </tbody>
        </table>
      </details>
    </figure>
  );
}

export function RankedBars({ title, data, empty }: { title: string; data: { name: string; count: number }[]; empty: string }) {
  const max = Math.max(1, ...data.map((d) => d.count));
  return (
    <section className="rounded-lg border border-line p-3">
      <h3 className="text-sm font-semibold">{title}</h3>
      {data.length === 0 ? (
        <p className="py-4 text-center text-sm text-muted">{empty}</p>
      ) : (
        <ul className="mt-2 space-y-2">
          {data.map((d) => (
            <li key={d.name} className="text-xs">
              <div className="flex justify-between gap-2">
                <span className="truncate capitalize">{d.name.replace(/_/g, " ")}</span>
                <span className="font-semibold tabular-nums">{d.count}</span>
              </div>
              <div className="mt-1 h-2">
                <div className="h-full rounded-r bg-[var(--chart)]" style={{ width: `${Math.max(2, (d.count / max) * 100)}%` }} />
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
