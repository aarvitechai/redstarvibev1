"use client";
import { Sparkles } from "lucide-react";
import { useRef } from "react";
import { Field } from "@/components/ui";
import type { MediaEdit, TextOverlay } from "@/lib/api/types";
import { cn } from "@/lib/utils";
import { editStyle, FILTERS, NO_EDIT } from "./mediaEdit";
import { overlayFrameStyle, overlayStyle } from "./TextOverlay";

const COLORS = ["#FFFFFF", "#111111", "#C8102E", "#F2A541", "#2EC4B6", "#4361EE"];
const STYLES: { value: TextOverlay["style"]; label: string }[] = [
  { value: "shadow", label: "Plain" },
  { value: "label", label: "Label" },
  { value: "highlight", label: "Highlight" },
];
const SIZES: { value: TextOverlay["size"]; label: string }[] = [
  { value: "small", label: "Small" },
  { value: "medium", label: "Medium" },
  { value: "large", label: "Large" },
];
const EFFECTS: { value: NonNullable<TextOverlay["effect"]>; label: string }[] = [
  { value: "none", label: "Still" },
  { value: "fade", label: "Fade" },
  { value: "pop", label: "Pop" },
  { value: "slide", label: "Slide" },
  { value: "glow", label: "Glow" },
];
const PLACES = [
  { label: "Top", y: 15 },
  { label: "Middle", y: 50 },
  { label: "Bottom", y: 85 },
];
const START = { x: 50, y: 50, size: "medium", style: "shadow", color: "#FFFFFF", effect: "none" } as const;

function Choice({ pressed, onClick, children }: { pressed: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      type="button"
      aria-pressed={pressed}
      onClick={onClick}
      className={cn("min-h-11 flex-1 rounded-lg border px-2 text-sm", pressed ? "border-brand font-semibold text-brand" : "border-line")}
    >
      {children}
    </button>
  );
}

