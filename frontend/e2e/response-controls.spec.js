import { test, expect } from "./harness.js";
import { chooseKnowledgeBase } from "./composer-helpers.js";

async function send(page, question) {
  await page.getByRole("textbox", { name: "Message" }).fill(question);
  await page.getByRole("button", { name: "Send", exact: true }).click();
  await expect(page.getByRole("button", { name: "Stop", exact: true })).toHaveCount(0);
}
async function inspect(page, name) {
  await page.getByRole("button", { name: "More response options" }).last().click();
  await page.getByRole("menuitem", { name, exact: true }).click();
}
async function sourceChat(app, page) {
  const kb = await (await page.request.post(app.apiUrl + "/api/v2/kb", { data: { name: "Refund policies" } })).json();
  for (const [name, days] of [["policy_2025.md", 14], ["policy_2026_with_a_long_document_title_for_citation_layout.md", 30]]) {
    const year = name.includes("2025") ? 2025 : 2026;
    const response = await page.request.post(`${app.apiUrl}/api/v2/kb/${kb.id}/documents`, {
      multipart: { files: { name, mimeType: "text/markdown", buffer: Buffer.from(`Refund policy ${year}: The refund window is ${days} days. Contact support with your purchase receipt.`) } },
    });
    expect(response.ok()).toBeTruthy();
  }
  await expect.poll(async () => (await (await page.request.get(`${app.apiUrl}/api/v2/kb/${kb.id}`)).json()).documents.filter(d => d.status === "ready").length).toBe(2);
  const session = await (await page.request.post(app.apiUrl + "/api/v2/sessions", { data: { title: "Compare refund policies", kb_ids: [kb.id] } })).json();
  await page.goto(`/chat/${session.id}`);
  await expect(page.getByRole("textbox", { name: "Message" })).toBeEnabled();
  await send(page, "Compare the 2025 and 2026 refund windows");
  await expect(page.getByRole("button", { name: /View source:/ }).first()).toBeVisible();
  return { kb, session };
}

