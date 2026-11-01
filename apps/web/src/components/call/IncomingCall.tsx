"use client";
import { Phone, PhoneOff } from "lucide-react";
import { useRouter } from "next/navigation";
import { Avatar, Button } from "@/components/ui";
import { api } from "@/lib/api/client";
import { useUi } from "@/stores/ui";

export function IncomingCall() {
  const { incomingCall: call, setIncomingCall } = useUi();
  const router = useRouter();
  if (!call) return null;
  return (
    <div role="alertdialog" aria-label="Incoming call" className="fixed inset-x-3 top-3 z-50 mx-auto flex max-w-md items-center gap-3 rounded-2xl border border-line bg-bg p-3 shadow-xl">
      <Avatar user={call.from} size={48} />
      <div className="min-w-0 flex-1">
        <p className="truncate font-semibold">{call.from?.username}</p>
        <p className="text-sm text-muted">Incoming {call.kind} call</p>
      </div>
      <Button
        variant="danger"
        aria-label="Decline"
        onClick={async () => {
          setIncomingCall(null);
          await api(`/calls/${call.call_id}/decline`, { method: "POST" }).catch(() => undefined);
        }}
      >
        <PhoneOff className="h-5 w-5" />
      </Button>
      <Button
        aria-label="Accept"
        onClick={() => {
          setIncomingCall(null);
          router.push(`/call/${call.room}`);
        }}
      >
        <Phone className="h-5 w-5" />
      </Button>
    </div>
  );
}
