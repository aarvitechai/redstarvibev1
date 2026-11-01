"use client";
import { useQuery } from "@tanstack/react-query";
import dynamic from "next/dynamic";
import { useParams, useRouter } from "next/navigation";
import { CenterSpinner, Empty } from "@/components/ui";
import { api, errorMessage } from "@/lib/api/client";
import type { CallJoin } from "@/lib/api/types";

const CallRoom = dynamic(() => import("@/components/call/CallRoom"), { ssr: false, loading: () => <CenterSpinner /> });

export default function CallPage() {
  const { roomId } = useParams<{ roomId: string }>();
  const router = useRouter();
  const join = useQuery({
    queryKey: ["call", roomId],
    queryFn: () => api<CallJoin>(`/calls/rooms/${roomId}/join`, { method: "POST" }),
    gcTime: 0,
    staleTime: Infinity,
  });
  if (join.isLoading) return <CenterSpinner />;
  if (!join.data) return <Empty title="This call has ended" hint={join.error ? errorMessage(join.error) : undefined} />;
  const leave = async () => {
    const data = join.data!;
    if (data.kind !== "live") await api(`/calls/${data.call_id}/end`, { method: "POST" }).catch(() => undefined);
    else await api(`/live/${data.call_id}/end`, { method: "POST" }).catch(() => undefined);
    router.back();
  };
  return <CallRoom join={join.data} onLeave={leave} />;
}
