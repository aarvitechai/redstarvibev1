import type { Metadata, Viewport } from "next";
import { Providers } from "@/components/Providers";
import { ThemeBoot } from "@/components/ThemeBoot";
import "@/styles/globals.css";

export const dynamic = "force-dynamic"; // Every page carries a per request CSP nonce.

export const metadata: Metadata = {
  title: { default: "RedStarVibe", template: "%s · RedStarVibe" },
  description: "Share photos, stories and reels. Follow, chat and call.",
  manifest: "/manifest.webmanifest",
  icons: { icon: "/favicon.ico", apple: "/icons/apple-touch-icon.png" },
  appleWebApp: { capable: true, title: "RedStarVibe", statusBarStyle: "default" },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#FFFFFF" },
    { media: "(prefers-color-scheme: dark)", color: "#0B0B0F" },
  ],
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body>
        <ThemeBoot />
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
