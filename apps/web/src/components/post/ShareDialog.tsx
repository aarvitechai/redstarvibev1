"use client";
import { useQuery } from "@tanstack/react-query";
import { Link2, MessageCircle, Send } from "lucide-react";
import { Modal } from "@/components/ui";
import { useMe } from "@/hooks/useMe";
import { api, errorMessage } from "@/lib/api/client";
import type { Conversation } from "@/lib/api/types";
import { useUi } from "@/stores/ui";

const ROW = "flex min-h-11 w-full items-center gap-2 rounded-lg px-3 hover:bg-surface";

function ShareToChat({ postId, onDone }: { postId: string; onDone: () => void }) {
  const toast = useUi((s) => s.showToast);
  const { data: me } = useMe();
  const chats = useQuery({ queryKey: ["conversations"], queryFn: () => api<Conversation[]>("/conversations") });
  if (!chats.data?.length) return null;
  return (
    <div className="border-b border-line pb-1">
      <p className="px-3 py-1 text-xs font-semibold text-muted">Send in a message</p>
      {chats.data.slice(0, 6).map((c) => {
        const name = c.title || c.members.filter((m) => m.user.id !== me?.id).map((m) => m.user.username).join(", ") || "Just you";
        return (
          <button
            key={c.id}
            className="flex min-h-11 w-full items-center rounded-lg px-3 text-left text-sm hover:bg-surface"
            onClick={async () => {
              try {
                await api(`/conversations/${c.id}/messages`, { json: { body: "", post_id: postId } });
                toast("Sent");
                onDone();
              } catch (e) {
                toast(errorMessage(e));
              }
            }}
          >
            <span className="truncate">{name}</span>
          </button>
        );
      })}
    </div>
  );
}

export function ShareDialog({ postId, open, onClose }: { postId: string; open: boolean; onClose: () => void }) {
  const toast = useUi((s) => s.showToast);
  const { data: me } = useMe();
  const postUrl = () => `${location.origin}/p/${postId}`;
  const copyLink = async () => {
    try {
      await navigator.clipboard.writeText(postUrl());
      toast("Link copied");
    } catch {
      toast("Could not copy the link");
    }
    onClose();
  };
  const nativeShare = async () => {
    onClose();
    try {
      await navigator.share({ url: postUrl(), title: "RedStarVibe" });
    } catch {} // the person closed the share sheet
  };
  return (
    <Modal open={open} onClose={onClose} title="Share post">
      <div className="space-y-1">
        {open && me && <ShareToChat postId={postId} onDone={onClose} />}
        <button className={ROW} onClick={copyLink}>
          <Link2 className="h-4 w-4" /> Copy link
        </button>
        {open && (
          <a href={`https://wa.me/?text=${encodeURIComponent(postUrl())}`} target="_blank" rel="noopener noreferrer" onClick={onClose} className={ROW}>
            <MessageCircle className="h-4 w-4" /> Share on WhatsApp
          </a>
        )}
        {open && "share" in navigator && (
          <button className={ROW} onClick={nativeShare}>
            <Send className="h-4 w-4" /> More options
          </button>
        )}
      </div>
    </Modal>
  );
}
