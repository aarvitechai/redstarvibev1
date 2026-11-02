"use client";
import { useMutation, useQuery } from "@tanstack/react-query";
import { CheckCircle2, Circle, ImagePlus, Type, X } from "lucide-react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useRef, useState } from "react";
import { BestTimes } from "@/components/post/BestTimes";
import { ScheduleRequests } from "@/components/post/ScheduleRequests";
import { CaptionChips, ImproveCaption, MakeEffective, useAiFeatures, useCaptionSuggestions } from "@/components/post/AiWriting";
import { frameRatio } from "@/components/post/MediaCarousel";
import { MusicPicker, type TrackId } from "@/components/post/Music";
import { isEdited } from "@/components/post/mediaEdit";
import { postChecklist } from "@/components/post/postChecklist";
import { TextOverlayEditor } from "@/components/post/TextOverlayEditor";
import { Button, ErrorNote, Field, Input, Spinner } from "@/components/ui";
import { useMe } from "@/hooks/useMe";
import { api, errorMessage } from "@/lib/api/client";
import type { CaptionSuggestions, MediaEdit, Post, TextOverlay } from "@/lib/api/types";
import { uploadAsset } from "@/lib/api/upload";
import { cn } from "@/lib/utils";
import { useUi } from "@/stores/ui";

type Item = {
  key: string;
  file: File;
  preview: string;
  progress: number;
  assetId?: string;
  error?: string;
  width?: number | null;
  height?: number | null;
  overlay?: TextOverlay;
  edit?: MediaEdit;
};

const REEL_RATIO = 9 / 16;

