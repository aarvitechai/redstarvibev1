"use client";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Button, ErrorNote, Field, Input } from "@/components/ui";
import { api, errorMessage } from "@/lib/api/client";

export default function AgeCheck() {
  const [dob, setDob] = useState("");
  const [error, setError] = useState<string | null>(null);
  const router = useRouter();
  return (
    <div className="space-y-3">
      <p className="text-center text-sm text-muted">One more step: you must be at least 13 to use RedStarVibe.</p>
      <ErrorNote message={error} />
      <Field label="Date of birth">
        <Input type="date" value={dob} onChange={(e) => setDob(e.target.value)} />
      </Field>
      <Button
        className="w-full"
        disabled={!dob}
        onClick={async () => {
          try {
            await api("/auth/age", { json: { date_of_birth: dob } });
            router.replace("/feed");
          } catch (e) {
            setError(errorMessage(e));
          }
        }}
      >
        Continue
      </Button>
    </div>
  );
}
