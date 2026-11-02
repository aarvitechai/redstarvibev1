"use client";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect } from "react";
import { PostCard } from "@/components/post/PostCard";
import { CenterSpinner, Empty } from "@/components/ui";
import { useMe } from "@/hooks/useMe";
import { api } from "@/lib/api/client";
import type { Post } from "@/lib/api/types";
import { socket } from "@/lib/ws/client";

export default function PostPage() {
  const { postId } = useParams<{ postId: string }>();
  const { data: me } = useMe();
  const q = useQuery({
    queryKey: ["post", postId],
    queryFn: () => api<Post>(`/posts/${postId}`),
    refetchInterval: (query) => (query.state.data?.status === "processing" ? 2000 : false),
  });
  useEffect(() => {
    if (!me) return; // this route is public and sits outside the app shell, which owns the socket elsewhere
    socket.connect();
    return () => socket.disconnect();
  }, [me]);
  return (
    <main className="mx-auto max-w-[520px] sm:p-4">
      <nav className="flex min-h-12 items-center gap-2 border-b border-line px-3 sm:border-0">
        <Link href={me ? "/feed" : "/login"} className="flex min-h-11 items-center gap-2 font-bold">
          <img src="/brand/logo.png" alt="" width={28} height={28} /> RedStarVibe
        </Link>
      </nav>
      {q.isLoading ? <CenterSpinner /> : q.data ? <PostCard post={q.data} standalone priority /> : <Empty title="This post is not available" hint="It may have been removed, or the account is private." />}
    </main>
  );
}
