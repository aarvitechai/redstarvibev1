"use client";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Trash2 } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { Avatar, Button, CenterSpinner, ErrorNote, Input } from "@/components/ui";
import { useInfinite } from "@/hooks/useInfinite";
import { api, errorMessage } from "@/lib/api/client";
import type { Comment } from "@/lib/api/types";
import { timeAgo } from "@/lib/utils";
import { Caption } from "./Caption";

function CommentItem({ comment, postId, isPostOwner, onReply }: { comment: Comment; postId: string; isPostOwner?: boolean; onReply: (c: Comment) => void }) {
  const qc = useQueryClient();
  const [showReplies, setShowReplies] = useState(false);
  const replies = useInfinite<Comment>(["comments", postId, comment.id], `/posts/${postId}/comments?parent_id=${comment.id}`, showReplies);
  return (
    <li className="flex gap-3 py-2">
      <Link href={`/${comment.author.username}`} aria-label={comment.author.username}>
        <Avatar user={comment.author} size={34} />
      </Link>
      <div className="min-w-0 flex-1 text-sm">
        <p className="break-words">
          <Link href={`/${comment.author.username}`} className="font-semibold">
            {comment.author.username}
          </Link>{" "}
          <Caption text={comment.body} />
        </p>
        <div className="mt-0.5 flex items-center gap-3 text-xs text-muted">
          <span>{timeAgo(comment.created_at)}</span>
          {comment.held && <span className="font-semibold text-brand">Hidden from others</span>}
          {comment.held && isPostOwner && (
            <button
              className="min-h-8 font-semibold"
              onClick={async () => {
                await api(`/comments/${comment.id}/approve`, { method: "POST" });
                qc.invalidateQueries({ queryKey: ["comments", postId] });
              }}
            >
              Show to everyone
            </button>
          )}
          <button className="min-h-8 font-semibold" onClick={() => onReply(comment)}>
            Reply
          </button>
          {comment.can_delete && (
            <button
              aria-label="Delete comment"
              className="flex h-8 w-8 items-center justify-center"
              onClick={async () => {
                await api(`/comments/${comment.id}`, { method: "DELETE" });
                qc.invalidateQueries({ queryKey: ["comments", postId] });
              }}
            >
              <Trash2 className="h-3.5 w-3.5" />
            </button>
          )}
        </div>
        {comment.reply_count > 0 && !showReplies && (
          <button className="min-h-8 text-xs font-semibold text-muted" onClick={() => setShowReplies(true)}>
            View {comment.reply_count} {comment.reply_count === 1 ? "reply" : "replies"}
          </button>
        )}
        {showReplies && (
          <ul>
            {[...replies.items].reverse().map((r) => (
              <CommentItem key={r.id} comment={r} postId={postId} isPostOwner={isPostOwner} onReply={onReply} />
            ))}
          </ul>
        )}
      </div>
    </li>
  );
}

export function Comments({ postId, isPostOwner }: { postId: string; isPostOwner?: boolean }) {
  const qc = useQueryClient();
  const list = useInfinite<Comment>(["comments", postId], `/posts/${postId}/comments`);
  const [body, setBody] = useState("");
  const [replyTo, setReplyTo] = useState<Comment | null>(null);
  const send = useMutation({
    mutationFn: () => api<Comment>(`/posts/${postId}/comments`, { json: { body, parent_id: replyTo?.id ?? null } }),
    onSuccess: () => {
      setBody("");
      setReplyTo(null);
      qc.invalidateQueries({ queryKey: ["comments", postId] });
    },
  });
  return (
    <div>
      {list.isLoading ? (
        <CenterSpinner />
      ) : list.items.length === 0 ? (
        <p className="py-6 text-center text-sm text-muted">No comments yet. Be the first.</p>
      ) : (
        <ul className="divide-y divide-transparent">
          {list.items.map((c) => (
            <CommentItem key={c.id} comment={c} postId={postId} isPostOwner={isPostOwner} onReply={setReplyTo} />
          ))}
        </ul>
      )}
      {list.hasNextPage && (
        <Button variant="ghost" className="w-full" onClick={() => list.fetchNextPage()}>
          Load more comments
        </Button>
      )}
      <ErrorNote message={send.error ? errorMessage(send.error) : null} />
      {replyTo && (
        <p className="pt-2 text-xs text-muted">
          Replying to @{replyTo.author.username}{" "}
          <button className="min-h-8 font-semibold" onClick={() => setReplyTo(null)}>
            Cancel
          </button>
        </p>
      )}
      <form
        className="flex gap-2 pt-2"
        onSubmit={(e) => {
          e.preventDefault();
          if (body.trim()) send.mutate();
        }}
      >
        <Input aria-label="Add a comment" placeholder="Add a comment" value={body} maxLength={2200} onChange={(e) => setBody(e.target.value)} />
        <Button type="submit" loading={send.isPending} disabled={!body.trim()}>
          Post
        </Button>
      </form>
    </div>
  );
}
