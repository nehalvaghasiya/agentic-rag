import { test, expect } from "./harness.js";
import { chooseKnowledgeBase } from "./composer-helpers.js";

async function send(page, text) {
  await page.getByRole("textbox", { name: "Message" }).fill(text);
  await page.getByRole("button", { name: "Send", exact: true }).click();
  await expect(page.getByRole("button", { name: "Stop", exact: true })).toHaveCount(0);
}
async function inspect(page, name, index = -1) {
  const menus = page.getByRole("button", { name: "More response options" });
  await (index < 0 ? menus.last() : menus.nth(index)).click();
  await page.getByRole("menuitem", { name, exact: true }).click();
}

test("one chat supports quiet answers, on-demand metadata, history, and caching", async ({ page }) => {
  await page.goto("/agent");
  await expect(page).toHaveURL(/\/chat\/[^/]+$/);
  await expect(page.getByText("What would you like to know?", { exact: true })).toBeVisible();
  await send(page, "Hello");
  await expect(page.getByText("Hello! How can I help you?", { exact: true })).toBeVisible();
  await expect(page.getByText("Direct LLM", { exact: true })).toHaveCount(0);
  await expect(page.getByText(/No external sources used/)).toHaveCount(0);
  await inspect(page, "Response details");
  await expect(page.getByText("Direct LLM", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Close response details" }).click();
  const firstUrl = page.url();
  await page.getByRole("button", { name: "New Chat", exact: true }).click();
  await expect(page).not.toHaveURL(firstUrl);
  await send(page, "Hello");
  await expect(page.getByText("Cached response", { exact: true })).toHaveCount(0);
  await inspect(page, "Response details");
  await expect(page.getByText("Cached response", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Close response details" }).click();
  await send(page, "My name is Nehal.");
  await send(page, "What is my name?");
  await expect(page.getByText("Your name is Nehal.", { exact: true })).toBeVisible();
  await page.reload();
  await expect(page.getByText("Your name is Nehal.", { exact: true })).toBeVisible();
});

test("fast retrieval and agentic research expose sources and activity on demand", async ({ app, page }) => {
  await page.goto("/");
  await expect(page).toHaveURL(/\/chat\/[^/]+$/);
  await page.getByRole("button", { name: "Create Knowledge Base", exact: true }).click();
  await page.getByPlaceholder("e.g., Nvidia Q2 results").fill("Refund policies");
  await page.locator('input[type="file"]').setInputFiles([
    { name: "policy_2025.md", mimeType: "text/markdown", buffer: Buffer.from("Refund policy 2025: The refund window is 14 days.") },
    { name: "policy_2026.md", mimeType: "text/markdown", buffer: Buffer.from("Refund policy 2026: The refund window is 30 days.") },
  ]);
  await page.getByRole("button", { name: "Create", exact: true }).click();
  await expect(page).toHaveURL(/\/kb\/[^/]+$/);
  await expect(page.getByText("Indexed", { exact: true })).toHaveCount(2);
  await page.getByRole("button", { name: "New Chat", exact: true }).click();
  await chooseKnowledgeBase(page, "Refund policies");
  await send(page, "What is the refund window in policy 2026?");
  await expect(page.getByText("Fast RAG", { exact: true })).toHaveCount(0);
  await expect(page.getByText(/The refund window is 30 days/).first()).toBeVisible();
  await expect(page.getByRole("region", { name: "Answer sources" })).toHaveCount(0);
  await page.getByRole("button", { name: /View source:/ }).first().click();
  await expect(page.getByRole("region", { name: "Answer sources" })).toBeVisible();
  await page.getByRole("button", { name: "Close sources" }).click();
  await send(page, "Compare the 2025 and 2026 refund windows");
  await inspect(page, "View activity");
  await expect(page.getByText("Research specialist started", { exact: true })).toBeVisible();
  await expect(page.getByText("Calling search", { exact: true })).toHaveCount(2);
  await page.getByRole("button", { name: "Close activity" }).click();
  const url = page.url();
  await send(page, "Hello");
  await expect(page.getByText("Hello! How can I help you?", { exact: true })).toBeVisible();
  expect(page.url()).toBe(url);
  const ready = await (await page.request.get(app.apiUrl + "/api/v2/health/ready")).json();
  if (!ready.ephemeral) {
    await app.restartBackend();
    await page.reload();
    await expect(page.getByRole("button", { name: /View source:/ }).first()).toBeVisible();
    await inspect(page, "View sources", 1);
    await expect(page.getByRole("region", { name: "Answer sources" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Choose knowledge base" })).toContainText("Refund policies");
  }
});

test("errors and cancellation are visible and the chat remains usable", async ({ page }) => {
  await page.goto("/");
  await expect(page).toHaveURL(/\/chat\/[^/]+$/);
  await send(page, "Trigger a controlled failure");
  await expect(page.getByText("The response could not be completed. You can retry this message.", { exact: true })).toBeVisible();
  await expect(page.getByText("private-provider-sentinel")).toHaveCount(0);
  await page.getByRole("textbox", { name: "Message" }).fill("Please respond slowly");
  await page.getByRole("button", { name: "Send", exact: true }).click();
  await page.getByRole("button", { name: "Stop", exact: true }).click();
  await expect(page.getByText("Response cancelled.", { exact: true })).toBeVisible();
  await send(page, "Hello");
  await expect(page.getByText("Hello! How can I help you?", { exact: true })).toBeVisible();
});

test("uploaded plans retain full coverage while details stay outside the transcript", async ({ page }) => {
  await page.goto("/");
  await expect(page).toHaveURL(/\/chat\/[^/]+$/);
  await page.getByRole("button", { name: "Create Knowledge Base", exact: true }).click();
  await page.getByPlaceholder("e.g., Nvidia Q2 results").fill("Harbor plan");
  const document = "# Harbor library plan\n\n" + Array.from({ length: 8 }, (_, i) =>
    `## Phase ${i + 1}\nCatalog ${(i + 1) * 1000} books and preserve original metadata. ` +
    "Support offline access, validate the catalog, and test accessible navigation. ".repeat(20)).join("\n\n");
  await page.locator('input[type="file"]').setInputFiles({ name: "harbor-plan.md", mimeType: "text/markdown", buffer: Buffer.from(document) });
  await page.getByRole("button", { name: "Create", exact: true }).click();
  await expect(page.getByText("Indexed", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "New Chat", exact: true }).click();
  await chooseKnowledgeBase(page, "Harbor plan");
  for (const question of ["whats this about", "whats this plan about", "Give me top 5 takeaways from this plan", "Create an implementation checklist from this document"]) await send(page, question);
  await expect(page.getByRole("region", { name: "Answer sources" })).toHaveCount(0);
  await expect(page.getByText(/Document coverage:/)).toHaveCount(0);
  await expect(page.getByRole("article", { name: "Assistant response" })).toHaveCount(4);
  await inspect(page, "Response details");
  await expect(page.getByText("Document coverage", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Close response details" }).click();
  await inspect(page, "View activity");
  await expect(page.getByText("Complete document loaded", { exact: true })).toBeVisible();
  await page.reload();
  await expect(page.getByRole("region", { name: "Answer sources" })).toHaveCount(0);
  await inspect(page, "View sources");
  await expect(page.getByRole("region", { name: "Answer sources" })).toBeVisible();
});
