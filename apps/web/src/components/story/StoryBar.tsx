"use client";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus } from "lucide-react";
import { useRef, useState } from "react";
import { Avatar, Spinner } from "@/components/ui";
import { useMe } from "@/hooks/useMe";
import { api, errorMessage } from "@/lib/api/client";
import type { Story, StoryGroup } from "@/lib/api/types";
import { uploadAsset } from "@/lib/api/upload";
import { useUi } from "@/stores/ui";
import { StoryViewer } from "./StoryViewer";

export function StoryBar() {
  const { data: me } = useMe();
  const qc = useQueryClient();
  const toast = useUi((s) => s.showToast);
  const groups = useQuery({ queryKey: ["stories"], queryFn: () => api<StoryGroup[]>("/stories/feed") });
  const [open, setOpen] = useState<StoryGroup | null>(null);
  const [busy, setBusy] = useState(false);
  const input = useRef<HTMLInputElement>(null);

  const add = async (file: File) => {
    setBusy(true);
    try {
      const asset = await uploadAsset(file, "story");
      await api<Story>("/stories", { json: { asset_id: asset.id } });
      qc.invalidateQueries({ queryKey: ["stories"] });
      toast("Story added. It disappears after 24 hours.");
    } catch (e) {
      toast(errorMessage(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="no-scrollbar flex gap-3 overflow-x-auto border-b border-line px-3 py-3 sm:rounded-lg sm:border">
      <button className="flex w-[68px] shrink-0 flex-col items-center gap-1" aria-label="Add a story" onClick={() => input.current?.click()} disabled={busy}>
        <span className="relative">
          <Avatar user={me} size={58} />
          <span className="absolute -bottom-0.5 -right-0.5 flex h-5 w-5 items-center justify-center rounded-full border-2 border-bg bg-brand text-white">
            {busy ? <Spinner className="h-3 w-3 border border-white/40 border-t-white" /> : <Plus className="h-3 w-3" />}
          </span>
        </span>
        <span className="w-full truncate text-center text-xs">Your story</span>
      </button>
      <input
        ref={input}
        type="file"
        accept="image/*,video/*"
        className="hidden"
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) add(file);
          e.target.value = "";
        }}
      />
      {(groups.data ?? []).map((g) => (
        <button key={g.author.id} className="flex w-[68px] shrink-0 flex-col items-center gap-1" onClick={() => setOpen(g)} aria-label={`Stories by ${g.author.username}`}>
          <Avatar user={g.author} size={58} ring={!g.all_viewed} />
          <span className="w-full truncate text-center text-xs">{g.author.username}</span>
        </button>
      ))}
      {open && (
        <StoryViewer
          stories={open.stories}
          ownerIsMe={open.author.id === me?.id}
          onClose={() => {
            setOpen(null);
            qc.invalidateQueries({ queryKey: ["stories"] });
          }}
        />
      )}
    </div>
  );
}
