"use client";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useEffect, type ReactNode } from "react";
import { IncomingCall } from "@/components/call/IncomingCall";
import { Button, CenterSpinner } from "@/components/ui";
import { useMe } from "@/hooks/useMe";
import { api } from "@/lib/api/client";
import type { Conversation } from "@/lib/api/types";
import { socket } from "@/lib/ws/client";
import { useUi } from "@/stores/ui";
import { BottomNav, SideNav, TopBar } from "./nav";

export function AppShell({ children }: { children: ReactNode }) {
  const { data: me, isLoading, isError, refetch } = useMe();
  const router = useRouter();
  const qc = useQueryClient();
  const { setIncomingCall, setTyping, toast, showToast } = useUi();

  const unread = useQuery({
    queryKey: ["unread"],
    enabled: !!me,
    queryFn: () => api<{ count: number }>("/notifications/unread-count"),
  });
  const conversations = useQuery({
    queryKey: ["conversations"],
    enabled: !!me,
    queryFn: () => api<Conversation[]>("/conversations"),
  });

  useEffect(() => {
    if (me === null) router.replace("/login");
    else if (me && me.delete_after === undefined) router.refresh();
  }, [me, router]);

  useEffect(() => {
    if (!me) return;
    socket.connect();
    const off = socket.on((event) => {
      if (event.type === "notification") {
        qc.invalidateQueries({ queryKey: ["unread"] });
        qc.invalidateQueries({ queryKey: ["notifications"] });
      } else if (event.type === "message") {
        qc.invalidateQueries({ queryKey: ["conversations"] });
        qc.invalidateQueries({ queryKey: ["messages", event.message.conversation_id] });
        if (event.message.sender_id !== me.id) socket.send({ type: "delivered", conversation_id: event.message.conversation_id });
      } else if (event.type === "seen" || event.type === "delivered") {
        qc.invalidateQueries({ queryKey: ["conversation", event.conversation_id] });
      } else if (event.type === "typing") {
        setTyping(event.conversation_id, Date.now());
      } else if (event.type === "call") {
        setIncomingCall(event);
      } else if (event.type === "call_ended") {
        setIncomingCall(null);
      }
    });
    return () => {
      off();
      socket.disconnect();
    };
  }, [me, qc, setIncomingCall, setTyping]);

  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(() => showToast(null), 3500);
    return () => clearTimeout(t);
  }, [toast, showToast]);

  if (isError) {
    return (
      <div className="flex h-dvh flex-col items-center justify-center gap-3 p-6 text-center">
        <p>We could not reach RedStarVibe.</p>
        <Button onClick={() => refetch()}>Try again</Button>
      </div>
    );
  }
  if (isLoading || !me) return <CenterSpinner />;

  const counts = {
    notifications: unread.data?.count ?? 0,
    messages: conversations.data?.reduce((n, c) => n + (c.unread > 0 ? 1 : 0), 0) ?? 0,
  };
  return (
    <div className="flex min-h-dvh">
      <SideNav me={me} counts={counts} />
      <div className="min-w-0 flex-1">
        <TopBar counts={counts} />
        {me.status === "deleting" && (
          <div className="bg-brand px-4 py-2 text-center text-sm text-white">
            This account is scheduled for deletion.{" "}
            <button
              className="min-h-11 font-bold underline"
              onClick={async () => {
                await api("/users/me/restore", { method: "POST" });
                qc.invalidateQueries({ queryKey: ["me"] });
              }}
            >
              Restore it
            </button>
          </div>
        )}
        <main className="pb-20 sm:pb-6">{children}</main>
      </div>
      <BottomNav me={me} counts={counts} />
      <IncomingCall />
      {toast && (
        <div role="status" className="fixed bottom-20 left-1/2 z-50 -translate-x-1/2 rounded-lg bg-fg px-4 py-2 text-sm text-bg shadow-lg sm:bottom-6">
          {toast}
        </div>
      )}
    </div>
  );
}
