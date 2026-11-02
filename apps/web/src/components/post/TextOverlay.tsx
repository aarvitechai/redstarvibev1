import type { CSSProperties } from "react";
import type { TextOverlay } from "@/lib/api/types";

const FONT_SIZE = { small: 5, medium: 7, large: 10 } as const;

function readableOn(hex: string): string {
  const [r, g, b] = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16));
  return 0.299 * r! + 0.587 * g! + 0.114 * b! > 150 ? "#111111" : "#ffffff";
}

/** Position and size use percent and container width, so the text sits in the same place on every screen. */
export function overlayStyle(overlay: TextOverlay): CSSProperties {
  const look: Record<TextOverlay["style"], CSSProperties> = {
    shadow: { color: overlay.color, textShadow: "0 1px 4px rgb(0 0 0 / 0.85)" },
    label: { color: overlay.color, backgroundColor: "rgb(0 0 0 / 0.6)", padding: "0.2em 0.5em", borderRadius: "0.3em" },
    highlight: { color: readableOn(overlay.color), backgroundColor: overlay.color, padding: "0.2em 0.5em", borderRadius: "0.3em" },
  };
  return {
    position: "absolute",
    left: `${overlay.x}%`,
    top: `${overlay.y}%`,
    transform: "translate(-50%, -50%)",
    width: "max-content",
    maxWidth: "90%",
    fontSize: `${FONT_SIZE[overlay.size]}cqw`,
    fontWeight: 700,
    lineHeight: 1.2,
    textAlign: "center",
    whiteSpace: "pre-wrap",
    overflowWrap: "anywhere",
    ...look[overlay.style],
  };
}

export const overlayFrameStyle: CSSProperties = { containerType: "inline-size" };

/** Clicks pass through, so swiping and the video controls keep working. */
export function TextOverlayView({ overlay }: { overlay?: TextOverlay | null }) {
  if (!overlay) return null;
  return (
    <div className="pointer-events-none absolute inset-0 overflow-hidden" style={overlayFrameStyle}>
      <p data-testid="text-overlay" style={overlayStyle(overlay)}>
        {overlay.text}
      </p>
    </div>
  );
}
