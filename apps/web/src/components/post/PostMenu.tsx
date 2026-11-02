"use client";
import { useQueryClient } from "@tanstack/react-query";
import { BarChart3, Flag, Pencil, Pin, Trash2, UserX } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Button, Modal } from "@/components/ui";
import { useMe } from "@/hooks/useMe";
import { api, errorMessage } from "@/lib/api/client";
import type { Insights, Post } from "@/lib/api/types";
import { useUi } from "@/stores/ui";

const ROW = "flex min-h-11 w-full items-center gap-2 rounded-lg px-3 hover:bg-surface";

type Props = {
  post: Post;
  caption: string;
  open: boolean;
  standalone?: boolean;
  onClose: () => void;
  onCaption: (caption: string) => void;
  onReport: () => void;
  onRemoved?: () => void;
};

export function PostMenu({ post, caption, open, standalone, onClose, onCaption, onReport, onRemoved }: Props) {
  const [insights, setInsights] = useState<Insights | null>(null);
  const [draft, setDraft] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const toast = useUi((s) => s.showToast);
  const router = useRouter();
  const { data: me } = useMe();
  const qc = useQueryClient();

  const run = async (action: () => Promise<unknown>) => {
    try {
      await action();
    } catch (e) {
      toast(errorMessage(e));
    }
  };
  const close = () => {
    setDraft(null);
    onClose();
  };
  const saveCaption = () =>
    run(async () => {
      setSaving(true);
      try {
        const saved = await api<Post>(`/posts/${post.id}`, { method: "PATCH", json: { caption: draft ?? "" } });
        onCaption(saved.caption);
        toast("Caption updated");
        close();
      } finally {
        setSaving(false);
      }
    });
  const togglePin = () =>
    run(async () => {
      await api(`/posts/${post.id}/pin`, { method: post.pinned ? "DELETE" : "POST" });
      toast(post.pinned ? "Unpinned" : "Pinned to your profile");
      close();
      qc.invalidateQueries({ queryKey: ["user-posts"] });
      qc.invalidateQueries({ queryKey: ["post", post.id] });
    });
  const remove = () =>
    run(async () => {
      await api(`/posts/${post.id}`, { method: "DELETE" });
      close();
      toast("Post deleted");
      if (standalone) router.push("/feed");
      onRemoved?.();
    });
  const removeTag = () =>
    run(async () => {
      await api(`/posts/${post.id}/tags/me`, { method: "DELETE" });
      close();
      toast("Tag removed");
    });

  return (
    <Modal open={open} onClose={close} title="Post options">
      {draft !== null ? (
        <div className="space-y-2">
          <textarea
            aria-label="Edit caption"
            value={draft}
            maxLength={2200}
            rows={5}
            onChange={(e) => setDraft(e.target.value)}
            className="w-full rounded-lg border border-line bg-surface p-3 text-[16px] focus:border-brand focus:outline-none sm:text-sm"
          />
          <div className="flex gap-2">
            <Button className="flex-1" loading={saving} onClick={saveCaption}>Save</Button>
            <Button variant="secondary" onClick={() => setDraft(null)}>Cancel</Button>
          </div>
        </div>
      ) : (
        <div className="space-y-1">
          <Link href={`/p/${post.id}`} className={ROW}>Go to post</Link>
          {post.is_own ? (
            <>
              <button className={ROW} onClick={() => setDraft(caption)}>
                <Pencil className="h-4 w-4" /> Edit caption
              </button>
              {post.status === "published" && (
                <button className={ROW} onClick={togglePin}>
                  <Pin className="h-4 w-4" /> {post.pinned ? "Unpin from profile" : "Pin to profile"}
                </button>
              )}
              <button className={ROW} onClick={() => run(async () => setInsights(await api<Insights>(`/posts/${post.id}/insights`)))}>
                <BarChart3 className="h-4 w-4" /> View insights
              </button>
              {insights && (
                <p className="px-3 py-1 text-sm text-muted">
                  {insights.views} views, {insights.likes} likes, {insights.comments} comments, {insights.saves} saves.
                  Engagement {(insights.engagement_rate * 100).toFixed(1)}%.
                </p>
              )}
              <Button variant="danger" className="w-full !justify-start" onClick={remove}>
                <Trash2 className="h-4 w-4" /> Delete post
              </Button>
            </>
          ) : (
            <>
              {me && post.tagged?.some((u) => u.id === me.id) && (
                <button className={ROW} onClick={removeTag}>
                  <UserX className="h-4 w-4" /> Remove my tag
                </button>
              )}
              <button className={`${ROW} text-brand`} onClick={() => { close(); onReport(); }}>
                <Flag className="h-4 w-4" /> Report post
              </button>
            </>
          )}
        </div>
      )}
    </Modal>
  );
}
