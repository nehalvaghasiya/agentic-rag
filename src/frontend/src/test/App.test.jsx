import { screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { KnowledgeBaseDashboard } from "../views/KnowledgeBaseDashboard";
import { CreateKnowledgeBaseModal } from "../components/features/knowledge-base/CreateKnowledgeBaseModal";
import { ApiError } from "../api/client";
import { capturedRequests, createChatStreamErrorHandler, createChatStreamHandler } from "./handlers";
import { correlationIdFixture, errorFixture } from "./fixtures";
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
        "The model provider is temporarily unavailable. Try again later."
      )
    ).toBeInTheDocument();
    expect(input).toBeEnabled();

    await user.type(input, "Retry");
    expect(input).toHaveValue("Retry");
  });

  it("replaces partial output with a terminal SSE error and clears loading", async () => {
    server.use(createChatStreamHandler({ events: [
      { type: "token", data: { token: "partial answer" } },
      { type: "error", data: errorFixture({ retryable: false }) },
      { type: "complete", data: { answer: "late answer" } },
    ] }));
    const { user } = renderApp();
    const input = await screen.findByPlaceholderText("Ask a question…");
    await user.type(input, "Trigger SSE failure");
    await user.click(screen.getByRole("button", { name: "Send" }));
    expect(await screen.findByText(`Reference: ${correlationIdFixture}`)).toBeInTheDocument();
    expect(screen.queryByText("partial answer")).not.toBeInTheDocument();
    expect(screen.queryByText("late answer")).not.toBeInTheDocument();
    expect(screen.queryByText("You can try again later.")).not.toBeInTheDocument();
    expect(screen.queryByText("Generating response...")).not.toBeInTheDocument();
    expect(input).toBeEnabled();
    expect(capturedRequests.chat).toHaveLength(1);
  });

  it("shows validation details and the reference when KB creation fails", async () => {
    const onCreate = vi.fn().mockRejectedValue(new ApiError({
      code: "VALIDATION_ERROR", message: "Some request fields are invalid. Check the field details.",
      correlationId: correlationIdFixture,
      details: [{ field: "files", code: "invalid_value", message: "This field has an invalid value." }],
    }));
    const { user, container } = renderWithAppProviders(
      <CreateKnowledgeBaseModal open onCreate={onCreate} onClose={() => {}} />
    );
    await user.type(screen.getByPlaceholderText("e.g., Nvidia Q2 results"), "Test KB");
    await user.upload(container.querySelector('input[type="file"]'), new File(["data"], "notes.txt", { type: "text/plain" }));
    await user.click(screen.getByRole("button", { name: "Create", exact: true }));
    expect(await screen.findByText(/files: This field has an invalid value\./)).toHaveTextContent(`Reference: ${correlationIdFixture}`);
    expect(screen.getByRole("button", { name: "Create", exact: true })).toBeEnabled();
  });
});
