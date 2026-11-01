export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <main className="pt-safe flex min-h-dvh flex-col items-center justify-center px-4 py-8">
      <div className="w-full max-w-sm">
        <div className="mb-6 flex flex-col items-center gap-2">
          <img src="/brand/logo.png" alt="" width={72} height={72} />
          <h1 className="text-2xl font-bold">RedStarVibe</h1>
        </div>
        {children}
      </div>
    </main>
  );
}
