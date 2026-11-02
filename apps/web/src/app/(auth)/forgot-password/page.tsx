"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Button, ErrorNote, Field, Input } from "@/components/ui";
import { api, errorMessage } from "@/lib/api/client";
import { useUi } from "@/stores/ui";

export default function ForgotPassword() {
  const router = useRouter();
  const toast = useUi((s) => s.showToast);
  const [step, setStep] = useState<"email" | "reset">("email");
  const [email, setEmail] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const run = async (fn: () => Promise<void>) => {
    setBusy(true);
    setError(null);
    try {
      await fn();
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <form
      className="space-y-3"
      onSubmit={(e) => {
        e.preventDefault();
        const form = new FormData(e.currentTarget);
        if (step === "email") {
          const typed = String(form.get("email"));
          run(async () => {
            await api("/auth/password/forgot", { json: { email: typed } });
            setEmail(typed);
            setStep("reset");
          });
        } else {
          const body = { email, code: String(form.get("code")), password: String(form.get("password")) };
          run(async () => {
            await api("/auth/password/reset", { json: body });
            toast("Password changed. Please log in.");
            router.replace("/login");
          });
        }
      }}
    >
      <h1 className="text-center text-lg font-semibold">Reset your password</h1>
      <ErrorNote message={error} />
      {step === "email" ? (
        <Field label="Email">
          <Input name="email" type="email" required autoComplete="email" />
        </Field>
      ) : (
        <>
          <p className="text-center text-sm text-muted">If that account exists, we sent a 6 digit code to {email}.</p>
          <Field label="Code">
            <Input name="code" required inputMode="numeric" autoComplete="one-time-code" />
          </Field>
          <Field label="New password">
            <Input name="password" type="password" required minLength={10} maxLength={128} autoComplete="new-password" />
          </Field>
        </>
      )}
      <Button type="submit" className="w-full" loading={busy}>
        {step === "email" ? "Send code" : "Change password"}
      </Button>
      <Link href="/login" className="flex min-h-11 items-center justify-center text-sm font-semibold text-brand">
        Back to login
      </Link>
    </form>
  );
}
