import { expect, test, type Page } from "@playwright/test";

const PASSWORD = process.env.SEED_PASSWORD ?? "RedStarDemo#2026";

async function login(page: Page, username = "demo") {
  await page.goto("/login");
  await page.getByLabel("Username or email").fill(username);
  await page.getByLabel("Password").fill(PASSWORD);
  await page.getByRole("button", { name: "Log in", exact: true }).click();
  await expect(page).toHaveURL(/\/feed/);
}

test("login page shows the logo", async ({ page }) => {
  await page.goto("/login");
  const logo = page.locator('img[src="/brand/logo.png"]');
  await expect(logo).toBeVisible();
  expect(await logo.evaluate((i: HTMLImageElement) => i.naturalWidth)).toBeGreaterThan(0);
});

test("feed renders posts, images load, no horizontal scroll", async ({ page }) => {
  const errors: string[] = [];
  page.on("console", (m) => m.type() === "error" && errors.push(m.text()));
  await login(page);
  const post = page.locator("article").first();
  await expect(post).toBeVisible();
  const img = post.locator("picture img").first();
  await expect.poll(() => img.evaluate((i: HTMLImageElement) => i.complete && i.naturalWidth)).toBeGreaterThan(0);
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(overflow).toBeLessThanOrEqual(0);
  expect(errors.filter((e) => /Content Security Policy|hydrat/i.test(e))).toEqual([]);
});

test("layout follows the breakpoint", async ({ page }, info) => {
  await login(page);
  const width = page.viewportSize()!.width;
  const bottom = page.locator("nav.fixed.bottom-0");
  if (width < 640) await expect(bottom).toBeVisible();
  else await expect(bottom).toBeHidden();
  if (width >= 1024) await expect(page.getByRole("link", { name: "Explore" }).first()).toContainText("Explore");
  await page.screenshot({ path: `test-results/feed-${info.project.name}.png` });
});

test("like updates optimistically and persists", async ({ page }) => {
  await login(page);
  const post = page.locator("article").first();
  const button = post.getByRole("button", { name: /^(Like|Unlike)$/ });
  const before = await button.getAttribute("aria-pressed");
  await button.click();
  await expect(button).toHaveAttribute("aria-pressed", before === "true" ? "false" : "true");
  await page.waitForTimeout(500);
  await page.reload();
  await expect(page.locator("article").first().getByRole("button", { name: /^(Like|Unlike)$/ })).toHaveAttribute(
    "aria-pressed",
    before === "true" ? "false" : "true",
  );
});

test("touch targets on the mobile nav are at least 44 px", async ({ page }) => {
  await login(page);
  test.skip(page.viewportSize()!.width >= 640, "mobile only");
  for (const link of await page.locator("nav.fixed.bottom-0 a").all()) {
    const box = (await link.boundingBox())!;
    expect(box.height).toBeGreaterThanOrEqual(44);
    expect(box.width).toBeGreaterThanOrEqual(44);
  }
});

test("search finds a user and a profile opens", async ({ page }) => {
  await login(page);
  await page.goto("/search");
  await page.getByRole("textbox", { name: "Search" }).fill("asha");
  await page.getByRole("link", { name: /asha/ }).first().click();
  await expect(page.getByRole("heading", { name: "asha" })).toBeVisible();
});

test("key pages load", async ({ page }) => {
  await login(page);
  for (const path of ["/explore", "/reels", "/messages", "/notifications", "/saved", "/settings", "/new", "/live", "/ai", "/admin"]) {
    const res = await page.goto(path);
    expect(res?.status(), path).toBe(200);
    await expect(page.locator("main").first()).toBeVisible();
  }
});
