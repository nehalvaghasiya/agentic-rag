import { readFile } from "node:fs/promises";
import { test, expect } from "./harness.js";
import { chooseKnowledgeBase } from "./composer-helpers.js";

function syntheticPdf() {
  const stream = "BT /F1 16 Tf 50 700 Td (Synthetic PDF original with Saturn rings.) Tj ET\n";
  const objects = [
    "<< /Type /Catalog /Pages 2 0 R >>",
    "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
    "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
    "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    `<< /Length ${Buffer.byteLength(stream)} >>\nstream\n${stream}endstream`,
  ];
  let pdf = "%PDF-1.4\n";
  const offsets = [0];
  objects.forEach((object, i) => { offsets.push(Buffer.byteLength(pdf)); pdf += `${i + 1} 0 obj\n${object}\nendobj\n`; });
  const start = Buffer.byteLength(pdf);
  pdf += `xref\n0 6\n0000000000 65535 f \n${offsets.slice(1).map(offset => `${String(offset).padStart(10, "0")} 00000 n \n`).join("")}trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n${start}\n%%EOF\n`;
  return Buffer.from(pdf);
}

async function createBase(app, page, name, files = []) {
  const created = await page.request.post(app.apiUrl + "/api/v2/kb", { data: { name } });
  expect(created.status()).toBe(201);
  const kb = await created.json();
  for (const file of files) {
    const accepted = await page.request.post(`${app.apiUrl}/api/v2/kb/${kb.id}/documents`, { multipart: { files: file } });
    expect(accepted.status()).toBe(202);
  }
  return kb;
}

async function downloadOriginal(page, filename) {
  const [download] = await Promise.all([
    page.waitForEvent("download"), page.getByRole("button", { name: `Download ${filename}`, exact: true }).click(),
  ]);
  expect(download.suggestedFilename()).toBe(filename);
  return readFile(await download.path());
}

