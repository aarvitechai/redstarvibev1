"use client";
import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { CenterSpinner } from "@/components/ui";
import { useMe } from "@/hooks/useMe";

export default function Home() {
  const { data: me, isLoading } = useMe();
  const router = useRouter();
  useEffect(() => {
    if (!isLoading) router.replace(me ? "/feed" : "/login");
  }, [me, isLoading, router]);
  return <CenterSpinner />;
}
