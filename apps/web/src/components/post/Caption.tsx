import Link from "next/link";
import { parseCaption } from "@/lib/utils";

export function Caption({ text }: { text: string }) {
  return (
    <>
      {parseCaption(text).map((part, i) =>
        part.kind === "text" ? (
          <span key={i}>{part.value}</span>
        ) : (
          <Link
            key={i}
            href={part.kind === "tag" ? `/tag/${encodeURIComponent(part.value)}` : `/${part.value}`}
            className="font-medium text-brand hover:underline"
          >
            {part.kind === "tag" ? "#" : "@"}
            {part.value}
          </Link>
        ),
      )}
    </>
  );
}
