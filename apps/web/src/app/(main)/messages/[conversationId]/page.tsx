"use client";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, ImagePlus, Languages, Phone, Send, Settings2, Video } from "lucide-react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { GroupSettings } from "@/components/chat/GroupSettings";
import { VoiceRecorder } from "@/components/chat/VoiceRecorder";
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

const LANGUAGES = [["en", "English"], ["hi", "Hindi"], ["bn", "Bengali"], ["ta", "Tamil"], ["te", "Telugu"], ["mr", "Marathi"], ["gu", "Gujarati"], ["kn", "Kannada"], ["ml", "Malayalam"], ["pa", "Punjabi"], ["ur", "Urdu"]] as const;

function Translate({ conversationId, messageId, language }: { conversationId: string; messageId: string; language: string }) {
  const toast = useUi((s) => s.showToast);
  const [text, setText] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => setText(null), [language]);
  if (text) return <p className="border-t border-line px-3 py-1 text-xs italic">{text}</p>;
  return (
    <button
      disabled={busy}
      className="block min-h-8 px-3 text-left text-xs font-semibold text-muted"
      onClick={async () => {
        setBusy(true);
        try {
          setText((await api<{ text: string }>(`/conversations/${conversationId}/messages/${messageId}/translate`, { json: { language } })).text);
        } catch (e) {
          toast(errorMessage(e));
        } finally {
          setBusy(false);
        }
      }}
    >
      {busy ? "Translating..." : "Translate"}
    </button>
  );
}

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
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [translateOpen, setTranslateOpen] = useState(false);
  const [language, setLanguage] = useState("en");

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
    mutationFn: (payload: { body: string; asset_id?: string; post_id?: string }) => api<Message>(`/conversations/${id}/messages`, { json: payload }),
    onSuccess: () => {
      setBody("");
      qc.invalidateQueries({ queryKey: ["messages", id] });
    },
    onError: (e) => toast(errorMessage(e)),
  });

  const answerRequest = async (verb: "accept" | "decline") => {
    try {
      await api(`/conversations/${id}/${verb}`, { method: "POST" });
      qc.invalidateQueries({ queryKey: ["conversations"] });
      if (verb === "decline") router.replace("/messages");
      else qc.invalidateQueries({ queryKey: ["conversation", id] });
    } catch (e) {
      toast(errorMessage(e));
    }
  };

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
          <h1 className="truncate text-sm font-semibold">{title}</h1>
          <p className="text-xs text-muted">{isTyping ? "typing..." : others[0]?.online ? "Online" : ""}</p>
        </div>
        <button aria-label="Translate messages" aria-pressed={translateOpen} onClick={() => setTranslateOpen(!translateOpen)} className="flex h-11 w-11 items-center justify-center"><Languages className="h-5 w-5" /></button>
        {conversation.data?.is_group && <button aria-label="Group settings" onClick={() => setSettingsOpen(true)} className="flex h-11 w-11 items-center justify-center"><Settings2 className="h-5 w-5" /></button>}
        <button aria-label="Audio call" onClick={() => call("audio")} className="flex h-11 w-11 items-center justify-center"><Phone className="h-5 w-5" /></button>
        <button aria-label="Video call" onClick={() => call("video")} className="flex h-11 w-11 items-center justify-center"><Video className="h-5 w-5" /></button>
      </header>
      {translateOpen && (
        <label className="flex items-center gap-2 border-b border-line p-2 text-sm">
          Translate to
          <select value={language} onChange={(e) => setLanguage(e.target.value)} className="min-h-11 flex-1 rounded-lg border border-line bg-surface px-2 text-[16px] sm:text-sm">
            {LANGUAGES.map(([code, name]) => <option key={code} value={code}>{name}</option>)}
          </select>
        </label>
      )}
      {conversation.data?.my_state === "request" && (
        <div data-testid="request-banner" className="border-b border-line p-3 text-sm">
          <p><b>{title}</b> wants to message you. They will not know you saw this until you reply.</p>
          <div className="mt-2 flex gap-2">
            <Button onClick={() => answerRequest("accept")}>Accept</Button>
            <Button variant="danger" onClick={() => answerRequest("decline")}>Decline</Button>
          </div>
        </div>
      )}
      {conversation.data?.waiting_for_accept && !conversation.data.is_group && (
        <p className="border-b border-line p-2 text-center text-xs text-muted">Message request sent. You can send 3 messages until they accept.</p>
      )}
      <div className="flex-1 space-y-1 overflow-y-auto p-3">
        {list.hasNextPage && <Button variant="ghost" className="w-full" onClick={() => list.fetchNextPage()}>Load earlier messages</Button>}
        {list.isLoading && <CenterSpinner />}
        {messages.map((m) => {
          const mine = m.sender_id === me?.id;
          return (
            <div key={m.id} className={cn("flex", mine ? "justify-end" : "justify-start")}>
              <div className={cn("max-w-[78%] overflow-hidden rounded-2xl text-sm", mine ? "bg-brand text-white" : "bg-surface")}>
                {m.media?.kind === "audio" && m.media.audio && <audio controls preload="metadata" src={m.media.audio} className="w-64 max-w-full p-1" aria-label="Voice note" />}
                {m.media && m.media.kind !== "audio" && (m.media.kind === "video" ? <div className="aspect-video w-64"><VideoPlayer asset={m.media} className="h-full w-full" /></div> : <MediaImage asset={m.media} sizes="256px" className="max-h-72 w-full object-cover" />)}
                {m.post_id && (
                  m.shared_post ? (
                    <Link href={`/p/${m.post_id}`} data-testid="shared-post" className="block w-56 max-w-full">
                      {m.shared_post.media[0] && <MediaImage asset={m.shared_post.media[0]} sizes="224px" className="aspect-square w-full object-cover" alt="" />}
                      <span className="block truncate px-3 pt-1 text-xs font-semibold">{m.shared_post.author.username}</span>
                      <span className="block truncate px-3 pb-2 text-xs">{m.shared_post.caption || "View post"}</span>
                    </Link>
                  ) : <p className="px-3 py-2 text-xs italic">This post is not available to you.</p>
                )}
                {m.body && <p className="whitespace-pre-wrap break-words px-3 py-2">{m.body}</p>}
                {!mine && m.body && translateOpen && <Translate conversationId={id} messageId={m.id} language={language} />}
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
        <VoiceRecorder onSend={(assetId) => send.mutate({ body: "", asset_id: assetId })} />
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
      {settingsOpen && conversation.data && <GroupSettings conversation={conversation.data} onClose={() => setSettingsOpen(false)} />}
    </div>
  );
}