export function TextOverlayEditor({
  src,
  isVideo,
  ratio,
  value,
  onChange,
  edit,
  onEditChange,
  tagline,
}: {
  src: string;
  isVideo: boolean;
  ratio: number;
  value?: TextOverlay;
  onChange: (next: TextOverlay | undefined) => void;
  edit?: MediaEdit;
  onEditChange: (next: MediaEdit) => void;
  tagline?: string | null;
}) {
  const current = edit ?? NO_EDIT;

  const frame = useRef<HTMLDivElement>(null);
  const noun = isVideo ? "video" : "photo";

  const moveTo = (clientX: number, clientY: number) => {
    const box = frame.current?.getBoundingClientRect();
    if (!box || !value) return;
    const clamp = (n: number) => Math.round(Math.min(95, Math.max(5, n)) * 10) / 10;
    onChange({ ...value, x: clamp(((clientX - box.left) / box.width) * 100), y: clamp(((clientY - box.top) / box.height) * 100) });
  };

  return (
    <section className="space-y-3 rounded-lg border border-line p-3">
      <div ref={frame} className="relative mx-auto overflow-hidden rounded-lg bg-black" style={{ ...overlayFrameStyle, aspectRatio: ratio, width: `min(100%, calc(70dvh * ${ratio}))` }}>
        {isVideo ? (
          <video src={src} muted loop autoPlay playsInline style={editStyle(edit)} className="h-full w-full object-contain" />
        ) : (
          <img src={src} alt="" style={editStyle(edit)} className="h-full w-full object-cover" />
        )}
        {value && (
          <p
            data-testid="text-overlay-preview"
            title="Drag to move"
            className="cursor-move touch-none select-none"
            style={overlayStyle(value)}
            onPointerDown={(e) => e.currentTarget.setPointerCapture(e.pointerId)}
            onPointerMove={(e) => {
              if (e.currentTarget.hasPointerCapture(e.pointerId)) moveTo(e.clientX, e.clientY);
            }}
          >
            {value.text}
          </p>
        )}
      </div>

      <div className="no-scrollbar flex gap-2 overflow-x-auto" role="group" aria-label="Filter">
        {FILTERS.map((f) => (
          <button key={f.value} type="button" aria-pressed={current.filter === f.value} onClick={() => onEditChange({ ...current, filter: f.value })} className={cn("min-h-11 shrink-0 rounded-lg border px-3 text-sm", current.filter === f.value ? "border-brand font-semibold text-brand" : "border-line")}>
            {f.label}
          </button>
        ))}
      </div>
      <details className="text-sm">
        <summary className="flex min-h-11 cursor-pointer items-center font-medium">Adjust brightness, contrast and colour</summary>
        {([["brightness", "Brightness", 50, 150], ["contrast", "Contrast", 50, 150], ["saturate", "Colour", 0, 200]] as const).map(([key, label, min, max]) => (
          <label key={key} className="flex min-h-11 items-center gap-3">
            <span className="w-20 shrink-0">{label}</span>
            <input type="range" min={min} max={max} value={current[key]} onChange={(e) => onEditChange({ ...current, [key]: Number(e.target.value) })} className="flex-1 accent-[#C8102E]" />
          </label>
        ))}
      </details>
      {tagline && (
        <button type="button" onClick={() => onChange({ ...START, ...value, text: tagline })} className="flex min-h-11 w-full items-center gap-2 rounded-lg border border-line px-3 text-left text-sm hover:bg-surface">
          <Sparkles aria-hidden className="h-4 w-4 shrink-0 text-brand" /> <span className="truncate">Use AI tagline: {tagline}</span>
        </button>
      )}
      <Field label={`Text on ${noun}`}>
        <textarea
          value={value?.text ?? ""}
          maxLength={200}
          rows={2}
          placeholder="Write something that stops the scroll"
          onChange={(e) => onChange(e.target.value ? { ...START, ...value, text: e.target.value } : undefined)}
          className="w-full rounded-lg border border-line bg-surface p-3 text-[16px] focus:border-brand focus:outline-none sm:text-sm"
        />
      </Field>

      {value && (
        <>
          <p className="text-xs text-muted">{value.text.length}/200. Drag the text to move it, or pick a place below.</p>
          <div className="flex gap-2" role="group" aria-label="Text place">
            {PLACES.map((p) => (
              <Choice key={p.label} pressed={value.x === 50 && value.y === p.y} onClick={() => onChange({ ...value, x: 50, y: p.y })}>
                {p.label}
              </Choice>
            ))}
          </div>
          <div className="flex gap-2" role="group" aria-label="Text style">
            {STYLES.map((s) => (
              <Choice key={s.value} pressed={value.style === s.value} onClick={() => onChange({ ...value, style: s.value })}>
                {s.label}
              </Choice>
            ))}
          </div>
          <div className="flex gap-2" role="group" aria-label="Text size">
            {SIZES.map((s) => (
              <Choice key={s.value} pressed={value.size === s.value} onClick={() => onChange({ ...value, size: s.value })}>
                {s.label}
              </Choice>
            ))}
          </div>
          <div className="flex gap-2" role="group" aria-label="Text animation">
            {EFFECTS.map((e) => (
              <Choice key={e.value} pressed={(value.effect ?? "none") === e.value} onClick={() => onChange({ ...value, effect: e.value })}>
                {e.label}
              </Choice>
            ))}
          </div>
          <div className="flex justify-between gap-1" role="group" aria-label="Text colour">
            {COLORS.map((color) => (
              <button
                key={color}
                type="button"
                aria-label={`Colour ${color}`}
                aria-pressed={value.color === color}
                onClick={() => onChange({ ...value, color })}
                className="flex h-11 w-11 items-center justify-center"
              >
                <span className={cn("h-8 w-8 rounded-full border border-line", value.color === color && "ring-2 ring-brand ring-offset-2")} style={{ backgroundColor: color }} />
              </button>
            ))}
          </div>
        </>
      )}
    </section>
  );
}
