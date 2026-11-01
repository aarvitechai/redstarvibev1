"use client";
import { useParams } from "next/navigation";
import { InfiniteGrid } from "@/components/post/InfiniteGrid";

export default function PlacePage() {
  const place = decodeURIComponent(useParams<{ place: string }>().place);
  return (
    <div className="mx-auto max-w-4xl sm:p-4">
      <h1 className="p-3 text-xl font-bold">{place}</h1>
      <InfiniteGrid queryKey={["place", place]} path={`/places/${encodeURIComponent(place)}/posts`} emptyTitle="No posts from this place" />
    </div>
  );
}
