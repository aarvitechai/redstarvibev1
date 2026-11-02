"use client";
import { useQuery } from "@tanstack/react-query";
import { Edit, X } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Avatar, Button, CenterSpinner, Empty, ErrorNote, Field, Input, Modal, UserRow } from "@/components/ui";
import { useMe } from "@/hooks/useMe";
import { api, errorMessage } from "@/lib/api/client";
import type { Conversation, Me, Page, UserBrief } from "@/lib/api/types";
import { cn, timeAgo } from "@/lib/utils";

function conversationName(c: Conversation, me?: Me | null) {
  if (c.title) return c.title;
  return c.members.filter((m) => m.user.id !== me?.id).map((m) => m.user.username).join(", ") || "Just you";
}

function lastLine(c: Conversation) {
  const m = c.last_message;
  if (!m) return "Say hello";
  if (m.body) return m.body;
  if (m.media?.kind === "audio") return "Voice note";
  if (m.post_id) return "Shared a post";
  return "Sent an attachment";
}

function NewChat({ onClose }: { onClose: () => void }) {
  const [q, setQ] = useState("");
  const [debounced, setDebounced] = useState("");
  const [picked, setPicked] = useState<UserBrief[]>([]);
  const [title, setTitle] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const router = useRouter();
  useEffect(() => {
    const t = setTimeout(() => setDebounced(q.trim()), 250);
    return () => clearTimeout(t);
  }, [q]);
  const found = useQuery({ queryKey: ["search", debounced], enabled: !!debounced, queryFn: () => api<Page<UserBrief>>(`/search?q=${encodeURIComponent(debounced)}&type=users`) });
  const start = async () => {
    setBusy(true);
    setError(null);
    try {
      const c = await api<Conversation>("/conversations", { json: { usernames: picked.map((u) => u.username), title: picked.length > 1 ? title.trim() || null : null } });
      router.push(`/messages/${c.id}`);
    } catch (e) {
      setError(errorMessage(e));
      setBusy(false);
    }
  };
  return (
    <Modal open onClose={onClose} title="New message">
      <div className="space-y-2">
        {picked.length > 0 && (
          <ul className="flex flex-wrap gap-1">
            {picked.map((u) => (
              <li key={u.id} className="flex items-center gap-1 rounded-full bg-surface pl-3 text-sm">
                {u.username}
                <button aria-label={`Remove ${u.username}`} className="flex h-9 w-9 items-center justify-center" onClick={() => setPicked(picked.filter((x) => x.id !== u.id))}><X className="h-4 w-4" /></button>
              </li>
            ))}
          </ul>
        )}
        <Input aria-label="Search people" placeholder="Search people" value={q} autoFocus onChange={(e) => setQ(e.target.value)} />
        {found.data?.items.filter((u) => !picked.some((p) => p.id === u.id)).map((u) => (
          <button key={u.id} className="block w-full text-left" onClick={() => { setPicked([...picked, u]); setQ(""); }}>
            <span className="pointer-events-none block"><UserRow user={u} /></span>
          </button>
        ))}
        {picked.length > 1 && <Field label="Group name (optional)"><Input value={title} maxLength={80} onChange={(e) => setTitle(e.target.value)} /></Field>}
        <ErrorNote message={error} />
        <Button className="w-full" disabled={!picked.length} loading={busy} onClick={start}>{picked.length > 1 ? "Create group" : "Chat"}</Button>
      </div>
    </Modal>
  );
}

export default function MessagesPage() {
  const { data: me } = useMe();
  const [creating, setCreating] = useState(false);
  const [folder, setFolder] = useState<"inbox" | "requests">("inbox");
  const inbox = useQuery({ queryKey: ["conversations"], queryFn: () => api<Conversation[]>("/conversations") });
  const requests = useQuery({ queryKey: ["conversations", "requests"], queryFn: () => api<Conversation[]>("/conversations?folder=requests") });
  const q = folder === "inbox" ? inbox : requests;
  return (
    <div className="mx-auto max-w-xl p-3 sm:p-4">
      <div className="flex items-center justify-between pb-2">
        <h1 className="text-xl font-bold">Messages</h1>
        <button aria-label="New message" className="flex h-11 w-11 items-center justify-center" onClick={() => setCreating(true)}>
          <Edit className="h-5 w-5" />
        </button>
      </div>
      <div role="tablist" className="mb-2 grid grid-cols-2 gap-1">
        {(["inbox", "requests"] as const).map((value) => (
          <button key={value} role="tab" aria-selected={folder === value} onClick={() => setFolder(value)} className={cn("min-h-11 rounded-lg text-sm font-semibold capitalize", folder === value ? "bg-fg text-bg" : "bg-surface")}>
            {value}{value === "requests" && requests.data?.length ? ` (${requests.data.length})` : ""}
          </button>
        ))}
      </div>
      {q.isLoading ? (
        <CenterSpinner />
      ) : !q.data?.length ? (
        <Empty title={folder === "inbox" ? "No messages yet" : "No message requests"} hint={folder === "inbox" ? "Start a conversation with someone you follow." : "Messages from people you do not follow appear here."} />
      ) : (
        <ul>
          {q.data.map((c) => {
            const other = c.members.find((m) => m.user.id !== me?.id);
            return (
              <li key={c.id}>
                <Link href={`/messages/${c.id}`} className="flex min-h-16 items-center gap-3 rounded-lg px-2 hover:bg-surface">
                  <span className="relative">
                    <Avatar user={other?.user} size={50} />
                    {other?.online && <span className="absolute bottom-0 right-0 h-3 w-3 rounded-full border-2 border-bg bg-green-500" />}
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className={cn("block truncate text-sm", c.unread > 0 ? "font-bold" : "font-medium")}>{conversationName(c, me)}</span>
                    <span className={cn("block truncate text-sm", c.unread > 0 ? "font-semibold" : "text-muted")}>{lastLine(c)}</span>
                  </span>
                  <span className="text-xs text-muted">{timeAgo(c.last_message_at)}</span>
                  {c.unread > 0 && <span className="h-2.5 w-2.5 rounded-full bg-brand" aria-label={`${c.unread} unread`} />}
                </Link>
              </li>
            );
          })}
        </ul>
      )}
      {creating && <NewChat onClose={() => setCreating(false)} />}
    </div>
  );
}
