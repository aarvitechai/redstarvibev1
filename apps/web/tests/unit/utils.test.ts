import { describe, expect, it } from "vitest";
import { compactNumber, parseCaption, timeAgo } from "@/lib/utils";

describe("parseCaption", () => {
  it("splits hashtags and mentions from text", () => {
    expect(parseCaption("Hi @asha see #sunset now")).toEqual([
      { kind: "text", value: "Hi " },
      { kind: "mention", value: "asha" },
      { kind: "text", value: " see " },
      { kind: "tag", value: "sunset" },
      { kind: "text", value: " now" },
    ]);
  });
  it("does not treat an email as a mention", () => {
    expect(parseCaption("mail a@b.com")).toEqual([{ kind: "text", value: "mail a@b.com" }]);
  });
  it("supports Hindi hashtags", () => {
    expect(parseCaption("#नमस्ते")[0]?.kind).toBe("tag");
  });
});

describe("formatting", () => {
  it("compacts numbers", () => {
    expect(compactNumber(999)).toBe("999");
    expect(compactNumber(1500)).toBe("1.5K");
  });
  it("formats relative time", () => {
    const now = Date.parse("2026-11-01T12:00:00Z");
    expect(timeAgo("2026-11-01T11:59:30Z", now)).toBe("now");
    expect(timeAgo("2026-11-01T10:00:00Z", now)).toBe("2h");
  });
});