function NewPost() {
  const router = useRouter();
  const params = useSearchParams();
  const toast = useUi((s) => s.showToast);
  const [isReel, setIsReel] = useState(params.has("reel"));
  const [items, setItems] = useState<Item[]>([]);
  const [selectedKey, setSelectedKey] = useState<string | null>(null);
  const [caption, setCaption] = useState("");
  const [location, setLocation] = useState("");
  const [tags, setTags] = useState("");
  const [collab, setCollab] = useState("");
  const [capsule, setCapsule] = useState(false);
  const [visibility, setVisibility] = useState("public");
  const [schedule, setSchedule] = useState("");
  const [altText, setAltText] = useState("");
  const [music, setMusic] = useState<TrackId | null>(null);
  const { data: me } = useMe();
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
          .then((asset) => update({ assetId: asset.id, progress: 1, width: asset.width, height: asset.height }))
          .catch((e) => update({ error: errorMessage(e) }));
      });
  };

  const selected = items.find((i) => i.key === selectedKey) ?? items[0];
  const setOverlay = (key: string, overlay: TextOverlay | undefined) =>
    setItems((list) => list.map((i) => (i.key === key ? { ...i, overlay } : i)));

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
          tagged_usernames: tags.split(/[\s,]+/).filter(Boolean),
          collab_username: collab.trim() || null,
          is_capsule: capsule && !draft,
          music,
          media_edits: items.map((i) => (isEdited(i.edit) ? i.edit : null)),
          text_overlays: items.map((i) => (i.overlay?.text.trim() ? i.overlay : null)),
        },
        headers: { "Idempotency-Key": idempotency.current },
      }),
    onSuccess: (post, draft) => {
      toast(draft ? "Saved to drafts" : capsule && schedule ? "Time capsule sealed" : schedule ? "Scheduled" : "Publishing your post");
      router.push(draft || schedule ? "/new" : `/p/${post.id}`);
      if (draft || schedule) {
        setItems([]);
        setCaption("");
        setMusic(null);
        setTags("");
        setCollab("");
        setCapsule(false);
        setSchedule("");
        idempotency.current = crypto.randomUUID();
        drafts.refetch();
      }
    },
    onError: (e) => setError(errorMessage(e)),
  });

  const features = useAiFeatures();
  const suggestions = useCaptionSuggestions(selected?.assetId, !!features?.captions);
  const addHashtag = (tag: string) => setCaption((text) => (text.includes(`#${tag}`) ? text : `${text.trimEnd()} #${tag}`.trimStart()));
  const applyAi = (s: CaptionSuggestions) => {
    // Fills only what is still empty, so nothing the person wrote is ever replaced.
    if (!caption.trim() && s.captions[0]) setCaption(s.captions[0]);
    s.hashtags.forEach(addHashtag);
    if (!altText && s.alt_text) setAltText(s.alt_text);
    if (!music && s.music) setMusic(s.music as TrackId);
    if (selected && !selected.overlay && s.tagline) {
      setOverlay(selected.key, { text: s.tagline, x: 50, y: 15, size: "large", style: "highlight", color: "#C8102E", effect: "pop" });
    }
    toast("Applied. Check it and change anything you like.");
  };
  const checklist = postChecklist({ caption, altText, location, hasPhoto: items.some((i) => i.file.type.startsWith("image")) });

  return (
    <div className="mx-auto max-w-xl space-y-4 p-3 sm:p-4">
      <h1 className="text-xl font-bold">{isReel ? "New reel" : "New post"}</h1>
      <ScheduleRequests />
      <label className="flex min-h-11 items-center gap-3 text-sm">
        <input type="checkbox" checked={isReel} disabled={items.length > 0} onChange={(e) => setIsReel(e.target.checked)} className="h-5 w-5 accent-[#C8102E]" />
        This is a reel: one vertical video up to 90 seconds
      </label>
      <div className="grid grid-cols-3 gap-2">
        {items.map((item, index) => (
          <div key={item.key} className={cn("relative aspect-square overflow-hidden rounded-lg bg-surface", items.length > 1 && item.key === selected?.key && "ring-2 ring-brand")}>
            {item.file.type.startsWith("video") ? <video src={item.preview} muted className="h-full w-full object-cover" /> : <img src={item.preview} alt="" className="h-full w-full object-cover" />}
            <button type="button" aria-label={`Write text on item ${index + 1}`} aria-pressed={item.key === selected?.key} className="absolute inset-0" onClick={() => setSelectedKey(item.key)} />
            {item.overlay && <Type aria-hidden className="pointer-events-none absolute bottom-1 left-1 h-5 w-5 rounded bg-black/60 p-0.5 text-white" />}
            {!item.assetId && !item.error && (
              <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center bg-black/50 text-xs text-white">
                <Spinner className="h-5 w-5 border-2" />
                {item.progress < 1 ? `${Math.round(item.progress * 100)}%` : "Processing"}
              </div>
            )}
            {item.error && <div className="pointer-events-none absolute inset-0 flex items-center justify-center bg-black/70 p-1 text-center text-xs text-white">{item.error}</div>}
            <button aria-label="Remove" className="absolute right-0 top-0 flex h-11 w-11 items-center justify-center text-white drop-shadow" onClick={() => setItems((l) => l.filter((i) => i.key !== item.key))}>
              <X className="h-5 w-5" />
            </button>
          </div>
        ))}
        {items.length < (isReel ? 1 : 10) && (
          <button onClick={() => input.current?.click()} className="flex aspect-square flex-col items-center justify-center gap-1 rounded-lg border-2 border-dashed border-line text-sm text-muted hover:bg-surface">
            <ImagePlus className="h-5 w-5" /> Add
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
      {selected && (
        <TextOverlayEditor
          key={selected.key}
          src={selected.preview}
          isVideo={selected.file.type.startsWith("video")}
          ratio={isReel ? REEL_RATIO : frameRatio(items[0]?.width, items[0]?.height)}
          value={selected.overlay}
          onChange={(overlay) => setOverlay(selected.key, overlay)}
          edit={selected.edit}
          tagline={suggestions?.tagline}
          onEditChange={(edit) => setItems((list) => list.map((i) => (i.key === selected.key ? { ...i, edit } : i)))}
        />
      )}
      {items.length > 0 && <MakeEffective enabled={!!features?.captions} suggestions={suggestions} canSetUp={!!me && me.role !== "user"} onApply={applyAi} />}
      <Field label="Caption">
        <textarea value={caption} maxLength={2200} rows={4} onChange={(e) => setCaption(e.target.value)} placeholder="Say something. Use #hashtags and @mentions." className="w-full rounded-lg border border-line bg-surface p-3 text-[16px] focus:border-brand focus:outline-none sm:text-sm" />
      </Field>
      <p className="-mt-3 text-right text-xs text-muted">{caption.length}/2200</p>
      <CaptionChips suggestions={suggestions} onCaption={setCaption} onHashtag={addHashtag} onAltText={setAltText} />
      {features?.writing && <ImproveCaption caption={caption} onAccept={setCaption} onHashtag={addHashtag} />}
      {items.length > 0 && <MusicPicker value={music} onChange={setMusic} />}
      <Field label="Image description for screen readers">
        <Input value={altText} maxLength={500} onChange={(e) => setAltText(e.target.value)} />
      </Field>
      <Field label="Tag people">
        <Input value={tags} onChange={(e) => setTags(e.target.value)} placeholder="@asha, @kabir" autoCapitalize="none" />
      </Field>
      <Field label="Invite a collaborator (optional)">
        <Input value={collab} onChange={(e) => setCollab(e.target.value)} placeholder="@username" autoCapitalize="none" />
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
      <BestTimes onPick={setSchedule} />
      {schedule && (
        <label className="flex min-h-11 items-center gap-3 text-sm">
          <input type="checkbox" checked={capsule} onChange={(e) => setCapsule(e.target.checked)} className="h-5 w-5 accent-[#C8102E]" />
          Seal as a time capsule: it cannot be opened before this date
        </label>
      )}
      {items.length > 0 && (
        <section aria-label="Post checklist" data-testid="post-checklist" className="rounded-lg border border-line p-3">
          <h2 className="pb-1 text-xs font-semibold text-muted">Post checklist: {checklist.filter((i) => i.done).length} of {checklist.length}</h2>
          <ul className="grid gap-1 text-xs sm:grid-cols-2">
            {checklist.map((item) => (
              <li key={item.label} className={cn("flex items-center gap-1.5", !item.done && "text-muted")}>
                {item.done ? <CheckCircle2 aria-label="Done" className="h-3.5 w-3.5 shrink-0 text-brand" /> : <Circle aria-label="To do" className="h-3.5 w-3.5 shrink-0" />}
                {item.label}
              </li>
            ))}
          </ul>
        </section>
      )}
      <ErrorNote message={error} />
      <div className="flex gap-2">
        <Button className="flex-1" disabled={!ready || failed} loading={publish.isPending} onClick={() => publish.mutate(false)}>
          {schedule ? (capsule ? "Seal time capsule" : "Schedule") : "Share"}
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
                  {d.caption || "Untitled"} <span className="text-muted">({d.is_capsule ? "time capsule" : d.status}{d.scheduled_at ? `, ${new Date(d.scheduled_at).toLocaleString()}` : ""})</span>
                </Link>
                {(d.status === "draft" || d.status === "scheduled") && !d.is_capsule && (
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
