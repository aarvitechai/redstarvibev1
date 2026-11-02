"use client";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Flag, ImagePlus, Trash2 } from "lucide-react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useRef, useState } from "react";
import { MediaImage } from "@/components/post/MediaImage";
import { ReportDialog } from "@/components/post/ReportDialog";
import { Avatar, Button, CenterSpinner, Empty, ErrorNote, Modal, UserRow } from "@/components/ui";
import { useInfinite } from "@/hooks/useInfinite";
import { useMe } from "@/hooks/useMe";
import { api, errorMessage } from "@/lib/api/client";
import type { Community, CommunityPost, UserBrief } from "@/lib/api/types";
import { uploadAsset } from "@/lib/api/upload";
import { timeAgo } from "@/lib/utils";

export default function CommunityPage() {
  const { slug } = useParams<{ slug: string }>();
  const router = useRouter();
  const qc = useQueryClient();
  const { data: me } = useMe();
  const [body, setBody] = useState("");
  const [image, setImage] = useState<File | null>(null);
  const [showMembers, setShowMembers] = useState(false);
  const [report, setReport] = useState<string | null>(null);
  const file = useRef<HTMLInputElement>(null);
  const community = useQuery({ queryKey: ["community", slug], queryFn: () => api<Community>(`/communities/${slug}`) });
  const posts = useInfinite<CommunityPost>(["community-posts", slug], `/communities/${slug}/posts`);
  const members = useQuery({ queryKey: ["community-members", slug], enabled: showMembers, queryFn: () => api<UserBrief[]>(`/communities/${slug}/members`) });
  const refresh = () => {
    qc.invalidateQueries({ queryKey: ["community", slug] });
    qc.invalidateQueries({ queryKey: ["community-posts", slug] });
    qc.invalidateQueries({ queryKey: ["community-members", slug] });
  };
  const membership = useMutation({ mutationFn: (verb: "join" | "leave") => api(`/communities/${slug}/${verb}`, { method: "POST" }), onSuccess: refresh });
  const add = useMutation({
    mutationFn: async () => {
      const asset = image ? await uploadAsset(image, "post") : null;
      await api(`/communities/${slug}/posts`, { json: { body, asset_id: asset?.id ?? null } });
    },
    onSuccess: () => {
      setBody("");
      setImage(null);
      refresh();
    },
  });
  if (community.isError) return <Empty title="This community is not available" action={<Link href="/communities" className="font-semibold text-brand">All communities</Link>} />;
  if (!community.data) return <CenterSpinner />;
  const c = community.data;
  const error = membership.error ?? add.error;
  return (
    <div className="mx-auto max-w-xl space-y-4 p-3 sm:p-4">
      <header>
        <h1 className="text-xl font-bold">{c.name}</h1>
        {c.description && <p className="mt-1 whitespace-pre-wrap break-words text-sm">{c.description}</p>}
        <button className="min-h-8 text-sm text-muted" onClick={() => setShowMembers(true)}>{c.member_count} {c.member_count === 1 ? "member" : "members"}</button>
        <div className="mt-2 flex gap-2">
          {!c.is_member ? <Button loading={membership.isPending} onClick={() => membership.mutate("join")}>Join</Button> : !c.is_owner ? <Button variant="secondary" loading={membership.isPending} onClick={() => membership.mutate("leave")}>Leave</Button> : (
            <Button variant="danger" onClick={async () => { await api(`/communities/${slug}`, { method: "DELETE" }); router.replace("/communities"); }}>Delete community</Button>
          )}
        </div>
      </header>
      <ErrorNote message={error ? errorMessage(error) : null} />
      {c.is_member && (
        <form className="space-y-2 rounded-lg border border-line p-3" onSubmit={(e) => { e.preventDefault(); if (body.trim() || image) add.mutate(); }}>
          <textarea aria-label="Write a post" placeholder="Share something with this community" value={body} maxLength={4000} rows={3} onChange={(e) => setBody(e.target.value)} className="w-full rounded-lg border border-line bg-surface p-3 text-[16px] focus:border-brand focus:outline-none sm:text-sm" />
          <div className="flex items-center gap-2">
            <button type="button" aria-label="Add a photo" className="flex h-11 w-11 items-center justify-center" onClick={() => file.current?.click()}><ImagePlus className="h-5 w-5" /></button>
            <input ref={file} type="file" hidden accept="image/jpeg,image/png,image/webp" onChange={(e) => { setImage(e.target.files?.[0] ?? null); e.target.value = ""; }} />
            {image && <span className="min-w-0 flex-1 truncate text-xs text-muted">{image.name}</span>}
            <Button type="submit" className="ml-auto" disabled={!body.trim() && !image} loading={add.isPending}>Post</Button>
          </div>
        </form>
      )}
      {posts.isLoading ? <CenterSpinner /> : !posts.items.length ? <Empty title="No posts yet" hint={c.is_member ? "Be the first to post." : "Join to start the conversation."} /> : (
        <ul className="space-y-2">
          {posts.items.map((p) => (
            <li key={p.id} data-testid="community-post" className="rounded-lg border border-line p-3 text-sm">
              <div className="flex items-center gap-2">
                <Link href={`/${p.author.username}`} className="flex min-w-0 flex-1 items-center gap-2">
                  <Avatar user={p.author} size={32} />
                  <span className="truncate font-semibold">{p.author.username}</span>
                </Link>
                <span className="text-xs text-muted">{timeAgo(p.created_at)}</span>
                {me && p.author.id !== me.id && (
                  <button aria-label="Report post" className="flex h-11 w-11 items-center justify-center" onClick={() => setReport(p.id)}><Flag className="h-4 w-4" /></button>
                )}
                {p.can_delete && (
                  <button aria-label="Delete post" className="flex h-11 w-11 items-center justify-center" onClick={async () => { await api(`/community-posts/${p.id}`, { method: "DELETE" }); refresh(); }}><Trash2 className="h-4 w-4" /></button>
                )}
              </div>
              {p.body && <p className="mt-2 whitespace-pre-wrap break-words">{p.body}</p>}
              {p.media && <div className="mt-2 overflow-hidden rounded-lg"><MediaImage asset={p.media} sizes="(max-width: 640px) 100vw, 560px" className="w-full" /></div>}
            </li>
          ))}
        </ul>
      )}
      {posts.hasNextPage && <Button variant="ghost" className="w-full" onClick={() => posts.fetchNextPage()}>Load more</Button>}
      <Modal open={showMembers} onClose={() => setShowMembers(false)} title="Members">
        {members.data?.map((u) => (
          <UserRow key={u.id} user={u} action={c.is_owner && u.id !== me?.id ? <Button variant="secondary" onClick={async () => { await api(`/communities/${slug}/members/${u.id}`, { method: "DELETE" }); refresh(); }}>Remove</Button> : undefined} />
        ))}
      </Modal>
      <ReportDialog open={!!report} onClose={() => setReport(null)} entityType="community" entityId={report ?? ""} />
    </div>
  );
}
