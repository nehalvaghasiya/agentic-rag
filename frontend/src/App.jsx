import { useEffect, useState } from "react";
import { BrowserRouter, Navigate, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import { CreateKnowledgeBaseModal } from "./components/features/knowledge-base/CreateKnowledgeBaseModal";
import { MainWrapper } from "./components/layout/MainWrapper";
import { Sidebar } from "./components/layout/Sidebar";
import { ErrorBoundary } from "./components/ui/ErrorBoundary";
import { AppStateProvider, useAppState } from "./state/AppStateContext";
import { ChatView } from "./views/ChatView";
import { KnowledgeBaseDashboard } from "./views/KnowledgeBaseDashboard";
import { KnowledgeBaseLibrary } from "./views/KnowledgeBaseLibrary";

function AppShell() {
  const navigate = useNavigate();
  const location = useLocation();
  const { actions, loading, failure, ephemeral } = useAppState();
  const [createKbOpen, setCreateKbOpen] = useState(false);
  const [navigationError, setNavigationError] = useState("");
  useEffect(() => {
    let stored;
    try { stored = window.localStorage.getItem("theme"); } catch { /* Use the system preference. */ }
    const dark = stored === "dark" || (stored !== "light" && window.matchMedia?.("(prefers-color-scheme: dark)").matches);
    document.documentElement.classList.toggle("dark", Boolean(dark));
  }, []);
  useEffect(() => {
    if (location.pathname !== "/" || loading || failure) return;
    let active = true;
    actions.startChat().then(chat => { if (active) navigate(`/chat/${chat.id}`, { replace: true }); })
      .catch(() => setNavigationError("Unable to create a chat. Check the backend connection."));
    return () => { active = false; };
  }, [location.pathname, actions, loading, failure, navigate]);
  return <MainWrapper sidebar={<Sidebar onOpenCreateKb={() => setCreateKbOpen(true)} />}>
    <div className="flex h-full min-h-0 flex-col">
      {(failure || navigationError) && <div role="alert" className="flex items-center gap-3 border-b border-red-400/40 bg-red-400/10 p-3 text-sm text-text">
        <span>{failure || navigationError}</span><button onClick={() => { setNavigationError(""); void actions.refresh(); }} className="underline">Reconnect</button>
      </div>}
      {ephemeral && <div className="border-b border-border py-2 pl-16 pr-6 text-xs text-muted lg:pl-6">Temporary demo storage — use npm run dev with PostgreSQL to retain chats after restart.</div>}
      <CreateKnowledgeBaseModal open={createKbOpen} onClose={() => setCreateKbOpen(false)} onOpenCreated={id => navigate(`/kb/${id}`)} onCreate={async payload => {
        const kb = await actions.createKnowledgeBase(payload); setCreateKbOpen(false); navigate(`/kb/${kb.id}`);
      }} />
      <div className="min-h-0 flex-1"><Routes>
        <Route path="/" element={<div className="p-8 text-sm text-muted">{loading ? "Connecting to chat…" : "Opening chat…"}</div>} />
        <Route path="/agent" element={<Navigate to="/" replace />} />
        <Route path="/kb" element={<KnowledgeBaseLibrary onCreate={() => setCreateKbOpen(true)} />} />
        <Route path="/kb/:kbId" element={<KnowledgeBaseDashboard />} />
        <Route path="/chat/:chatId" element={<ChatView />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes></div>
    </div>
  </MainWrapper>;
}
export default function App() {
  return <AppStateProvider><BrowserRouter><ErrorBoundary><AppShell /></ErrorBoundary></BrowserRouter></AppStateProvider>;
}
