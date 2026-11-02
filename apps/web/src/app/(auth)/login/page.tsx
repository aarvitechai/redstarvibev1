"use client";
import { standardSchemaResolver } from "@hookform/resolvers/standard-schema";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod/mini";
import { Button, ErrorNote, Field, Input } from "@/components/ui";
import { api, ApiError, errorMessage } from "@/lib/api/client";
import type { Me } from "@/lib/api/types";

const schema = z.object({
  identifier: z.string().check(z.minLength(3, "Enter your username or email")),
  password: z.string().check(z.minLength(1, "Enter your password")),
  totp_code: z.optional(z.string()),
});
type Form = z.infer<typeof schema>;

export default function LoginPage() {
  const router = useRouter();
  const qc = useQueryClient();
  const [error, setError] = useState<string | null>(null);
  const [needsMfa, setNeedsMfa] = useState(false);
  const [otpMode, setOtpMode] = useState<"off" | "email" | "code">("off");
  const [email, setEmail] = useState("");
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const providers = useQuery({ queryKey: ["providers"], queryFn: () => api<{ google: boolean }>("/auth/providers") });
  const { register, handleSubmit, getValues, formState } = useForm<Form>({ resolver: standardSchemaResolver(schema) });

  const finish = (me: Me) => {
    qc.setQueryData(["me"], me);
    router.replace("/feed");
  };
  const submit = async (data: Form) => {
    setError(null);
    try {
      finish(await api<Me>("/auth/login", { json: { ...data, totp_code: data.totp_code || null } }));
    } catch (e) {
      if (e instanceof ApiError && e.code === "mfa_required") setNeedsMfa(true);
      else if (e instanceof ApiError && e.code === "email_unverified") {
        const id = getValues("identifier");
        router.push(`/signup?verify=${encodeURIComponent(id.includes("@") ? id : "")}`);
      } else setError(errorMessage(e));
    }
  };

  if (otpMode !== "off") {
    return (
      <div className="space-y-3">
        <ErrorNote message={error} />
        <Field label="Email">
          <Input type="email" autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} />
        </Field>
        {otpMode === "code" && (
          <Field label="6 digit code">
            <Input inputMode="numeric" autoComplete="one-time-code" maxLength={6} value={code} onChange={(e) => setCode(e.target.value)} />
          </Field>
        )}
        <Button
          className="w-full"
          loading={busy}
          onClick={async () => {
            setBusy(true);
            setError(null);
            try {
              if (otpMode === "email") {
                await api("/auth/otp/request", { json: { email } });
                setOtpMode("code");
              } else finish(await api<Me>("/auth/otp/login", { json: { email, code } }));
            } catch (e) {
              setError(errorMessage(e));
            } finally {
              setBusy(false);
            }
          }}
        >
          {otpMode === "email" ? "Email me a code" : "Log in"}
        </Button>
        <Button variant="ghost" className="w-full" onClick={() => setOtpMode("off")}>
          Use my password instead
        </Button>
      </div>
    );
  }

  return (
    <form onSubmit={handleSubmit(submit)} className="space-y-3">
      <ErrorNote message={error} />
      <Field label="Username or email" error={formState.errors.identifier?.message}>
        <Input autoComplete="username" autoCapitalize="none" {...register("identifier")} />
      </Field>
      <Field label="Password" error={formState.errors.password?.message}>
        <Input type="password" autoComplete="current-password" {...register("password")} />
      </Field>
      {needsMfa && (
        <Field label="Authenticator code">
          <Input inputMode="numeric" autoComplete="one-time-code" autoFocus {...register("totp_code")} />
        </Field>
      )}
      <Button type="submit" className="w-full" loading={formState.isSubmitting}>
        Log in
      </Button>
      <Link href="/forgot-password" className="flex min-h-11 items-center justify-center text-sm font-semibold text-brand">
        Forgot password?
      </Link>
      <Button type="button" variant="secondary" className="w-full" onClick={() => setOtpMode("email")}>
        Log in with an email code
      </Button>
      {providers.data?.google && (
        <a href="/api/v1/auth/google/login" className="flex min-h-11 items-center justify-center rounded-lg bg-surface text-sm font-semibold hover:bg-line">
          Continue with Google
        </a>
      )}
      <p className="pt-2 text-center text-sm text-muted">
        New here?{" "}
        <Link href="/signup" className="font-semibold text-brand">
          Create an account
        </Link>
      </p>
    </form>
  );
}
