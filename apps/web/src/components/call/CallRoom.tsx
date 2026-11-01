"use client";
import "@livekit/components-styles";
import { LiveKitRoom, RoomAudioRenderer, VideoConference } from "@livekit/components-react";
import type { CallJoin } from "@/lib/api/types";

/** Loaded only on the call route: LiveKit is heavy and must stay out of the initial bundle. */
export default function CallRoom({ join, onLeave }: { join: CallJoin; onLeave: () => void }) {
  return (
    <LiveKitRoom
      data-lk-theme="default"
      serverUrl={join.url}
      token={join.token}
      connect
      audio={join.can_publish}
      video={join.can_publish && join.kind !== "audio"}
      onDisconnected={onLeave}
      style={{ height: "100dvh" }}
    >
      <VideoConference />
      <RoomAudioRenderer />
    </LiveKitRoom>
  );
}
