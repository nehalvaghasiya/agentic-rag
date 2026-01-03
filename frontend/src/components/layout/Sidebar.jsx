import { FolderPlus, MessageSquareText, Moon, Plus, Sun } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

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

export function Sidebar({ onOpenCreateKb }) {
  const { chatHistory, actions } = useAppState();
  const navigate = useNavigate();
  const params = useParams();

  const [theme, setTheme] = useState(() => getInitialTheme());

  useEffect(() => {
    document.documentElement.classList.toggle("dark", theme === "dark");
    try {
      window.localStorage.setItem(THEME_STORAGE_KEY, theme);
    } catch {
      // Ignore.
    }
  }, [theme]);

  const activeChatId = params.chatId ?? null;

  const recentChats = useMemo(() => {
    return [...chatHistory]
      .sort((a, b) => new Date(b.updatedAt) - new Date(a.updatedAt))
      .slice(0, 8);
  }, [chatHistory]);

  return (
    <aside className="flex h-full w-[260px] flex-col border-r border-border bg-surface">
      <div className="flex items-center gap-2 border-b border-border px-4 py-4">
        <div className="flex h-8 w-8 items-center justify-center rounded-md border border-border bg-bg text-accent">
          <MessageSquareText size={16} />
        </div>
        <div>
          <div className="text-sm font-semibold text-text">File Search</div>
          <div className="text-xs text-muted">RAG Interface</div>
        </div>

        <div className="ml-auto">
          <Button
            variant="ghost"
            size="sm"
            className="h-8 w-8 px-0"
            onClick={() => setTheme((t) => (t === "dark" ? "light" : "dark"))}
          >
            {theme === "dark" ? <Sun size={16} /> : <Moon size={16} />}
          </Button>
        </div>
      </div>

      <div className="px-4 py-4">
        <Button
          variant="primary"
          className="w-full"
          onClick={() => {
            const chat = actions.createChat({ kbId: null });
            navigate(`/chat/${chat.id}`);
          }}
        >
          <Plus size={16} />
          New Chat
        </Button>

        <Button
          variant="secondary"
          className="mt-3 w-full"
          onClick={() => onOpenCreateKb?.()}
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
                <button
                  key={chat.id}
                  type="button"
                  onClick={() => navigate(`/chat/${chat.id}`)}
                  className={`w-full rounded-md px-2 py-2 text-left text-sm transition-colors ${
                    isActive ? "bg-border/40 text-text" : "text-muted hover:bg-border/30"
                  }`}
                >
                  <div className="truncate">{chat.title}</div>
                </button>
              );
            })}
          </div>
        )}
      </div>

      <div className="border-t border-border px-4 py-4">
        <div className="flex items-center gap-3">
          <div className="h-9 w-9 rounded-full border border-border bg-bg" />
          <div className="min-w-0">
            <div className="truncate text-sm font-medium text-text">Workspace</div>
            <div className="text-xs text-muted">General</div>
          </div>
        </div>
      </div>
    </aside>
  );
}
