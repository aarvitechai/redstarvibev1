import { expect, test, type Page } from "@playwright/test";

const PASSWORD = process.env.SEED_PASSWORD ?? "RedStarDemo#2026";
const noSideScroll = (page: Page) => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth);

async function login(page: Page, username = "kabir") {
  await page.goto("/login");
  await page.getByLabel("Username or email").fill(username);
  await page.getByLabel("Password").fill(PASSWORD);
  await page.getByRole("button", { name: "Log in", exact: true }).click();
  await expect(page).toHaveURL(/\/feed/);
}

test("choosing interests fills For You, and both tabs show posts", async ({ page }) => {
  await login(page);
  await page.request.put("/api/v1/users/me/interests", {
    data: { interests: [] },
    headers: { "x-csrf-token": (await page.context().cookies()).find((c) => c.name === "rsv_csrf")?.value ?? "" },
  });
  await page.goto("/explore");
  const picker = page.getByTestId("interest-picker");
  await expect(picker).toBeVisible();
  expect(await noSideScroll(page)).toBe(true);
  await picker.getByRole("button", { name: "travel" }).click();
  await picker.getByRole("button", { name: "Done" }).click();
  await expect(picker).toHaveCount(0);
  await expect(page.locator(".grid-item").first()).toBeVisible({ timeout: 15_000 });
  await page.getByRole("tab", { name: "Latest" }).click();
  await expect(page.locator(".grid-item").first()).toBeVisible({ timeout: 15_000 });
  expect(await noSideScroll(page)).toBe(true);
});

test("a hurtful comment gets a nudge, and the person can still post it", async ({ page }) => {
  await login(page);
  await page.goto("/explore");
  await page.getByRole("tab", { name: "Latest" }).click();
  const link = page.locator('a[href^="/p/"]').first();
  await link.waitFor();
  await page.goto((await link.getAttribute("href")) as string);
  const box = page.getByLabel("Add a comment");
  await box.fill("You are an idiot");
  await page.getByRole("button", { name: "Post", exact: true }).click();
  await expect(page.getByTestId("comment-nudge")).toBeVisible();
  expect(await noSideScroll(page)).toBe(true);

  await box.fill("Lovely colours here");
  await expect(page.getByTestId("comment-nudge")).toHaveCount(0);
  await page.getByRole("button", { name: "Post", exact: true }).click();
  await expect(box).toHaveValue("");

  await box.fill("You are an idiot");
  await page.getByRole("button", { name: "Post", exact: true }).click();
  await page.getByRole("button", { name: "Post anyway" }).click();
  await expect(box).toHaveValue("");
});
