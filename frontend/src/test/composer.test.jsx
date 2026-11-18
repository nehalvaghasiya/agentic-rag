import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { http, HttpResponse } from "msw";
import { describe, expect, it, vi } from "vitest";
import { ChatComposer } from "../components/features/chat/ChatComposer";
import { renderApp } from "./render";
import { server } from "./server";
import { runRequests } from "./chat-handlers";

const bases = [
  { id: "finance", name: "NVIDIA earnings", documents: [{ status: "Indexed" }, { status: "running" }] },
  { id: "handbook", name: "Team handbook", documents: [] },
];
const models = [{ id: "default", name: "auto/best-fast" }, { id: "other", name: "Research model" }];
function props(overrides = {}) {
  return { value: "Draft question", onValueChange: vi.fn(), onSubmit: vi.fn(), onStop: vi.fn(),
    knowledgeBases: bases, kbId: null, onKnowledgeBaseChange: vi.fn().mockResolvedValue(true),
    modelConfigs: models, selectedModelId: "default", onModelChange: vi.fn(),
    deep: false, onDeepChange: vi.fn(), hydrated: true, busy: false, generating: false, canStop: false, ...overrides };
}
function widget(options) {
  return render(<MemoryRouter><ChatComposer {...options} /></MemoryRouter>);
}

