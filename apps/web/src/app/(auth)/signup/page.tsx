"use client";
import { standardSchemaResolver } from "@hookform/resolvers/standard-schema";
import { useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod/mini";
import { Button, ErrorNote, Field, Input } from "@/components/ui";
import { api, errorMessage } from "@/lib/api/client";
import type { Me } from "@/lib/api/types";

const schema = z.object({
  email: z.string().check(z.email("Enter a valid email")),
  username: z.string().check(z.regex(/^[a-zA-Z0-9_.]{3,30}$/, "3 to 30 letters, numbers, _ or .")),
  display_name: z.optional(z.string().check(z.maxLength(80))),
  password: z.string().check(z.minLength(10, "Use at least 10 characters")),
  date_of_birth: z.string().check(z.minLength(1, "Enter your date of birth")),
});
type Form = z.infer<typeof schema>;

function Signup() {
  const params = useSearchParams();
  const initial = params.get("verify");
  const router = useRouter();
  const qc = useQueryClient();
  const [email, setEmail] = useState(initial ?? "");
  const [step, setStep] = useState<"form" | "verify">(params.has("verify") ? "verify" : "form");
  const [code, setCode] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const { register, handleSubmit, formState } = useForm<Form>({ resolver: standardSchemaResolver(schema) });

  const submit = async (data: Form) => {
    setError(null);
    try {
      await api("/auth/signup", { json: data });
      setEmail(data.email);
      setStep("verify");
    } catch (e) {
      setError(errorMessage(e));
    }
  };

  if (step === "verify") {
    return (
      <form
        className="space-y-3"
        onSubmit={async (e) => {
          e.preventDefault();
          setBusy(true);
          setError(null);
          try {
            qc.setQueryData(["me"], await api<Me>("/auth/verify-email", { json: { email, code } }));
            router.replace("/feed");
          } catch (err) {
            setError(errorMessage(err));
          } finally {
            setBusy(false);
          }
        }}
      >
        <p className="text-center text-sm text-muted">We sent a 6 digit code to your email.</p>
        <ErrorNote message={error} />
        {notice && <p className="text-center text-sm text-muted">{notice}</p>}
        <Field label="Email">
          <Input type="email" value={email} onChange={(e) => setEmail(e.target.value)} />
        </Field>
        <Field label="Code">
          <Input inputMode="numeric" autoComplete="one-time-code" maxLength={6} autoFocus value={code} onChange={(e) => setCode(e.target.value)} />
        </Field>
        <Button type="submit" className="w-full" loading={busy}>
          Verify and continue
        </Button>
        <Button
          type="button"
          variant="ghost"
          className="w-full"
          onClick={async () => {
            await api("/auth/resend-otp", { json: { email } }).catch(() => undefined);
            setNotice("If that account needs verifying, a new code is on its way.");
          }}
        >
          Send a new code
        </Button>
      </form>
    );
  }

  return (
    <form onSubmit={handleSubmit(submit)} className="space-y-3">
      <ErrorNote message={error} />
      <Field label="Email" error={formState.errors.email?.message}>
        <Input type="email" autoComplete="email" {...register("email")} />
      </Field>
      <Field label="Username" error={formState.errors.username?.message}>
        <Input autoComplete="username" autoCapitalize="none" {...register("username")} />
      </Field>
      <Field label="Name (optional)">
        <Input autoComplete="name" {...register("display_name")} />
      </Field>
      <Field label="Password" error={formState.errors.password?.message}>
        <Input type="password" autoComplete="new-password" {...register("password")} />
      </Field>
      <Field label="Date of birth (you must be at least 13)" error={formState.errors.date_of_birth?.message}>
        <Input type="date" autoComplete="bday" {...register("date_of_birth")} />
      </Field>
      <Button type="submit" className="w-full" loading={formState.isSubmitting}>
        Sign up
      </Button>
      <p className="pt-2 text-center text-sm text-muted">
        Have an account?{" "}
        <Link href="/login" className="font-semibold text-brand">
          Log in
        </Link>
      </p>
    </form>
  );
}

export default function SignupPage() {
  return (
    <Suspense>
      <Signup />
    </Suspense>
  );
}
