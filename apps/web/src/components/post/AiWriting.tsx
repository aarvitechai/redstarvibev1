"use client";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Sparkles } from "lucide-react";
import { useState } from "react";
import { Button, ErrorNote } from "@/components/ui";
import { api, errorMessage } from "@/lib/api/client";
import type { AiFeatures, CaptionSuggestions, HashtagIdeas, Rewrite } from "@/lib/api/types";

const POLL_MS = 3000;
const POLL_TRIES = 20; // one minute: the person never waits on this, they can post at any time
const STYLES = [
  ["fun", "Fun"],
  ["short", "Short"],
  ["hinglish", "Hinglish"],
] as const;
const chip = "min-h-9 max-w-full rounded-full border border-line px-3 py-1 text-left text-xs hover:bg-surface";

export function useAiFeatures() {
  return useQuery({ queryKey: ["ai-features"], staleTime: 300_000, queryFn: () => api<AiFeatures>("/ai/features") }).data;
}

export function useCaptionSuggestions(assetId: string | undefined, enabled: boolean) {
  return useQuery({
    queryKey: ["ai-captions", assetId],
    enabled: enabled && !!assetId,
    queryFn: () => api<CaptionSuggestions>(`/ai/captions/${assetId}`),
    refetchInterval: (q) => (q.state.data?.status === "pending" && q.state.dataUpdateCount < POLL_TRIES ? POLL_MS : false),
  }).data;
}

/** The one place to find AI help in the composer, including why it is missing when it is switched off. */
export function MakeEffective({ enabled, suggestions, canSetUp, onApply }: { enabled: boolean; suggestions?: CaptionSuggestions; canSetUp: boolean; onApply: (s: CaptionSuggestions) => void }) {
  if (!enabled) {
    if (!canSetUp) return null;
    return (
      <p data-testid="ai-off" className="flex gap-2 rounded-lg border border-line p-3 text-xs text-muted">
        <Sparkles aria-hidden className="h-4 w-4 shrink-0" />
        <span><b>Make it effective with AI is off.</b> Set AI_PROVIDER, CLOUDFLARE_ACCOUNT_ID and CLOUDFLARE_AI_TOKEN in .env, then restart. Only staff see this note.</span>
      </p>
    );
  }
  const ready = suggestions?.status === "ready";
  return (
    <section aria-label="Make it effective" className="rounded-lg border border-brand/40 p-3">
      <Button className="w-full" disabled={!ready} onClick={() => suggestions && onApply(suggestions)}>
        <Sparkles aria-hidden className="h-4 w-4" /> Make it effective with AI
      </Button>
      <p className="mt-1.5 text-xs text-muted">
        {suggestions?.status === "failed"
          ? "AI could not read this one. You can still write your own."
          : ready
            ? "Adds a caption, hashtags, animated text, an image description and matching music. You can change all of it."
            : "AI is looking at your upload. You can share without waiting."}
      </p>
    </section>
  );
}

export function CaptionChips({ suggestions, onCaption, onHashtag, onAltText }: { suggestions?: CaptionSuggestions; onCaption: (text: string) => void; onHashtag: (tag: string) => void; onAltText: (text: string) => void }) {
  if (!suggestions || suggestions.status === "disabled" || suggestions.status === "failed") return null;
  if (suggestions.status === "pending") return <p className="flex items-center gap-2 text-xs text-muted"><Sparkles aria-hidden className="h-3.5 w-3.5" /> AI suggestions are on the way. You can share without waiting.</p>;
  return (
    <section aria-label="AI suggestions" data-testid="ai-suggestions" className="space-y-2">
      <p className="flex items-center gap-1 text-xs font-semibold text-muted"><Sparkles aria-hidden className="h-3.5 w-3.5" /> AI suggestions</p>
      <div className="flex flex-wrap gap-1">
        {suggestions.captions?.map((text) => <button key={text} type="button" className={chip} onClick={() => onCaption(text)}>{text}</button>)}
      </div>
      <div className="flex flex-wrap gap-1">
        {suggestions.hashtags?.map((tag) => <button key={tag} type="button" className={chip} onClick={() => onHashtag(tag)}>#{tag}</button>)}
      </div>
      {suggestions.alt_text && <button type="button" className={chip} onClick={() => onAltText(suggestions.alt_text as string)}>Use image description: {suggestions.alt_text}</button>}
    </section>
  );
}

export function ImproveCaption({ caption, onAccept, onHashtag }: { caption: string; onAccept: (text: string) => void; onHashtag: (tag: string) => void }) {
  const [preview, setPreview] = useState<string | null>(null);
  const [note, setNote] = useState<string | null>(null);
  const improve = useMutation({
    mutationFn: (style: string) => api<Rewrite>("/ai/rewrite", { json: { text: caption, style } }),
    onMutate: () => setNote(null),
    onSuccess: (r) => (r.text ? setPreview(r.text) : setNote("Could not improve this right now. Try again.")),
  });
  const ideas = useMutation({
    mutationFn: () => api<HashtagIdeas>("/ai/hashtags", { json: { text: caption } }),
    onMutate: () => setNote(null),
    onSuccess: (r) => r.status !== "ready" && setNote("Could not suggest hashtags right now. Try again."),
  });
  const error = improve.error ?? ideas.error;
  const busy = improve.isPending || ideas.isPending;
  return (
    <div className="space-y-2">
      <div role="group" aria-label="Improve caption" className="flex flex-wrap items-center gap-1">
        <span className="text-xs font-semibold text-muted">Improve:</span>
        {STYLES.map(([value, label]) => (
          <Button key={value} variant="secondary" disabled={!caption.trim() || busy} loading={improve.isPending && improve.variables === value} onClick={() => improve.mutate(value)}>{label}</Button>
        ))}
        <Button variant="ghost" disabled={!caption.trim() || busy} loading={ideas.isPending} onClick={() => ideas.mutate()}>Hashtag ideas</Button>
      </div>
      <ErrorNote message={error ? errorMessage(error) : note} />
      {preview && (
        <div data-testid="rewrite-preview" className="space-y-2 rounded-lg border border-line p-2 text-sm">
          <p className="whitespace-pre-wrap break-words">{preview}</p>
          <div className="flex gap-2">
            <Button variant="secondary" onClick={() => { onAccept(preview); setPreview(null); }}>Use this</Button>
            <Button variant="ghost" onClick={() => setPreview(null)}>Keep mine</Button>
          </div>
        </div>
      )}
      {!!ideas.data?.hashtags?.length && (
        <div className="flex flex-wrap gap-1">
          {ideas.data.hashtags.map((tag) => <button key={tag} type="button" className={chip} onClick={() => onHashtag(tag)}>#{tag}</button>)}
        </div>
      )}
    </div>
  );
}
