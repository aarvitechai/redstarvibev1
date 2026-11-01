import { expect, request, test, type Page } from "@playwright/test";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import zlib from "node:zlib";

const PASSWORD = process.env.SEED_PASSWORD ?? "RedStarDemo#2026";
const MAILPIT = process.env.MAILPIT_URL ?? "http://localhost:8025";

async function login(page: Page, username: string) {
  await page.goto("/login");
  await page.getByLabel("Username or email").fill(username);
  await page.getByLabel("Password").fill(PASSWORD);
  await page.getByRole("button", { name: "Log in", exact: true }).click();
  await expect(page).toHaveURL(/\/feed/);
}

/** A real PNG with a solid colour, written without any image library. */
function pngFile(): string {
  const crcTable = Array.from({ length: 256 }, (_, n) => {
    let c = n;
    for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
    return c >>> 0;
  });
  const crc = (b: Buffer) => {
    let c = 0xffffffff;
    for (const x of b) c = crcTable[(c ^ x) & 255]! ^ (c >>> 8);
    return (c ^ 0xffffffff) >>> 0;
  };
  const chunk = (type: string, data: Buffer) => {
    const len = Buffer.alloc(4);
    len.writeUInt32BE(data.length);
    const body = Buffer.concat([Buffer.from(type), data]);
    const sum = Buffer.alloc(4);
    sum.writeUInt32BE(crc(body));
    return Buffer.concat([len, body, sum]);
  };
  const size = 400;
  const ihdr = Buffer.alloc(13);
  ihdr.writeUInt32BE(size, 0);
  ihdr.writeUInt32BE(size, 4);
  ihdr[8] = 8;
  ihdr[9] = 2;
  const row = Buffer.concat([Buffer.from([0]), Buffer.alloc(size * 3, Buffer.from([200, 16, 46]))]);
  const raw = Buffer.concat(Array.from({ length: size }, () => row));
  const png = Buffer.concat([
    Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]),
    chunk("IHDR", ihdr),
    chunk("IDAT", zlib.deflateSync(raw)),
    chunk("IEND", Buffer.alloc(0)),
  ]);
  const file = path.join(os.tmpdir(), `rsv-${Date.now()}.png`);
  fs.writeFileSync(file, png);
  return file;
}

test.describe.configure({ mode: "serial" });

test("sign up with an emailed code, then land on the feed", async ({ page }, info) => {
  test.skip(info.project.name !== "mobile-360", "once is enough");
  const name = `e2e${Date.now() % 1_000_000_000}`;
  await page.goto("/signup");
  await page.getByLabel("Email").fill(`${name}@example.com`);
  await page.getByLabel("Username").fill(name);
  await page.getByLabel("Password").fill("a long unusual passphrase 7");
  await page.getByLabel(/Date of birth/).fill("2000-01-15");
  await page.getByRole("button", { name: "Sign up" }).click();
  await expect(page.getByLabel("Code")).toBeVisible();

  const mail = await request.newContext();
  let code = "";
  await expect
    .poll(
      async () => {
        const url = `${MAILPIT}/api/v1/search?query=${encodeURIComponent(`to:${name}@example.com`)}`;
        const res = await (await mail.get(url)).json();
        code = res.messages?.[0]?.Subject?.slice(0, 6) ?? "";
        return code;
      },
      { timeout: 20_000 },
    )
    .toMatch(/^\d{6}$/);
  await page.getByLabel("Code").fill(code);
  await page.getByRole("button", { name: "Verify and continue" }).click();
  await expect(page).toHaveURL(/\/feed/);
});

