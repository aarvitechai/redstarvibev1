import type { CSSProperties } from "react";
import type { MediaEdit } from "@/lib/api/types";

export const FILTERS: { value: MediaEdit["filter"]; label: string; css: string }[] = [
  { value: "none", label: "Original", css: "" },
  { value: "clarendon", label: "Bright", css: "contrast(1.2) saturate(1.35)" },
  { value: "warm", label: "Warm", css: "sepia(0.25) saturate(1.2)" },
  { value: "cool", label: "Cool", css: "hue-rotate(-10deg) saturate(1.1)" },
  { value: "vintage", label: "Vintage", css: "sepia(0.4) contrast(0.9) brightness(1.05)" },
  { value: "mono", label: "Black and white", css: "grayscale(1)" },
];

export const NO_EDIT: MediaEdit = { filter: "none", brightness: 100, contrast: 100, saturate: 100 };

/** Shown with CSS, so the original file stays untouched and the edit can be changed before sharing. */
export function editStyle(edit?: MediaEdit | null): CSSProperties | undefined {
  if (!edit) return undefined;
  const preset = FILTERS.find((f) => f.value === edit.filter)?.css ?? "";
  return { filter: `${preset} brightness(${edit.brightness}%) contrast(${edit.contrast}%) saturate(${edit.saturate}%)`.trim() };
}

export const isEdited = (edit?: MediaEdit) =>
  !!edit && (edit.filter !== "none" || edit.brightness !== 100 || edit.contrast !== 100 || edit.saturate !== 100);
