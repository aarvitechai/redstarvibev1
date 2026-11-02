import { create } from "zustand";
import type { WsEvent } from "@/lib/ws/client";

type UiState = {
  incomingCall: WsEvent | null;
  setIncomingCall: (call: WsEvent | null) => void;
  typing: Record<string, number>;
  setTyping: (conversationId: string, at: number) => void;
  toast: string | null;
  showToast: (message: string | null) => void;
  videoMuted: boolean;
  setVideoMuted: (muted: boolean) => void;
};

export const useUi = create<UiState>((set) => ({
  incomingCall: null,
  setIncomingCall: (incomingCall) => set({ incomingCall }),
  typing: {},
  setTyping: (id, at) => set((s) => ({ typing: { ...s.typing, [id]: at } })),
  toast: null,
  showToast: (toast) => set({ toast }),
  videoMuted: true,
  setVideoMuted: (videoMuted) => set({ videoMuted }),
}));
