import { expect, request, test, type Page } from "@playwright/test";

const PASSWORD = process.env.SEED_PASSWORD ?? "RedStarDemo#2026";
const MAILPIT = process.env.MAILPIT_URL ?? "http://localhost:8025";

async function login(page: Page, username: string, password = PASSWORD) {
  await page.goto("/login");
  await page.getByLabel("Username or email").fill(username);
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: "Log in", exact: true }).click();
  await expect(page).toHaveURL(/\/feed/);
}

async function latestCode(address: string, not = ""): Promise<string> {
  const mail = await request.newContext();
  let code = "";
  await expect
    .poll(
      async () => {
        const res = await (await mail.get(`${MAILPIT}/api/v1/search?query=${encodeURIComponent(`to:${address}`)}`)).json();
        code = res.messages?.[0]?.Subject?.slice(0, 6) ?? "";
        return code === not ? "" : code;
      },
      { timeout: 20_000 },
    )
    .toMatch(/^\d{6}$/);
  await mail.dispose();
  return code;
}

test("forgot password: reset with an emailed code, then log in", async ({ page }, info) => {
  test.skip(info.project.name !== "mobile-360", "once is enough");
  const name = `e2ereset${Date.now() % 1_000_000_000}`;
  const address = `${name}@example.com`;
  await page.goto("/signup");
  await page.getByLabel("Email").fill(address);
  await page.getByLabel("Username").fill(name);
  await page.getByLabel("Password").fill("a long unusual passphrase 7");
  await page.getByLabel(/Date of birth/).fill("2000-01-15");
  await page.getByRole("button", { name: "Sign up" }).click();
  const signupCode = await latestCode(address);
  await page.getByLabel("Code").fill(signupCode);
  await page.getByRole("button", { name: "Verify and continue" }).click();
  await expect(page).toHaveURL(/\/feed/);
  await page.context().clearCookies();

  await page.goto("/login");
  await page.getByRole("link", { name: "Forgot password?" }).click();
  await expect(page).toHaveURL(/forgot-password/);
  await page.getByLabel("Email", { exact: true }).fill(address);
  await page.getByRole("button", { name: "Send code" }).click();
  await page.getByLabel("Code").fill(await latestCode(address, signupCode));
  await page.getByLabel("New password").fill("a brand new passphrase 8");
  await page.getByRole("button", { name: "Change password" }).click();
  await expect(page).toHaveURL(/\/login/);
  await login(page, name, "a brand new passphrase 8");
});

test("share options on a post", async ({ page }) => {
  await login(page, "demo");
  await page.goto("/feed");
  await page.getByRole("button", { name: "Share" }).first().click();
  await expect(page.getByRole("button", { name: "Copy link" })).toBeVisible();
  const whatsapp = page.getByRole("link", { name: "Share on WhatsApp" });
  await expect(whatsapp).toHaveAttribute("href", /^https:\/\/wa\.me\/\?text=.*%2Fp%2F/);
});

test("mute and restrict from a profile, and manage them in settings", async ({ page }, info) => {
  test.skip(info.project.name !== "mobile-360", "once is enough");
  await login(page, "demo");
  await page.goto("/kabir");
  await page.getByRole("button", { name: "More options" }).click();
  await page.getByRole("button", { name: "Mute", exact: true }).click();
  await expect(page.getByText(/They will not be told/)).toBeVisible();
  await page.getByRole("button", { name: "More options" }).click();
  await page.getByRole("button", { name: "Restrict", exact: true }).click();
  await expect(page.getByText(/stay hidden until you allow/)).toBeVisible();

  await page.goto("/settings");
  await page.getByLabel(/Words to hide/).fill("badword, another one");
  await page.getByRole("button", { name: "Save hidden words" }).click();
  await page.reload();
  await expect(page.getByLabel(/Words to hide/)).toHaveValue("another one, badword");
  await page.getByLabel(/Words to hide/).fill("");
  await page.getByRole("button", { name: "Save hidden words" }).click();

  const muted = page.locator("section").filter({ hasText: "Muted accounts" });
  await muted.getByRole("button", { name: "Unmute" }).click();
  await expect(muted).toBeHidden();
  const restricted = page.locator("section").filter({ hasText: "Restricted accounts" });
  await restricted.getByRole("button", { name: "Remove" }).click();
  await expect(restricted).toBeHidden();
});

test("hashtag page has Top and Recent, profile has Tagged", async ({ page }) => {
  await login(page, "demo");
  await page.goto("/tag/travel");
  await expect(page.getByRole("tab", { name: "top" })).toHaveAttribute("aria-selected", "true");
  await page.getByRole("tab", { name: "recent" }).click();
  await expect(page.getByRole("tab", { name: "recent" })).toHaveAttribute("aria-selected", "true");
  await page.goto("/kabir");
  await page.getByRole("tab", { name: "Tagged" }).click();
  await expect(page.getByText("No tagged posts yet")).toBeVisible();
});
