import type { Metadata } from "next";
import { Compass, MessageCircle, Video } from "lucide-react";
import Link from "next/link";
import { BannerVideo } from "@/components/home/BannerVideo";
import { BUSINESSES } from "@/components/home/businesses";
import { SiteFooter, SiteHeader } from "@/components/home/SiteHeader";

export const metadata: Metadata = {
  title: { absolute: "RedStarVibe: where people and businesses connect" },
  description: "Share photos, reels and stories, get discovered, and talk to customers with chat and calls.",
};

const FEATURES = [
  { icon: Compass, title: "Get discovered", text: "Hashtags, places and Explore put your work in front of new people." },
  { icon: Video, title: "Show, do not tell", text: "Reels, stories and live video show what you do better than words." },
  { icon: MessageCircle, title: "Talk directly", text: "Messages, audio calls and video calls, all in one app." },
];

export default async function HomePage() {
  return (
    <>
      <SiteHeader />
      <main>
        <section aria-labelledby="banner-title" className="relative flex min-h-[70dvh] items-center overflow-hidden bg-[#2a0610] text-white">
          <BannerVideo />
          <div aria-hidden className="pointer-events-none absolute inset-0 bg-gradient-to-r from-black/80 via-black/55 to-transparent" />
          <div className="relative mx-auto w-full max-w-6xl px-4 py-16">
            <h1 id="banner-title" className="max-w-2xl text-4xl font-extrabold leading-tight sm:text-6xl">
              Bring your business to where people connect
            </h1>
            <p className="mt-4 max-w-xl text-lg text-white/90">
              Share photos, reels and stories. Get discovered. Talk to customers with chat and calls.
            </p>
            <div className="mt-8 flex flex-wrap gap-3">
              <Link href="/signup" className="flex min-h-12 items-center rounded-lg bg-brand px-6 font-semibold text-white hover:bg-brand-dark">
                Get started free
              </Link>
              <a href="#businesses" className="flex min-h-12 items-center rounded-lg bg-white px-6 font-semibold text-[#111111] hover:bg-white/90">
                Find your business type
              </a>
            </div>
          </div>
        </section>

        <section id="businesses" aria-labelledby="businesses-title" className="mx-auto max-w-6xl scroll-mt-16 px-4 py-14">
          <h2 id="businesses-title" className="text-3xl font-bold">Built for every kind of business</h2>
          <p className="mt-2 text-muted">Choose yours to see how it can work for you.</p>
          <ul className="mt-8 grid grid-cols-2 gap-3 sm:gap-5 lg:grid-cols-4">
            {BUSINESSES.map((b) => (
              <li key={b.slug}>
                <Link href={`/business/${b.slug}`} className="group block overflow-hidden rounded-2xl border border-line bg-bg transition-shadow hover:shadow-xl">
                  <span className="block aspect-[4/3] overflow-hidden">
                    <img src={b.image} alt="" width={800} height={600} loading="lazy" className="h-full w-full object-cover transition-transform duration-300 group-hover:scale-105" />
                  </span>
                  <span className="block p-3 sm:p-4">
                    <span className="block font-semibold">{b.name}</span>
                    <span className="mt-1 hidden text-sm text-muted sm:block">{b.tagline}</span>
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        </section>

        <section aria-labelledby="video-title" className="bg-surface px-4 py-14">
          <div className="mx-auto max-w-4xl">
            <h2 id="video-title" className="text-center text-3xl font-bold">See how it works</h2>
            <p className="mb-6 mt-2 text-center text-muted">Three simple steps, in 16 seconds.</p>
            <video
              data-testid="explainer-video"
              controls
              playsInline
              preload="metadata"
              poster="/home/explainer-poster.jpg"
              src="/home/explainer.mp4"
              aria-label="Show what you do, get discovered, and talk to customers. This video has no sound."
              className="aspect-video w-full rounded-2xl bg-black shadow-xl"
            />
          </div>
        </section>

        <section aria-label="Features" className="mx-auto grid max-w-6xl gap-6 px-4 py-14 sm:grid-cols-3">
          {FEATURES.map((f) => (
            <div key={f.title}>
              <f.icon className="h-8 w-8 text-brand" aria-hidden />
              <h3 className="mt-3 text-lg font-semibold">{f.title}</h3>
              <p className="mt-1 text-sm text-muted">{f.text}</p>
            </div>
          ))}
        </section>

        <section className="px-4 pb-14 text-center">
          <h2 className="text-2xl font-bold">Ready to start?</h2>
          <Link href="/signup" className="mt-4 inline-flex min-h-12 items-center rounded-lg bg-brand px-6 font-semibold text-white hover:bg-brand-dark">
            Create your free account
          </Link>
        </section>
      </main>
      <SiteFooter />
    </>
  );
}
