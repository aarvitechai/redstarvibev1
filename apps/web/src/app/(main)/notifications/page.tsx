"use client";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useEffect } from "react";
import { Avatar, Button, CenterSpinner, Empty, UserRow } from "@/components/ui";
import { useInfinite, useSentinel } from "@/hooks/useInfinite";
import { api } from "@/lib/api/client";
import type { Notification, Post, UserBrief } from "@/lib/api/types";
import { cn, timeAgo } from "@/lib/utils";

const TEXT: Record<string, string> = {
  like: "liked your post",
  comment: "commented on your post",
  mention: "mentioned you",
  story_reaction: "reacted to your story",
  collab_invite: "invited you to a collab post",
  collab_accepted: "joined your post as a collaborator",
  ticket_reply: "Support replied to your ticket.",
  ticket_resolved: "Your support ticket was resolved.",
  verification_approved: "Your account is now verified.",
  verification_rejected: "Your verification request was not approved.",
  ad_approved: "Your ad request was approved.",
  ad_rejected: "Your ad request was not approved.",
  business_staff_added: "added you as business staff",
  tagged: "tagged you in a post",
  follow: "started following you",
  follow_request: "asked to follow you",
  follow_accepted: "accepted your follow request",
  new_post: "shared a new post",
  message: "sent you a message",
  message_request: "wants to send you a message",
  live: "started a live video",
  post_failed: "Your post could not be published.",
  post_published: "Your post is live.",
};

function hrefFor(n: Notification): string {
  if (["like", "comment", "mention", "tagged", "new_post", "post_published", "collab_invite", "collab_accepted"].includes(n.type) && n.entity_id) return `/p/${n.entity_id}`;
  if ((n.type === "message" || n.type === "message_request") && n.entity_id) return `/messages/${n.entity_id}`;
  if (n.type === "live") return "/live";
  if (n.type === "post_failed") return "/new";
  if (n.type.startsWith("ticket_")) return "/support";
  if (n.type.startsWith("verification_")) return "/support";
  if (n.type.startsWith("ad_")) return "/business-tools";
  return n.actor ? `/${n.actor.username}` : "/feed";
}

export default function NotificationsPage() {
  const qc = useQueryClient();
  const q = useInfinite<Notification>(["notifications"], "/notifications");
  const sentinel = useSentinel(() => q.fetchNextPage(), !!q.hasNextPage && !q.isFetchingNextPage);
  const requests = useQuery({ queryKey: ["follow-requests"], queryFn: () => api<UserBrief[]>("/follow-requests") });

  useEffect(() => {
    api("/notifications/read", { method: "POST" })
      .then(() => qc.setQueryData(["unread"], { count: 0 }))
      .catch(() => undefined);
  }, [qc]);

  const collabs = useQuery({ queryKey: ["collab-requests"], queryFn: () => api<Post[]>("/collab-requests") });
  const answerCollab = async (id: string, accept: boolean) => {
    await api(`/posts/${id}/collab/${accept ? "accept" : "me"}`, { method: accept ? "POST" : "DELETE" });
    qc.invalidateQueries({ queryKey: ["collab-requests"] });
  };
  const answer = async (id: string, verb: "accept" | "reject") => {
    await api(`/follow-requests/${id}/${verb}`, { method: "POST" });
    qc.invalidateQueries({ queryKey: ["follow-requests"] });
  };
  return (
    <div className="mx-auto max-w-xl p-3 sm:p-4">
      <h1 className="pb-2 text-xl font-bold">Notifications</h1>
      {!!requests.data?.length && (
        <section className="mb-4 border-b border-line pb-3">
          <h2 className="text-sm font-semibold text-muted">Follow requests</h2>
          {requests.data.map((u) => (
            <UserRow
              key={u.id}
              user={u}
              action={
                <div className="flex gap-1">
                  <Button onClick={() => answer(u.id, "accept")}>Accept</Button>
                  <Button variant="secondary" onClick={() => answer(u.id, "reject")}>Delete</Button>
                </div>
              }
            />
          ))}
        </section>
      )}
      {!!collabs.data?.length && (
        <section className="mb-4 border-b border-line pb-3">
          <h2 className="text-sm font-semibold text-muted">Collab invites</h2>
          {collabs.data.map((p) => (
            <div key={p.id} className="flex items-center gap-2 py-2 text-sm">
              <Link href={`/p/${p.id}`} className="min-w-0 flex-1 truncate"><b>{p.author.username}</b> {p.caption || "shared a post"}</Link>
              <Button onClick={() => answerCollab(p.id, true)}>Accept</Button>
              <Button variant="secondary" onClick={() => answerCollab(p.id, false)}>Decline</Button>
            </div>
          ))}
        </section>
      )}
      {q.isLoading ? (
        <CenterSpinner />
      ) : q.items.length === 0 ? (
        <Empty title="No notifications yet" hint="Likes, comments and follows will appear here." />
      ) : (
        <ul>
          {q.items.map((n) => (
            <li key={n.id}>
              <Link href={hrefFor(n)} className={cn("flex min-h-14 items-center gap-3 rounded-lg px-2 py-2 hover:bg-surface", !n.read && "bg-brand/5")}>
                {n.actor ? <Avatar user={n.actor} size={44} /> : <img src="/brand/logo.png" alt="" width={44} height={44} />}
                <span className="min-w-0 flex-1 text-sm">
                  {n.actor && <b>{n.actor.username} </b>}
                  {TEXT[n.type] ?? "New activity"} <span className="text-muted">{timeAgo(n.created_at)}</span>
                </span>
              </Link>
            </li>
          ))}
        </ul>
      )}
      <div ref={sentinel} />
    </div>
  );
}
