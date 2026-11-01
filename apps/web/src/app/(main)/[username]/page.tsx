"use client";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Ban, Flag, Grid3x3, Lock, MessageCircle, MoreHorizontal, Film } from "lucide-react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useState } from "react";
import { InfiniteGrid } from "@/components/post/InfiniteGrid";
import { ReportDialog } from "@/components/post/ReportDialog";
import { StoryViewer } from "@/components/story/StoryViewer";
import { Avatar, Button, CenterSpinner, Empty, Modal, UserRow } from "@/components/ui";
import { useInfinite } from "@/hooks/useInfinite";
import { api, ApiError, errorMessage } from "@/lib/api/client";
import type { Conversation, Highlight, Profile, Story, UserBrief } from "@/lib/api/types";
import { compactNumber, cn } from "@/lib/utils";
import { useUi } from "@/stores/ui";

function People({ username, kind, onClose }: { username: string; kind: "followers" | "following"; onClose: () => void }) {
  const q = useInfinite<UserBrief>([kind, username], `/users/${username}/${kind}`);
  return (
    <Modal open onClose={onClose} title={kind === "followers" ? "Followers" : "Following"}>
      {q.isLoading && <CenterSpinner />}
      {q.items.map((u) => <UserRow key={u.id} user={u} />)}
      {q.hasNextPage && <Button variant="ghost" className="w-full" onClick={() => q.fetchNextPage()}>Load more</Button>}
      {!q.isLoading && !q.items.length && <p className="text-sm text-muted">Nobody yet.</p>}
    </Modal>
  );
}

