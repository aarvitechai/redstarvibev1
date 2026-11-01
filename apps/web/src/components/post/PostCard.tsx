"use client";
import { Bookmark, Flag, Heart, MessageCircle, MoreHorizontal, Send, Trash2, BarChart3 } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { Avatar, Button, Modal } from "@/components/ui";
import { api, errorMessage } from "@/lib/api/client";
import type { Insights, Post } from "@/lib/api/types";
import { compactNumber, cn, timeAgo } from "@/lib/utils";
import { socket } from "@/lib/ws/client";
import { useUi } from "@/stores/ui";
import { Caption } from "./Caption";
import { Comments } from "./Comments";
import { MediaCarousel } from "./MediaCarousel";
import { ReportDialog } from "./ReportDialog";

export function PostCard({ post, priority, standalone, onRemoved }: { post: Post; priority?: boolean; standalone?: boolean; onRemoved?: () => void }) {
  const [liked, setLiked] = useState(post.liked);
  const [likes, setLikes] = useState(post.like_count);
  const [commentCount, setCommentCount] = useState(post.comment_count);
  const [saved, setSaved] = useState(post.saved);
  const [showComments, setShowComments] = useState(false);
  const [menu, setMenu] = useState(false);
  const [report, setReport] = useState(false);
  const [insights, setInsights] = useState<Insights | null>(null);
  const toast = useUi((s) => s.showToast);
  const router = useRouter();

  useEffect(() => {
    const unwatch = socket.watchPost(post.id);
    const off = socket.on((event) => {
      if (event.type === "counter" && event.post_id === post.id) {
        if (event.field === "like_count") setLikes(event.value);
        if (event.field === "comment_count") setCommentCount(event.value);
      }
    });
    return () => {
      off();
      unwatch();
    };
  }, [post.id]);

  const toggleLike = async () => {
    const next = !liked;
    setLiked(next); // optimistic
    setLikes((n) => Math.max(0, n + (next ? 1 : -1)));
    try {
      const res = await api<{ like_count: number }>(`/posts/${post.id}/like`, { method: next ? "POST" : "DELETE" });
      setLikes(res.like_count);
    } catch (e) {
      setLiked(!next);
      setLikes((n) => Math.max(0, n + (next ? -1 : 1)));
      toast(errorMessage(e));
    }
  };

  const toggleSave = async () => {
    const next = !saved;
    setSaved(next);
    try {
      if (next) await api(`/posts/${post.id}/save`, { json: {} });
      else await api(`/posts/${post.id}/save`, { method: "DELETE" });
    } catch (e) {
      setSaved(!next);
      toast(errorMessage(e));
    }
  };

  const share = async () => {
    const url = `${location.origin}/p/${post.id}`;
    try {
      if (navigator.share) await navigator.share({ url, title: "RedStarVibe" });
      else {
        await navigator.clipboard.writeText(url);
        toast("Link copied");
      }
    } catch {}
  };

  const recordView = useCallback(() => {
    api(`/posts/${post.id}/view`, { method: "POST" }).catch(() => undefined);
  }, [post.id]);

  return (
    <article className={cn("border-b border-line bg-bg sm:rounded-lg sm:border", !standalone && "feed-item")}>
      <header className="flex items-center gap-3 px-3 py-2">
        <Link href={`/${post.author.username}`} aria-label={post.author.username}>
          <Avatar user={post.author} size={36} />
        </Link>
        <div className="min-w-0 flex-1 text-sm leading-tight">
          <Link href={`/${post.author.username}`} className="font-semibold">
            {post.author.username}
          </Link>
          {post.location && (
            <Link href={`/place/${encodeURIComponent(post.location)}`} className="block truncate text-xs text-muted">
              {post.location}
            </Link>
          )}
        </div>
        <time dateTime={post.created_at} className="text-xs text-muted">
          {timeAgo(post.created_at)}
        </time>
        <button aria-label="More options" onClick={() => setMenu(true)} className="flex h-11 w-11 items-center justify-center rounded-full hover:bg-surface">
          <MoreHorizontal className="h-5 w-5" />
        </button>
      </header>

      {post.status !== "published" && (
        <p className="bg-surface px-3 py-1.5 text-xs text-muted">
          {post.status === "processing" ? "Processing. It will go live shortly." : `Status: ${post.status}`}
        </p>
      )}
      <MediaCarousel media={post.media} priority={priority} onView={recordView} />

      <div className="flex items-center px-1 pt-1">
        <button aria-label={liked ? "Unlike" : "Like"} aria-pressed={liked} onClick={toggleLike} className="flex h-11 w-11 items-center justify-center">
          <Heart className={cn("h-6 w-6 transition-transform active:scale-125", liked && "fill-brand stroke-brand")} />
        </button>
        <button aria-label="Comments" onClick={() => setShowComments(true)} className="flex h-11 w-11 items-center justify-center">
          <MessageCircle className="h-6 w-6" />
        </button>
        <button aria-label="Share" onClick={share} className="flex h-11 w-11 items-center justify-center">
          <Send className="h-6 w-6" />
        </button>
        <button aria-label={saved ? "Remove from saved" : "Save"} aria-pressed={saved} onClick={toggleSave} className="ml-auto flex h-11 w-11 items-center justify-center">
          <Bookmark className={cn("h-6 w-6", saved && "fill-fg")} />
        </button>
      </div>
      <div className="space-y-1 px-3 pb-3 text-sm">
        <p className="font-semibold">
          {compactNumber(likes)} {likes === 1 ? "like" : "likes"}
        </p>
        {post.caption && (
          <p className="whitespace-pre-wrap break-words">
            <Link href={`/${post.author.username}`} className="font-semibold">
              {post.author.username}
            </Link>{" "}
            <Caption text={post.caption} />
          </p>
        )}
        {!standalone && (
          <button className="min-h-8 text-muted" onClick={() => setShowComments(true)}>
            {commentCount > 0 ? `View all ${compactNumber(commentCount)} comments` : "Add a comment"}
          </button>
        )}
      </div>
      {standalone && (
        <div className="border-t border-line px-3 pb-3">
          <Comments postId={post.id} />
        </div>
      )}

      {!standalone && (
        <Modal open={showComments} onClose={() => setShowComments(false)} title="Comments">
          {showComments && <Comments postId={post.id} />}
        </Modal>
      )}
      <Modal open={menu} onClose={() => setMenu(false)} title="Post options">
        <div className="space-y-1">
          <Link href={`/p/${post.id}`} className="flex min-h-11 items-center rounded-lg px-3 hover:bg-surface">
            Go to post
          </Link>
          {post.is_own ? (
            <>
              <button
                className="flex min-h-11 w-full items-center gap-2 rounded-lg px-3 hover:bg-surface"
                onClick={async () => setInsights(await api<Insights>(`/posts/${post.id}/insights`))}
              >
                <BarChart3 className="h-4 w-4" /> View insights
              </button>
              {insights && (
                <p className="px-3 py-1 text-sm text-muted">
                  {insights.views} views, {insights.likes} likes, {insights.comments} comments, {insights.saves} saves.
                  Engagement {(insights.engagement_rate * 100).toFixed(1)}%.
                </p>
              )}
              <Button
                variant="danger"
                className="w-full !justify-start"
                onClick={async () => {
                  await api(`/posts/${post.id}`, { method: "DELETE" });
                  setMenu(false);
                  toast("Post deleted");
                  if (standalone) router.push("/feed");
                  onRemoved?.();
                }}
              >
                <Trash2 className="h-4 w-4" /> Delete post
              </Button>
            </>
          ) : (
            <button
              className="flex min-h-11 w-full items-center gap-2 rounded-lg px-3 text-brand hover:bg-surface"
              onClick={() => {
                setMenu(false);
                setReport(true);
              }}
            >
              <Flag className="h-4 w-4" /> Report post
            </button>
          )}
        </div>
      </Modal>
      <ReportDialog open={report} onClose={() => setReport(false)} entityType="post" entityId={post.id} />
    </article>
  );
}
