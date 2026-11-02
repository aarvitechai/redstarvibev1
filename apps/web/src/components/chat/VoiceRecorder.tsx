"use client";
import { Mic, Square, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { errorMessage } from "@/lib/api/client";
import { uploadAsset } from "@/lib/api/upload";
import { cn } from "@/lib/utils";
import { useUi } from "@/stores/ui";

const MAX_SECONDS = 300;
const TYPES = ["audio/webm", "audio/mp4", "audio/ogg"];

/** Records in the browser, uploads through the normal media pipeline, then hands back the asset id. */
export function VoiceRecorder({ onSend }: { onSend: (assetId: string) => void }) {
  const toast = useUi((s) => s.showToast);
  const [seconds, setSeconds] = useState<number | null>(null);
  const [uploading, setUploading] = useState(false);
  const recorder = useRef<MediaRecorder | null>(null);
  const cancelled = useRef(false);

  useEffect(() => {
    if (seconds == null) return;
    if (seconds >= MAX_SECONDS) {
      recorder.current?.stop();
      return;
    }
    const t = setTimeout(() => setSeconds((n) => (n == null ? n : n + 1)), 1000);
    return () => clearTimeout(t);
  }, [seconds]);

  useEffect(
    () => () => {
      cancelled.current = true;
      if (recorder.current?.state === "recording") recorder.current.stop();
    },
    [],
  );

  const start = async () => {
    const type = typeof MediaRecorder !== "undefined" ? TYPES.find((t) => MediaRecorder.isTypeSupported(t)) : undefined;
    if (!type || !navigator.mediaDevices) return toast("This browser cannot record voice notes");
    let stream: MediaStream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch {
      return toast("Allow the microphone to record a voice note");
    }
    const chunks: Blob[] = [];
    const rec = new MediaRecorder(stream, { mimeType: type });
    rec.ondataavailable = (e) => chunks.push(e.data);
    rec.onstop = async () => {
      stream.getTracks().forEach((t) => t.stop());
      setSeconds(null);
      if (cancelled.current || !chunks.length) return;
      setUploading(true);
      try {
        const file = new File(chunks, "voice-note", { type });
        const asset = await uploadAsset(file, "message");
        onSend(asset.id);
      } catch (e) {
        toast(errorMessage(e));
      } finally {
        setUploading(false);
      }
    };
    cancelled.current = false;
    recorder.current = rec;
    rec.start();
    setSeconds(0);
  };

  if (seconds != null) {
    return (
      <div className="flex shrink-0 items-center">
        <button type="button" aria-label="Cancel voice note" className="flex h-11 w-11 items-center justify-center" onClick={() => { cancelled.current = true; recorder.current?.stop(); }}>
          <X className="h-5 w-5" />
        </button>
        <span className="text-xs tabular-nums text-brand" data-testid="recording-time">{Math.floor(seconds / 60)}:{String(seconds % 60).padStart(2, "0")}</span>
        <button type="button" aria-label="Stop and send voice note" className="flex h-11 w-11 items-center justify-center text-brand" onClick={() => recorder.current?.stop()}>
          <Square className="h-5 w-5 fill-current" />
        </button>
      </div>
    );
  }
  return (
    <button type="button" aria-label="Record a voice note" disabled={uploading} onClick={start} className="flex h-11 w-11 shrink-0 items-center justify-center">
      <Mic className={cn("h-5 w-5", uploading && "animate-pulse text-brand")} />
    </button>
  );
}
