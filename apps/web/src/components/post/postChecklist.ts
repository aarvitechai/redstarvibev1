export type ChecklistInput = { caption: string; altText: string; location: string; hasPhoto: boolean };
export type ChecklistItem = { label: string; done: boolean };

const MIN_CAPTION = 15;
const MAX_FIRST_LINE = 125;
const MAX_HASHTAGS = 8;
const HASHTAG = /#[\p{L}\p{N}_]+/gu;

/** Simple habits of a complete post. These are guidance, not a prediction of reach. */
export function postChecklist({ caption, altText, location, hasPhoto }: ChecklistInput): ChecklistItem[] {
  const text = caption.trim();
  const words = text.replace(HASHTAG, "").trim();
  const firstLine = text.split("\n")[0] ?? "";
  const hashtags = text.match(HASHTAG)?.length ?? 0;
  const items: ChecklistItem[] = [
    { label: "Caption says something", done: words.length >= MIN_CAPTION },
    { label: "First line is short and clear", done: firstLine.length > 0 && firstLine.length <= MAX_FIRST_LINE },
    { label: `1 to ${MAX_HASHTAGS} hashtags`, done: hashtags >= 1 && hashtags <= MAX_HASHTAGS },
    { label: "Location added", done: location.trim().length > 0 },
  ];
  if (hasPhoto) items.push({ label: "Image description added", done: altText.trim().length > 0 });
  return items;
}
