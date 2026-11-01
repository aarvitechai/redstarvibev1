export default function Offline() {
  return (
    <div className="flex h-dvh flex-col items-center justify-center gap-3 p-6 text-center">
      <img src="/brand/logo.png" alt="RedStarVibe" width={72} height={72} />
      <h1 className="text-xl font-bold">You are offline</h1>
      <p className="text-sm text-muted">Reconnect to see the latest posts.</p>
    </div>
  );
}
