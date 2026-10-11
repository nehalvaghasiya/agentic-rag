import { screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { KnowledgeBaseDashboard } from "../views/KnowledgeBaseDashboard";
import { capturedRequests, createChatStreamErrorHandler } from "./handlers";
import { renderApp, renderWithAppProviders } from "./render";
import { server } from "./server";

describe("frontend component harness", () => {
  it("renders routed state from deterministic API fixtures", async () => {
    const { user } = renderWithAppProviders(<KnowledgeBaseDashboard />, {
      route: "/kb/kb_fixture",
      path: "/kb/:kbId",
    });

    expect(await screen.findByText("Fixture Knowledge Base")).toBeInTheDocument();
    expect(screen.getByText("fixture-report.pdf")).toBeInTheDocument();
    expect(screen.getByText("Indexed")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Delete file" }));

    expect(screen.queryByText("fixture-report.pdf")).not.toBeInTheDocument();
  });

  it("submits chat history and renders a controlled SSE response", async () => {
    vi.spyOn(console, "log").mockImplementation(() => {});

    const { user } = renderApp();
    const prompt = "How does the fixture work?";
    const input = await screen.findByPlaceholderText("Ask a question…");

    await user.type(input, prompt);
    await user.click(screen.getByRole("button", { name: "Send" }));

    expect(await screen.findByText(prompt, { selector: "span" })).toBeInTheDocument();
    expect(
      await screen.findByText("Preparing a deterministic response.")
    ).toBeInTheDocument();
    expect(await screen.findByText("Fixture answer.")).toBeInTheDocument();

    await waitFor(() => expect(capturedRequests.chat).toHaveLength(1));
    expect(capturedRequests.chat[0].messages.at(-1)).toEqual({
      role: "user",
      content: prompt,
    });
    expect(capturedRequests.chat[0].model_config_override).toBeNull();
    expect(screen.queryByText("Generating response...")).not.toBeInTheDocument();
  });

  it("renders a controlled transport failure and remains interactive", async () => {
    server.use(createChatStreamErrorHandler());
    vi.spyOn(console, "log").mockImplementation(() => {});
    vi.spyOn(console, "error").mockImplementation(() => {});

    const { user } = renderApp();
    const input = await screen.findByPlaceholderText("Ask a question…");

    await user.type(input, "Trigger the fixture error");
    await user.click(screen.getByRole("button", { name: "Send" }));

    expect(
      await screen.findByText(
        "Query failed: API 503: Fixture provider unavailable"
      )
    ).toBeInTheDocument();
    expect(input).toBeEnabled();

    await user.type(input, "Retry");
    expect(input).toHaveValue("Retry");
  });
});
