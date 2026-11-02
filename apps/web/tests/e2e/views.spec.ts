import { expect, test, type Browser, type Page } from "@playwright/test";

async function publicPhotoPost(page: Page): Promise<string> {
  const res = await page.request.get("/api/v1/explore?limit=24");
  const items: { id: string; is_reel: boolean; media: { kind: string }[] }[] = (await res.json()).items;
  const post = items.find((p) => !p.is_reel && p.media[0]?.kind === "image");
  expect(post, "needs a public photo post").toBeTruthy();
  return post!.id;
}

const count = async (page: Page, id: string): Promise<number> =>
  (await (await page.request.get(`/api/v1/posts/${id}`)).json()).view_count;

async function visit(browser: Browser, id: string): Promise<void> {
  const context = await browser.newContext();
  const page = await context.newPage();
  await page.goto(`/p/${id}`);
  await expect(page.locator("article").getByText(/\d+ views?/)).toBeVisible();
  await page.waitForTimeout(1500);
  await context.close();
}

test("views show on a post, and a visitor counts once per browser", async ({ page, browser }, info) => {
  test.skip(info.project.name !== "desktop-1280", "once is enough");
  const id = await publicPhotoPost(page);
  const start = await count(page, id);

  await page.goto(`/p/${id}`);
  await expect(page.locator("article").getByText(/\d+ views?/)).toBeVisible();
  await expect.poll(() => count(page, id), { timeout: 8000 }).toBe(start + 1);
  const cookies = await page.context().cookies();
  expect(cookies.find((c) => c.name === "rsv_visitor")?.httpOnly).toBe(true);

  await page.reload();
  await page.waitForTimeout(1500);
  expect(await count(page, id)).toBe(start + 1);
  await expect(page.locator("article").getByText(`${start + 1} view`)).toBeVisible();

  await visit(browser, id); // a different browser is a different visitor
  await expect.poll(() => count(page, id), { timeout: 8000 }).toBe(start + 2);
});

test("view count fits on small screens", async ({ page }) => {
  const id = await publicPhotoPost(page);
  await page.goto(`/p/${id}`);
  await expect(page.locator("article").getByText(/\d+ views?/)).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
});
