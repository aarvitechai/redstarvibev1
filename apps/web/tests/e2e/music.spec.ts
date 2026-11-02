import { expect, test, type Page } from "@playwright/test";
import fs from "node:fs";

const PASSWORD = process.env.SEED_PASSWORD ?? "RedStarDemo#2026";
const noSideScroll = (page: Page) => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth);

async function login(page: Page, username = "asha") {
  await page.goto("/login");
  await page.getByLabel("Username or email").fill(username);
  await page.getByLabel("Password").fill(PASSWORD);
  await page.getByRole("button", { name: "Log in", exact: true }).click();
  await expect(page).toHaveURL(/\/feed/);
}

const upload = (page: Page) =>
  page.getByTestId("file-input").setInputFiles({ name: "photo.jpg", mimeType: "image/jpeg", buffer: fs.readFileSync("public/home/banner-poster.jpg") });

test("a post with music and animated text plays the music after a tap", async ({ page }) => {
  test.setTimeout(120_000);
  await login(page);
  await page.goto("/new");
  await upload(page);
  await page.getByRole("button", { name: /^Festival/ }).click();
  await page.getByLabel("Text on photo").fill("Festival nights");
  await page.getByRole("group", { name: "Text animation" }).getByRole("button", { name: "Pop" }).click();
  await expect(page.getByTestId("text-overlay-preview")).toHaveCSS("animation-name", "text-pop");
  expect(await noSideScroll(page)).toBe(true);
  await expect(page.getByRole("button", { name: "Share" })).toBeEnabled({ timeout: 60_000 });
  await page.getByRole("button", { name: "Share" }).click();
  await expect(page).toHaveURL(/\/p\//, { timeout: 30_000 });

  const chip = page.getByTestId("post-music");
  await expect(chip).toContainText("Festival");
  await expect(page.getByTestId("text-overlay")).toHaveCSS("animation-name", "text-pop");
  await chip.click();
  await expect.poll(() => page.locator("article audio").evaluate((a: HTMLAudioElement) => !a.paused && a.currentTime > 0), { timeout: 10_000 }).toBe(true);
  expect(await noSideScroll(page)).toBe(true);

  await page.locator("article").getByRole("button", { name: "More options" }).click();
  await page.getByRole("button", { name: "Delete post" }).click();
  await expect(page).toHaveURL(/\/feed/);
});

test("staff see why AI is off", async ({ page }) => {
  await login(page, "demo");
  await page.goto("/new");
  await upload(page);
  await expect(page.getByTestId("ai-off")).toBeVisible();
});

test("normal people do not see the AI setup note", async ({ page }) => {
  await login(page);
  await page.goto("/new");
  await upload(page);
  await expect(page.getByRole("region", { name: "Music" })).toBeVisible();
  await expect(page.getByTestId("ai-off")).toHaveCount(0);
});

test("make it effective fills what is empty and keeps what was written", async ({ page }) => {
  await page.route("**/api/v1/ai/features", (r) => r.fulfill({ json: { semantic_search: false, writing: false, captions: true } }));
  await page.route("**/api/v1/ai/captions/*", (r) =>
    r.fulfill({ json: { status: "ready", captions: ["A quiet red sky over the fort"], tagline: "Red sky nights", hashtags: ["fort", "sunset"], alt_text: "A fort under a red sky", music: "sunrise" } }),
  );
  await login(page);
  await page.goto("/new");
  await upload(page);
  await page.getByLabel("Caption").fill("My own words");
  await page.getByRole("button", { name: "Make it effective with AI" }).click({ timeout: 60_000 });
  await expect(page.getByLabel("Caption")).toHaveValue("My own words #fort #sunset");
  await expect(page.getByLabel("Image description for screen readers")).toHaveValue("A fort under a red sky");
  await expect(page.getByTestId("text-overlay-preview")).toHaveText("Red sky nights");
  await expect(page.getByTestId("text-overlay-preview")).toHaveCSS("animation-name", "text-pop");
  await expect(page.getByRole("button", { name: /^Sunrise/ })).toHaveAttribute("aria-pressed", "true");
  expect(await noSideScroll(page)).toBe(true);
});
