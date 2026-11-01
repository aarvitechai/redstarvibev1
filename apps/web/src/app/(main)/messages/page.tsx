"use client";
import { useQuery } from "@tanstack/react-query";
import { Edit } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Avatar, CenterSpinner, Empty, Input, Modal, UserRow } from "@/components/ui";
import { useMe } from "@/hooks/useMe";
import { api } from "@/lib/api/client";
import type { Conversation, Me, SearchResults } from "@/lib/api/types";
import { cn, timeAgo } from "@/lib/utils";
import { useUi } from "@/stores/ui";

function conversationName(c: Conversation, me?: Me | null) {
  if (c.title) return c.title;
  return c.members.filter((m) => m.user.id !== me?.id).map((m) => m.user.username).join(", ") || "Just you";
}

function NewChat({ onClose }: { onClose: () => void }) {
  const [q, setQ] = useState("");
  const [debounced, setDebounced] = useState("");
  const router = useRouter();
  const toast = useUi((s) => s.showToast);
  useEffect(() => {
    const t = setTimeout(() => setDebounced(q.trim()), 250);
    return () => clearTimeout(t);
  }, [q]);
  const found = useQuery({ queryKey: ["search", debounced], enabled: !!debounced, queryFn: () => api<SearchResults>(`/search?q=${encodeURIComponent(debounced)}`) });
  return (
    <Modal open onClose={onClose} title="New message">
      <Input aria-label="Search people" placeholder="Search people" value={q} autoFocus onChange={(e) => setQ(e.target.value)} />
      {found.data?.users?.map((u) => (
        <button
          key={u.id}
          className="block w-full text-left"
          onClick={async () => {
            try {
              const c = await api<Conversation>("/conversations", { json: { usernames: [u.username] } });
              router.push(`/messages/${c.id}`);
            } catch (e) {
              toast((e as Error).message);
            }
          }}
        >
          <span className="pointer-events-none block"><UserRow user={u} /></span>
        </button>
      ))}
    </Modal>
  );
}

export default function MessagesPage() {
  const { data: me } = useMe();
  const [creating, setCreating] = useState(false);
  const q = useQuery({ queryKey: ["conversations"], queryFn: () => api<Conversation[]>("/conversations") });
  return (
    <div className="mx-auto max-w-xl p-3 sm:p-4">
      <div className="flex items-center justify-between pb-2">
        <h1 className="text-xl font-bold">Messages</h1>
        <button aria-label="New message" className="flex h-11 w-11 items-center justify-center" onClick={() => setCreating(true)}>
          <Edit className="h-5 w-5" />
        </button>
      </div>
      {q.isLoading ? (
        <CenterSpinner />
      ) : !q.data?.length ? (
        <Empty title="No messages yet" hint="Start a conversation with someone you follow." />
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
                    <span className={cn("block truncate text-sm", c.unread > 0 ? "font-semibold" : "text-muted")}>
                      {c.last_message ? c.last_message.body || "Sent an attachment" : "Say hello"}
                    </span>
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
