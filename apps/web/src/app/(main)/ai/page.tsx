"use client";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Bot, Send } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { ErrorNote, Input, Spinner } from "@/components/ui";
import { api, errorMessage } from "@/lib/api/client";
import type { AskOut, InsightsOut } from "@/lib/api/types";

type Turn = { q: string; a?: AskOut };

export default function AiPage() {
  const [text, setText] = useState("");
  const [turns, setTurns] = useState<Turn[]>([]);
  const insights = useQuery({ queryKey: ["ai-insights"], queryFn: () => api<InsightsOut>("/ai/insights") });
  const ask = useMutation({
    mutationFn: (question: string) => api<AskOut>("/ai/assistant", { json: { question } }),
    onSuccess: (a) => setTurns((list) => list.map((t, i) => (i === list.length - 1 ? { ...t, a } : t))),
  });
  return (
    <div className="mx-auto flex h-[calc(100dvh-7rem)] max-w-2xl flex-col p-3 sm:h-dvh sm:p-4">
      <h1 className="flex items-center gap-2 text-xl font-bold"><Bot className="h-6 w-6 text-brand" /> Vibe AI</h1>
      {insights.data && <p className="mt-2 rounded-lg bg-surface p-3 text-sm"><b>Your insights: </b>{insights.data.summary}</p>}
      <div className="mt-3 flex-1 space-y-3 overflow-y-auto">
        {!turns.length && <p className="text-sm text-muted">Ask about how RedStarVibe works or about your own posts. For example: how long do stories last?</p>}
        {turns.map((t, i) => (
          <div key={i} className="space-y-1">
            <p className="ml-auto w-fit max-w-[85%] rounded-2xl bg-brand px-3 py-2 text-sm text-white">{t.q}</p>
            {t.a ? (
              <div className="w-fit max-w-[90%] rounded-2xl bg-surface px-3 py-2 text-sm">
                <p className="whitespace-pre-wrap">{t.a.answer}</p>
                {!!t.a.citations.length && (
                  <ol className="mt-2 list-decimal pl-4 text-xs text-muted">
                    {t.a.citations.map((c, n) => (
                      <li key={n}>{c.entity_type === "own_post" ? <Link className="underline" href={`/p/${c.entity_id}`}>{c.title}</Link> : c.title}</li>
                    ))}
                  </ol>
                )}
                {!t.a.llm_used && <p className="mt-1 text-xs text-muted">Quoted from sources. Set ANTHROPIC_API_KEY for full AI answers.</p>}
              </div>
            ) : ask.isPending ? <Spinner /> : null}
          </div>
        ))}
        <ErrorNote message={ask.error ? errorMessage(ask.error) : null} />
      </div>
      <form
        className="flex gap-2 pt-2"
        onSubmit={(e) => {
          e.preventDefault();
          const q = text.trim();
          if (q.length < 2) return;
          setTurns((l) => [...l, { q }]);
          setText("");
          ask.mutate(q);
        }}
      >
        <Input aria-label="Ask Vibe AI" placeholder="Ask Vibe AI" value={text} maxLength={1000} onChange={(e) => setText(e.target.value)} />
        <button type="submit" aria-label="Send" className="flex h-11 w-11 shrink-0 items-center justify-center text-brand"><Send className="h-5 w-5" /></button>
      </form>
    </div>
  );
}
