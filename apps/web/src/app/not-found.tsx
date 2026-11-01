import Link from "next/link";

export default function NotFound() {
  return (
    <div className="flex h-dvh flex-col items-center justify-center gap-3 p-6 text-center">
      <img src="/brand/logo.png" alt="" width={64} height={64} />
      <h1 className="text-xl font-bold">This page is not available</h1>
      <Link href="/feed" className="min-h-11 font-semibold text-brand">
        Back to RedStarVibe
      </Link>
    </div>
  );
}
