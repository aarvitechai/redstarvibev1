"use client";
import { useQuery } from "@tanstack/react-query";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { Button, CenterSpinner, ErrorNote } from "@/components/ui";
import { useMe } from "@/hooks/useMe";
import { api, errorMessage } from "@/lib/api/client";

const SCOPE_TEXT: Record<string, string> = {
  read: "See your profile, posts, insights and notifications",
  "write:drafts": "Create and change drafts, and ask to schedule them. You approve each one in the app.",
  "write:reports": "File moderation reports for you",
};

function Consent() {
  const params = useSearchParams();
  const router = useRouter();
  const { data: me, isLoading } = useMe();
  const [error, setError] = useState<string | null>(null);
  const clientId = params.get("client_id") ?? "";
  const scope = params.get("scope") ?? "read";
  const client = useQuery({ queryKey: ["oauth-client", clientId], enabled: !!me && !!clientId, queryFn: () => api<{ client_name: string }>(`/oauth/clients/${encodeURIComponent(clientId)}`) });

  useEffect(() => {
    if (!isLoading && !me) router.replace("/login");
  }, [isLoading, me, router]);

  const decide = async (approve: boolean) => {
    try {
      const res = await api<{ redirect_to: string }>("/oauth/consent", {
        json: { client_id: clientId, redirect_uri: params.get("redirect_uri"), code_challenge: params.get("code_challenge"), state: params.get("state") ?? "", scope, approve },
      });
      location.assign(res.redirect_to); // validated by the server against the registered client
    } catch (e) {
      setError(errorMessage(e));
    }
  };
  if (isLoading || !me) return <CenterSpinner />;
  return (
    <main className="mx-auto flex min-h-dvh max-w-sm flex-col justify-center gap-4 p-4">
      <img src="/brand/logo.png" alt="" width={64} height={64} className="mx-auto" />
      <h1 className="text-center text-xl font-bold">{client.data?.client_name ?? "An app"} wants to access your account</h1>
      <p className="text-center text-sm text-muted">Signed in as {me.username}</p>
      <ul className="list-disc space-y-1 pl-5 text-sm">
        {scope.split(" ").map((s) => <li key={s}>{SCOPE_TEXT[s] ?? s}</li>)}
      </ul>
      <ErrorNote message={error} />
      <Button onClick={() => decide(true)}>Allow</Button>
      <Button variant="secondary" onClick={() => decide(false)}>Deny</Button>
    </main>
  );
}

export default function ConsentPage() {
  return (
    <Suspense>
      <Consent />
    </Suspense>
  );
}
