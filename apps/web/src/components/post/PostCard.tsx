"use client";
import { BadgeCheck, Bookmark, Heart, MessageCircle, MoreHorizontal, Send } from "lucide-react";
import Link from "next/link";
import { useEffect, useRef, useState, type MouseEvent } from "react";
import { Avatar, Modal } from "@/components/ui";
import { api, errorMessage } from "@/lib/api/client";
import type { Post } from "@/lib/api/types";
import { compactNumber, cn, timeAgo } from "@/lib/utils";
import { socket } from "@/lib/ws/client";
import { useUi } from "@/stores/ui";
import { Caption } from "./Caption";
import { Comments } from "./Comments";
import { MediaCarousel } from "./MediaCarousel";
import { PostMusic } from "./Music";
import { PostMenu } from "./PostMenu";
import { ReportDialog } from "./ReportDialog";
import { ShareDialog } from "./ShareDialog";

const VIEW_DWELL_MS = 1000;
const DOUBLE_TAP_MS = 300;
const HEART_MS = 700;
const LONG_CAPTION = 140;
const ACTION = "flex h-11 w-11 items-center justify-center";
const ACTION_ICON = "h-5 w-5";

export function PostCard({ post, priority, standalone, onRemoved }: { post: Post; priority?: boolean; standalone?: boolean; onRemoved?: () => void }) {
  const [liked, setLiked] = useState(post.liked);
  const [likes, setLikes] = useState(post.like_count);
  const [commentCount, setCommentCount] = useState(post.comment_count);
  const [views, setViews] = useState(post.view_count);
  const [saved, setSaved] = useState(post.saved);
  const [caption, setCaption] = useState(post.caption);
  const [expanded, setExpanded] = useState(false);
  const [heart, setHeart] = useState(false);
  const [showComments, setShowComments] = useState(false);
  const [menu, setMenu] = useState(false);
  const [sharing, setSharing] = useState(false);
  const [report, setReport] = useState(false);
  const mediaRef = useRef<HTMLDivElement>(null);
  const lastTap = useRef(0);
  const toast = useUi((s) => s.showToast);

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

  const setLike = async (next: boolean) => {
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

  // Double tap likes and never unlikes. Real controls keep working, while the video surface still counts as media.
  const onMediaClick = (e: MouseEvent<HTMLDivElement>) => {
    if ((e.target as HTMLElement).closest("button:not([data-surface]), a, input")) return;
    const now = e.timeStamp;
    if (now - lastTap.current > DOUBLE_TAP_MS) {
      lastTap.current = now;
      return;
    }
    lastTap.current = 0;
    setHeart(true);
    setTimeout(() => setHeart(false), HEART_MS);
    if (!liked) void setLike(true);
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

  const clamped = !standalone && !expanded && caption.length > LONG_CAPTION;

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
          {post.author.verified && <BadgeCheck aria-label="Verified" className="ml-1 inline h-3.5 w-3.5 text-brand" />}
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
        <button aria-label="More options" onClick={() => setMenu(true)} className={cn(ACTION, "rounded-full hover:bg-surface")}>
          <MoreHorizontal className={ACTION_ICON} />
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
      <div ref={mediaRef} onClick={onMediaClick} className="relative">
        <MediaCarousel media={post.media} priority={priority} silent={!!post.music} />
        {post.music && <PostMusic track={post.music} className="left-1 top-0" />}
        {heart && (
          <span data-testid="double-tap-heart" className="pointer-events-none absolute inset-0 flex items-center justify-center">
            <Heart aria-hidden className="h-16 w-16 animate-ping fill-white stroke-white opacity-80" />
          </span>
        )}
      </div>

      <div className="flex items-center px-1 pt-1">
        <button aria-label={liked ? "Unlike" : "Like"} aria-pressed={liked} onClick={() => setLike(!liked)} className={ACTION}>
          <Heart className={cn(ACTION_ICON, "transition-transform active:scale-125", liked && "fill-brand stroke-brand")} />
        </button>
        <button aria-label="Comments" onClick={() => setShowComments(true)} className={ACTION}>
          <MessageCircle className={ACTION_ICON} />
        </button>
        <button aria-label="Share" onClick={() => setSharing(true)} className={ACTION}>
          <Send className={ACTION_ICON} />
        </button>
        <button aria-label={saved ? "Remove from saved" : "Save"} aria-pressed={saved} onClick={toggleSave} className={cn(ACTION, "ml-auto")}>
          <Bookmark className={cn(ACTION_ICON, saved && "fill-fg")} />
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
        {caption && (
          <>
            <p className={cn("whitespace-pre-wrap break-words", clamped && "line-clamp-2")}>
              <Link href={`/${post.author.username}`} className="font-semibold">
                {post.author.username}
              </Link>{" "}
              <Caption text={caption} />
            </p>
            {clamped && <button className="min-h-8 text-muted" onClick={() => setExpanded(true)}>more</button>}
          </>
        )}
        {!standalone && (
          <button className="block min-h-8 text-muted" onClick={() => setShowComments(true)}>
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
      <ShareDialog postId={post.id} open={sharing} onClose={() => setSharing(false)} />
      <PostMenu
        post={post}
        caption={caption}
        open={menu}
        standalone={standalone}
        onClose={() => setMenu(false)}
        onCaption={setCaption}
        onReport={() => setReport(true)}
        onRemoved={onRemoved}
      />
      <ReportDialog open={report} onClose={() => setReport(false)} entityType="post" entityId={post.id} />
    </article>
  );
}
