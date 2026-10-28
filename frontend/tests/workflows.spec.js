import { test, expect } from "@playwright/test";
import { readFile } from "node:fs/promises";

const NW = "Northwind Logistics";
const BP = "Bluepeak Retail";

async function login(page, email, org) {
  await page.goto("/");
  await page.getByLabel("Email", { exact: true }).fill(email);
  await page.getByLabel("Password", { exact: true }).fill("pulse123");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await page.getByRole("button", { name: org, exact: true }).click();
}

async function complete(page) {
  await expect(page.locator("select").first()).toBeVisible();
  for (const select of await page.locator("select").all()) await select.selectOption({ index: 4 });
  for (const area of await page.locator("textarea").all())
    await area.fill("I draft with AI, remove private details and check facts.");
  await page.getByRole("button", { name: "Submit diagnostic" }).click();
}

test("employee submission, JSON download, deletion, live dashboard suppression and retake", async ({ page, browser }, testInfo) => {
  const errors = [];
  page.on("pageerror", e => errors.push(e.message));
  await login(page, "priya@northwind.test", NW);
  await complete(page);
  await expect(page.getByText("Demo mode: AI scores and explanations are simulated.")).toBeVisible();

  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("button", { name: "Export my data (JSON)" }).click();
  const download = await downloadPromise;
  const exported = JSON.parse(await readFile(await download.path(), "utf8"));
  expect(exported.employee.email).toBe("priya@northwind.test");
  expect(exported.report.status).toBe("completed");
  expect(exported.responses.length).toBeGreaterThan(5);
  expect(exported.responses.every(row => row.question && row.answer && row.score)).toBe(true);
  expect(exported.responses.some(row => row.ai_explanation)).toBe(true);

  const context = await browser.newContext();
  const admin = await context.newPage();
  await login(admin, "asha@northwind.test", NW);
  await expect(admin.getByRole("cell", { name: "Support", exact: true })).toBeVisible();
  await expect(admin.getByRole("cell", { name: "5", exact: true })).toBeVisible();
  await admin.screenshot({ path: testInfo.outputPath("dashboard-five.png"), fullPage: true });

  await page.getByRole("button", { name: "Delete my diagnostic data", exact: true }).click();
  await page.getByRole("button", { name: "Cancel", exact: true }).click();
  await expect(page.getByText("Average score:", { exact: false })).toBeVisible();
  await page.getByRole("button", { name: "Delete my diagnostic data", exact: true }).click();
  await page.getByRole("button", { name: "Confirm deletion", exact: true }).click();
  await expect(page.getByText("No diagnostic data.", { exact: false })).toBeVisible();
  await expect(admin.getByText("No departments meet the privacy threshold yet.")).toBeVisible({ timeout: 10000 });
  await admin.screenshot({ path: testInfo.outputPath("dashboard-four.png"), fullPage: true });

  const emptyDownloadPromise = page.waitForEvent("download");
  await page.getByRole("button", { name: "Export my data (JSON)" }).click();
  const emptyDownload = await emptyDownloadPromise;
  const empty = JSON.parse(await readFile(await emptyDownload.path(), "utf8"));
  expect(empty.responses).toEqual([]);
  expect(empty.report.status).toBe("empty");

  await page.getByRole("button", { name: "Take diagnostic", exact: true }).click();
  await complete(page);
  await admin.getByRole("button", { name: "Refresh dashboard" }).click();
  await expect(admin.getByRole("cell", { name: "Support", exact: true })).toBeVisible();
  expect(errors).toEqual([]);
  await context.close();
});

test("organization switch uses Ravi's role in each organization; API rejects dashboard bypass", async ({ page }) => {
  await login(page, "ravi@consult.test", BP);
  await expect(page.getByRole("heading", { name: "Leadership dashboard" })).toBeVisible();
  await page.getByRole("button", { name: "Switch organization" }).click();
  await page.getByRole("button", { name: NW, exact: true }).click();
  await expect(page.getByRole("heading", { name: "Your AI diagnostic" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Dashboard", exact: true })).toHaveCount(0);
  const token = await page.evaluate(() => sessionStorage.getItem("token"));
  const forbidden = await page.request.get("http://127.0.0.1:8001/dashboard?org_id=2",
    { headers: { Authorization: `Bearer ${token}` } });
  expect(forbidden.status()).toBe(403);
  await page.getByRole("button", { name: "Switch organization" }).click();
  await page.getByRole("button", { name: BP, exact: true }).click();
  await expect(page.getByRole("heading", { name: "Leadership dashboard" })).toBeVisible();
});

test("scoring error is visible, preserves input, and allows retry", async ({ page }) => {
  await login(page, "dev@northwind.test", NW);
  await page.route("**/diagnostic/submit", route => route.fulfill({
    status: 502, contentType: "application/json",
    body: JSON.stringify({ detail: "AI evaluation failed validation; no answers were saved." }),
  }));
  await complete(page);
  await expect(page.getByRole("alert")).toContainText("AI evaluation failed validation");
  await expect(page.locator("textarea").first()).toHaveValue("I draft with AI, remove private details and check facts.");
  await page.unroute("**/diagnostic/submit");
  await page.getByRole("button", { name: "Submit diagnostic" }).click();
  await expect(page.getByText("Average score:", { exact: false })).toBeVisible();
});
