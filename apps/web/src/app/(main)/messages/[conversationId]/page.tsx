"use client";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, ImagePlus, Phone, Send, Video } from "lucide-react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { MediaImage } from "@/components/post/MediaImage";
import { VideoPlayer } from "@/components/post/VideoPlayer";
import { Avatar, Button, CenterSpinner, Empty, Input } from "@/components/ui";
import { useInfinite } from "@/hooks/useInfinite";
import { useMe } from "@/hooks/useMe";
import { api, errorMessage } from "@/lib/api/client";
import type { CallJoin, Conversation, Message } from "@/lib/api/types";
import { uploadAsset } from "@/lib/api/upload";
import { cn } from "@/lib/utils";
import { socket } from "@/lib/ws/client";
import { useUi } from "@/stores/ui";

export default function ThreadPage() {
  const { conversationId: id } = useParams<{ conversationId: string }>();
  const { data: me } = useMe();
  const qc = useQueryClient();
  const router = useRouter();
  const toast = useUi((s) => s.showToast);
  const typingAt = useUi((s) => s.typing[id] ?? 0);
  const [body, setBody] = useState("");
  const [isTyping, setIsTyping] = useState(false);
  const [uploading, setUploading] = useState(false);
  const bottom = useRef<HTMLDivElement>(null);
  const file = useRef<HTMLInputElement>(null);
  const lastTyping = useRef(0);

  const conversation = useQuery({ queryKey: ["conversation", id], queryFn: () => api<Conversation>(`/conversations/${id}`) });
  const list = useInfinite<Message>(["messages", id], `/conversations/${id}/messages`);
  const messages = [...list.items].reverse();
  const lastId = messages[messages.length - 1]?.id;

  useLayoutEffect(() => {
    bottom.current?.scrollIntoView();
  }, [lastId]);

  useEffect(() => {
    if (!lastId) return;
    api(`/conversations/${id}/seen`, { method: "POST" })
      .then(() => qc.invalidateQueries({ queryKey: ["conversations"] }))
      .catch(() => undefined);
    socket.send({ type: "delivered", conversation_id: id });
  }, [id, lastId, qc]);

  useEffect(() => {
    if (!typingAt) return;
    setIsTyping(true);
    const t = setTimeout(() => setIsTyping(false), 3000);
    return () => clearTimeout(t);
  }, [typingAt]);

  const send = useMutation({
    mutationFn: (payload: { body: string; asset_id?: string }) => api<Message>(`/conversations/${id}/messages`, { json: payload }),
    onSuccess: () => {
      setBody("");
      qc.invalidateQueries({ queryKey: ["messages", id] });
    },
    onError: (e) => toast(errorMessage(e)),
  });

  const call = async (kind: "audio" | "video") => {
    try {
      const join = await api<CallJoin>("/calls", { json: { conversation_id: id, kind } });
      router.push(`/call/${join.room}`);
    } catch (e) {
      toast(errorMessage(e));
    }
  };

  const others = conversation.data?.members.filter((m) => m.user.id !== me?.id) ?? [];
  const title = conversation.data?.title || others.map((m) => m.user.username).join(", ");
  const lastMine = [...messages].reverse().find((m) => m.sender_id === me?.id);
  const receipt = (() => {
    if (!lastMine || lastMine.id !== lastId) return null;
    const at = new Date(lastMine.created_at).getTime();
    const after = (v?: string | null) => !!v && new Date(v).getTime() >= at;
    if (others.some((o) => after(o.last_seen_at))) return "Seen";
    if (others.some((o) => after(o.last_delivered_at))) return "Delivered";
    return "Sent";
  })();

  if (conversation.isError) return <Empty title="Conversation not found" action={<Link href="/messages" className="font-semibold text-brand">Back to messages</Link>} />;

  return (
    <div className="mx-auto flex h-[calc(100dvh-7rem)] max-w-2xl flex-col sm:h-dvh">
      <header className="flex items-center gap-2 border-b border-line px-1 py-1">
        <Link href="/messages" aria-label="Back" className="flex h-11 w-11 items-center justify-center"><ArrowLeft className="h-5 w-5" /></Link>
        <Avatar user={others[0]?.user} size={36} />
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-semibold">{title}</p>
          <p className="text-xs text-muted">{isTyping ? "typing..." : others[0]?.online ? "Online" : ""}</p>
        </div>
        <button aria-label="Audio call" onClick={() => call("audio")} className="flex h-11 w-11 items-center justify-center"><Phone className="h-5 w-5" /></button>
        <button aria-label="Video call" onClick={() => call("video")} className="flex h-11 w-11 items-center justify-center"><Video className="h-5 w-5" /></button>
      </header>
      <div className="flex-1 space-y-1 overflow-y-auto p-3">
        {list.hasNextPage && <Button variant="ghost" className="w-full" onClick={() => list.fetchNextPage()}>Load earlier messages</Button>}
        {list.isLoading && <CenterSpinner />}
        {messages.map((m) => {
          const mine = m.sender_id === me?.id;
          return (
            <div key={m.id} className={cn("flex", mine ? "justify-end" : "justify-start")}>
              <div className={cn("max-w-[78%] overflow-hidden rounded-2xl text-sm", mine ? "bg-brand text-white" : "bg-surface")}>
                {m.media && (m.media.kind === "video" ? <div className="aspect-video w-64"><VideoPlayer asset={m.media} className="h-full w-full" /></div> : <MediaImage asset={m.media} sizes="256px" className="max-h-72 w-full object-cover" />)}
                {m.body && <p className="whitespace-pre-wrap break-words px-3 py-2">{m.body}</p>}
              </div>
            </div>
          );
        })}
        {receipt && <p className="pr-1 text-right text-xs text-muted">{receipt}</p>}
        <div ref={bottom} />
      </div>
      <form
        className="pb-safe flex items-center gap-1 border-t border-line p-2"
        onSubmit={(e) => {
          e.preventDefault();
          if (body.trim()) send.mutate({ body });
        }}
      >
        <button type="button" aria-label="Attach a photo or video" disabled={uploading} onClick={() => file.current?.click()} className="flex h-11 w-11 shrink-0 items-center justify-center">
          <ImagePlus className={cn("h-5 w-5", uploading && "animate-pulse text-brand")} />
        </button>
        <input
          ref={file}
          type="file"
          hidden
          accept="image/*,video/*"
          onChange={async (e) => {
            const f = e.target.files?.[0];
            e.target.value = "";
            if (!f) return;
            setUploading(true);
            try {
              const asset = await uploadAsset(f, "message");
              send.mutate({ body: "", asset_id: asset.id });
            } catch (err) {
              toast(errorMessage(err));
            } finally {
              setUploading(false);
            }
          }}
        />
        <Input
          aria-label="Message"
          placeholder="Message"
          value={body}
          onChange={(e) => {
            setBody(e.target.value);
            if (Date.now() - lastTyping.current > 2000) {
              lastTyping.current = Date.now();
              socket.send({ type: "typing", conversation_id: id });
            }
          }}
        />
        <button type="submit" aria-label="Send" disabled={!body.trim() || send.isPending} className="flex h-11 w-11 shrink-0 items-center justify-center text-brand disabled:opacity-40">
          <Send className="h-5 w-5" />
        </button>
      </form>
    </div>
  );
}