describe("chat composer", () => {
  it("uses accessible icon-only Send and Stop controls and locks settings during generation", async () => {
    const user = userEvent.setup();
    const options = props({ value: "" });
    const { rerender } = widget(options);
    const send = screen.getByRole("button", { name: "Send", exact: true });
    expect(send).toBeDisabled(); expect(send).toHaveTextContent("");
    expect(send.textContent).toBe("");
    expect(screen.queryByText("Send", { exact: true })).not.toBeInTheDocument();
    rerender(<MemoryRouter><ChatComposer {...options} value="A question" busy generating canStop /></MemoryRouter>);
    const stop = screen.getByRole("button", { name: "Stop", exact: true });
    expect(stop.textContent).toBe(""); expect(stop).toBeEnabled();
    for (const name of ["Choose knowledge base", "Choose model", "Deep analysis"]) expect(screen.getByRole("button", { name })).toBeDisabled();
    expect(screen.getByRole("textbox", { name: "Message" })).toBeEnabled();
    await user.click(stop); expect(options.onStop).toHaveBeenCalledOnce();
  });

  it("searches bases, exposes document/indexing status, and supports keyboard selection", async () => {
    const user = userEvent.setup();
    const options = props();
    widget(options);
    await user.click(screen.getByRole("button", { name: "Choose knowledge base" }));
    const search = screen.getByRole("searchbox", { name: "Search knowledge bases" });
    expect(search).toHaveFocus();
    expect(screen.getByRole("option", { name: "General chat" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByText("2 documents · Indexing")).toBeInTheDocument();
    await user.type(search, "NVIDIA");
    expect(screen.queryByRole("option", { name: "Team handbook" })).not.toBeInTheDocument();
    expect(screen.queryByRole("option", { name: "General chat" })).not.toBeInTheDocument();
    await user.keyboard("{ArrowDown}{Enter}");
    await waitFor(() => expect(options.onKnowledgeBaseChange).toHaveBeenCalledWith("finance"));
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    expect(screen.getByRole("textbox", { name: "Message" })).toHaveValue("Draft question");
    await waitFor(() => expect(screen.getByRole("button", { name: "Choose knowledge base" })).toHaveFocus());
  });

  it("shows search misses, management links, model selection, and empty model focus", async () => {
    const user = userEvent.setup();
    const options = props({ kbId: "finance" });
    const { rerender } = widget(options);
    expect(screen.getByRole("link", { name: "Manage knowledge base", exact: true })).toHaveAttribute("href", "/kb/finance");
    await user.click(screen.getByRole("button", { name: "Choose knowledge base" }));
    expect(screen.getByRole("link", { name: "Manage knowledge bases", exact: true })).toHaveAttribute("href", "/kb");
    await user.type(screen.getByRole("searchbox"), "General");
    expect(screen.getByRole("option", { name: "General chat" })).toBeInTheDocument();
    expect(screen.queryByText("No knowledge bases match your search.")).not.toBeInTheDocument();
    await user.clear(screen.getByRole("searchbox"));
    await user.type(screen.getByRole("searchbox"), "missing");
    expect(screen.getByText("No knowledge bases match your search.")).toBeInTheDocument();
    await user.keyboard("{Escape}");
    await user.click(screen.getByRole("button", { name: "Choose model" }));
    expect(screen.getByRole("option", { name: "Auto · Best fast" })).toHaveAttribute("aria-selected", "true");
    await user.click(screen.getByRole("option", { name: "Research model" }));
    expect(options.onModelChange).toHaveBeenCalledWith("other");
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    rerender(<MemoryRouter><ChatComposer {...options} modelConfigs={[]} /></MemoryRouter>);
    await user.click(screen.getByRole("button", { name: "Choose model" }));
    expect(screen.getByText("No models available.")).toBeInTheDocument();
    expect(screen.getByRole("dialog", { name: "Choose model" })).toHaveFocus();
    await user.keyboard("{Escape}");
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
  });

  it("disables sending while a knowledge selection is being saved", async () => {
    const user = userEvent.setup();
    let finish;
    const options = props({ onKnowledgeBaseChange: vi.fn(() => new Promise(resolve => { finish = resolve; })) });
    widget(options);
    await user.click(screen.getByRole("button", { name: "Choose knowledge base" }));
    await user.click(screen.getByRole("option", { name: "NVIDIA earnings" }));
    expect(screen.getByRole("button", { name: "Send", exact: true })).toBeDisabled();
    expect(screen.getByRole("textbox", { name: "Message" })).toBeEnabled();
    fireEvent.keyDown(screen.getByRole("textbox", { name: "Message" }), { key: "Enter" });
    expect(options.onSubmit).not.toHaveBeenCalled();
    finish(true);
    await waitFor(() => expect(screen.getByRole("button", { name: "Send", exact: true })).toBeEnabled());
  });

  it("distinguishes catalog loading from an empty catalog", async () => {
    const user = userEvent.setup();
    const options = props({ knowledgeBases: [], knowledgeLoading: true });
    const { rerender } = widget(options);
    await user.click(screen.getByRole("button", { name: "Choose knowledge base" }));
    expect(screen.getByRole("status")).toHaveTextContent("Loading knowledge bases…");
    expect(screen.queryByText(/No knowledge bases yet/)).not.toBeInTheDocument();
    rerender(<MemoryRouter><ChatComposer {...options} knowledgeLoading={false} /></MemoryRouter>);
    expect(screen.getByText(/No knowledge bases yet/)).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "General chat" })).toBeEnabled();
  });

  it("retains the draft and sends the selected knowledge base and analysis mode", async () => {
    const { user } = renderApp();
    const message = await screen.findByRole("textbox", { name: "Message" });
    await user.type(message, "Summarize this document");
    await user.click(screen.getByRole("button", { name: "Choose knowledge base" }));
    await user.click(screen.getByRole("option", { name: "Fixture Knowledge Base" }));
    await screen.findByRole("link", { name: "Manage knowledge base", exact: true });
    await user.click(screen.getByRole("button", { name: "Deep analysis" }));
    expect(screen.getByRole("button", { name: "Deep analysis" })).toHaveAttribute("aria-pressed", "true");
    expect(message).toHaveValue("Summarize this document");
    await user.click(screen.getByRole("button", { name: "Send", exact: true }));
    await waitFor(() => expect(runRequests).toHaveLength(1));
    expect(runRequests[0]).toMatchObject({ question: "Summarize this document", kb_ids: ["kb_fixture"], mode: "agentic", model_id: "default" });
  });

  it("preserves the previous selection on access errors and allows retry", async () => {
    server.use(http.patch("*/api/v2/sessions/:id", () => HttpResponse.json({ error: { code: "ACCESS_DENIED", message: "Access denied", retryable: false } }, { status: 403 })));
    const { user } = renderApp();
    const message = await screen.findByRole("textbox", { name: "Message" });
    await user.type(message, "Keep my draft");
    const trigger = screen.getByRole("button", { name: "Choose knowledge base" });
    await user.click(trigger);
    await user.click(screen.getByRole("option", { name: "Fixture Knowledge Base" }));
    const dialog = await screen.findByRole("dialog", { name: "Choose knowledge base" });
    expect(await within(dialog).findByRole("alert")).toHaveTextContent("Couldn’t update your selection");
    expect(trigger).toHaveTextContent("Knowledge base"); expect(message).toHaveValue("Keep my draft");
    server.resetHandlers();
    await user.click(screen.getByRole("option", { name: "Fixture Knowledge Base" }));
    await waitFor(() => expect(trigger).toHaveTextContent("Fixture Knowledge Base"));
    expect(message).toHaveValue("Keep my draft");
  });

  it("uses Enter to send, Shift+Enter for new lines, and respects IME composition", async () => {
    const { user } = renderApp();
    const message = await screen.findByRole("textbox", { name: "Message" });
    await user.type(message, "First line");
    await user.keyboard("{Shift>}{Enter}{/Shift}Second line");
    expect(message).toHaveValue("First line\nSecond line");
    fireEvent.keyDown(message, { key: "Enter", code: "Enter", isComposing: true });
    expect(runRequests).toHaveLength(0);
    await user.keyboard("{Enter}");
    await waitFor(() => expect(runRequests).toHaveLength(1));
    expect(runRequests[0].question).toBe("First line\nSecond line");
    expect(message).toHaveValue("");
  });
});
