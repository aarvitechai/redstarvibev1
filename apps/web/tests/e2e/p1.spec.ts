import { chromium, expect, test, type Browser, type Page } from "@playwright/test";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import zlib from "node:zlib";

const PASSWORD = process.env.SEED_PASSWORD ?? "RedStarDemo#2026";
const OWNER_PASSWORD = process.env.OWNER_PASSWORD ?? PASSWORD;

/** A real solid colour PNG, written without any image library. */
function png(): string {
  const table = Array.from({ length: 256 }, (_, n) => {
    let c = n;
    for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
    return c >>> 0;
  });
  const crc = (b: Buffer) => {
    let c = 0xffffffff;
    for (const x of b) c = table[(c ^ x) & 255]! ^ (c >>> 8);
    return (c ^ 0xffffffff) >>> 0;
  };
  const chunk = (type: string, data: Buffer) => {
    const length = Buffer.alloc(4);
    length.writeUInt32BE(data.length);
    const body = Buffer.concat([Buffer.from(type), data]);
    const sum = Buffer.alloc(4);
    sum.writeUInt32BE(crc(body));
    return Buffer.concat([length, body, sum]);
  };
  const size = 400;
  const header = Buffer.alloc(13);
  header.writeUInt32BE(size, 0);
  header.writeUInt32BE(size, 4);
  header[8] = 8;
  header[9] = 2;
  const row = Buffer.concat([Buffer.from([0]), Buffer.alloc(size * 3, Buffer.from([46, 120, 200]))]);
  const file = path.join(os.tmpdir(), `rsv-p1-${Date.now()}.png`);
  fs.writeFileSync(file, Buffer.concat([
    Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]),
    chunk("IHDR", header),
    chunk("IDAT", zlib.deflateSync(Buffer.concat(Array.from({ length: size }, () => row)))),
    chunk("IEND", Buffer.alloc(0)),
  ]));
  return file;
}

async function login(page: Page, username: string, password = PASSWORD) {
  await page.goto("/login");
  await page.getByLabel("Username or email").fill(username);
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: "Log in", exact: true }).click();
  await expect(page).toHaveURL(/\/feed/);
}

async function session(browser: Browser, baseURL: string | undefined, username: string, password = PASSWORD, viewport = { width: 1280, height: 800 }) {
  const context = await browser.newContext({ baseURL, viewport });
  const page = await context.newPage();
  await login(page, username, password);
  return page;
}

async function call(page: Page, method: "post" | "delete" | "patch" | "put", url: string, data?: unknown) {
  const csrf = (await page.context().cookies()).find((c) => c.name === "rsv_csrf")!.value;
  return page.request[method](`/api/v1${url}`, { data, headers: { "x-csrf-token": csrf } });
}

const noSideScroll = (page: Page) => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth);

test("story with a poll, a frame and close friends", async ({ page, browser, baseURL }, info) => {
  test.skip(info.project.name !== "mobile-360", "once is enough");
  await login(page, "asha");
  await page.goto("/settings");
  await page.getByLabel("Close friend username").fill("kabir");
  await page.getByRole("button", { name: "Add", exact: true }).first().click();
  await expect(page.locator("section").filter({ hasText: "Close friends" }).getByText("kabir", { exact: true })).toBeVisible();

  await page.goto("/feed");
  await page.getByTestId("story-file").setInputFiles(png());
  await page.getByLabel("Festival frame").selectOption("diwali");
  await page.getByLabel("Add a poll or quiz").selectOption("poll");
  const question = `Tea or coffee ${Date.now()}?`;
  await page.getByLabel("Question").fill(question);
  await page.getByLabel("Option 1").fill("Tea");
  await page.getByLabel("Option 2").fill("Coffee");
  expect(await noSideScroll(page)).toBe(true);
  await page.getByRole("button", { name: "Share story" }).click();
  await expect(page.getByText("Story added")).toBeVisible({ timeout: 30_000 });

  const kabir = await session(browser, baseURL, "kabir");
  await kabir.goto("/feed");
  await kabir.getByRole("button", { name: "Stories by asha" }).click();
  const sticker = kabir.getByTestId("story-sticker").filter({ hasText: question });
  // Older stories from this author play first, so step forward to the new one.
  await expect
    .poll(async () => {
      if (await sticker.isVisible()) return true;
      await kabir.getByRole("button", { name: "Next story" }).click();
      return sticker.isVisible();
    }, { timeout: 20_000, intervals: [200] })
    .toBe(true);
  await expect(kabir.getByText("Happy Diwali")).toBeVisible();
  await sticker.getByRole("button", { name: /Coffee/ }).click();
  await expect(sticker.getByRole("button", { name: /Coffee/ })).toContainText("100%");
  await kabir.getByRole("button", { name: "React 🔥" }).click();
  await expect(kabir.getByRole("button", { name: "React 🔥" })).toHaveAttribute("aria-pressed", "true");
  await kabir.context().close();

  await page.goto("/settings");
  const friends = page.locator("section").filter({ hasText: "Close friends" });
  await friends.getByRole("button", { name: "Remove" }).click();
  await expect(friends.getByText("kabir", { exact: true })).toHaveCount(0);
});

