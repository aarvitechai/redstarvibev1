const FRAMES: Record<string, { label: string; greeting: string; colors: string }> = {
  diwali: { label: "Diwali", greeting: "Happy Diwali", colors: "#f59e0b, #dc2626, #f59e0b" },
  holi: { label: "Holi", greeting: "Happy Holi", colors: "#ec4899, #8b5cf6, #22c55e, #f59e0b" },
  eid: { label: "Eid", greeting: "Eid Mubarak", colors: "#047857, #fbbf24, #047857" },
  christmas: { label: "Christmas", greeting: "Merry Christmas", colors: "#b91c1c, #15803d, #b91c1c" },
};

export const FRAME_OPTIONS = Object.entries(FRAMES).map(([value, f]) => ({ value, label: f.label }));

export function StoryFrame({ frame }: { frame?: string | null }) {
  const f = frame ? FRAMES[frame] : undefined;
  if (!f) return null;
  return (
    <div className="pointer-events-none absolute inset-0" data-testid="story-frame">
      <div className="absolute inset-0" style={{ border: "10px solid transparent", borderImage: `linear-gradient(135deg, ${f.colors}) 1` }} />
      <p className="absolute inset-x-0 bottom-20 text-center text-2xl font-bold text-white" style={{ textShadow: "0 1px 6px rgb(0 0 0 / 0.8)" }}>
        {f.greeting}
      </p>
    </div>
  );
}
