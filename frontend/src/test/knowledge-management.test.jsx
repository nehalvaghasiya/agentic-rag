import { screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { renderApp } from "./render";
import { server } from "./server";
import { validateFiles } from "../components/features/knowledge-base/uploadRules";
import { acceptFixtureUpload } from "./chat-handlers";

const fixtureName = "Fixture Knowledge Base";
const documentName = "fixture-report.pdf";
const unavailable = () => HttpResponse.json({ error: { code: "UNAVAILABLE", message: "Synthetic service failure", retryable: true } }, { status: 503 });

beforeEach(() => {
  Object.defineProperty(navigator, "pdfViewerEnabled", { configurable: true, value: false });
  Object.defineProperty(URL, "createObjectURL", { configurable: true, writable: true, value: vi.fn(() => "blob:synthetic-pdf") });
  Object.defineProperty(URL, "revokeObjectURL", { configurable: true, writable: true, value: vi.fn() });
});

async function dashboard() {
  const rendered = renderApp({ route: "/kb/kb_fixture" });
  await screen.findByRole("button", { name: `Preview ${documentName}` });
  return rendered;
}

describe("knowledge management", () => {
  it("opens the library directly without creating a chat and searches existing bases", async () => {
    const create = vi.fn();
    server.use(http.post("*/api/v2/sessions", () => { create(); return unavailable(); }));
    const { user } = renderApp({ route: "/kb" });
    expect(await screen.findByRole("link", { name: fixtureName })).toBeVisible();
    expect(screen.getByRole("link", { name: "Knowledge Bases", exact: true })).toHaveAttribute("aria-current", "page");
    await user.type(screen.getByRole("searchbox"), "missing");
    expect(screen.getByText("No knowledge bases match your search.")).toBeVisible();
    await user.clear(screen.getByRole("searchbox"));
    await user.click(screen.getByRole("link", { name: `Open ${fixtureName}` }));
    expect(await screen.findByRole("heading", { name: fixtureName })).toBeVisible();
    expect(create).not.toHaveBeenCalled();
  });

  it("takes an attached chat to its dashboard and back to the library", async () => {
    const { user } = renderApp();
    await user.click(await screen.findByRole("button", { name: "Choose knowledge base" }));
    await user.click(screen.getByRole("option", { name: fixtureName }));
    await user.click(await screen.findByRole("link", { name: "Manage knowledge base" }));
    expect(await screen.findByRole("button", { name: `Preview ${documentName}` })).toBeVisible();
    await user.click(screen.getByRole("link", { name: /Back to Knowledge Bases/ }));
    expect(await screen.findByRole("link", { name: `Open ${fixtureName}` })).toBeVisible();
  });

  it("keeps failed library loading distinct from an empty library and retries", async () => {
    server.use(http.get("*/api/v2/kb", unavailable));
    const { user } = renderApp({ route: "/kb" });
    expect(await screen.findByRole("alert")).toHaveTextContent("Synthetic service failure");
    expect(screen.queryByText("No knowledge bases yet")).not.toBeInTheDocument();
    server.resetHandlers();
    await user.click(screen.getByRole("button", { name: "Retry", exact: true }));
    expect(await screen.findByRole("link", { name: fixtureName })).toBeVisible();
  });

  it("cancels deletion and keeps the document and route on server failure", async () => {
    const { user } = await dashboard();
    await user.click(screen.getByRole("button", { name: `Delete document ${documentName}` }));
    await user.click(screen.getByRole("button", { name: "Cancel", exact: true }));
    expect(screen.getByRole("button", { name: `Preview ${documentName}` })).toBeVisible();
    server.use(http.delete("*/api/v2/documents/:id", unavailable));
    await user.click(screen.getByRole("button", { name: `Delete document ${documentName}` }));
    await user.click(screen.getByRole("button", { name: "Confirm delete" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Synthetic service failure");
    expect(window.location.pathname).toBe("/kb/kb_fixture");
    expect(screen.getByRole("button", { name: `Preview ${documentName}` })).toBeVisible();
    server.resetHandlers();
    await user.click(screen.getByRole("button", { name: "Confirm delete" }));
    expect(await screen.findByText(/No documents yet/)).toBeVisible();
    expect(screen.getByRole("heading", { name: fixtureName })).toBeVisible();
  });

  it("waits for successful whole-base deletion before returning to the library", async () => {
    const { user } = await dashboard();
    server.use(http.delete("*/api/v2/kb/:id", unavailable));
    await user.click(screen.getByRole("button", { name: "Delete knowledge base", exact: true }));
    await user.click(screen.getByRole("button", { name: "Confirm delete" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Synthetic service failure");
    expect(window.location.pathname).toBe("/kb/kb_fixture");
    server.resetHandlers();
    await user.click(screen.getByRole("button", { name: "Confirm delete" }));
    expect(await screen.findByText("No knowledge bases yet")).toBeVisible();
    expect(window.location.pathname).toBe("/kb");
    expect(screen.getByRole("status")).toHaveTextContent(`Deleted knowledge base ${fixtureName}.`);
  });

  it("uploads into the existing base and allows removing selected files", async () => {
    const { user } = await dashboard();
    // Read the browser FormData before Node/undici replaces jsdom File names with "blob".
    const fetch = globalThis.fetch;
    vi.spyOn(globalThis, "fetch").mockImplementation((url, init) => {
      if (String(url).endsWith("/kb/kb_fixture/documents") && init?.method === "POST") {
        const files = init.body.getAll("files");
        expect(files.map(file => file.name)).toEqual(["notes.txt"]);
        return Promise.resolve(new Response(JSON.stringify(acceptFixtureUpload("kb_fixture", files)), { status: 202, headers: { "Content-Type": "application/json" } }));
      }
      return fetch(url, init);
    });
    await user.upload(screen.getByLabelText("Add documents", { selector: "input" }), [
      new File(["Synthetic reference"], "notes.txt", { type: "text/plain" }),
      new File(["Other reference"], "remove.txt", { type: "text/plain" }),
    ]);
    await user.click(screen.getByRole("button", { name: "Remove remove.txt" }));
    await user.click(screen.getByRole("button", { name: "Upload documents" }));
    expect(await screen.findByRole("button", { name: "Preview notes.txt" })).toBeVisible();
    expect(screen.getByRole("button", { name: `Preview ${documentName}` })).toBeVisible();
    expect(screen.queryByRole("button", { name: "Preview remove.txt" })).not.toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("Documents uploaded");
  });

  it("retains selected files and enables retry when uploading fails", async () => {
    const { user } = await dashboard();
    server.use(http.post("*/api/v2/kb/:id/documents", unavailable));
    await user.upload(screen.getByLabelText("Add documents", { selector: "input" }), new File(["Synthetic reference"], "notes.txt", { type: "text/plain" }));
    await user.click(screen.getByRole("button", { name: "Upload documents" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Synthetic service failure");
    expect(screen.getByRole("button", { name: "Remove notes.txt" })).toBeEnabled();
    expect(screen.getByRole("button", { name: "Upload documents" })).toBeEnabled();
  });

  it("recovers a created base after upload failure without creating a duplicate", async () => {
    const { user } = renderApp();
    await screen.findByRole("button", { name: "Choose knowledge base" });
    server.use(http.post("*/api/v2/kb/:id/documents", unavailable));
    const fetch = vi.spyOn(globalThis, "fetch");
    await user.click(screen.getByRole("button", { name: "Create Knowledge Base", exact: true }));
    await user.type(screen.getByPlaceholderText("e.g., Nvidia Q2 results"), "Recoverable base");
    await user.upload(screen.getByLabelText("Select documents"), new File(["Synthetic reference"], "notes.txt", { type: "text/plain" }));
    await user.click(screen.getByRole("button", { name: "Create", exact: true }));
    expect(await screen.findByText(/Your knowledge base was created/)).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Open knowledge base", exact: true }));
    expect(await screen.findByRole("heading", { name: "Recoverable base" })).toBeVisible();
    expect(fetch.mock.calls.filter(([url, init]) => String(url).endsWith("/api/v2/kb") && init?.method === "POST")).toHaveLength(1);
  });

  it("paginates extracted previews and restores focus on Escape", async () => {
    const { user } = await dashboard();
    const button = screen.getByRole("button", { name: `Preview ${documentName}` });
    await user.click(button);
    await waitFor(() => expect(screen.getByText("First.")).toBeVisible());
    await user.click(screen.getByRole("button", { name: "Next", exact: true }));
    expect(await screen.findByText("Last.")).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Previous", exact: true }));
    expect(await screen.findByText("First.")).toBeVisible();
    await user.keyboard("{Escape}");
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    expect(button).toHaveFocus();
  });

  it("uses an authorized PDF blob and revokes it when switching to text", async () => {
    Object.defineProperty(navigator, "pdfViewerEnabled", { configurable: true, value: true });
    const { user } = await dashboard();
    await user.click(screen.getByRole("button", { name: `Preview ${documentName}` }));
    expect(await screen.findByTitle(`PDF preview of ${documentName}`)).toHaveAttribute("src", "blob:synthetic-pdf");
    await user.click(screen.getByRole("button", { name: "View as text" }));
    expect(await screen.findByText("First.")).toBeVisible();
    expect(URL.revokeObjectURL).toHaveBeenCalledWith("blob:synthetic-pdf");
  });

  it("reports preview and download errors within their own controls", async () => {
    const { user } = await dashboard();
    server.use(http.get("*/api/v2/documents/:id/preview", unavailable), http.get("*/api/v2/documents/:id/download", unavailable));
    await user.click(screen.getByRole("button", { name: `Preview ${documentName}` }));
    const dialog = await screen.findByRole("dialog");
    expect(await within(dialog).findByRole("alert")).toHaveTextContent("Synthetic service failure");
    await user.click(within(dialog).getByRole("button", { name: `Download ${documentName}` }));
    await waitFor(() => expect(within(dialog).getAllByRole("alert")).toHaveLength(2));
  });

  it("validates file count, size, and supported extensions", () => {
    expect(validateFiles(Array.from({ length: 11 }, () => new File(["x"], "a.txt")))).toMatch(/at most 10/);
    expect(validateFiles([new File([], "empty.txt")])).toMatch(/non-empty/);
    expect(validateFiles([{ name: "large.pdf", size: 8 * 1024 * 1024 + 1 }])).toMatch(/8 MiB/);
    expect(validateFiles([new File(["x"], "script.exe")])).toMatch(/unsupported/);
    expect(validateFiles([new File(["{}"], "data.JSON")])).toBe("");
  });
});
