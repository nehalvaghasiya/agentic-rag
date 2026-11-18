import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { ChatBubble } from "../components/features/chat/ChatBubble";
import { SourceList } from "../components/features/chat/SourceList";
import { SidePanel } from "../components/ui/SidePanel";

const sources = [
  { id: "passage-1", kind: "document", document_id: "report", version: 1, title: "Financial report.pdf", page: 1, excerpt: "First cited passage." },
  { id: "passage-2", kind: "document", document_id: "report", version: 1, title: "Financial report.pdf", page: 2, excerpt: "Second cited passage." },
  { id: "tool-1", kind: "tool", title: "Calculator", excerpt: "42", tool: "calculate" },
];

describe("response presentation", () => {
  it("keeps successful response metadata hidden and offers it through the menu", async () => {
    const user = userEvent.setup();
    const onOpen = vi.fn();
    render(<ChatBubble role="assistant" content="Hello!" isLatest onOpen={onOpen}
      run={{ model: "private-model", latency_ms: 7300, execution_path: "direct", grounding: "model", served_from_cache: true }}
      events={[{ id: 1, type: "route", data: { title: "Execution activity" } }]} />);
    for (const text of ["private-model", "7.3 s", "Direct LLM", "Cached response", "Execution activity", "No external sources used"]) {
      expect(screen.queryByText(text)).not.toBeInTheDocument();
    }
    await user.click(screen.getByRole("button", { name: "More response options" }));
    expect(screen.queryByRole("menuitem", { name: "View sources" })).not.toBeInTheDocument();
    await user.keyboard("{ArrowDown}{Enter}");
    expect(onOpen).toHaveBeenCalledWith("activity");
    expect(screen.getByRole("button", { name: "More response options" })).toHaveFocus();
  });

  it("uses document chips and sends exact passage IDs without rendering excerpts", async () => {
    const user = userEvent.setup();
    const onOpen = vi.fn();
    render(<ChatBubble role="assistant" content="Revenue grew. [1] [2] Another result. [3]" sources={sources} onOpen={onOpen} />);
    expect(screen.queryByText("First cited passage.")).not.toBeInTheDocument();
    const report = screen.getByRole("button", { name: "View source: Financial report.pdf, page 1" });
    expect(screen.getAllByText("Financial report.pdf")).toHaveLength(1);
    await user.click(report);
    expect(onOpen).toHaveBeenCalledWith("sources", ["passage-1", "passage-2"]);
    await user.click(screen.getByRole("button", { name: "More response options" }));
    await user.click(screen.getByRole("menuitem", { name: "View sources" }));
    expect(onOpen).toHaveBeenLastCalledWith("sources");
  });

  it("copies the answer separately from its bibliography and handles clipboard denial", async () => {
    const user = userEvent.setup();
    const copy = vi.spyOn(navigator.clipboard, "writeText").mockResolvedValue(undefined);
    render(<ChatBubble role="assistant" content="Revenue grew. [1]" sources={sources.slice(0, 1)} />);
    await user.click(screen.getByRole("button", { name: "Copy response" }));
    expect(copy).toHaveBeenLastCalledWith("Revenue grew. [1]");
    await user.click(screen.getByRole("button", { name: "More response options" }));
    await user.click(screen.getByRole("menuitem", { name: "Copy with citations" }));
    expect(copy).toHaveBeenLastCalledWith("Revenue grew. [1]\n\nSources\n[1] Financial report.pdf · Page 1 · Version 1");
    copy.mockRejectedValueOnce(new Error("denied"));
    await user.click(screen.getByRole("button", { name: "Copied" }));
    expect(await screen.findByText("Couldn’t copy. Select the answer text to copy it.")).toBeInTheDocument();
  });

  it("counts completed answer versions and disables generation during updates", async () => {
    const user = userEvent.setup();
    const onVersion = vi.fn();
    const props = { role: "assistant", content: "Second answer", isLatest: true, runId: "second", onVersion,
      versions: [{ run_id: "first", status: "completed" }, { run_id: "second", status: "completed" }, { run_id: "failed", status: "failed" }] };
    const { rerender } = render(<ChatBubble {...props} />);
    expect(screen.getByText("2 / 2")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Previous answer version" }));
    expect(onVersion).toHaveBeenCalledWith("first");
    rerender(<ChatBubble {...props} versionBusy />);
    expect(screen.getByRole("button", { name: "Regenerate response" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Previous answer version" })).toBeDisabled();
  });

  it("groups source passages and suppresses unavailable excerpts", async () => {
    const user = userEvent.setup();
    render(<SourceList sources={[...sources.slice(0, 2), { ...sources[2], available: false, excerpt: "private unavailable text" }]} selectedIds={["passage-2"]} />);
    expect(screen.getAllByRole("heading", { name: "Financial report.pdf" })).toHaveLength(1);
    expect(screen.getByText("Second cited passage.")).toBeInTheDocument();
    expect(screen.queryByText("private unavailable text")).not.toBeInTheDocument();
    expect(screen.getByText("This source is no longer available.")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Show more" }));
    expect(screen.getByRole("button", { name: "Show less" })).toHaveAttribute("aria-expanded", "true");
  });

  it("contains focus in an overlay and restores the trigger on close", async () => {
    const user = userEvent.setup();
    const close = vi.fn();
    const trigger = document.createElement("button"); trigger.textContent = "Source trigger";
    document.body.appendChild(trigger); trigger.focus();
    const { unmount } = render(<SidePanel title="Sources" onClose={close}><button type="button">Open document</button></SidePanel>);
    expect(screen.getByRole("heading", { name: "Sources" })).toHaveFocus();
    await user.keyboard("{Shift>}{Tab}{/Shift}");
    expect(screen.getByRole("button", { name: "Open document" })).toHaveFocus();
    await user.keyboard("{Tab}");
    expect(screen.getByRole("button", { name: "Close sources" })).toHaveFocus();
    await user.keyboard("{Escape}");
    expect(close).toHaveBeenCalledOnce();
    unmount();
    await waitFor(() => expect(trigger).toHaveFocus());
    trigger.remove();
  });
});
