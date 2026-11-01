"use client";
import { useInfiniteQuery } from "@tanstack/react-query";
import { useEffect, useRef } from "react";
import { api } from "@/lib/api/client";
import type { Page } from "@/lib/api/types";

export function useInfinite<T>(key: unknown[], path: string, enabled = true) {
  const query = useInfiniteQuery<Page<T>>({
    queryKey: key,
    enabled,
    initialPageParam: null,
    queryFn: ({ pageParam, signal }) => {
      const sep = path.includes("?") ? "&" : "?";
      return api<Page<T>>(pageParam ? `${path}${sep}cursor=${pageParam}` : path, { signal });
    },
    getNextPageParam: (last) => last.next_cursor ?? null,
  });
  return { ...query, items: query.data?.pages.flatMap((p) => p.items) ?? [] };
}

/** Loads the next page shortly before the end of the list becomes visible. */
export function useSentinel(onHit: () => void, active: boolean) {
  const ref = useRef<HTMLDivElement | null>(null);
  useEffect(() => {
    const node = ref.current;
    if (!node || !active) return;
    const io = new IntersectionObserver((e) => e[0]?.isIntersecting && onHit(), { rootMargin: "800px" });
    io.observe(node);
    return () => io.disconnect();
  }, [onHit, active]);
  return ref;
}
