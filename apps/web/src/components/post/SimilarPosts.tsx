"use client";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api/client";
import type { Post } from "@/lib/api/types";
import { PostGrid } from "./PostGrid";

export function SimilarPosts({ postId }: { postId: string }) {
  const similar = useQuery({ queryKey: ["similar", postId], queryFn: () => api<Post[]>(`/posts/${postId}/similar`) });
  if (!similar.data?.length) return null;
  return (
    <section data-testid="similar-posts" className="py-4">
      <h2 className="px-3 pb-2 text-sm font-semibold sm:px-0">More like this</h2>
      <PostGrid posts={similar.data} />
    </section>
  );
}
