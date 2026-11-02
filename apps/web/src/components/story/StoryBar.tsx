"use client";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus } from "lucide-react";
import { useRef, useState } from "react";
import { Avatar } from "@/components/ui";
import { useMe } from "@/hooks/useMe";
import { api } from "@/lib/api/client";
import type { StoryGroup } from "@/lib/api/types";
import { useUi } from "@/stores/ui";
import { StoryComposer } from "./StoryComposer";
import { StoryViewer } from "./StoryViewer";

export function StoryBar() {
  const { data: me } = useMe();
  const qc = useQueryClient();
  const toast = useUi((s) => s.showToast);
  const groups = useQuery({ queryKey: ["stories"], queryFn: () => api<StoryGroup[]>("/stories/feed") });
  const [open, setOpen] = useState<StoryGroup | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const input = useRef<HTMLInputElement>(null);

  return (
    <div className="no-scrollbar flex gap-3 overflow-x-auto border-b border-line px-3 py-3 sm:rounded-lg sm:border">
      <button className="flex w-[68px] shrink-0 flex-col items-center gap-1" aria-label="Add a story" onClick={() => input.current?.click()}>
        <span className="relative">
          <Avatar user={me} size={58} />
          <span className="absolute -bottom-0.5 -right-0.5 flex h-5 w-5 items-center justify-center rounded-full border-2 border-bg bg-brand text-white">
            <Plus className="h-3 w-3" />
          </span>
        </span>
        <span className="w-full truncate text-center text-xs">Your story</span>
      </button>
      <input
        ref={input}
        type="file"
        data-testid="story-file"
        accept="image/*,video/*"
        className="hidden"
        onChange={(e) => {
          setFile(e.target.files?.[0] ?? null);
          e.target.value = "";
        }}
      />
      {(groups.data ?? []).map((g) => (
        <button key={g.author.id} className="flex w-[68px] shrink-0 flex-col items-center gap-1" onClick={() => setOpen(g)} aria-label={`Stories by ${g.author.username}`}>
          <Avatar user={g.author} size={58} ring={!g.all_viewed} />
          <span className="w-full truncate text-center text-xs">{g.author.username}</span>
        </button>
      ))}
      {file && (
        <StoryComposer
          file={file}
          onClose={() => setFile(null)}
          onShared={() => {
            setFile(null);
            qc.invalidateQueries({ queryKey: ["stories"] });
            toast("Story added. It disappears after 24 hours.");
          }}
        />
      )}
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
