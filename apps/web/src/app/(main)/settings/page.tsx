"use client";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { applyTheme } from "@/components/ThemeBoot";
import { Avatar, Button, CenterSpinner, ErrorNote, Field, Input, Modal, UserRow } from "@/components/ui";
import { useMe } from "@/hooks/useMe";
import { api, errorMessage } from "@/lib/api/client";
import type { UserBrief } from "@/lib/api/types";
import { uploadAsset } from "@/lib/api/upload";
import { socket } from "@/lib/ws/client";
import { useUi } from "@/stores/ui";

function urlBase64ToUint8Array(value: string) {
  const padded = value + "=".repeat((4 - (value.length % 4)) % 4);
  const raw = atob(padded.replace(/-/g, "+").replace(/_/g, "/"));
  return Uint8Array.from(raw, (c) => c.charCodeAt(0));
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="space-y-3 border-b border-line py-5">
      <h2 className="font-semibold">{title}</h2>
      {children}
    </section>
  );
}

function PushToggle() {
  const toast = useUi((s) => s.showToast);
  const [state, setState] = useState<"unknown" | "unsupported" | "off" | "on">("unknown");
  useEffect(() => {
    if (!("serviceWorker" in navigator) || !("PushManager" in window)) return setState("unsupported");
    navigator.serviceWorker.getRegistration().then(async (r) => {
      const sub = await r?.pushManager.getSubscription();
      setState(sub ? "on" : "off");
    });
  }, []);
  if (state === "unsupported") return <p className="text-sm text-muted">This browser does not support push notifications.</p>;
  return (
    <Button
      variant="secondary"
      onClick={async () => {
        try {
          const registration = await navigator.serviceWorker.ready;
          if (state === "on") {
            const sub = await registration.pushManager.getSubscription();
            if (sub) {
              const j = sub.toJSON();
              await api("/push/subscribe", { method: "DELETE", json: { endpoint: j.endpoint, keys: j.keys } });
              await sub.unsubscribe();
            }
            setState("off");
            return;
          }
          const { public_key } = await api<{ public_key: string | null }>("/push/public-key");
          if (!public_key) return toast("Push is not configured on this server");
          if ((await Notification.requestPermission()) !== "granted") return toast("Notifications are blocked in your browser");
          const sub = await registration.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: urlBase64ToUint8Array(public_key) });
          const j = sub.toJSON();
          await api("/push/subscribe", { json: { endpoint: j.endpoint, keys: j.keys } });
          setState("on");
        } catch (e) {
          toast(errorMessage(e));
        }
      }}
    >
      {state === "on" ? "Turn off push notifications" : "Turn on push notifications"}
    </Button>
  );
}

function InstallApp() {
  const prompt = useRef<(Event & { prompt: () => void }) | null>(null);
  const [can, setCan] = useState(false);
  useEffect(() => {
    const on = (e: Event) => {
      e.preventDefault();
      prompt.current = e as Event & { prompt: () => void };
      setCan(true);
    };
    addEventListener("beforeinstallprompt", on);
    return () => removeEventListener("beforeinstallprompt", on);
  }, []);
  if (!can) return <p className="text-sm text-muted">To install, use your browser menu and choose Install app or Add to Home Screen.</p>;
  return <Button variant="secondary" onClick={() => prompt.current?.prompt()}>Install RedStarVibe</Button>;
}

function HiddenWords() {
  const { data: me } = useMe();
  const qc = useQueryClient();
  const toast = useUi((s) => s.showToast);
  const [text, setText] = useState("");
  useEffect(() => setText((me?.hidden_words ?? []).join(", ")), [me?.hidden_words]);
  const save = useMutation({
    mutationFn: () => api("/users/me", { method: "PATCH", json: { hidden_words: text.split(",") } }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["me"] });
      toast("Saved");
    },
  });
  return (
    <>
      <Field label="Words to hide, separated by commas">
        <textarea value={text} rows={2} onChange={(e) => setText(e.target.value)} className="w-full rounded-lg border border-line bg-surface p-3 text-[16px] focus:border-brand focus:outline-none sm:text-sm" />
      </Field>
      <p className="text-xs text-muted">New comments on your posts with these words stay hidden from others until you allow them.</p>
      <ErrorNote message={save.error ? errorMessage(save.error) : null} />
      <Button variant="secondary" loading={save.isPending} onClick={() => save.mutate()}>Save hidden words</Button>
    </>
  );
}

