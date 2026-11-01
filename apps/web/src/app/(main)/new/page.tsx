"use client";
import { useMutation, useQuery } from "@tanstack/react-query";
import { ImagePlus, Sparkles, X } from "lucide-react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useRef, useState } from "react";
import { Button, ErrorNote, Field, Input, Spinner } from "@/components/ui";
import { api, errorMessage } from "@/lib/api/client";
import type { CaptionOut, Post } from "@/lib/api/types";
import { uploadAsset } from "@/lib/api/upload";
import { useUi } from "@/stores/ui";

type Item = { key: string; file: File; preview: string; progress: number; assetId?: string; error?: string };

function NewPost() {
  const router = useRouter();
  const params = useSearchParams();
  const toast = useUi((s) => s.showToast);
  const [isReel, setIsReel] = useState(params.has("reel"));
  const [items, setItems] = useState<Item[]>([]);
  const [caption, setCaption] = useState("");
  const [location, setLocation] = useState("");
  const [visibility, setVisibility] = useState("public");
  const [schedule, setSchedule] = useState("");
  const [altText, setAltText] = useState("");
  const [error, setError] = useState<string | null>(null);
  const input = useRef<HTMLInputElement>(null);
  const idempotency = useRef(crypto.randomUUID());

  const drafts = useQuery({ queryKey: ["drafts"], queryFn: () => api<Post[]>("/posts/drafts") });

  const addFiles = (files: FileList) => {
    const room = (isReel ? 1 : 10) - items.length;
    Array.from(files)
      .slice(0, Math.max(0, room))
      .forEach((file) => {
        const key = crypto.randomUUID();
        setItems((list) => [...list, { key, file, preview: URL.createObjectURL(file), progress: 0 }]);
        const update = (patch: Partial<Item>) => setItems((list) => list.map((i) => (i.key === key ? { ...i, ...patch } : i)));
        uploadAsset(file, isReel ? "reel" : "post", (progress) => update({ progress }))
          .then((asset) => update({ assetId: asset.id, progress: 1 }))
          .catch((e) => update({ error: errorMessage(e) }));
      });
  };

  const ready = items.length > 0 && items.every((i) => i.assetId);
  const failed = items.some((i) => i.error);

  const publish = useMutation({
    mutationFn: (draft: boolean) =>
      api<Post>("/posts", {
        json: {
          asset_ids: items.map((i) => i.assetId),
          caption,
          location: location || null,
          visibility,
          is_reel: isReel,
          draft,
          scheduled_at: !draft && schedule ? new Date(schedule).toISOString() : null,
          alt_texts: altText ? [altText] : null,
        },
        headers: { "Idempotency-Key": idempotency.current },
      }),
    onSuccess: (post, draft) => {
      toast(draft ? "Saved to drafts" : schedule ? "Scheduled" : "Publishing your post");
      router.push(draft || schedule ? "/new" : `/p/${post.id}`);
      if (draft || schedule) {
        setItems([]);
        setCaption("");
        idempotency.current = crypto.randomUUID();
        drafts.refetch();
      }
    },
    onError: (e) => setError(errorMessage(e)),
  });

  const suggest = useMutation({
    mutationFn: () => api<CaptionOut>("/ai/caption", { json: { asset_id: items[0]?.assetId } }),
    onSuccess: (r) => {
      setCaption(`${r.caption}\n\n${r.hashtags.map((t) => `#${t}`).join(" ")}`);
      setAltText(r.alt_text);
    },
    onError: (e) => setError(errorMessage(e)),
  });

  return (
    <div className="mx-auto max-w-xl space-y-4 p-3 sm:p-4">
      <h1 className="text-xl font-bold">{isReel ? "New reel" : "New post"}</h1>
      <label className="flex min-h-11 items-center gap-3 text-sm">
        <input type="checkbox" checked={isReel} disabled={items.length > 0} onChange={(e) => setIsReel(e.target.checked)} className="h-5 w-5 accent-[#C8102E]" />
        This is a reel: one vertical video up to 90 seconds
      </label>
      <div className="grid grid-cols-3 gap-2">
        {items.map((item) => (
          <div key={item.key} className="relative aspect-square overflow-hidden rounded-lg bg-surface">
            {item.file.type.startsWith("video") ? <video src={item.preview} muted className="h-full w-full object-cover" /> : <img src={item.preview} alt="" className="h-full w-full object-cover" />}
            {!item.assetId && !item.error && (
              <div className="absolute inset-0 flex flex-col items-center justify-center bg-black/50 text-xs text-white">
                <Spinner className="h-5 w-5 border-2" />
                {item.progress < 1 ? `${Math.round(item.progress * 100)}%` : "Processing"}
              </div>
            )}
            {item.error && <div className="absolute inset-0 flex items-center justify-center bg-black/70 p-1 text-center text-xs text-white">{item.error}</div>}
            <button aria-label="Remove" className="absolute right-0 top-0 flex h-11 w-11 items-center justify-center text-white drop-shadow" onClick={() => setItems((l) => l.filter((i) => i.key !== item.key))}>
              <X className="h-5 w-5" />
            </button>
          </div>
        ))}
        {items.length < (isReel ? 1 : 10) && (
          <button onClick={() => input.current?.click()} className="flex aspect-square flex-col items-center justify-center gap-1 rounded-lg border-2 border-dashed border-line text-sm text-muted hover:bg-surface">
            <ImagePlus className="h-7 w-7" /> Add
          </button>
        )}
      </div>
      <input
        ref={input}
        data-testid="file-input"
        type="file"
        hidden
        multiple={!isReel}
        accept={isReel ? "video/mp4,video/quicktime,video/webm" : "image/jpeg,image/png,image/webp,image/avif,image/gif,video/mp4,video/quicktime,video/webm"}
        onChange={(e) => {
          if (e.target.files) addFiles(e.target.files);
          e.target.value = "";
        }}
      />
      <Field label="Caption">
        <textarea value={caption} maxLength={2200} rows={4} onChange={(e) => setCaption(e.target.value)} placeholder="Say something. Use #hashtags and @mentions." className="w-full rounded-lg border border-line bg-surface p-3 text-[16px] focus:border-brand focus:outline-none sm:text-sm" />
      </Field>
      <Button type="button" variant="secondary" disabled={!items[0]?.assetId} loading={suggest.isPending} onClick={() => suggest.mutate()}>
        <Sparkles className="h-4 w-4" /> Suggest a caption with AI
      </Button>
      <Field label="Image description for screen readers">
        <Input value={altText} maxLength={500} onChange={(e) => setAltText(e.target.value)} />
      </Field>
      <Field label="Location">
        <Input value={location} maxLength={120} onChange={(e) => setLocation(e.target.value)} placeholder="Add a place" />
      </Field>
      <Field label="Who can see this">
        <select value={visibility} onChange={(e) => setVisibility(e.target.value)} className="min-h-11 w-full rounded-lg border border-line bg-surface px-3 text-[16px] sm:text-sm">
          <option value="public">Everyone</option>
          <option value="followers">Followers only</option>
        </select>
      </Field>
      <Field label="Schedule for later (optional)">
        <Input type="datetime-local" value={schedule} onChange={(e) => setSchedule(e.target.value)} />
      </Field>
      <ErrorNote message={error} />
      <div className="flex gap-2">
        <Button className="flex-1" disabled={!ready || failed} loading={publish.isPending} onClick={() => publish.mutate(false)}>
          {schedule ? "Schedule" : "Share"}
        </Button>
        <Button variant="secondary" disabled={!ready || failed || publish.isPending} onClick={() => publish.mutate(true)}>
          Save draft
        </Button>
      </div>
      {!!drafts.data?.length && (
        <section>
          <h2 className="pb-1 pt-3 text-sm font-semibold text-muted">Drafts and scheduled</h2>
          <ul>
            {drafts.data.map((d) => (
              <li key={d.id} className="flex items-center justify-between gap-2 py-1 text-sm">
                <Link href={`/p/${d.id}`} className="min-h-11 min-w-0 flex-1 truncate leading-[44px]">
                  {d.caption || "Untitled"} <span className="text-muted">({d.status}{d.scheduled_at ? `, ${new Date(d.scheduled_at).toLocaleString()}` : ""})</span>
                </Link>
                {(d.status === "draft" || d.status === "scheduled") && (
                  <Button variant="secondary" onClick={async () => { await api(`/posts/${d.id}/publish`, { method: "POST" }); drafts.refetch(); toast("Publishing"); }}>
                    Publish
                  </Button>
                )}
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}

export default function NewPage() {
  return (
    <Suspense>
      <NewPost />
    </Suspense>
  );
}
