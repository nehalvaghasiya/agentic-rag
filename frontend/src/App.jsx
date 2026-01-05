import { useEffect, useState } from "react";
import { BrowserRouter, Route, Routes, useNavigate, useLocation } from "react-router-dom";

import { CreateKnowledgeBaseModal } from "./components/features/knowledge-base/CreateKnowledgeBaseModal";
import { MainWrapper } from "./components/layout/MainWrapper";
import { Sidebar } from "./components/layout/Sidebar";
import { ErrorBoundary } from "./components/ui/ErrorBoundary";
import { AppStateProvider, useAppState } from "./state/AppStateContext";
import { ChatView } from "./views/ChatView";
import { KnowledgeBaseDashboard } from "./views/KnowledgeBaseDashboard";

function AppShell() {
  const navigate = useNavigate();
  const location = useLocation();
  const { knowledgeBases, actions } = useAppState();
  const [createKbOpen, setCreateKbOpen] = useState(false);

  // Auto-create a chat when user lands on "/" so there's no extra click.
  useEffect(() => {
    if (location.pathname === "/") {
      const chat = actions.createChat({ kbId: null });
      navigate(`/chat/${chat.id}`, { replace: true });
    }
  }, [location.pathname, actions, navigate]);

  return (
    <MainWrapper sidebar={<Sidebar onOpenCreateKb={() => setCreateKbOpen(true)} />}>
      <CreateKnowledgeBaseModal
        open={createKbOpen}
        onClose={() => setCreateKbOpen(false)}
        onCreate={async (payload) => {
          const kb = await actions.createKnowledgeBase(payload);
          setCreateKbOpen(false);
          navigate(`/kb/${kb.id}`);
        }}
      />

      <Routes>
        <Route path="/" element={null} />
        <Route path="/kb/:kbId" element={<KnowledgeBaseDashboard />} />
        <Route path="/chat/:chatId" element={<ChatView />} />
      </Routes>
    </MainWrapper>
  );
}

export default function App() {
  return (
    <AppStateProvider>
      <BrowserRouter>
        <ErrorBoundary>
          <AppShell />
        </ErrorBoundary>
      </BrowserRouter>
    </AppStateProvider>
  );
}
