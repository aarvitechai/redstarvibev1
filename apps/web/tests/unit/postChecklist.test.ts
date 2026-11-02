import { describe, expect, it } from "vitest";
import { postChecklist } from "@/components/post/postChecklist";

const done = (input: Parameters<typeof postChecklist>[0]) => postChecklist(input).filter((i) => i.done).length;

describe("postChecklist", () => {
  it("starts empty", () => {
    expect(done({ caption: "", altText: "", location: "", hasPhoto: true })).toBe(0);
  });

  it("passes a complete post", () => {
    const input = { caption: "Sunset over the Goa beach today\n#goa #sunset", altText: "A beach", location: "Goa", hasPhoto: true };
    expect(postChecklist(input).every((i) => i.done)).toBe(true);
  });

  it("does not count hashtags as a caption", () => {
    const [caption] = postChecklist({ caption: "#one #two #three #four #five", altText: "", location: "", hasPhoto: false });
    expect(caption?.done).toBe(false);
  });

  it("rejects too many hashtags and counts Hindi ones", () => {
    const many = Array.from({ length: 9 }, (_, i) => `#t${i}`).join(" ");
    expect(postChecklist({ caption: many, altText: "", location: "", hasPhoto: false })[2]?.done).toBe(false);
    expect(postChecklist({ caption: "#गोवा", altText: "", location: "", hasPhoto: false })[2]?.done).toBe(true);
  });

  it("only asks for an image description when there is a photo", () => {
    expect(postChecklist({ caption: "", altText: "", location: "", hasPhoto: false })).toHaveLength(4);
    expect(postChecklist({ caption: "", altText: "", location: "", hasPhoto: true })).toHaveLength(5);
  });
});
