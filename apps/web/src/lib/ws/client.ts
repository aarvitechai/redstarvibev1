"use client";
/** Native WebSocket with reconnect, exponential backoff and heartbeat. */
type Handler = (event: WsEvent) => void;
export type WsEvent = { type: string; [key: string]: any };

class Socket {
  private ws: WebSocket | null = null;
  private handlers = new Set<Handler>();
  private watched = new Map<string, number>();
  private attempts = 0;
  private closed = true;
  private heartbeat: ReturnType<typeof setInterval> | undefined;
  private timer: ReturnType<typeof setTimeout> | undefined;

  connect() {
    if (!this.closed) return;
    this.closed = false;
    this.open();
  }

  private open() {
    const proto = location.protocol === "https:" ? "wss:" : "ws:";
    const ws = new WebSocket(`${proto}//${location.host}/ws`);
    this.ws = ws;
    ws.onopen = () => {
      this.attempts = 0;
      for (const id of this.watched.keys()) this.send({ type: "watch_post", post_id: id });
      this.heartbeat = setInterval(() => this.send({ type: "ping" }), 25_000);
    };
    ws.onmessage = (m) => {
      try {
        const event = JSON.parse(m.data) as WsEvent;
        this.handlers.forEach((h) => h(event));
      } catch {}
    };
    ws.onclose = () => {
      clearInterval(this.heartbeat);
      if (this.closed) return;
      const delay = Math.min(30_000, 1000 * 2 ** this.attempts++) * (0.7 + Math.random() * 0.6);
      this.timer = setTimeout(() => this.open(), delay);
    };
  }

  disconnect() {
    this.closed = true;
    clearTimeout(this.timer);
    this.ws?.close();
  }

  send(data: WsEvent) {
    if (this.ws?.readyState === WebSocket.OPEN) this.ws.send(JSON.stringify(data));
  }

  on(handler: Handler) {
    this.handlers.add(handler);
    return () => {
      this.handlers.delete(handler);
    };
  }

  watchPost(id: string) {
    const count = this.watched.get(id) ?? 0;
    this.watched.set(id, count + 1);
    if (count === 0) this.send({ type: "watch_post", post_id: id });
    return () => {
      const left = (this.watched.get(id) ?? 1) - 1;
      if (left <= 0) {
        this.watched.delete(id);
        this.send({ type: "unwatch_post", post_id: id });
      } else this.watched.set(id, left);
    };
  }
}

export const socket = new Socket();
