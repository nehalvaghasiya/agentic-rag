import { Database, FolderPlus, MessageSquareText, Moon, Plus, Sun, Trash2 } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { NavLink, useNavigate, useMatch } from "react-router-dom";

import { useAppState } from "../../state/AppStateContext";
import { Button } from "../ui/Button";

const THEME_STORAGE_KEY = "theme";

function getInitialTheme() {
  try {
    const stored = window.localStorage.getItem(THEME_STORAGE_KEY);
    if (stored === "light" || stored === "dark") return stored;
  } catch {
    // Ignore.
  }

  const prefersDark = window.matchMedia?.("(prefers-color-scheme: dark)")?.matches;
  return prefersDark ? "dark" : "light";
}

export function Sidebar({ onOpenCreateKb, onNavigate }) {
  const { chatHistory, actions } = useAppState();
  const navigate = useNavigate();
  const activeChat = useMatch("/chat/:chatId");

  const [theme, setTheme] = useState(() => getInitialTheme());

  useEffect(() => {
    document.documentElement.classList.toggle("dark", theme === "dark");
    try {
      window.localStorage.setItem(THEME_STORAGE_KEY, theme);
    } catch {
      // Ignore.
    }
  }, [theme]);

  const activeChatId = activeChat?.params.chatId ?? null;

  const recentChats = useMemo(() => {
    return [...chatHistory]
      .sort((a, b) => new Date(b.updatedAt) - new Date(a.updatedAt))
;
  }, [chatHistory]);

  return (
    <aside className="flex h-full w-full flex-col border-r border-border bg-surface">
      <div className="flex items-center gap-2 border-b border-border px-4 py-4">
        <div className="flex h-8 w-8 items-center justify-center rounded-md border border-border bg-bg text-accent">
          <MessageSquareText size={16} />
        </div>
        <div>
          <div className="text-sm font-semibold text-text">Chat</div>
          <div className="text-xs text-muted">Agentic RAG</div>
        </div>

        <div className="ml-auto">
          <Button
            variant="ghost"
            size="sm"
            className="h-8 w-8 px-0"
            aria-label="Toggle color theme"
            onClick={() => setTheme((t) => (t === "dark" ? "light" : "dark"))}
          >
            {theme === "dark" ? <Sun size={16} /> : <Moon size={16} />}
          </Button>
        </div>
      </div>

      <div className="px-4 py-4">
        <NavLink to="/kb" className={({ isActive }) => `mb-3 flex items-center gap-2 rounded-md px-3 py-2 text-sm font-medium ${isActive ? "bg-accent/10 text-accent" : "text-text hover:bg-border/30"}`}><Database size={16} />Knowledge Bases</NavLink>
        <Button
          variant="primary"
          className="w-full"
          onClick={() => {
            onNavigate?.();
            void actions.createChat({ kbId: null }).then(chat => navigate(`/chat/${chat.id}`)).catch(() => {});
          }}
        >
          <Plus size={16} />
          New Chat
        </Button>

        <Button
          variant="secondary"
          className="mt-3 w-full"
          onClick={() => { onNavigate?.(); onOpenCreateKb?.(); }}
        >
          <FolderPlus size={16} />
          Create Knowledge Base
        </Button>
      </div>

      <div className="px-4">
        <div className="text-xs font-semibold text-muted">Recent Activity</div>
      </div>

      <div className="mt-2 flex-1 overflow-auto px-2 pb-2">
        {recentChats.length === 0 ? (
          <div className="px-2 py-2 text-xs text-muted">No chats yet.</div>
        ) : (
          <div className="space-y-1">
            {recentChats.map((chat) => {
              const isActive = chat.id === activeChatId;
              return (
                <div key={chat.id} className="flex items-center gap-1">
                <button
                  type="button"
                  onClick={() => { onNavigate?.(); navigate(`/chat/${chat.id}`); }}
                  className={`min-w-0 flex-1 rounded-md px-2 py-2 text-left text-sm transition-colors ${
                    isActive ? "bg-border/40 text-text" : "text-muted hover:bg-border/30"
                  }`}
                >
                  <div className="truncate">{chat.title}</div>
                </button>
                <button aria-label={`Delete chat ${chat.title}`} className="rounded p-2 text-muted hover:bg-border/30" onClick={async () => {
                  await actions.deleteChat(chat.id); if (chat.id === activeChatId) navigate("/");
                }}><Trash2 size={13} /></button>
                </div>
              );
            })}
          </div>
        )}
      </div>

      <div className="border-t border-border px-4 py-4">
        <div className="flex items-center gap-3">
          <div className="h-9 w-9 rounded-full border border-border bg-bg" />
          <div className="min-w-0">
            <div className="truncate text-sm font-medium text-text">Local chat</div>
            <div className="text-xs text-muted">General</div>
          </div>
        </div>
      </div>
    </aside>
  );
}