test("upload a photo, it is processed and published", async ({ page }, info) => {
  test.skip(info.project.name !== "desktop-1280", "once is enough");
  await login(page, "demo");
  await page.goto("/new");
  await page.getByTestId("file-input").setInputFiles(pngFile());
  const caption = `e2e upload ${Date.now()} #e2etest`;
  await page.getByLabel("Caption").fill(caption);
  const share = page.getByRole("button", { name: "Share" });
  await expect(share).toBeEnabled({ timeout: 30_000 });
  await share.click();
  await expect(page).toHaveURL(/\/p\//);
  await expect(page.getByText("Processing. It will go live shortly.")).toBeHidden({ timeout: 30_000 });
  await expect(page.locator("article picture img").first()).toBeVisible();
  await page.goto("/feed");
  await expect(page.getByText(caption).first()).toBeVisible({ timeout: 15_000 });
});

test("two people chat in real time with typing and seen receipts", async ({ browser }, info) => {
  test.skip(info.project.name !== "desktop-1280", "once is enough");
  const a = await (await browser.newContext({ viewport: { width: 1280, height: 800 } })).newPage();
  const b = await (await browser.newContext({ viewport: { width: 1280, height: 800 } })).newPage();
  await login(a, "asha");
  await login(b, "kabir");
  await a.goto("/kabir");
  await a.getByRole("button", { name: "Message" }).click();
  await expect(a).toHaveURL(/\/messages\//);
  await b.goto(a.url());
  await expect(a.getByRole("textbox", { name: "Message" })).toBeVisible();
  await a.waitForTimeout(1500); // both sockets connected
  await a.getByRole("textbox", { name: "Message" }).pressSequentially("hi");
  await expect(b.getByText("typing...")).toBeVisible({ timeout: 5000 });
  const text = `hello ${Date.now()}`;
  await a.getByRole("textbox", { name: "Message" }).fill(text);
  await a.keyboard.press("Enter");
  await expect(b.getByText(text)).toBeVisible({ timeout: 5000 });
  await expect(a.getByText("Seen")).toBeVisible({ timeout: 8000 });
});

test("a like appears live on the screen of another viewer", async ({ browser }, info) => {
  test.skip(info.project.name !== "desktop-1280", "once is enough");
  const a = await (await browser.newContext({ viewport: { width: 1280, height: 900 } })).newPage();
  const b = await (await browser.newContext({ viewport: { width: 1280, height: 900 } })).newPage();
  await login(a, "meera");
  await login(b, "rohan");
  const id = await a.evaluate(async () => (await (await fetch("/api/v1/feed")).json()).items[0].id);
  await a.goto(`/p/${id}`);
  await b.goto(`/p/${id}`);
  await a.waitForTimeout(1500);
  const count = a.locator("p.font-semibold", { hasText: /like/ }).first();
  const before = await count.innerText();
  await b.getByRole("button", { name: /^(Like|Unlike)$/ }).click();
  await expect(count).not.toHaveText(before, { timeout: 5000 });
});

test("video call connects through LiveKit", async ({ browser }, info) => {
  test.skip(info.project.name !== "desktop-1280", "once is enough");
  const launch = await browser.browserType().launch({
    args: ["--use-fake-ui-for-media-stream", "--use-fake-device-for-media-stream"],
  });
  const options = { viewport: { width: 1280, height: 800 }, permissions: ["camera", "microphone"] };
  const a = await (await launch.newContext(options)).newPage();
  const b = await (await launch.newContext(options)).newPage();
  await login(a, "asha");
  await login(b, "kabir");
  await a.goto("/kabir");
  await a.getByRole("button", { name: "Message" }).click();
  await expect(a).toHaveURL(/\/messages\//);
  await b.waitForTimeout(1500);
  await a.getByRole("button", { name: "Video call" }).click();
  await expect(a).toHaveURL(/\/call\//);
  await b.getByRole("button", { name: "Accept" }).click({ timeout: 15_000 });
  await expect(b).toHaveURL(/\/call\//);
  await expect(a.locator(".lk-participant-tile")).toHaveCount(2, { timeout: 30_000 });
  await expect(a.locator(".lk-participant-tile video")).toHaveCount(2, { timeout: 30_000 }); // camera tracks flow both ways
  await expect(b.locator(".lk-participant-tile")).toHaveCount(2, { timeout: 30_000 });
  await a.screenshot({ path: "test-results/call.png" });
  await launch.close();
});

test("video upload produces HLS that plays", async ({ page }, info) => {
  test.skip(info.project.name !== "desktop-1280" || !process.env.E2E_VIDEO, "needs E2E_VIDEO");
  await login(page, "rohan");
  await page.goto("/new?reel=1");
  await page.getByTestId("file-input").setInputFiles(process.env.E2E_VIDEO!);
  await page.getByLabel("Caption").fill(`reel ${Date.now()} #reel`);
  const share = page.getByRole("button", { name: "Share" });
  await expect(share).toBeEnabled({ timeout: 120_000 });
  await share.click();
  await expect(page).toHaveURL(/\/p\//);
  await expect(page.getByText("Processing. It will go live shortly.")).toBeHidden({ timeout: 60_000 });
  const video = page.locator("video").first();
  await expect.poll(() => video.evaluate((v: HTMLVideoElement) => v.readyState), { timeout: 30_000 }).toBeGreaterThan(1);
  await expect.poll(() => video.evaluate((v: HTMLVideoElement) => v.currentTime), { timeout: 20_000 }).toBeGreaterThan(0);
});
