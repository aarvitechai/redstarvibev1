import { expect, test, type Page } from "@playwright/test";
import fs from "node:fs";

const PASSWORD = process.env.SEED_PASSWORD ?? "RedStarDemo#2026";
const noSideScroll = (page: Page) => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth);

async function login(page: Page) {
  await page.goto("/login");
  await page.getByLabel("Username or email").fill("demo");
  await page.getByLabel("Password").fill(PASSWORD);
  await page.getByRole("button", { name: "Log in", exact: true }).click();
  await expect(page).toHaveURL(/\/feed/);
}

test("search page: posts, people and tags", async ({ page }) => {
  await login(page);
  await page.goto("/search");
  await page.getByRole("textbox", { name: "Search", exact: true }).fill("sunset");
  await expect(page.locator(".grid-item").first()).toBeVisible({ timeout: 15_000 });
  expect(await noSideScroll(page)).toBe(true);

  await page.getByRole("tab", { name: "Tags" }).click();
  await expect(page.getByRole("link", { name: /#sunset/ })).toBeVisible();

  await page.getByRole("textbox", { name: "Search", exact: true }).fill("deem");
  await page.getByRole("tab", { name: "People" }).click();
  await expect(page.getByRole("link", { name: /demo/ }).first()).toBeVisible();
  expect(await noSideScroll(page)).toBe(true);
});

test("header search box suggests people and tags", async ({ page }, info) => {
  test.skip(info.project.name !== "desktop-1280", "the box shows on wide screens");
  await login(page);
  await page.getByRole("textbox", { name: "Quick search" }).fill("trav");
  await expect(page.getByTestId("search-suggestions").getByText("travel")).toBeVisible();
  await page.getByRole("textbox", { name: "Quick search" }).press("Enter");
  await expect(page).toHaveURL(/\/search\?q=trav/);
});

test("composer shows what AI can do, and never blocks sharing", async ({ page }) => {
  test.setTimeout(420_000);
  await login(page);
  const features = await (await page.request.get("/api/v1/ai/features")).json();
  await page.goto("/new");
  if (!features.writing) await expect(page.getByRole("group", { name: "Improve caption" })).toHaveCount(0);
  else {
    await page.getByLabel("Caption").fill("nice view from the hill today");
    await page.getByRole("button", { name: "Short", exact: true }).click();
    await expect(page.getByTestId("rewrite-preview").getByRole("button", { name: "Use this" })).toBeVisible({ timeout: 30_000 });
    await page.getByRole("button", { name: "Use this" }).click();
    expect(await page.getByLabel("Caption").inputValue()).not.toBe("nice view from the hill today");
  }

  await page.getByTestId("file-input").setInputFiles({ name: "photo.jpg", mimeType: "image/jpeg", buffer: fs.readFileSync("public/home/banner-poster.jpg") });
  await expect(page.getByRole("button", { name: "Share" })).toBeEnabled({ timeout: 30_000 });
  if (!features.captions) {
    await expect(page.getByTestId("ai-suggestions")).toHaveCount(0);
    return;
  }
  await expect(page.getByTestId("ai-suggestions")).toBeVisible({ timeout: 300_000 });
  await page.getByTestId("ai-suggestions").getByRole("button").first().click();
  expect((await page.getByLabel("Caption").inputValue()).length).toBeGreaterThan(0);
  await page.getByRole("button", { name: /Use AI tagline/ }).click();
  await expect(page.getByTestId("text-overlay-preview")).toBeVisible();
  expect(await noSideScroll(page)).toBe(true);
});
