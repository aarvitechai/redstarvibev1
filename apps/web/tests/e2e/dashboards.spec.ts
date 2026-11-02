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

const noSideScroll = (page: Page) => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth);

test("admin sees the dashboard and every report, but not super admin tabs", async ({ page }, info) => {
  await login(page, "demo");
  await page.goto("/admin");
  await expect(page.getByRole("heading", { name: "Admin dashboard" })).toBeVisible();
  await expect(page.getByTestId("daily-chart")).toHaveCount(4);
  await expect(page.getByText("Median time to resolve")).toBeVisible();
  for (const tab of ["Platform", "Audit log", "Admins"]) await expect(page.getByRole("tab", { name: tab })).toHaveCount(0);
  await page.getByRole("button", { name: "7 days" }).click();
  await expect(page.getByRole("button", { name: "7 days" })).toHaveAttribute("aria-pressed", "true");
  expect(await noSideScroll(page)).toBe(true);
  await page.screenshot({ path: test.info().outputPath("admin-dashboard.png"), fullPage: true });

  await page.getByRole("tab", { name: "Reports" }).click();
  await expect(page.getByRole("tab", { name: /^All/ })).toBeVisible();
  await page.getByRole("tab", { name: /^All/ }).click();
  await page.getByLabel("Reason").selectOption("spam");
  await page.getByLabel("Content type").selectOption("post");
  await expect(page.getByRole("link", { name: "Export CSV" })).toHaveAttribute("href", /status=all.*reason=spam.*entity_type=post/);
  const [download] = await Promise.all([page.waitForEvent("download"), page.getByRole("link", { name: "Export CSV" }).click()]);
  expect(download.suggestedFilename()).toMatch(/\.csv$/);
  expect(await noSideScroll(page)).toBe(true);
  void info;
});

test("a report goes from the queue to history", async ({ page, browser }, info) => {
  test.skip(info.project.name !== "desktop-1280", "once is enough");
  const reporterContext = await browser.newContext({ baseURL: info.project.use.baseURL });
  const reporter = await reporterContext.newPage();
  await login(reporter, "kabir");
  const posts = (await (await reporter.request.get("/api/v1/explore?limit=1")).json()).items;
  const csrf = (await reporterContext.cookies()).find((c) => c.name === "rsv_csrf")!.value;
  const details = `e2e report ${Date.now()}`;
  const made = await reporter.request.post("/api/v1/reports", {
    data: { entity_type: "post", entity_id: posts[0].id, reason: "other", details },
    headers: { "x-csrf-token": csrf },
  });
  expect(made.ok()).toBe(true);
  await reporterContext.close();

  await login(page, "demo");
  await page.goto("/admin");
  await page.getByRole("button", { name: "Review now" }).click();
  const row = page.getByTestId("report").filter({ hasText: details });
  await expect(row).toContainText("Reported by kabir");
  await row.getByRole("button", { name: "Dismiss" }).click();
  await page.getByRole("button", { name: "Yes, dismiss" }).click();
  await expect(row).toHaveCount(0);
  await page.getByRole("tab", { name: /^Dismissed/ }).click();
  await expect(row).toContainText("Resolved by demo");
});

test("super admin sees platform health, staff activity and the audit log", async ({ page }) => {
  await login(page, "owner", OWNER_PASSWORD);
  await page.goto("/admin");
  await expect(page.getByRole("heading", { name: "Super admin dashboard" })).toBeVisible();
  await page.getByRole("tab", { name: "Platform" }).click();
  await expect(page.getByText("Database:")).toContainText("OK");
  await expect(page.getByRole("cell", { name: "owner" })).toBeVisible();
  await expect(page.getByTestId("platform-warnings")).toBeVisible();
  expect(await noSideScroll(page)).toBe(true);
  await page.screenshot({ path: test.info().outputPath("platform.png"), fullPage: true });

  await page.getByRole("tab", { name: "Audit log" }).click();
  await expect(page.getByTestId("audit-row").first()).toBeVisible();
  await page.getByLabel("Audit category").selectOption("auth");
  await expect(page.getByTestId("audit-row").first()).toContainText("auth.");
  expect(await noSideScroll(page)).toBe(true);
});
