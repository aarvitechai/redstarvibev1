import { ChevronDown } from "lucide-react";
import { cookies } from "next/headers";
import Link from "next/link";
import { BUSINESSES } from "./businesses";

/** Server rendered. The menu is a native <details>, so it works without any page JavaScript. */
export async function SiteHeader() {
  // Only decides which button to show. Real access is still checked by the API.
  const signedIn = (await cookies()).has("rsv_csrf");
  return (
    <header className="pt-safe sticky top-0 z-40 border-b border-line bg-bg/95 backdrop-blur">
      <div className="mx-auto flex h-16 max-w-6xl items-center gap-2 px-4">
        <Link href="/" className="flex min-h-11 items-center gap-2 font-bold">
          <img src="/brand/logo.png" alt="" width={34} height={34} />
          <span className="hidden min-[400px]:inline">RedStarVibe</span>
        </Link>
        <details className="group relative ml-1 sm:ml-4">
          <summary className="flex min-h-11 cursor-pointer list-none items-center gap-1 rounded-lg px-2 text-sm font-semibold hover:bg-surface [&::-webkit-details-marker]:hidden">
            For business <ChevronDown className="h-4 w-4 transition-transform group-open:rotate-180" />
          </summary>
          <ul className="fixed inset-x-3 top-[4.25rem] grid gap-1 rounded-2xl border border-line bg-bg p-2 shadow-xl sm:absolute sm:inset-x-auto sm:left-0 sm:top-full sm:mt-2 sm:w-[30rem] sm:grid-cols-2">
            {BUSINESSES.map((b) => (
              <li key={b.slug}>
                <Link href={`/business/${b.slug}`} className="flex min-h-12 items-center gap-3 rounded-lg p-1.5 text-sm font-medium hover:bg-surface">
                  <img src={b.image} alt="" width={44} height={33} className="rounded-md" />
                  {b.name}
                </Link>
              </li>
            ))}
          </ul>
        </details>
        <nav aria-label="Account" className="ml-auto flex items-center gap-1 sm:gap-2">
          {signedIn ? (
            <Link href="/feed" className="flex min-h-11 items-center rounded-lg bg-brand px-4 text-sm font-semibold text-white hover:bg-brand-dark">
              Open app
            </Link>
          ) : (
            <>
              <Link href="/login" className="flex min-h-11 items-center rounded-lg px-2 text-sm font-semibold hover:bg-surface sm:px-3">
                Log in
              </Link>
              <Link href="/signup" className="flex min-h-11 items-center whitespace-nowrap rounded-lg bg-brand px-3 text-sm font-semibold text-white hover:bg-brand-dark sm:px-4">
                Sign up
              </Link>
            </>
          )}
        </nav>
      </div>
    </header>
  );
}

export function SiteFooter() {
  return (
    <footer className="border-t border-line px-4 py-8 text-center text-sm text-muted">
      <img src="/brand/logo.png" alt="" width={36} height={36} className="mx-auto mb-2" />
      RedStarVibe. Share, connect and grow.
    </footer>
  );
}
