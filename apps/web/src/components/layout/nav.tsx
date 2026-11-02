"use client";
import {
  Bell, Bot, Briefcase, Compass, LifeBuoy, Film, Home, MessageCircle, PlusSquare, Radio, Search, Settings, Shield, Bookmark, Users,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Avatar } from "@/components/ui";
import type { Me } from "@/lib/api/types";
import { cn } from "@/lib/utils";

type Counts = { notifications: number; messages: number };

function Badge({ count }: { count: number }) {
  if (!count) return null;
  return (
    <span className="absolute -right-1 -top-1 flex h-[18px] min-w-[18px] items-center justify-center rounded-full bg-brand px-1 text-[11px] font-bold text-white">
      {count > 99 ? "99+" : count}
    </span>
  );
}

function items(counts: Counts, me: Me) {
  return [
    { href: "/feed", label: "Home", icon: Home },
    { href: "/search", label: "Search", icon: Search },
    { href: "/explore", label: "Explore", icon: Compass },
    { href: "/reels", label: "Reels", icon: Film },
    { href: "/messages", label: "Messages", icon: MessageCircle, count: counts.messages },
    { href: "/notifications", label: "Notifications", icon: Bell, count: counts.notifications },
    { href: "/new", label: "Create", icon: PlusSquare },
    { href: "/live", label: "Live", icon: Radio },
    { href: "/communities", label: "Communities", icon: Users },
    { href: "/saved", label: "Saved", icon: Bookmark },
    { href: "/ai", label: "Vibe AI", icon: Bot },
    ...(me.permissions?.includes("moderate_first_level") ? [{ href: "/admin", label: "Admin", icon: Shield }] : []),
    ...(me.permissions?.includes("manage_business") ? [{ href: "/business-tools", label: "Business", icon: Briefcase }] : []),
    { href: "/support", label: "Support", icon: LifeBuoy },
    { href: "/settings", label: "Settings", icon: Settings },
  ];
}

const isActive = (path: string, href: string) => path === href || path.startsWith(`${href}/`);

/** Mobile, under 640 px: bottom tab bar. */
export function BottomNav({ me, counts }: { me: Me; counts: Counts }) {
  const path = usePathname();
  const tabs = [
    { href: "/feed", label: "Home", icon: Home },
    { href: "/explore", label: "Explore", icon: Compass },
    { href: "/new", label: "Create", icon: PlusSquare },
    { href: "/reels", label: "Reels", icon: Film },
  ];
  return (
    <nav aria-label="Main" className="pb-safe fixed inset-x-0 bottom-0 z-40 border-t border-line bg-bg sm:hidden">
      <ul className="flex h-14 items-center justify-around">
        {tabs.map((t) => (
          <li key={t.href}>
            <Link href={t.href} aria-label={t.label} className="flex h-12 w-12 items-center justify-center">
              <t.icon className={cn("h-6 w-6", isActive(path, t.href) && "stroke-[2.6] text-brand")} />
            </Link>
          </li>
        ))}
        <li>
          <Link href={`/${me.username}`} aria-label="Profile" className="flex h-12 w-12 items-center justify-center">
            <Avatar user={me} size={28} />
          </Link>
        </li>
      </ul>
      <span className="sr-only">{counts.notifications} unread notifications</span>
    </nav>
  );
}

/** Mobile top bar with the logo, notifications and messages. */
export function TopBar({ counts }: { counts: Counts }) {
  return (
    <header className="pt-safe sticky top-0 z-30 flex items-center justify-between border-b border-line bg-bg px-3 sm:hidden">
      <Link href="/feed" className="flex h-12 items-center gap-2 font-bold">
        <img src="/brand/logo.png" alt="" width={28} height={28} />
        RedStarVibe
      </Link>
      <div className="flex">
        <Link href="/search" aria-label="Search" className="flex h-11 w-11 items-center justify-center">
          <Search className="h-6 w-6" />
        </Link>
        <Link href="/notifications" aria-label="Notifications" className="relative flex h-11 w-11 items-center justify-center">
          <span className="relative">
            <Bell className="h-6 w-6" />
            <Badge count={counts.notifications} />
          </span>
        </Link>
        <Link href="/messages" aria-label="Messages" className="relative flex h-11 w-11 items-center justify-center">
          <span className="relative">
            <MessageCircle className="h-6 w-6" />
            <Badge count={counts.messages} />
          </span>
        </Link>
      </div>
    </header>
  );
}

/** Tablet icon rail (640 to 1023 px) and desktop full side nav (1024 px and above). */
export function SideNav({ me, counts }: { me: Me; counts: Counts }) {
  const path = usePathname();
  return (
    <nav
      aria-label="Main"
      className="sticky top-0 hidden h-dvh w-[72px] shrink-0 flex-col overflow-y-auto border-r border-line px-2 py-3 sm:flex lg:w-60 lg:px-3"
    >
      <Link href="/feed" className="mb-3 flex h-12 items-center justify-center gap-2 lg:justify-start lg:px-2">
        <img src="/brand/logo.png" alt="" width={34} height={34} />
        <span className="hidden text-lg font-bold lg:inline">RedStarVibe</span>
      </Link>
      <ul className="flex-1 space-y-0.5">
        {items(counts, me).map((item) => {
          const active = isActive(path, item.href);
          return (
            <li key={item.href}>
              <Link
                href={item.href}
                aria-label={item.label}
                aria-current={active ? "page" : undefined}
                className={cn(
                  "flex min-h-11 items-center justify-center gap-3 rounded-lg hover:bg-surface lg:justify-start lg:px-3",
                  active && "font-bold text-brand",
                )}
              >
                <span className="relative">
                  <item.icon className={cn("h-6 w-6", active && "stroke-[2.6]")} />
                  <Badge count={item.count ?? 0} />
                </span>
                <span className="hidden text-[15px] lg:inline">{item.label}</span>
              </Link>
            </li>
          );
        })}
      </ul>
      <Link href={`/${me.username}`} aria-label="Profile" className="flex min-h-11 items-center justify-center gap-3 rounded-lg hover:bg-surface lg:justify-start lg:px-3">
        <Avatar user={me} size={28} />
        <span className="hidden truncate text-[15px] lg:inline">{me.username}</span>
      </Link>
    </nav>
  );
}
