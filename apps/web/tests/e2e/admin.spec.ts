import { expect, test, type Page } from "@playwright/test";

const PASSWORD = process.env.SEED_PASSWORD ?? "RedStarDemo#2026";
const OWNER_PASSWORD = process.env.OWNER_PASSWORD ?? PASSWORD;

async function login(page: Page, username: string, password = PASSWORD) {
  await page.goto("/login");
  await page.getByLabel("Username or email").fill(username);
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: "Log in", exact: true }).click();
  await expect(page).toHaveURL(/\/feed/);
}

test.describe.configure({ mode: "serial" });

test("an admin adds test data, sees it in the app, then removes it", async ({ page }, info) => {
  test.skip(info.project.name !== "desktop-1280", "once is enough");
  await login(page, "demo");
  await page.goto("/admin");
  await page.getByRole("tab", { name: "Test data" }).click();
  await expect(page.getByRole("tab", { name: "Admins" })).toHaveCount(0); // admins do not manage roles
  const label = `e2e ${Date.now()}`;
  await page.getByLabel("Name for this batch").fill(label);
  await page.getByRole("spinbutton", { name: /^Accounts/ }).fill("3");
  await page.getByRole("spinbutton", { name: /^Posts per account/ }).fill("1");
  await page.getByRole("spinbutton", { name: /^Reels/ }).fill("1");
  await page.getByRole("spinbutton", { name: /^Stories/ }).fill("1");
  await page.getByRole("button", { name: "Add test data" }).click();
  const batch = page.getByTestId("batch").filter({ hasText: label });
  await expect(batch).toContainText("Live", { timeout: 80_000 });
  await expect(batch).toContainText("3 accounts · 4 posts");
  await page.screenshot({ path: "test-results/admin-test-data.png" });

  const found = await page.evaluate(async () => (await (await fetch("/api/v1/search?q=test_")).json()).users.length);
  expect(found).toBeGreaterThanOrEqual(3);
  const reels = await page.evaluate(async () => (await (await fetch("/api/v1/reels")).json()).items.length);
  expect(reels).toBeGreaterThan(0);

  await batch.getByRole("button", { name: "Remove" }).click();
  await page.getByRole("button", { name: "Yes, remove" }).click();
  await expect(batch).toContainText("Removed", { timeout: 60_000 });
  const left = await page.evaluate(async () => (await (await fetch("/api/v1/search?q=test_")).json()).users.length);
  expect(left).toBe(found - 3);
});

test("a normal user cannot open the admin page", async ({ page }, info) => {
  test.skip(info.project.name !== "desktop-1280", "once is enough");
  await login(page, "asha");
  await expect(page.getByRole("link", { name: "Admin" })).toHaveCount(0);
  await page.goto("/admin");
  await expect(page.getByText("Staff only")).toBeVisible();
});

test("a super admin can make and remove an admin", async ({ page }, info) => {
  test.skip(info.project.name !== "desktop-1280", "once is enough");
  await login(page, "owner", OWNER_PASSWORD);
  await page.goto("/admin");
  await page.getByRole("tab", { name: "Admins" }).click();
  await page.getByLabel("Search users").fill("rohan");
  await page.getByRole("button", { name: "Make admin" }).click();
  await expect(page.getByRole("button", { name: "Remove admin" })).toBeVisible();
  await page.screenshot({ path: "test-results/admin-roles.png" });
  await page.getByRole("button", { name: "Remove admin" }).click();
  await expect(page.getByRole("button", { name: "Make admin" })).toBeVisible();
});
