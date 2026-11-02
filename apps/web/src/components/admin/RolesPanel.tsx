"use client";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Button, CenterSpinner, Empty, ErrorNote, Input } from "@/components/ui";
import { useMe } from "@/hooks/useMe";
import { api, errorMessage } from "@/lib/api/client";
import type { AdminUserRow } from "@/lib/api/types";

const LABEL: Record<string, string> = { superadmin: "Super admin", admin: "Admin", staff: "Staff", business: "Business", user: "User" };
const ROLES = ["admin", "staff", "business"];

export function RolesPanel() {
  const { data: me } = useMe();
  const qc = useQueryClient();
  const [text, setText] = useState("");
  const [q, setQ] = useState("");
  useEffect(() => {
    const t = setTimeout(() => setQ(text.trim()), 250);
    return () => clearTimeout(t);
  }, [text]);
  const users = useQuery({
    queryKey: ["admin-users", q],
    queryFn: () => api<AdminUserRow[]>(`/admin/users?q=${encodeURIComponent(q)}`),
  });
  const change = useMutation({
    mutationFn: ({ id, role }: { id: string; role: string }) => api(`/admin/users/${id}/role`, { method: "PATCH", json: { role } }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin-users"] }),
  });
  return (
    <div className="space-y-3">
      <p className="text-sm text-muted">Search for a person to give them a role. With an empty search, this lists current staff.</p>
      <Input aria-label="Search users" placeholder="Username or email" value={text} onChange={(e) => setText(e.target.value)} />
      <ErrorNote message={change.error ? errorMessage(change.error) : null} />
      {users.isLoading ? (
        <CenterSpinner />
      ) : !users.data?.length ? (
        <Empty title="Nobody found" />
      ) : (
        <ul className="divide-y divide-line">
          {users.data.map((u) => (
            <li key={u.id} className="flex items-center gap-3 py-2 text-sm">
              <div className="min-w-0 flex-1">
                <p className="truncate font-semibold">{u.username}</p>
                <p className="truncate text-muted">
                  {LABEL[u.role] ?? u.role} · {u.email}
                </p>
              </div>
              {u.id !== me?.id && u.role !== "superadmin" && !u.is_test && (
                <div className="flex flex-wrap justify-end gap-1">
                  {u.role !== "user" ? (
                    <Button variant="secondary" onClick={() => change.mutate({ id: u.id, role: "user" })}>Remove {LABEL[u.role]?.toLowerCase()}</Button>
                  ) : (
                    ROLES.map((role) => <Button key={role} variant="secondary" onClick={() => change.mutate({ id: u.id, role })}>Make {LABEL[role]?.toLowerCase()}</Button>)
                  )}
                </div>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