function CloseFriends() {
  const [username, setUsername] = useState("");
  const list = useQuery({ queryKey: ["close-friends"], queryFn: () => api<UserBrief[]>("/close-friends") });
  const add = useMutation({
    mutationFn: () => api("/close-friends", { json: { username } }),
    onSuccess: () => {
      setUsername("");
      list.refetch();
    },
  });
  return (
    <>
      <p className="text-xs text-muted">Only these people see stories you share with close friends. They are not told they are on the list.</p>
      <div className="flex gap-2">
        <Input aria-label="Close friend username" placeholder="Username" value={username} onChange={(e) => setUsername(e.target.value)} />
        <Button variant="secondary" disabled={!username.trim()} loading={add.isPending} onClick={() => add.mutate()}>Add</Button>
      </div>
      <ErrorNote message={add.error ? errorMessage(add.error) : null} />
      {list.data?.map((u) => (
        <UserRow key={u.id} user={u} action={<Button variant="secondary" onClick={async () => { await api(`/close-friends/${u.id}`, { method: "DELETE" }); list.refetch(); }}>Remove</Button>} />
      ))}
    </>
  );
}

function Mfa() {
  const { data: me } = useMe();
  const qc = useQueryClient();
  const [setup, setSetup] = useState<{ secret: string; otpauth_uri: string } | null>(null);
  const [code, setCode] = useState("");
  const [error, setError] = useState<string | null>(null);
  const run = async (fn: () => Promise<unknown>) => {
    setError(null);
    try {
      await fn();
      setCode("");
      qc.invalidateQueries({ queryKey: ["me"] });
    } catch (e) {
      setError(errorMessage(e));
    }
  };
  return (
    <div className="space-y-2">
      <ErrorNote message={error} />
      {me?.totp_enabled ? (
        <>
          <p className="text-sm">Authenticator app is on.</p>
          <Field label="Current code"><Input value={code} inputMode="numeric" onChange={(e) => setCode(e.target.value)} /></Field>
          <Button variant="danger" onClick={() => run(() => api("/auth/mfa/totp/disable", { json: { code } }))}>Turn off</Button>
        </>
      ) : setup ? (
        <>
          <p className="text-sm">Add this key to your authenticator app, then enter the code it shows.</p>
          <code className="block break-all rounded bg-surface p-2 text-sm">{setup.secret}</code>
          <Field label="Code"><Input value={code} inputMode="numeric" onChange={(e) => setCode(e.target.value)} /></Field>
          <Button onClick={() => run(async () => { await api("/auth/mfa/totp/enable", { json: { code } }); setSetup(null); })}>Turn on</Button>
        </>
      ) : (
        <Button variant="secondary" onClick={() => run(async () => setSetup(await api("/auth/mfa/totp/setup", { method: "POST" })))}>Set up an authenticator app</Button>
      )}
    </div>
  );
}

