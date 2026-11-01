"use client";
/** Thin typed fetch wrapper: CSRF header, one shared token refresh, consistent errors. */

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
    public requestId?: string,
  ) {
    super(message);
  }
}

type Options = { method?: string; json?: unknown; headers?: Record<string, string>; signal?: AbortSignal };

function csrf(): string {
  const match = document.cookie.match(/(?:^|; )rsv_csrf=([^;]+)/);
  return match ? decodeURIComponent(match[1]!) : "";
}

let refreshing: Promise<boolean> | null = null;

function refreshOnce(): Promise<boolean> {
  refreshing ??= fetch("/api/v1/auth/refresh", { method: "POST", headers: { "x-csrf-token": csrf() } })
    .then((r) => r.ok)
    .catch(() => false)
    .finally(() => {
      refreshing = null;
    });
  return refreshing;
}

async function raw(path: string, opts: Options): Promise<Response> {
  const headers: Record<string, string> = { ...opts.headers };
  const method = opts.method ?? (opts.json !== undefined ? "POST" : "GET");
  if (opts.json !== undefined) headers["content-type"] = "application/json";
  if (method !== "GET") headers["x-csrf-token"] = csrf();
  return fetch(`/api/v1${path}`, {
    method,
    headers,
    body: opts.json !== undefined ? JSON.stringify(opts.json) : undefined,
    signal: opts.signal,
  });
}

const REFRESHABLE = new Set(["token_expired", "unauthorized", "token_revoked", "invalid_token"]);

export async function api<T = unknown>(path: string, opts: Options = {}): Promise<T> {
  let res = await raw(path, opts);
  if (res.status === 401 && !path.startsWith("/auth/login") && !path.startsWith("/auth/refresh")) {
    const body = await res.clone().json().catch(() => null);
    if (REFRESHABLE.has(body?.error?.code) && (await refreshOnce())) res = await raw(path, opts);
  }
  if (res.status === 204) return undefined as T;
  const body = await res.json().catch(() => null);
  if (!res.ok) {
    const err = body?.error;
    throw new ApiError(res.status, err?.code ?? "error", err?.message ?? "Something went wrong", err?.request_id);
  }
  return body as T;
}

export const errorMessage = (e: unknown) => (e instanceof Error ? e.message : "Something went wrong");