test("existing knowledge supports library navigation, previews, downloads, uploads and deletion", async ({ app, page }, testInfo) => {
  const pdf = syntheticPdf();
  const text = Buffer.from("Synthetic reference: Saturn has rings.");
  const kb = await createBase(app, page, "Existing reference library", [
    { name: "reference.txt", mimeType: "text/plain", buffer: text },
    { name: "saturn.pdf", mimeType: "application/pdf", buffer: pdf },
  ]);
  await page.goto("/");
  await expect(page).toHaveURL(/\/chat\/[^/]+$/);
  const chatUrl = page.url();
  await chooseKnowledgeBase(page, kb.name);
  await page.getByRole("link", { name: "Manage knowledge base", exact: true }).click();
  await expect(page.getByRole("heading", { name: kb.name, exact: true })).toBeVisible();
  await page.getByRole("link", { name: /Back to Knowledge Bases/ }).click();
  await expect(page.getByRole("link", { name: `Open ${kb.name}`, exact: true })).toBeVisible();
  await page.reload();
  await expect(page.getByRole("link", { name: `Open ${kb.name}`, exact: true })).toBeVisible();
  await page.screenshot({ path: testInfo.outputPath("knowledge-library.png") });
  await page.getByRole("link", { name: `Open ${kb.name}`, exact: true }).click();
  await page.getByRole("button", { name: "Preview reference.txt", exact: true }).click();
  await expect(page.getByRole("dialog")).toContainText(text.toString());
  await page.getByRole("button", { name: "Close dialog", exact: true }).click();
  expect(await downloadOriginal(page, "reference.txt")).toEqual(text);
  await page.getByRole("button", { name: "Preview saturn.pdf", exact: true }).click();
  if (await page.evaluate(() => navigator.pdfViewerEnabled === true)) {
    await page.getByRole("button", { name: "View as text", exact: true }).click();
  }
  await expect(page.getByRole("dialog")).toContainText("Synthetic PDF original with Saturn rings.");
  await page.getByRole("button", { name: "Close dialog", exact: true }).click();
  expect(await downloadOriginal(page, "saturn.pdf")).toEqual(pdf);
  const ready = await (await page.request.get(app.apiUrl + "/api/v2/health/ready")).json();
  if (!ready.ephemeral) {
    await app.restartBackend();
    await page.reload();
    await expect(page.getByRole("button", { name: "Preview saturn.pdf", exact: true })).toBeVisible();
    expect(await downloadOriginal(page, "saturn.pdf")).toEqual(pdf);
  }
  await page.locator('input[aria-label="Add documents"]').setInputFiles({ name: "added.md", mimeType: "text/markdown", buffer: Buffer.from("# Added\n\nSynthetic added reference.") });
  await page.getByRole("button", { name: "Upload documents", exact: true }).click();
  await expect(page.getByRole("button", { name: "Preview added.md", exact: true })).toBeVisible();
  await expect(page.getByText("Indexed", { exact: true })).toHaveCount(3);
  await page.getByRole("button", { name: "Delete document added.md", exact: true }).click();
  await page.getByRole("button", { name: "Cancel", exact: true }).click();
  await expect(page.getByRole("button", { name: "Preview added.md", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Delete document added.md", exact: true }).click();
  await page.getByRole("button", { name: "Confirm delete", exact: true }).click();
  await expect(page.getByRole("button", { name: "Preview added.md", exact: true })).toHaveCount(0);
  await page.reload();
  await expect(page.getByText("Indexed", { exact: true })).toHaveCount(2);
  await page.getByRole("button", { name: "Delete knowledge base", exact: true }).click();
  await page.getByRole("button", { name: "Confirm delete", exact: true }).click();
  await expect(page).toHaveURL(/\/kb$/);
  await expect(page.getByText("No knowledge bases yet", { exact: true })).toBeVisible();
  await page.goto(chatUrl);
  await expect(page.getByRole("button", { name: "Choose knowledge base" })).toContainText("Knowledge base");
  await expect(page.getByRole("link", { name: "Manage knowledge base", exact: true })).toHaveCount(0);
  await expect(page.getByRole("textbox", { name: "Message", exact: true })).toBeEnabled();
});

test("deletion failure stays reviewable and an empty knowledge base can be deleted", async ({ app, page }) => {
  const kb = await createBase(app, page, "Empty managed base");
  await page.goto(`/kb/${kb.id}`);
  await expect(page.getByText(/No documents yet/)).toBeVisible();
  const routePattern = `**/api/v2/kb/${kb.id}`;
  await page.route(routePattern, route => route.request().method() === "DELETE"
    ? route.fulfill({ status: 503, json: { error: { code: "UNAVAILABLE", message: "Synthetic deletion failure", retryable: true } } }) : route.continue());
  await page.getByRole("button", { name: "Delete knowledge base", exact: true }).click();
  await page.getByRole("button", { name: "Confirm delete", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText("Synthetic deletion failure");
  await expect(page).toHaveURL(new RegExp(`/kb/${kb.id}$`));
  await page.unroute(routePattern);
  await page.getByRole("button", { name: "Confirm delete", exact: true }).click();
  await expect(page.getByText("No knowledge bases yet", { exact: true })).toBeVisible();
});

test("native PDF preview embeds the original page layout", async ({ app, page }, testInfo) => {
  const kb = await createBase(app, page, "PDF layout", [{ name: "layout.pdf", mimeType: "application/pdf", buffer: syntheticPdf() }]);
  await page.goto(`/kb/${kb.id}`);
  test.skip(!await page.evaluate(() => navigator.pdfViewerEnabled === true), "Browser has no inline PDF viewer; text fallback is covered separately.");
  await page.getByRole("button", { name: "Preview layout.pdf", exact: true }).click();
  const frame = page.getByTitle("PDF preview of layout.pdf", { exact: true });
  await expect(frame).toBeVisible();
  await expect(frame).toHaveAttribute("src", /^blob:/);
  await expect(page.getByRole("button", { name: "View as text", exact: true })).toBeEnabled();
  // Chromium's PDF plugin has a separate internal document that Playwright cannot query.
  // Text extraction and exact original bytes are verified by the management journey.
  await page.screenshot({ path: testInfo.outputPath("native-pdf-preview.png") });
});

test("Tailwind 4 preserves layout, theme colors, and class-based dark mode", async ({ app, page }) => {
  await page.emulateMedia({ colorScheme: "light" });
  const kb = await createBase(app, page, "Theme compatibility", [{ name: "theme.txt", mimeType: "text/plain", buffer: Buffer.from("Synthetic theme fixture.") }]);
  await page.goto(`/kb/${kb.id}`);
  const indexed = page.getByText("Indexed", { exact: true });
  await expect(indexed).toBeVisible();
  await expect(page.locator("aside")).toHaveCSS("width", "260px");
  await expect(page.locator("body")).toHaveCSS("background-color", "rgb(248, 250, 252)");
  await expect(page.getByRole("button", { name: "New Chat", exact: true })).toHaveCSS("background-color", "rgb(37, 99, 235)");
  const lightStatusColor = await indexed.evaluate(element => getComputedStyle(element).color);
  await page.locator("aside button").first().click();
  await expect(page.locator("body")).toHaveCSS("background-color", "rgb(11, 18, 32)");
  await expect(page.getByRole("button", { name: "New Chat", exact: true })).toHaveCSS("background-color", "rgb(96, 165, 250)");
  await expect.poll(() => indexed.evaluate(element => getComputedStyle(element).color)).not.toBe(lightStatusColor);
});