export default function SettingsPage() {
  const { data: me } = useMe();
  const qc = useQueryClient();
  const router = useRouter();
  const toast = useUi((s) => s.showToast);
  const [name, setName] = useState("");
  const [bio, setBio] = useState("");
  const [website, setWebsite] = useState("");
  const [isPrivate, setPrivate] = useState(false);
  const [theme, setTheme] = useState("system");
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [avatarBusy, setAvatarBusy] = useState(false);
  const file = useRef<HTMLInputElement>(null);
  const blocked = useQuery({ queryKey: ["blocked"], queryFn: () => api<UserBrief[]>("/users/me/blocked") });
  const muted = useQuery({ queryKey: ["muted"], queryFn: () => api<UserBrief[]>("/users/me/muted") });
  const restricted = useQuery({ queryKey: ["restricted"], queryFn: () => api<UserBrief[]>("/users/me/restricted") });

  useEffect(() => {
    if (!me) return;
    setName(me.display_name);
    setBio(me.bio);
    setWebsite(me.website ?? "");
    setPrivate(me.is_private);
    try {
      setTheme(localStorage.getItem("rsv-theme") ?? "system");
    } catch {}
  }, [me]);

  const save = useMutation({
    mutationFn: () => api("/users/me", { method: "PATCH", json: { display_name: name, bio, website: website || null, is_private: isPrivate } }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["me"] });
      qc.invalidateQueries({ queryKey: ["profile"] });
      toast("Saved");
    },
  });

  if (!me) return <CenterSpinner />;
  return (
    <div className="mx-auto max-w-xl p-3 sm:p-4">
      <h1 className="text-xl font-bold">Settings</h1>
      <Section title="Profile">
        <div className="flex items-center gap-3">
          <Avatar user={me} size={64} />
          <Button variant="secondary" loading={avatarBusy} onClick={() => file.current?.click()}>Change photo</Button>
          <input
            ref={file}
            type="file"
            hidden
            accept="image/jpeg,image/png,image/webp"
            onChange={async (e) => {
              const f = e.target.files?.[0];
              e.target.value = "";
              if (!f) return;
              setAvatarBusy(true);
              try {
                const asset = await uploadAsset(f, "avatar");
                await api("/users/me", { method: "PATCH", json: { avatar_asset_id: asset.id } });
                qc.invalidateQueries({ queryKey: ["me"] });
              } catch (err) {
                toast(errorMessage(err));
              } finally {
                setAvatarBusy(false);
              }
            }}
          />
        </div>
        <Field label="Name"><Input value={name} maxLength={80} onChange={(e) => setName(e.target.value)} /></Field>
        <Field label="Bio">
          <textarea value={bio} maxLength={500} rows={3} onChange={(e) => setBio(e.target.value)} className="w-full rounded-lg border border-line bg-surface p-3 text-[16px] focus:border-brand focus:outline-none sm:text-sm" />
        </Field>
        <Field label="Website"><Input type="url" value={website} placeholder="https://" onChange={(e) => setWebsite(e.target.value)} /></Field>
        <label className="flex min-h-11 items-center gap-3 text-sm">
          <input type="checkbox" checked={isPrivate} onChange={(e) => setPrivate(e.target.checked)} className="h-5 w-5 accent-[#C8102E]" />
          Private account: only approved followers see your posts
        </label>
        <ErrorNote message={save.error ? errorMessage(save.error) : null} />
        <Button loading={save.isPending} onClick={() => save.mutate()}>Save changes</Button>
      </Section>
      <Section title="Appearance">
        <Field label="Theme">
          <select
            value={theme}
            onChange={(e) => {
              const value = e.target.value;
              setTheme(value);
              try {
                if (value === "system") localStorage.removeItem("rsv-theme");
                else localStorage.setItem("rsv-theme", value);
              } catch {}
              applyTheme(value === "system" ? null : value);
            }}
            className="min-h-11 w-full rounded-lg border border-line bg-surface px-3 text-[16px] sm:text-sm"
          >
            <option value="system">Match my device</option>
            <option value="light">Light</option>
            <option value="dark">Dark</option>
          </select>
        </Field>
      </Section>
      <Section title="Notifications and app">
        <PushToggle />
        <InstallApp />
      </Section>
      <Section title="Security"><Mfa /></Section>
      <Section title="Close friends"><CloseFriends /></Section>
      <Section title="Hidden words"><HiddenWords /></Section>
      {!!muted.data?.length && (
        <Section title="Muted accounts">
          {muted.data.map((u) => (
            <UserRow key={u.id} user={u} action={<Button variant="secondary" onClick={async () => { await api(`/users/${u.username}/mute`, { method: "DELETE" }); muted.refetch(); }}>Unmute</Button>} />
          ))}
        </Section>
      )}
      {!!restricted.data?.length && (
        <Section title="Restricted accounts">
          {restricted.data.map((u) => (
            <UserRow key={u.id} user={u} action={<Button variant="secondary" onClick={async () => { await api(`/users/${u.username}/restrict`, { method: "DELETE" }); restricted.refetch(); }}>Remove</Button>} />
          ))}
        </Section>
      )}
      {!!blocked.data?.length && (
        <Section title="Blocked accounts">
          {blocked.data.map((u) => (
            <UserRow key={u.id} user={u} action={<Button variant="secondary" onClick={async () => { await api(`/users/${u.username}/block`, { method: "DELETE" }); blocked.refetch(); }}>Unblock</Button>} />
          ))}
        </Section>
      )}
      <Section title="Your data">
        <Button
          variant="secondary"
          onClick={async () => {
            const data = await api("/users/me/export");
            const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], { type: "application/json" }));
            const a = document.createElement("a");
            a.href = url;
            a.download = `redstarvibe-${me.username}.json`;
            a.click();
            URL.revokeObjectURL(url);
          }}
        >
          Download my data
        </Button>
        <Button variant="danger" onClick={() => setConfirmDelete(true)}>Delete my account</Button>
      </Section>
      <div className="py-5">
        <Button
          variant="secondary"
          className="w-full"
          onClick={async () => {
            await api("/auth/logout", { method: "POST" });
            socket.disconnect();
            qc.clear();
            router.replace("/login");
          }}
        >
          Log out
        </Button>
      </div>
      <Modal open={confirmDelete} onClose={() => setConfirmDelete(false)} title="Delete account">
        <p className="text-sm">Your account will be permanently removed after 30 days. You can restore it any time before then by logging in.</p>
        <Button
          variant="danger"
          className="mt-3 w-full"
          onClick={async () => {
            await api("/users/me", { method: "DELETE" });
            setConfirmDelete(false);
            qc.invalidateQueries({ queryKey: ["me"] });
          }}
        >
          Delete my account
        </Button>
      </Modal>
    </div>
  );
}
