"use client";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Button, ErrorNote, Field, Input, Modal, UserRow } from "@/components/ui";
import { api, errorMessage } from "@/lib/api/client";
import type { Conversation } from "@/lib/api/types";

export function GroupSettings({ conversation, onClose }: { conversation: Conversation; onClose: () => void }) {
  const qc = useQueryClient();
  const router = useRouter();
  const [title, setTitle] = useState(conversation.title ?? "");
  const [username, setUsername] = useState("");
  const refresh = () => {
    qc.invalidateQueries({ queryKey: ["conversation", conversation.id] });
    qc.invalidateQueries({ queryKey: ["conversations"] });
  };
  const rename = useMutation({ mutationFn: () => api(`/conversations/${conversation.id}`, { method: "PATCH", json: { title } }), onSuccess: refresh });
  const add = useMutation({
    mutationFn: () => api(`/conversations/${conversation.id}/members`, { json: { username } }),
    onSuccess: () => {
      setUsername("");
      refresh();
    },
  });
  const error = rename.error ?? add.error;
  return (
    <Modal open onClose={onClose} title="Group">
      <div className="space-y-3">
        <ErrorNote message={error ? errorMessage(error) : null} />
        <Field label="Group name"><Input value={title} maxLength={80} onChange={(e) => setTitle(e.target.value)} /></Field>
        <Button variant="secondary" disabled={!title.trim()} loading={rename.isPending} onClick={() => rename.mutate()}>Save name</Button>
        <Field label="Add a person"><Input value={username} placeholder="Username" onChange={(e) => setUsername(e.target.value)} /></Field>
        <Button variant="secondary" disabled={!username.trim()} loading={add.isPending} onClick={() => add.mutate()}>Add</Button>
        <div>
          <h3 className="text-sm font-semibold">{conversation.members.length} people</h3>
          {conversation.members.map((m) => <UserRow key={m.user.id} user={m.user} />)}
        </div>
        <Button
          variant="danger"
          className="w-full"
          onClick={async () => {
            await api(`/conversations/${conversation.id}/leave`, { method: "POST" });
            qc.invalidateQueries({ queryKey: ["conversations"] });
            router.replace("/messages");
          }}
        >
          Leave group
        </Button>
      </div>
    </Modal>
  );
}
