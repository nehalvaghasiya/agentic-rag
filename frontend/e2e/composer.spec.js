import { test, expect } from "./harness.js";
import { chooseKnowledgeBase } from "./composer-helpers.js";

async function setup(app, page) {
  const bases = [];
  for (const name of ["NVIDIAAn", "Team handbook", "Quarterly planning and product architecture reference"]) {
    const response = await page.request.post(`${app.apiUrl}/api/v2/kb`, { data: { name } });
    expect(response.ok()).toBeTruthy();
    bases.push(await response.json());
  }
  const uploaded = await page.request.post(`${app.apiUrl}/api/v2/kb/${bases[0].id}/documents`, {
    multipart: { files: { name: "earnings-notes.md", mimeType: "text/markdown", buffer: Buffer.from("Synthetic earnings reference for composer layout tests.") } },
  });
  expect(uploaded.ok()).toBeTruthy();
  const session = await (await page.request.post(`${app.apiUrl}/api/v2/sessions`, { data: { title: "Earnings analysis", kb_ids: [bases[0].id] } })).json();
  await page.goto(`/chat/${session.id}`);
  await expect(page.getByRole("button", { name: "Choose knowledge base", exact: true })).toContainText("NVIDIAAn");
  await expect(page.getByRole("textbox", { name: "Message" })).toBeEnabled();
  return { session, bases };
}

for (const [width, height] of [[390, 844], [1024, 768], [1440, 900]]) {
  for (const theme of ["light", "dark"]) {
    test.describe(`${width}x${height} ${theme} composer`, () => {
      test.use({ viewport: { width, height }, hasTouch: width < 640, isMobile: width < 640 });
      test("choices are readable, searchable, and keyboard accessible", async ({ app, page }, testInfo) => {
        await page.addInitScript(value => localStorage.setItem("theme", value), theme);
        const { bases } = await setup(app, page);
        const input = page.getByRole("textbox", { name: "Message" });
        const composer = page.locator("form.chat-composer");
        await input.fill("Compare the two quarterly earnings reports.");
        const send = page.getByRole("button", { name: "Send", exact: true });
        await expect(send).toBeEnabled();
        expect(await send.textContent()).toBe("");
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
        for (const name of ["Choose knowledge base", "Choose model", "Deep analysis", "Send"]) {
          const bounds = await page.getByRole("button", { name, exact: true }).boundingBox();
          expect(bounds.height).toBeGreaterThanOrEqual(44);
        }
        const manage = page.getByRole("link", { name: "Manage knowledge base", exact: true });
        await expect(manage).toHaveAttribute("href", `/kb/${bases[0].id}`);
        if (width < 640) expect((await manage.boundingBox()).width).toBeGreaterThanOrEqual(44);
        const sendBefore = await send.boundingBox();
        const analysis = page.getByRole("button", { name: "Deep analysis", exact: true });
        await analysis.click();
        await expect(analysis).toHaveAttribute("aria-pressed", "true");
        expect((await send.boundingBox()).x).toBe(sendBefore.x);
        const analysisBounds = await analysis.boundingBox();
        expect(analysisBounds.x + analysisBounds.width + 4).toBeLessThanOrEqual(sendBefore.x);
        await composer.screenshot({ path: testInfo.outputPath("composer.png") });
        await page.screenshot({ path: testInfo.outputPath("chat-with-composer.png") });
        await page.getByRole("button", { name: "Choose knowledge base", exact: true }).click();
        const picker = page.getByRole("dialog", { name: "Choose knowledge base", exact: true });
        await expect(picker).toBeVisible();
        await expect(page.getByRole("searchbox", { name: "Search knowledge bases" })).toBeFocused();
        await expect(page.getByRole("option", { name: "NVIDIAAn", exact: true })).toHaveAttribute("aria-selected", "true");
        const bounds = await picker.boundingBox();
        expect(bounds.x).toBeGreaterThanOrEqual(0); expect(bounds.y).toBeGreaterThanOrEqual(0);
        expect(bounds.x + bounds.width).toBeLessThanOrEqual(width);
        expect(bounds.y + bounds.height).toBeLessThanOrEqual(height);
        await page.screenshot({ path: testInfo.outputPath("knowledge-picker.png") });
        await page.getByRole("searchbox").fill("Team");
        await expect(page.getByRole("option")).toHaveCount(1);
        await page.keyboard.press("ArrowDown"); await page.keyboard.press("Enter");
        await expect(picker).toHaveCount(0);
        await expect(page.getByRole("button", { name: "Choose knowledge base" })).toContainText("Team handbook");
        await expect(input).toHaveValue("Compare the two quarterly earnings reports.");
        await page.getByRole("button", { name: "Choose model" }).click();
        const modelPicker = page.getByRole("dialog", { name: "Choose model" });
        await expect(modelPicker.getByRole("option", { selected: true })).toBeFocused();
        await page.screenshot({ path: testInfo.outputPath("model-picker.png") });
        await page.keyboard.press("Escape");
        await expect(page.getByRole("button", { name: "Choose model" })).toBeFocused();
        await chooseKnowledgeBase(page, "General chat");
        await expect(page.getByRole("link", { name: "Manage knowledge base", exact: true })).toHaveCount(0);
        await expect(input).toHaveValue("Compare the two quarterly earnings reports.");
      });
    });
  }
}

