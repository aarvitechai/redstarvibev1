import type { Asset } from "@/lib/api/types";

/** Pre-sized AVIF and WebP from the media worker, responsive sizes, colour placeholder to avoid layout shift. */
export function MediaImage({
  asset,
  sizes,
  className,
  priority,
  alt,
}: {
  asset: Asset;
  sizes: string;
  className?: string;
  priority?: boolean;
  alt?: string;
}) {
  const images = asset.images ?? [];
  const biggest = images[images.length - 1];
  const fallback = biggest?.webp ?? asset.poster ?? "";
  const avif = images.filter((i) => i.avif).map((i) => `${i.avif} ${i.w}w`).join(", ");
  const webp = images.map((i) => `${i.webp} ${i.w}w`).join(", ");
  return (
    <picture>
      {avif && <source type="image/avif" srcSet={avif} sizes={sizes} />}
      {webp && <source type="image/webp" srcSet={webp} sizes={sizes} />}
      <img
        src={fallback}
        alt={alt ?? asset.alt_text ?? ""}
        loading={priority ? "eager" : "lazy"}
        fetchPriority={priority ? "high" : "auto"}
        decoding="async"
        width={asset.width ?? undefined}
        height={asset.height ?? undefined}
        style={{ backgroundColor: asset.placeholder ?? undefined }}
        className={className}
      />
    </picture>
  );
}