test("regeneration persists versions and only the latest selected version changes context", async ({ app, page }) => {
  await page.goto("/");
  await send(page, "Explain answer versions");
  await expect(page.getByText("Answer version 1.", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Regenerate response" }).click();
  await expect(page.getByText("Answer version 2.", { exact: true })).toBeVisible();
  await expect(page.getByText("2 / 2", { exact: true })).toBeVisible();
  await expect(page.getByRole("article", { name: "Your message" })).toHaveCount(1);
  await page.getByRole("button", { name: "Previous answer version" }).click();
  await expect(page.getByText("Answer version 1.", { exact: true })).toBeVisible();
  const path = new URL(page.url()).pathname;
  await page.reload();
  await expect(page.getByText("Answer version 1.", { exact: true })).toBeVisible();
  await expect(page.getByText("1 / 2", { exact: true })).toBeVisible();
  const ready = await (await page.request.get(app.apiUrl + "/api/v2/health/ready")).json();
  if (!ready.ephemeral) {
    await app.restartBackend(); await page.reload();
    await expect(page.getByText("Answer version 1.", { exact: true })).toBeVisible();
    await expect(page.getByText("1 / 2", { exact: true })).toBeVisible();
  }
  await send(page, "Hello");
  await expect(page.getByRole("button", { name: "Regenerate response" })).toHaveCount(1);
  await page.getByRole("button", { name: "Next answer version" }).click();
  await expect(page.getByText("Answer version 2.", { exact: true })).toBeVisible();
  await expect(page.getByText(/Existing follow-ups keep their original context/)).toBeVisible();
  const stored = await (await page.request.get(app.apiUrl + "/api/v2/sessions/" + path.split("/").at(-1))).json();
  expect(stored.messages[1].run_id).toBe(stored.messages[1].versions[0].run_id);
});

test("failed and cancelled regeneration preserve the original answer across reload", async ({ page }) => {
  await page.goto("/");
  await send(page, "Explain regeneration recovery");
  await page.getByRole("button", { name: "Regenerate response" }).click();
  await expect(page.getByText(/Regeneration failed/)).toBeVisible();
  await expect(page.getByText("The original answer is available.", { exact: true })).toBeVisible();
  await expect(page.getByText("private-provider-sentinel")).toHaveCount(0);
  await page.reload();
  await expect(page.getByText(/Regeneration failed/)).toBeVisible();
  await page.getByRole("button", { name: "Regenerate response" }).click();
  await expect(page.getByRole("button", { name: "Stop", exact: true })).toBeEnabled();
  await page.getByRole("button", { name: "Stop", exact: true }).click();
  await expect(page.getByText(/Regeneration cancelled/)).toBeVisible();
  await expect(page.getByText("The original answer is available.", { exact: true })).toBeVisible();
  await expect(page.getByRole("article", { name: "Your message" })).toHaveCount(1);
  await page.screenshot({ path: test.info().outputPath("regeneration-recovery.png") });
});

test("metadata is fetched on demand and transport recovery replays the accepted run", async ({ page }) => {
  const requests = [];
  page.on("request", request => { if (/\/runs\/[^/]+(?:\/activity)?$/.test(request.url())) requests.push(request.url()); });
  await page.goto("/");
  await send(page, "Hello");
  expect(requests).toHaveLength(0);
  await inspect(page, "Response details");
  await expect(page.getByText("Direct LLM", { exact: true })).toBeVisible();
  expect(requests.some(url => url.endsWith("/activity"))).toBe(false);
  await page.getByRole("button", { name: "Close response details" }).click();
  await page.route("**/api/v2/runs/*/events", route => route.abort("connectionreset"), { times: 1 });
  await send(page, "Explain answer versions");
  await expect(page.getByText("Answer version 1.", { exact: true })).toBeVisible();
  await expect(page.getByRole("article", { name: "Your message" })).toHaveCount(2);
});

test("source inspection opens the document and removes revoked excerpts from an open panel", async ({ app, page }) => {
  const { kb } = await sourceChat(app, page);
  await page.getByRole("button", { name: /View source:/ }).first().click();
  await expect(page.getByRole("region", { name: "Answer sources" })).toBeVisible();
  await page.getByRole("button", { name: "Open document" }).first().click();
  await expect(page.getByRole("dialog", { name: /Preview:/ })).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog", { name: /Preview:/ })).toHaveCount(0);
  const documents = (await (await page.request.get(`${app.apiUrl}/api/v2/kb/${kb.id}`)).json()).documents;
  for (const doc of documents) expect((await page.request.delete(`${app.apiUrl}/api/v2/documents/${doc.id}`)).ok()).toBeTruthy();
  await page.evaluate(() => window.dispatchEvent(new Event("focus")));
  await expect(page.getByText("This answer used a source that is no longer available.", { exact: true })).toBeVisible();
  await expect(page.getByRole("region", { name: "Answer sources" }).getByText("This source is no longer available.")).toHaveCount(2);
  await expect(page.getByRole("region", { name: "Answer sources" }).getByText(/Contact support/)).toHaveCount(0);
  await page.screenshot({ path: test.info().outputPath("unavailable-sources.png") });
});

for (const [width, height] of [[390, 844], [1024, 768], [1440, 900]]) {
  for (const theme of ["light", "dark"]) {
    test(`sources layout and keyboard navigation at ${width}x${height} in ${theme}`, async ({ app, page }, testInfo) => {
      await page.setViewportSize({ width, height });
      await page.addInitScript(value => localStorage.setItem("theme", value), theme);
      await sourceChat(app, page);
      await expect(page.locator("html")).toHaveClass(theme === "dark" ? /dark/ : /^$/);
      await expect(page.getByRole("region", { name: "Answer sources" })).toHaveCount(0);
      await page.screenshot({ path: testInfo.outputPath("clean-answer.png") });
      await inspect(page, "View sources");
      const overlay = width < 1220;
      const panel = page.getByRole(overlay ? "dialog" : "region", { name: "Sources", exact: true });
      await expect(panel).toBeVisible();
      await expect(panel.getByRole("heading", { name: "Sources", exact: true })).toBeFocused();
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
      const position = await panel.boundingBox();
      if (!overlay) expect(Math.round(position.width)).toBe(360);
      for (const button of await panel.getByRole("button").all()) {
        const bounds = await button.boundingBox();
        if (bounds) expect(bounds.height).toBeGreaterThanOrEqual(44);
      }
      if (overlay) {
        await page.keyboard.press("Shift+Tab");
        expect(await panel.evaluate(element => element.contains(document.activeElement))).toBe(true);
        await page.keyboard.press("Tab");
        await expect(panel.getByRole("button", { name: "Close sources" })).toBeFocused();
      }
      await page.screenshot({ path: testInfo.outputPath("sources-panel.png") });
      await page.keyboard.press("Escape");
      await expect(panel).toHaveCount(0);
      await expect(page.getByRole("button", { name: "More response options" })).toBeFocused();
      await page.emulateMedia({ reducedMotion: "reduce" });
      await page.getByRole("button", { name: /View source:/ }).first().click();
      await expect(page.getByRole(overlay ? "dialog" : "region", { name: "Sources", exact: true })).toBeVisible();
    });
  }
}

test("empty chat, conversation details, and partial generation remain usable", async ({ page }, testInfo) => {
  await page.goto("/");
  await expect(page.getByText("What would you like to know?", { exact: true })).toBeVisible();
  await page.screenshot({ path: testInfo.outputPath("empty-chat.png") });
  await page.getByRole("button", { name: "Conversation options" }).click();
  await page.getByRole("menuitem", { name: "Conversation details" }).click();
  await expect(page.getByRole("heading", { name: "Conversation details" })).toBeVisible();
  await expect(page.getByText("History summary", { exact: true })).toBeVisible();
  await page.keyboard.press("Escape");
  await page.getByRole("textbox", { name: "Message" }).fill("Please respond slowly");
  await page.getByRole("button", { name: "Send", exact: true }).click();
  await expect(page.getByText("Writing response…", { exact: true })).toBeVisible();
  await page.screenshot({ path: testInfo.outputPath("partial-response.png") });
  await page.getByRole("button", { name: "Stop", exact: true }).click();
  await expect(page.getByText("Response cancelled.", { exact: true })).toBeVisible();
});

test("permission failures show recovery without exposing source excerpts", async ({ app, page }, testInfo) => {
  await sourceChat(app, page);
  await page.route(/\/api\/v2\/runs\/[^/]+$/, route => route.fulfill({ status: 403, contentType: "application/json",
    body: JSON.stringify({ error: { code: "ACCESS_DENIED", message: "Access denied", retryable: false } }) }));
  await inspect(page, "View sources");
  const panel = page.getByRole("region", { name: "Sources", exact: true });
  await expect(panel.getByRole("alert")).toContainText("Access denied");
  await expect(panel.getByText(/Contact support/)).toHaveCount(0);
  await page.screenshot({ path: testInfo.outputPath("source-permission-error.png") });
  await page.unroute(/\/api\/v2\/runs\/[^/]+$/);
  await panel.getByRole("button", { name: "Retry details" }).click();
  await expect(panel.getByRole("region", { name: "Answer sources" })).toBeVisible();
});

test("reading an earlier source preserves transcript position while new tokens arrive", async ({ app, page }) => {
  await sourceChat(app, page);
  await chooseKnowledgeBase(page, "General chat");
  await expect(page.getByRole("button", { name: "Choose knowledge base" })).toContainText("Knowledge base");
  await page.getByRole("textbox", { name: "Message" }).fill("Please respond slowly");
  await page.getByRole("button", { name: "Send", exact: true }).click();
  await expect(page.getByText("Writing response…", { exact: true })).toBeVisible();
  const transcript = page.locator('[aria-label="Conversation"]');
  await expect.poll(() => transcript.evaluate(element => element.scrollHeight - element.clientHeight)).toBeGreaterThan(120);
  await transcript.evaluate(element => { element.scrollTop = 0; element.dispatchEvent(new Event("scroll")); });
  await page.getByRole("button", { name: /View source:/ }).first().click();
  const before = await transcript.evaluate(element => element.scrollTop);
  const response = page.getByRole("article", { name: "Assistant response" }).last();
  const length = (await response.textContent()).length;
  await expect.poll(async () => (await response.textContent()).length).toBeGreaterThan(length);
  expect(await transcript.evaluate(element => element.scrollTop)).toBe(before);
  await page.getByRole("button", { name: "Close sources" }).click();
  await page.getByRole("button", { name: "Stop", exact: true }).click();
});