test("Enter sends multiline drafts and the icon control stops a response", async ({ page }, testInfo) => {
  await page.goto("/");
  const input = page.getByRole("textbox", { name: "Message" });
  await expect(input).toBeEnabled();
  await input.fill("Please respond");
  await input.press("Shift+Enter");
  await input.pressSequentially("slowly");
  await expect(input).toHaveValue("Please respond\nslowly");
  await input.press("Enter");
  await expect(page.getByRole("article", { name: "Your message" }).getByText("Please respond", { exact: true })).toBeVisible();
  await expect(page.getByRole("article", { name: "Your message" }).getByText("slowly", { exact: true })).toBeVisible();
  // A separate slow prompt makes the cancel control observable independently of multiline parsing.
  await expect(page.getByRole("button", { name: "Stop", exact: true })).toHaveCount(0);
  await input.fill("Please respond slowly");
  await input.press("Enter");
  const stop = page.getByRole("button", { name: "Stop", exact: true });
  await expect(stop).toBeEnabled(); expect(await stop.textContent()).toBe("");
  await expect(page.getByRole("button", { name: "Choose model" })).toBeDisabled();
  await page.locator("form.chat-composer").screenshot({ path: testInfo.outputPath("stop-control.png") });
  await stop.click();
  await expect(page.getByText("Response cancelled.", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Send", exact: true })).toBeDisabled();
});

test("the composer expands with the draft and stays bounded", async ({ page }, testInfo) => {
  await page.goto("/");
  const input = page.getByRole("textbox", { name: "Message" });
  await expect(input).toBeEnabled();
  const initial = (await input.boundingBox()).height;
  const draft = Array.from({ length: 14 }, (_, index) => `Line ${index + 1}: another question about the report.`).join("\n");
  await input.fill(draft);
  await expect.poll(async () => (await input.boundingBox()).height).toBeGreaterThan(initial);
  expect((await input.boundingBox()).height).toBeLessThanOrEqual(160);
  await page.locator("form.chat-composer").screenshot({ path: testInfo.outputPath("multiline-draft.png") });
  await page.getByRole("button", { name: "Choose model" }).click();
  await page.keyboard.press("Escape");
  await expect(input).toHaveValue(draft);
});

test("catalog loading and errors keep general chat available and allow retry", async ({ page }, testInfo) => {
  await page.goto("/");
  const input = page.getByRole("textbox", { name: "Message" });
  await expect(input).toBeEnabled();
  await input.fill("Keep this question while loading");
  let release;
  const waiting = new Promise(resolve => { release = resolve; });
  const pattern = "**/api/v2/kb";
  await page.route(pattern, async route => {
    await waiting;
    await route.fulfill({ status: 503, contentType: "application/json", body: JSON.stringify({ error: { code: "UNAVAILABLE", message: "Knowledge catalog unavailable", retryable: true } }) });
  });
  try {
    await page.evaluate(() => window.dispatchEvent(new Event("focus")));
    await page.getByRole("button", { name: "Choose knowledge base" }).click();
    const picker = page.getByRole("dialog", { name: "Choose knowledge base" });
    await expect(picker.getByRole("status")).toContainText("Loading knowledge bases");
    await expect(picker.getByRole("option", { name: "General chat" })).toBeEnabled();
    await page.screenshot({ path: testInfo.outputPath("catalog-loading.png") });
    release();
    await expect(picker.getByRole("alert")).toContainText("Knowledge bases couldn’t be loaded.");
    await page.screenshot({ path: testInfo.outputPath("catalog-error.png") });
    await page.unroute(pattern);
    await picker.getByRole("button", { name: "Retry loading" }).click();
    await expect(picker.getByText(/No knowledge bases yet/)).toBeVisible();
    await expect(input).toHaveValue("Keep this question while loading");
    await page.screenshot({ path: testInfo.outputPath("empty-catalog.png") });
  } finally { release(); await page.unroute(pattern); }
});

test("a denied selection keeps the previous base and draft and can be retried", async ({ app, page }, testInfo) => {
  await setup(app, page);
  const input = page.getByRole("textbox", { name: "Message" });
  await input.fill("Keep my draft and existing context");
  const pattern = /\/api\/v2\/sessions\/[^/]+$/;
  await page.route(pattern, route => route.request().method() === "PATCH"
    ? route.fulfill({ status: 403, contentType: "application/json", body: JSON.stringify({ error: { code: "ACCESS_DENIED", message: "Access denied", retryable: false } }) })
    : route.continue());
  await page.getByRole("button", { name: "Choose knowledge base" }).click();
  await page.getByRole("option", { name: "Team handbook", exact: true }).click();
  const picker = page.getByRole("dialog", { name: "Choose knowledge base" });
  await expect(picker.getByRole("alert")).toContainText("Couldn’t update your selection.");
  await expect(page.getByRole("button", { name: "Choose knowledge base" })).toContainText("NVIDIAAn");
  await expect(input).toHaveValue("Keep my draft and existing context");
  await page.screenshot({ path: testInfo.outputPath("selection-permission-error.png") });
  await page.unroute(pattern);
  await picker.getByRole("option", { name: "Team handbook", exact: true }).click();
  await expect(picker).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Choose knowledge base" })).toContainText("Team handbook");
  await expect(input).toHaveValue("Keep my draft and existing context");
});
