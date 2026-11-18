import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { http, HttpResponse } from "msw";

import { KnowledgeBaseDashboard } from "../views/KnowledgeBaseDashboard";
import { CreateKnowledgeBaseModal } from "../components/features/knowledge-base/CreateKnowledgeBaseModal";
import { ApiError } from "../api/client";
import { correlationIdFixture, errorFixture } from "./fixtures";
import { renderApp, renderWithAppProviders } from "./render";
import { ChatBubble } from "../components/features/chat/ChatBubble";
import { server } from "./server";
import { createRunErrorHandler as createChatStreamErrorHandler, createRunHandler as createChatStreamHandler, runRequests } from "./chat-handlers";

describe("frontend component harness", () => {
  it("distinguishes retrieved-but-unverified answers from no-source model answers", () => {
    render(<ChatBubble id="unverified" role="assistant" content="The model did not return valid source references."
      isLatest run={{ answer_status: "citation_error", evidence_count: 4 }} onRetry={() => {}} />);
    expect(screen.getByText("The answer’s source references could not be verified.")).toBeInTheDocument();
    expect(screen.queryByText(/No external sources used/)).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Retry response" })).toBeInTheDocument();
  });

  it("keeps whole-document coverage out of the default answer", () => {
    render(<ChatBubble id="covered" role="assistant" content="Five document takeaways."
      run={{ coverage: { read_chunks: 39, total_chunks: 39, strategy: "map_reduce" } }} />);
    expect(screen.queryByText(/Document coverage/)).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "More response options" })).toBeInTheDocument();
  });

  it("renders routed state from deterministic API fixtures", async () => {
    const { user } = renderWithAppProviders(<KnowledgeBaseDashboard />, {
      route: "/kb/kb_fixture",
      path: "/kb/:kbId",
    });

    expect(await screen.findByText("Fixture Knowledge Base")).toBeInTheDocument();
    expect(screen.getByText("fixture-report.pdf")).toBeInTheDocument();
    expect(screen.getByText("Indexed")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Delete document fixture-report.pdf" }));
    await user.click(screen.getByRole("button", { name: "Confirm delete" }));

    await waitFor(() => expect(screen.queryByText("fixture-report.pdf")).not.toBeInTheDocument());
  });

  it("submits chat history and renders a controlled SSE response", async () => {
    vi.spyOn(console, "log").mockImplementation(() => {});

    const { user } = renderApp();
    const prompt = "How does the fixture work?";
    const input = await screen.findByPlaceholderText("Ask a question…");

    await user.type(input, prompt);
    await user.click(screen.getByRole("button", { name: "Send" }));

    expect(await screen.findByText(prompt, { selector: "span" })).toBeInTheDocument();
    await screen.findByText("Fixture answer.");
    expect(screen.queryByText("Preparing a deterministic response.")).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "More response options" }));
    await user.click(screen.getByRole("menuitem", { name: "View activity" }));
    expect((await screen.findAllByText("Preparing a deterministic response."))[0]).toBeInTheDocument();
    expect(await screen.findByText("Fixture answer.")).toBeInTheDocument();

    await waitFor(() => expect(runRequests).toHaveLength(1));
    expect(runRequests[0].question).toBe(prompt);
    expect(runRequests[0].session_id).toBeTruthy();
    expect(runRequests[0].model_id).toBe("default");
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

  it("retries a rejected submission with the same message ID and one question", async () => {
    const rejected = [];
    server.use(http.post("*/api/v2/runs", async ({ request }) => {
      rejected.push(await request.json());
      return HttpResponse.json(errorFixture(), { status: 503 });
    }));
    const { user } = renderApp();
    const input = await screen.findByPlaceholderText("Ask a question…");
    await user.type(input, "Retry this original question");
    await user.click(screen.getByRole("button", { name: "Send" }));
    await screen.findByRole("button", { name: "Retry response" });
    server.use(createChatStreamHandler());
    await user.click(screen.getByRole("button", { name: "Retry response" }));
    expect(await screen.findByText("Fixture answer.")).toBeInTheDocument();
    expect(screen.getAllByRole("article", { name: "Your message" })).toHaveLength(1);
    expect(runRequests[0].client_message_id).toBe(rejected[0].client_message_id);
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
    expect(await screen.findByText("The model provider is temporarily unavailable. Try again later.")).toBeInTheDocument();
    expect(screen.queryByText(`Reference: ${correlationIdFixture}`)).not.toBeInTheDocument();
    expect(screen.queryByText("partial answer")).not.toBeInTheDocument();
    expect(screen.queryByText("late answer")).not.toBeInTheDocument();
    expect(screen.queryByText("You can try again later.")).not.toBeInTheDocument();
    expect(screen.queryByText("Generating response...")).not.toBeInTheDocument();
    expect(input).toBeEnabled();
    expect(runRequests).toHaveLength(1);
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
