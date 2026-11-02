"use client";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { BadgeCheck, Bookmark, Flag, Heart, Link2, MessageCircle, MoreHorizontal, Pin, Send, Trash2, BarChart3, UserX } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { Avatar, Button, Modal } from "@/components/ui";
import { useMe } from "@/hooks/useMe";
import { api, errorMessage } from "@/lib/api/client";
import type { Conversation, Insights, Post } from "@/lib/api/types";
import { compactNumber, cn, timeAgo } from "@/lib/utils";
import { socket } from "@/lib/ws/client";
import { useUi } from "@/stores/ui";
import { Caption } from "./Caption";
import { Comments } from "./Comments";
import { MediaCarousel } from "./MediaCarousel";
import { ReportDialog } from "./ReportDialog";

const VIEW_DWELL_MS = 1000;

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

export function PostCard({ post, priority, standalone, onRemoved }: { post: Post; priority?: boolean; standalone?: boolean; onRemoved?: () => void }) {
  const [liked, setLiked] = useState(post.liked);
  const [likes, setLikes] = useState(post.like_count);
  const [commentCount, setCommentCount] = useState(post.comment_count);
  const [views, setViews] = useState(post.view_count);
  const mediaRef = useRef<HTMLDivElement>(null);
  const [saved, setSaved] = useState(post.saved);
  const [showComments, setShowComments] = useState(false);
  const [menu, setMenu] = useState(false);
  const [sharing, setSharing] = useState(false);
  const [report, setReport] = useState(false);
  const [insights, setInsights] = useState<Insights | null>(null);
  const toast = useUi((s) => s.showToast);
  const router = useRouter();
  const { data: me } = useMe();
  const qc = useQueryClient();

  useEffect(() => {
    const unwatch = socket.watchPost(post.id);
    const off = socket.on((event) => {
      if (event.type === "counter" && event.post_id === post.id) {
        if (event.field === "like_count") setLikes(event.value);
        if (event.field === "comment_count") setCommentCount(event.value);
        if (event.field === "view_count") setViews(event.value);
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

  const postUrl = () => `${location.origin}/p/${post.id}`;
  const copyLink = async () => {
    try {
      await navigator.clipboard.writeText(postUrl());
      toast("Link copied");
    } catch {
      toast("Could not copy the link");
    }
    setSharing(false);
  };
  const nativeShare = async () => {
    setSharing(false);
    try {
      await navigator.share({ url: postUrl(), title: "RedStarVibe" });
    } catch {} // the person closed the share sheet
  };

  // A view counts once the media has been on screen for a second, for photos and videos alike.
  useEffect(() => {
    const el = mediaRef.current;
    if (!el || post.status !== "published" || post.is_own) return;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const io = new IntersectionObserver(
      ([entry]) => {
        clearTimeout(timer);
        if (!entry?.isIntersecting) return;
        timer = setTimeout(() => {
          io.disconnect();
          api<{ view_count: number }>(`/posts/${post.id}/view`, { method: "POST" })
            .then((r) => setViews(r.view_count))
            .catch(() => undefined);
        }, VIEW_DWELL_MS);
      },
      { threshold: 0.5 },
    );
    io.observe(el);
    return () => {
      clearTimeout(timer);
      io.disconnect();
    };
  }, [post.id, post.status, post.is_own]);

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
          {post.author.verified && <BadgeCheck aria-label="Verified" className="ml-1 inline h-4 w-4 text-brand" />}
          {post.collaborator && (
            <>
              {" and "}
              <Link href={`/${post.collaborator.username}`} className="font-semibold">{post.collaborator.username}</Link>
            </>
          )}
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

      {post.is_capsule && post.status === "published" && (
        <p className="bg-surface px-3 py-1.5 text-xs text-muted">Time capsule, sealed on {new Date(post.created_at).toLocaleDateString()}</p>
      )}
      {post.status !== "published" && (
        <p className="bg-surface px-3 py-1.5 text-xs text-muted">
          {post.status === "processing" ? "Processing. It will go live shortly." : `Status: ${post.status}`}
        </p>
      )}
      <div ref={mediaRef}>
        <MediaCarousel media={post.media} priority={priority} />
      </div>

      <div className="flex items-center px-1 pt-1">
        <button aria-label={liked ? "Unlike" : "Like"} aria-pressed={liked} onClick={toggleLike} className="flex h-11 w-11 items-center justify-center">
          <Heart className={cn("h-6 w-6 transition-transform active:scale-125", liked && "fill-brand stroke-brand")} />
        </button>
        <button aria-label="Comments" onClick={() => setShowComments(true)} className="flex h-11 w-11 items-center justify-center">
          <MessageCircle className="h-6 w-6" />
        </button>
        <button aria-label="Share" onClick={() => setSharing(true)} className="flex h-11 w-11 items-center justify-center">
          <Send className="h-6 w-6" />
        </button>
        <button aria-label={saved ? "Remove from saved" : "Save"} aria-pressed={saved} onClick={toggleSave} className="ml-auto flex h-11 w-11 items-center justify-center">
          <Bookmark className={cn("h-6 w-6", saved && "fill-fg")} />
        </button>
      </div>
      <div className="space-y-1 px-3 pb-3 text-sm">
        <p className="font-semibold">
          {compactNumber(likes)} {likes === 1 ? "like" : "likes"}
          <span className="font-normal text-muted"> · {compactNumber(views)} {views === 1 ? "view" : "views"}</span>
        </p>
        {!!post.tagged?.length && (
          <p className="text-xs text-muted">
            With{" "}
            {post.tagged.map((u, i) => (
              <span key={u.id}>
                {i > 0 && ", "}
                <Link href={`/${u.username}`} className="font-semibold">{u.username}</Link>
              </span>
            ))}
          </p>
        )}
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
          <Comments postId={post.id} isPostOwner={post.is_own} />
        </div>
      )}

      {!standalone && (
        <Modal open={showComments} onClose={() => setShowComments(false)} title="Comments">
          {showComments && <Comments postId={post.id} isPostOwner={post.is_own} />}
        </Modal>
      )}
      <Modal open={sharing} onClose={() => setSharing(false)} title="Share post">
        <div className="space-y-1">
          {sharing && me && <ShareToChat postId={post.id} onDone={() => setSharing(false)} />}
          <button className="flex min-h-11 w-full items-center gap-2 rounded-lg px-3 hover:bg-surface" onClick={copyLink}>
            <Link2 className="h-4 w-4" /> Copy link
          </button>
          {sharing && (
            <a
              href={`https://wa.me/?text=${encodeURIComponent(postUrl())}`}
              target="_blank"
              rel="noopener noreferrer"
              onClick={() => setSharing(false)}
              className="flex min-h-11 items-center gap-2 rounded-lg px-3 hover:bg-surface"
            >
              <MessageCircle className="h-4 w-4" /> Share on WhatsApp
            </a>
          )}
          {sharing && "share" in navigator && (
            <button className="flex min-h-11 w-full items-center gap-2 rounded-lg px-3 hover:bg-surface" onClick={nativeShare}>
              <Send className="h-4 w-4" /> More options
            </button>
          )}
        </div>
      </Modal>
      <Modal open={menu} onClose={() => setMenu(false)} title="Post options">
        <div className="space-y-1">
          <Link href={`/p/${post.id}`} className="flex min-h-11 items-center rounded-lg px-3 hover:bg-surface">
            Go to post
          </Link>
          {post.is_own ? (
            <>
              {post.status === "published" && (
                <button
                  className="flex min-h-11 w-full items-center gap-2 rounded-lg px-3 hover:bg-surface"
                  onClick={async () => {
                    try {
                      await api(`/posts/${post.id}/pin`, { method: post.pinned ? "DELETE" : "POST" });
                      toast(post.pinned ? "Unpinned" : "Pinned to your profile");
                      setMenu(false);
                      qc.invalidateQueries({ queryKey: ["user-posts"] });
                      qc.invalidateQueries({ queryKey: ["post", post.id] });
                    } catch (e) {
                      toast(errorMessage(e));
                    }
                  }}
                >
                  <Pin className="h-4 w-4" /> {post.pinned ? "Unpin from profile" : "Pin to profile"}
                </button>
              )}
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
            <>
            {me && post.tagged?.some((u) => u.id === me.id) && (
              <button
                className="flex min-h-11 w-full items-center gap-2 rounded-lg px-3 hover:bg-surface"
                onClick={async () => {
                  await api(`/posts/${post.id}/tags/me`, { method: "DELETE" });
                  setMenu(false);
                  toast("Tag removed");
                }}
              >
                <UserX className="h-4 w-4" /> Remove my tag
              </button>
            )}
            <button
              className="flex min-h-11 w-full items-center gap-2 rounded-lg px-3 text-brand hover:bg-surface"
              onClick={() => {
                setMenu(false);
                setReport(true);
              }}
            >
              <Flag className="h-4 w-4" /> Report post
            </button>
            </>
          )}
        </div>
      </Modal>
      <ReportDialog open={report} onClose={() => setReport(false)} entityType="post" entityId={post.id} />
    </article>
  );
}
