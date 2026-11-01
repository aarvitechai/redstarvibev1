"use client";
import { X } from "lucide-react";
import Link from "next/link";
import { useEffect, useRef, type ButtonHTMLAttributes, type InputHTMLAttributes, type ReactNode } from "react";
import type { UserBrief } from "@/lib/api/types";
import { cn } from "@/lib/utils";

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "ghost" | "danger";
  loading?: boolean;
};

export function Button({ variant = "primary", loading, className, children, disabled, ...rest }: ButtonProps) {
  return (
    <button
      disabled={disabled || loading}
      className={cn(
        "inline-flex min-h-11 items-center justify-center gap-2 rounded-lg px-4 text-sm font-semibold transition-colors disabled:cursor-not-allowed disabled:opacity-50",
        variant === "primary" && "bg-brand text-white hover:bg-brand-dark",
        variant === "secondary" && "bg-surface text-fg hover:bg-line",
        variant === "ghost" && "text-fg hover:bg-surface",
        variant === "danger" && "bg-surface text-brand hover:bg-line",
        className,
      )}
      {...rest}
    >
      {loading && <Spinner className="h-4 w-4 border-2" />}
      {children}
    </button>
  );
}

export function Spinner({ className }: { className?: string }) {
  return (
    <span
      role="status"
      aria-label="Loading"
      className={cn("inline-block animate-spin rounded-full border-line border-t-brand", className ?? "h-6 w-6 border-[3px]")}
    />
  );
}

export function CenterSpinner() {
  return (
    <div className="flex justify-center py-10">
      <Spinner />
    </div>
  );
}

export function Input({ className, ...rest }: InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      className={cn(
        "min-h-11 w-full rounded-lg border border-line bg-surface px-3 text-[16px] text-fg placeholder:text-muted focus:border-brand focus:outline-none sm:text-sm",
        className,
      )}
      {...rest}
    />
  );
}

export function Field({ label, error, children }: { label: string; error?: string; children: ReactNode }) {
  return (
    <label className="block space-y-1">
      <span className="text-sm font-medium">{label}</span>
      {children}
      {error && <span className="block text-xs text-brand">{error}</span>}
    </label>
  );
}

export function ErrorNote({ message }: { message?: string | null }) {
  if (!message) return null;
  return (
    <p role="alert" className="rounded-lg bg-brand/10 px-3 py-2 text-sm text-brand">
      {message}
    </p>
  );
}

export function Avatar({ user, size = 40, ring }: { user?: Pick<UserBrief, "username" | "avatar_url"> | null; size?: number; ring?: boolean }) {
  const initial = user?.username?.[0]?.toUpperCase() ?? "?";
  return (
    <span
      className={cn(
        "inline-flex shrink-0 items-center justify-center overflow-hidden rounded-full bg-surface font-semibold text-muted",
        ring && "outline outline-2 outline-offset-2 outline-brand",
      )}
      style={{ width: size, height: size, fontSize: size * 0.4 }}
    >
      {user?.avatar_url ? (
        <img src={user.avatar_url} alt="" width={size} height={size} loading="lazy" className="h-full w-full object-cover" />
      ) : (
        initial
      )}
    </span>
  );
}

export function UserRow({ user, action }: { user: UserBrief; action?: ReactNode }) {
  return (
    <div className="flex items-center gap-3 py-2">
      <Link href={`/${user.username}`} className="flex min-w-0 flex-1 items-center gap-3">
        <Avatar user={user} size={44} />
        <span className="min-w-0">
          <span className="block truncate text-sm font-semibold">{user.username}</span>
          <span className="block truncate text-sm text-muted">{user.display_name}</span>
        </span>
      </Link>
      {action}
    </div>
  );
}

export function Modal({
  open,
  onClose,
  title,
  children,
  wide,
}: {
  open: boolean;
  onClose: () => void;
  title?: string;
  children: ReactNode;
  wide?: boolean;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;
    if (open && !dialog.open) dialog.showModal();
    if (!open && dialog.open) dialog.close();
  }, [open]);
  return (
    <dialog
      ref={ref}
      onClose={onClose}
      onClick={(e) => e.target === ref.current && onClose()}
      className={cn(
        "m-auto max-h-[90dvh] w-[calc(100%-1.5rem)] overflow-hidden rounded-2xl bg-bg p-0 text-fg backdrop:bg-black/60",
        wide ? "max-w-2xl" : "max-w-md",
      )}
    >
      {open && (
        <div className="flex max-h-[90dvh] flex-col">
          <div className="flex items-center justify-between border-b border-line px-4 py-2">
            <h2 className="text-base font-semibold">{title}</h2>
            <button aria-label="Close" onClick={onClose} className="flex h-11 w-11 items-center justify-center rounded-full hover:bg-surface">
              <X className="h-5 w-5" />
            </button>
          </div>
          <div className="overflow-y-auto p-4">{children}</div>
        </div>
      )}
    </dialog>
  );
}

export function Empty({ title, hint, action }: { title: string; hint?: string; action?: ReactNode }) {
  return (
    <div className="px-6 py-14 text-center">
      <p className="text-lg font-semibold">{title}</p>
      {hint && <p className="mx-auto mt-1 max-w-sm text-sm text-muted">{hint}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}
