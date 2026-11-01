import { clsx } from "clsx";

export const cn = clsx;

export function compactNumber(n: number): string {
  if (n < 1000) return String(n);
  return new Intl.NumberFormat("en", { notation: "compact", maximumFractionDigits: 1 }).format(n);
}

export function timeAgo(iso: string, now: number = Date.now()): string {
  const seconds = Math.max(0, Math.floor((now - new Date(iso).getTime()) / 1000));
  if (seconds < 60) return "now";
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h`;
  if (seconds < 604800) return `${Math.floor(seconds / 86400)}d`;
  return new Date(iso).toLocaleDateString(undefined, { day: "numeric", month: "short" });
}

export type CaptionPart = { kind: "text" | "tag" | "mention"; value: string };

export function parseCaption(text: string): CaptionPart[] {
  const parts: CaptionPart[] = [];
  const re = /(^|\s)([#@])([\p{L}\p{N}_.]+)/gu;
  let last = 0;
  for (const m of text.matchAll(re)) {
    const start = m.index + (m[1]?.length ?? 0);
    if (start > last) parts.push({ kind: "text", value: text.slice(last, start) });
    parts.push({ kind: m[2] === "#" ? "tag" : "mention", value: m[3]!.replace(/\.+$/, "") });
    last = start + 1 + m[3]!.replace(/\.+$/, "").length;
  }
  if (last < text.length) parts.push({ kind: "text", value: text.slice(last) });
  return parts;
}