test("filter and pin a post, seal a time capsule", async ({ page }, info) => {
  test.skip(info.project.name !== "desktop-1280", "once is enough");
  await login(page, "meera");
  await page.goto("/new");
  await page.getByTestId("file-input").setInputFiles(png());
  await page.getByRole("button", { name: "Black and white" }).click();
  const caption = `filtered ${Date.now()}`;
  await page.getByLabel("Caption").fill(caption);
  const share = page.getByRole("button", { name: "Share" });
  await expect(share).toBeEnabled({ timeout: 30_000 });
  await share.click();
  await expect(page).toHaveURL(/\/p\//);
  await expect(page.getByText("Processing. It will go live shortly.")).toBeHidden({ timeout: 30_000 });
  const filter = await page.locator("article picture").first().evaluate((el) => getComputedStyle(el.parentElement!).filter);
  expect(filter).toContain("grayscale(1)");

  await page.getByRole("button", { name: "More options" }).first().click();
  await page.getByRole("button", { name: "Pin to profile" }).click();
  await page.goto("/meera");
  await expect(page.getByLabel("Pinned").first()).toBeVisible();

  await page.goto("/new");
  await page.getByTestId("file-input").setInputFiles(png());
  await page.getByLabel(/Schedule for later/).fill("2035-01-01T10:00");
  await page.getByLabel(/Seal as a time capsule/).check();
  const seal = page.getByRole("button", { name: "Seal time capsule" });
  await expect(seal).toBeEnabled({ timeout: 30_000 });
  await seal.click();
  await expect(page.getByText("Time capsule sealed")).toBeVisible();
  await page.goto("/meera");
  await expect(page.getByTestId("capsule-teaser")).toContainText(/sealed time capsule/);
});

test("a stranger's message waits in requests, then is accepted", async ({ page, browser, baseURL }, info) => {
  test.skip(info.project.name !== "mobile-360", "once is enough");
  const owner = await session(browser, baseURL, "owner", OWNER_PASSWORD);
  const made = await call(owner, "post", "/conversations", { usernames: ["rohan"] });
  expect(made.ok()).toBe(true);
  const conv = (await made.json()).id;
  const text = `hello from a stranger ${Date.now()}`;
  expect((await call(owner, "post", `/conversations/${conv}/messages`, { body: text })).ok()).toBe(true);
  await owner.context().close();

  await login(page, "rohan");
  await page.goto("/messages");
  await page.getByRole("tab", { name: /requests/ }).click();
  await page.getByRole("link", { name: new RegExp(text) }).click();
  await expect(page.getByTestId("request-banner")).toBeVisible();
  await page.getByRole("button", { name: "Accept" }).click();
  await expect(page.getByTestId("request-banner")).toHaveCount(0);
  await page.goto("/messages");
  await expect(page.getByRole("link", { name: new RegExp(text) })).toBeVisible();
  expect(await noSideScroll(page)).toBe(true);
});

test("create a group, share a post into it, send a voice note", async ({ baseURL }, info) => {
  test.skip(info.project.name !== "desktop-1280", "once is enough");
  const launched = await chromium.launch({ args: ["--use-fake-device-for-media-stream", "--use-fake-ui-for-media-stream"] });
  const context = await launched.newContext({ baseURL, viewport: { width: 1280, height: 800 }, permissions: ["microphone"] });
  const page = await context.newPage();
  await login(page, "demo");
  await page.goto("/messages");
  await page.getByRole("button", { name: "New message" }).click();
  for (const name of ["asha", "kabir"]) {
    await page.getByLabel("Search people").fill(name);
    await page.getByRole("button", { name: new RegExp(name) }).first().click();
  }
  const title = `Team ${Date.now()}`;
  await page.getByLabel("Group name (optional)").fill(title);
  await page.getByRole("button", { name: "Create group" }).click();
  await expect(page).toHaveURL(/\/messages\/[0-9a-f-]+/);
  await expect(page.getByRole("heading", { name: title })).toBeVisible();

  await page.getByRole("button", { name: "Record a voice note" }).click();
  await expect(page.getByTestId("recording-time")).toContainText("0:01", { timeout: 5000 });
  await page.getByRole("button", { name: "Stop and send voice note" }).click();
  await expect(page.locator("audio")).toBeVisible({ timeout: 30_000 });
  await expect.poll(() => page.locator("audio").first().evaluate((a: HTMLAudioElement) => a.duration), { timeout: 15_000 }).toBeGreaterThan(0);

  await page.goto("/feed");
  await page.getByRole("button", { name: "Share" }).first().click();
  await page.getByRole("button", { name: title }).click();
  await expect(page.getByText("Sent")).toBeVisible();
  await page.goto("/messages");
  await page.getByRole("link", { name: new RegExp(title) }).click();
  await expect(page.getByTestId("shared-post")).toBeVisible();

  await page.getByRole("button", { name: "Group settings" }).click();
  await page.getByRole("button", { name: "Leave group" }).click();
  await expect(page).toHaveURL(/\/messages$/);
  await launched.close();
});

test("communities: create, join, post, report", async ({ page, browser, baseURL }, info) => {
  test.skip(info.project.name !== "mobile-360", "once is enough");
  await login(page, "meera");
  await page.goto("/communities");
  await page.getByRole("button", { name: "Create", exact: true }).click();
  const name = `Bakers ${Date.now()}`;
  await page.getByLabel("Name").fill(name);
  await page.getByRole("button", { name: "Create community" }).click();
  await expect(page.getByRole("heading", { name })).toBeVisible();
  await page.getByLabel("Write a post").fill("Fresh bread tips");
  await page.getByRole("button", { name: "Post", exact: true }).click();
  await expect(page.getByTestId("community-post")).toContainText("Fresh bread tips");
  expect(await noSideScroll(page)).toBe(true);

  const other = await session(browser, baseURL, "rohan");
  await other.goto(page.url());
  await other.getByRole("button", { name: "Join" }).click();
  await expect(other.getByLabel("Write a post")).toBeVisible();
  await expect(other.getByRole("button", { name: "Report post" })).toBeVisible();
  await other.context().close();

  await page.getByRole("button", { name: "Delete community" }).click();
  await expect(page).toHaveURL(/\/communities$/);
});

test("support ticket goes from a person to staff, verification to a business", async ({ page, browser, baseURL }, info) => {
  test.skip(info.project.name !== "desktop-1280", "once is enough");
  await login(page, "rohan");
  await page.goto("/support");
  const subject = `Upload fails ${Date.now()}`;
  await page.getByLabel("Subject").fill(subject);
  await page.getByLabel("How can we help?").fill("My upload keeps failing");
  await page.getByRole("button", { name: "Send", exact: true }).click();
  await expect(page.getByRole("dialog").getByText("My upload keeps failing")).toBeVisible();
  await page.getByRole("button", { name: "Close" }).click();

  const admin = await session(browser, baseURL, "demo");
  await admin.goto("/admin");
  await admin.getByRole("tab", { name: "Tickets" }).click();
  await admin.getByRole("button", { name: new RegExp(subject) }).click();
  await admin.getByLabel("Reply").fill("We are checking this");
  await admin.getByRole("button", { name: "Send reply" }).click();
  await expect(admin.getByRole("dialog").getByText("We are checking this")).toBeVisible();
  await admin.getByRole("button", { name: "Mark resolved" }).click();
  await expect(admin.getByRole("dialog").getByText("resolved", { exact: true })).toBeVisible();
  await admin.getByRole("button", { name: "Close" }).click();

  await page.reload();
  await page.getByRole("button", { name: new RegExp(subject) }).click();
  await expect(page.getByRole("dialog").getByText("Support", { exact: false }).first()).toBeVisible();
  await page.getByRole("button", { name: "Close" }).click();

  await page.getByLabel("Verify as").selectOption("business");
  await page.getByLabel("Details that prove who you are").fill("Rohan Food Stall, GST 27ABCDE1234F1Z5");
  await page.getByRole("button", { name: "Request verification" }).click();
  await expect(page.getByText(/being reviewed/)).toBeVisible();

  await admin.getByRole("tab", { name: "Verification" }).click();
  const request = admin.getByTestId("verification").filter({ hasText: "rohan" });
  await request.getByRole("button", { name: "Approve" }).click();
  await expect(request).toHaveCount(0);
  await admin.context().close();

  await page.goto("/business-tools");
  await expect(page.getByRole("heading", { name: "Business tools" })).toBeVisible();
  await page.getByRole("combobox", { name: "Post" }).selectOption({ index: 1 });
  await page.getByLabel("Headline").fill("Best food in town");
  await page.getByLabel("Daily budget in rupees").fill("500");
  await page.getByRole("button", { name: "Send for review" }).click();
  await expect(page.getByText("Best food in town")).toBeVisible();
});

test("staff get only staff tabs, super admin sets plan prices", async ({ page, browser, baseURL }, info) => {
  test.skip(info.project.name !== "tablet-768", "once is enough");
  await login(page, "owner", OWNER_PASSWORD);
  await page.goto("/admin");
  await page.getByRole("tab", { name: "Plans" }).click();
  await expect(page.getByTestId("revenue")).toContainText("No revenue");
  await page.getByLabel("Premium price, rupees a month").fill("199");
  await page.getByRole("button", { name: "Save Premium" }).click();
  await page.reload();
  await page.getByRole("tab", { name: "Plans" }).click();
  await expect(page.getByLabel("Premium price, rupees a month")).toHaveValue("199");
  await page.getByLabel("Premium price, rupees a month").fill("");
  await page.getByRole("button", { name: "Save Premium" }).click();
  await expect(page.getByLabel("Premium price, rupees a month")).toHaveValue("");

  const users = await (await page.request.get("/api/v1/admin/users?q=asha")).json();
  const asha = users.find((u: { username: string }) => u.username === "asha");
  expect((await call(page, "patch", `/admin/users/${asha.id}/role`, { role: "staff" })).ok()).toBe(true);
  try {
    const staff = await session(browser, baseURL, "asha", PASSWORD, { width: 360, height: 740 });
    await staff.goto("/admin");
    await expect(staff.getByRole("heading", { name: "Staff dashboard" })).toBeVisible();
    await expect(staff.getByRole("tab", { name: "Reports" })).toBeVisible();
    await expect(staff.getByRole("tab", { name: "Tickets" })).toBeVisible();
    for (const tab of ["Dashboard", "Verification", "Ads", "Plans", "Admins", "Test data"]) await expect(staff.getByRole("tab", { name: tab })).toHaveCount(0);
    await expect(staff.getByRole("link", { name: "Export CSV" })).toHaveCount(0);
    expect(await noSideScroll(staff)).toBe(true);
    await staff.context().close();
  } finally {
    await call(page, "patch", `/admin/users/${asha.id}/role`, { role: "user" });
  }
});
