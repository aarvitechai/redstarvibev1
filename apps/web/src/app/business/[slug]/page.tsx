import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { BUSINESSES } from "@/components/home/businesses";
import { SiteFooter, SiteHeader } from "@/components/home/SiteHeader";

type Props = { params: Promise<{ slug: string }> };

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { slug } = await params;
  const business = BUSINESSES.find((b) => b.slug === slug);
  return business ? { title: business.name, description: business.intro } : {};
}

export default async function BusinessPage({ params }: Props) {
  const { slug } = await params;
  const business = BUSINESSES.find((b) => b.slug === slug);
  if (!business) notFound();
  return (
    <>
      <SiteHeader />
      <main>
        <section className="mx-auto grid max-w-6xl items-center gap-8 px-4 py-10 lg:grid-cols-2 lg:py-16">
          <div>
            <p className="text-sm font-semibold text-brand">{business.name}</p>
            <h1 className="mt-2 text-4xl font-extrabold leading-tight sm:text-5xl">{business.tagline}</h1>
            <p className="mt-4 text-lg text-muted">{business.intro}</p>
            <Link href="/signup" className="mt-6 inline-flex min-h-12 items-center rounded-lg bg-brand px-6 font-semibold text-white hover:bg-brand-dark">
              Get started free
            </Link>
          </div>
          <img src={business.image} alt="" width={800} height={600} className="w-full rounded-2xl shadow-xl" />
        </section>
        <section aria-label="Ways to use RedStarVibe" className="mx-auto grid max-w-6xl gap-4 px-4 pb-12 sm:grid-cols-3">
          {business.ideas.map(([title, text]) => (
            <div key={title} className="rounded-2xl bg-surface p-5">
              <h2 className="font-semibold">{title}</h2>
              <p className="mt-1 text-sm text-muted">{text}</p>
            </div>
          ))}
        </section>
        <section aria-labelledby="others" className="mx-auto max-w-6xl px-4 pb-14">
          <h2 id="others" className="text-xl font-bold">Other business types</h2>
          <ul className="mt-3 flex flex-wrap gap-2">
            {BUSINESSES.filter((b) => b.slug !== business.slug).map((b) => (
              <li key={b.slug}>
                <Link href={`/business/${b.slug}`} className="flex min-h-11 items-center rounded-full bg-surface px-4 text-sm font-medium hover:bg-line">
                  {b.name}
                </Link>
              </li>
            ))}
          </ul>
        </section>
      </main>
      <SiteFooter />
    </>
  );
}
