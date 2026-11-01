import { expect, test } from "@playwright/test";

test("homepage is public: banner, business menu, images and videos work without login", async ({ page }, info) => {
  const errors: string[] = [];
  page.on("console", (m) => m.type() === "error" && errors.push(m.text()));
  await page.goto("/");
  await expect(page).toHaveURL(/\/$/);
  await expect(page.getByRole("heading", { level: 1 })).toContainText("Bring your business");

  const banner = page.getByTestId("banner-video");
  await expect.poll(() => banner.evaluate((v: HTMLVideoElement) => v.currentTime), { timeout: 15_000 }).toBeGreaterThan(0);

  const cards = page.locator("#businesses li img");
  await expect(cards).toHaveCount(8);
  for (const img of await cards.all()) {
    await img.scrollIntoViewIfNeeded();
    await expect.poll(() => img.evaluate((i: HTMLImageElement) => i.naturalWidth)).toBeGreaterThan(0);
  }

  const explainer = page.getByTestId("explainer-video");
  await explainer.scrollIntoViewIfNeeded();
  await explainer.evaluate((v: HTMLVideoElement) => v.play());
  await expect.poll(() => explainer.evaluate((v: HTMLVideoElement) => v.currentTime), { timeout: 15_000 }).toBeGreaterThan(0);

  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(overflow).toBeLessThanOrEqual(0);
  expect(errors).toEqual([]);

  await page.evaluate(() => scrollTo(0, 0));
  await page.waitForTimeout(600);
  await page.screenshot({ path: `test-results/home-${info.project.name}.png` });
  await page.screenshot({ path: `test-results/home-full-${info.project.name}.png`, fullPage: true });
});

test("business menu opens a public page for that business type", async ({ page }, info) => {
  await page.goto("/");
  await page.getByText("For business").click();
  await page.screenshot({ path: `test-results/menu-${info.project.name}.png` });
  await page.locator("header").getByRole("link", { name: "Restaurants & Cafes" }).click();
  await expect(page).toHaveURL(/\/business\/food/);
  await expect(page.getByRole("heading", { level: 1 })).toContainText("hungry");
  await page.getByRole("link", { name: "Get started free" }).click();
  await expect(page).toHaveURL(/\/signup/);
});

test("an unknown business type is a 404", async ({ page }) => {
  expect((await page.goto("/business/nope"))?.status()).toBe(404);
});
