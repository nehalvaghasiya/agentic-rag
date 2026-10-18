import { test, expect } from "./harness.js";

const KNOWLEDGE_BASE_NAME = "Browser Fixture";
const FIXTURE_FILENAME = "browser-fixture.txt";
const FIXTURE_QUESTION = "Where does the browser harness store each run?";
const SCRIPTED_ANSWER = "Each browser test run uses disposable storage.";

test("starts isolated frontend and backend fixtures", async ({ app, page }) => {
  const healthResponse = await page.request.get(app.apiUrl + "/api/health");
  expect(healthResponse.ok()).toBe(true);
  await expect(healthResponse.json()).resolves.toEqual({ status: "ok" });

  const knowledgeBaseResponse = await page.request.get(app.apiUrl + "/api/kb");
  expect(knowledgeBaseResponse.ok()).toBe(true);
  await expect(knowledgeBaseResponse.json()).resolves.toEqual([]);

  await page.goto("/");
  await expect(page).toHaveURL(/\/chat\/chat_[^/]+$/);
  await expect(
    page.getByText("Ask me anything. If you attach a knowledge base to this chat, I’ll cite sources.")
  ).toBeVisible();
});

test("creates a knowledge base and queries it across routes", async ({
  app,
  page,
}) => {
  await page.goto("/");
  await expect(page).toHaveURL(/\/chat\/chat_[^/]+$/);

  await page.getByRole("button", { name: "Create Knowledge Base" }).click();
  await page.getByPlaceholder("e.g., Nvidia Q2 results").fill(KNOWLEDGE_BASE_NAME);
  await page.locator('input[type="file"]').setInputFiles(app.fixtureFile);
  await page.getByRole("button", { name: /Advanced Settings/ }).click();
  await page.getByLabel("Embedding Model").selectOption("deterministic");

  const createResponsePromise = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      response.url() === app.apiUrl + "/api/kb"
  );
  await page.getByRole("button", { name: "Create", exact: true }).click();
  const createResponse = await createResponsePromise;

  expect(createResponse.ok()).toBe(true);
  await expect(page).toHaveURL(/\/kb\/kb_[0-9a-f]+$/);
  await expect(page.getByText(KNOWLEDGE_BASE_NAME, { exact: true })).toBeVisible();
  await expect(page.getByText(FIXTURE_FILENAME, { exact: true }).last()).toBeVisible();
  await expect(page.getByText("Indexed", { exact: true })).toBeVisible();

  await page.getByRole("button", { name: "New Chat", exact: true }).click();
  await expect(page).toHaveURL(/\/chat\/chat_[^/]+$/);

  await page.getByRole("button", { name: "Attach knowledge base" }).click();
  await page
    .getByRole("button", { name: KNOWLEDGE_BASE_NAME, exact: true })
    .click();

  const composer = page.getByPlaceholder("Ask about " + KNOWLEDGE_BASE_NAME + "…");
  await expect(composer).toBeVisible();
  await composer.fill(FIXTURE_QUESTION);

  const streamResponsePromise = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      /\/api\/kb\/kb_[0-9a-f]+\/query\/stream$/.test(response.url())
  );
  await page.getByRole("button", { name: "Send", exact: true }).click();
  const streamResponse = await streamResponsePromise;

  expect(streamResponse.ok()).toBe(true);
  expect(streamResponse.headers()["content-type"]).toContain("text/event-stream");
  await expect(page.getByText("Retrieving", { exact: true })).toBeVisible();
  await expect(page.getByText(FIXTURE_FILENAME, { exact: true })).toBeVisible();
  await expect(page.getByText(SCRIPTED_ANSWER, { exact: true })).toBeVisible();
  await expect(page.getByText("Generating response...", { exact: true })).toHaveCount(0);
});

test("shows a safe terminal stream failure and allows another message", async ({ app, page }) => {
  const correlationId = "05ede9f0-4165-486c-a8d5-f1cd726b14c6";
  let requests = 0;
  // Fulfill one response in-browser; keep application fixture/provider code free
  // of test-only public fault switches.
  await page.route(app.apiUrl + "/api/chat/stream", async (route) => {
    requests += 1;
    if (requests > 1) return route.continue();
    const payload = { error: {
      code: "PROVIDER_UNAVAILABLE",
      message: "The model provider is temporarily unavailable. Try again later.",
      retryable: true,
      correlation_id: correlationId,
    } };
    await route.fulfill({
      status: 200,
      headers: {
        "Content-Type": "text/event-stream",
        "X-Correlation-ID": correlationId,
        "Access-Control-Allow-Origin": app.frontendUrl,
        "Access-Control-Expose-Headers": "X-Correlation-ID",
      },
      body: 'event: token\ndata: {"token":"partial answer"}\n\n' +
        `event: error\ndata: ${JSON.stringify(payload)}\n\n`,
    });
  });
  await page.goto("/");
  const composer = page.getByPlaceholder("Ask a question…");
  await composer.fill("Trigger a controlled stream failure");
  await page.getByRole("button", { name: "Send", exact: true }).click();
  await expect(page.getByText("The model provider is temporarily unavailable. Try again later.", { exact: true })).toBeVisible();
  await expect(page.getByText(`Reference: ${correlationId}`, { exact: true })).toBeVisible();
  await expect(page.getByText("partial answer", { exact: true })).toHaveCount(0);
  await expect(page.getByText("Generating response...", { exact: true })).toHaveCount(0);
  expect(requests).toBe(1);
  await expect(composer).toBeEnabled();
  await composer.fill("Try a new question");
  await page.getByRole("button", { name: "Send", exact: true }).click();
  await expect(page.getByText(SCRIPTED_ANSWER, { exact: true })).toBeVisible();
  expect(requests).toBe(2);
});