export default function ProfilePage() {
  const { username } = useParams<{ username: string }>();
  const qc = useQueryClient();
  const router = useRouter();
  const toast = useUi((s) => s.showToast);
  const [people, setPeople] = useState<"followers" | "following" | null>(null);
  const [tab, setTab] = useState<"posts" | "reels">("posts");
  const [menu, setMenu] = useState(false);
  const [report, setReport] = useState(false);
  const [stories, setStories] = useState<Story[] | null>(null);

  const profile = useQuery({ queryKey: ["profile", username], queryFn: () => api<Profile>(`/users/${username}`) });
  const p = profile.data;
  const highlights = useQuery({ queryKey: ["highlights", username], enabled: !!p?.can_view_posts, queryFn: () => api<Highlight[]>(`/users/${username}/highlights`) });

  const refresh = () => qc.invalidateQueries({ queryKey: ["profile", username] });
  const follow = useMutation({
    mutationFn: () => api(`/users/${username}/follow`, { method: p?.follow_status ? "DELETE" : "POST" }),
    onSuccess: refresh,
    onError: (e) => toast(errorMessage(e)),
  });

  if (profile.isLoading) return <CenterSpinner />;
  if (profile.isError) {
    const missing = profile.error instanceof ApiError && profile.error.status === 404;
    return <Empty title={missing ? "This account is not available" : "Could not load this profile"} action={<Link href="/feed" className="font-semibold text-brand">Back to feed</Link>} />;
  }
  if (!p) return null;

  const openStories = async () => {
    if (p.has_active_story) setStories(await api<Story[]>(`/users/${username}/stories`));
  };
  const message = async () => {
    try {
      const c = await api<Conversation>("/conversations", { json: { usernames: [username] } });
      router.push(`/messages/${c.id}`);
    } catch (e) {
      toast(errorMessage(e));
    }
  };

  return (
    <div className="mx-auto max-w-4xl sm:p-4">
      <header className="p-4">
        <div className="flex items-center gap-5 sm:gap-10">
          <button onClick={openStories} aria-label={p.has_active_story ? "View story" : "Profile picture"} className="rounded-full">
            <Avatar user={p} size={84} ring={p.has_active_story} />
          </button>
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2">
              <h1 className="truncate text-xl font-bold">{p.username}</h1>
              {!p.is_self && (
                <button aria-label="More options" onClick={() => setMenu(true)} className="flex h-11 w-11 items-center justify-center">
                  <MoreHorizontal className="h-5 w-5" />
                </button>
              )}
            </div>
            <dl className="mt-1 flex gap-4 text-sm sm:gap-8">
              <div><dd className="inline font-bold">{compactNumber(p.post_count)}</dd> <dt className="inline text-muted">posts</dt></div>
              <button className="min-h-8 text-left" onClick={() => p.can_view_posts && setPeople("followers")}><b>{compactNumber(p.follower_count)}</b> <span className="text-muted">followers</span></button>
              <button className="min-h-8 text-left" onClick={() => p.can_view_posts && setPeople("following")}><b>{compactNumber(p.following_count)}</b> <span className="text-muted">following</span></button>
            </dl>
          </div>
        </div>
        <div className="mt-3 text-sm">
          <p className="font-semibold">{p.display_name}</p>
          {p.bio && <p className="whitespace-pre-wrap break-words">{p.bio}</p>}
          {p.website && <a href={p.website} rel="noopener noreferrer nofollow ugc" target="_blank" className="break-all font-medium text-brand">{p.website.replace(/^https?:\/\//, "")}</a>}
        </div>
        <div className="mt-3 flex gap-2">
          {p.is_self ? (
            <Link href="/settings" className="flex min-h-11 flex-1 items-center justify-center rounded-lg bg-surface text-sm font-semibold hover:bg-line">Edit profile</Link>
          ) : p.is_blocked ? (
            <Button variant="secondary" className="flex-1" onClick={async () => { await api(`/users/${username}/block`, { method: "DELETE" }); refresh(); }}>Unblock</Button>
          ) : (
            <>
              <Button className="flex-1" variant={p.follow_status ? "secondary" : "primary"} loading={follow.isPending} onClick={() => follow.mutate()}>
                {p.follow_status === "active" ? "Following" : p.follow_status === "pending" ? "Requested" : p.follows_you ? "Follow back" : "Follow"}
              </Button>
              <Button variant="secondary" className="flex-1" onClick={message}>
                <MessageCircle className="h-4 w-4" /> Message
              </Button>
            </>
          )}
        </div>
        {!!highlights.data?.length && (
          <div className="no-scrollbar mt-4 flex gap-4 overflow-x-auto">
            {highlights.data.map((h) => (
              <button key={h.id} className="w-16 shrink-0 text-center" onClick={() => setStories(h.stories)}>
                <span className="mx-auto block h-14 w-14 overflow-hidden rounded-full border border-line bg-surface">
                  {h.cover?.images?.[0] && <img src={h.cover.images[0].webp} alt="" className="h-full w-full object-cover" />}
                </span>
                <span className="mt-1 block truncate text-xs">{h.title}</span>
              </button>
            ))}
          </div>
        )}
      </header>

      {p.can_view_posts ? (
        <>
          <div role="tablist" className="flex border-t border-line">
            {([["posts", Grid3x3, "Posts"], ["reels", Film, "Reels"]] as const).map(([value, Icon, label]) => (
              <button key={value} role="tab" aria-selected={tab === value} onClick={() => setTab(value)} className={cn("flex min-h-11 flex-1 items-center justify-center gap-2 text-sm font-semibold", tab === value ? "border-t-2 border-brand text-brand" : "text-muted")}>
                <Icon className="h-4 w-4" /> {label}
              </button>
            ))}
          </div>
          <InfiniteGrid key={tab} queryKey={["user-posts", username, tab]} path={`/users/${username}/posts${tab === "reels" ? "?reels=true" : ""}`} emptyTitle={tab === "reels" ? "No reels yet" : "No posts yet"} />
        </>
      ) : (
        <div className="border-t border-line">
          <Empty title="This account is private" hint="Follow this account to see their photos and videos." action={<Lock className="mx-auto h-8 w-8 text-muted" />} />
        </div>
      )}

      {people && <People username={username} kind={people} onClose={() => setPeople(null)} />}
      {stories && <StoryViewer stories={stories} ownerIsMe={p.is_self} onClose={() => setStories(null)} />}
      <Modal open={menu} onClose={() => setMenu(false)} title={p.username}>
        <button className="flex min-h-11 w-full items-center gap-2 rounded-lg px-3 text-brand hover:bg-surface" onClick={() => { setMenu(false); setReport(true); }}>
          <Flag className="h-4 w-4" /> Report account
        </button>
        <button
          className="flex min-h-11 w-full items-center gap-2 rounded-lg px-3 text-brand hover:bg-surface"
          onClick={async () => {
            await api(`/users/${username}/block`, { method: "POST" });
            setMenu(false);
            toast(`Blocked ${username}`);
            refresh();
            qc.invalidateQueries({ queryKey: ["feed"] });
          }}
        >
          <Ban className="h-4 w-4" /> Block
        </button>
      </Modal>
      <ReportDialog open={report} onClose={() => setReport(false)} entityType="user" entityId={p.id} />
    </div>
  );
}
