"use client";
import { useQuery } from "@tanstack/react-query";
import { api, ApiError } from "@/lib/api/client";
import type { Me } from "@/lib/api/types";

export function useMe() {
  return useQuery<Me | null>({
    queryKey: ["me"],
    queryFn: async () => {
      try {
        return await api<Me>("/auth/me");
      } catch (e) {
        if (e instanceof ApiError && e.status === 401) return null;
        throw e;
      }
    },
    staleTime: 60_000,
  });
}
