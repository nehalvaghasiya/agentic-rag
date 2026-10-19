import {
  type ReactNode,
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import {
  ApiError,
  describeApiError,
  createKnowledgeBase as apiCreateKnowledgeBase,
  listKnowledgeBases,
  getModelConfig,
  chatWithLlmStream,
  queryKnowledgeBaseStream,
} from "../api/client";
import { normalizeKb, normalizeSource, normalizeModelConfig, type KnowledgeBase, type Source, type ModelSettings } from "../api/adapters";
import { assertNever, type Dto } from "../api/contracts";
import type { CreateKnowledgeBaseParams } from "../api/client";
import { createId } from "../utils/id";

type ModelEntry = ModelSettings & { id: string; name: string; isDefault: boolean; hasApiKey: boolean };
type Message = {
  id: string; role: string; content: string; sources: Source[];
  isStreaming?: boolean; reasoningSteps?: Dto<"StepEvent">[];
  error?: Pick<ApiError, "code" | "message" | "retryable" | "correlationId" | "details" | "httpStatus"> | null;
};
type Chat = { id: string; kbId: string | null; title: string; updatedAt: string; messages: Message[] };
const AppStateContext = createContext<ReturnType<typeof useAppStateValue> | null>(null);

// LocalStorage key for persisting model configs
const MODEL_CONFIGS_KEY = "agentic-rag-model-configs";
const SELECTED_MODEL_KEY = "agentic-rag-selected-model";

function loadStoredModelConfigs(): ModelEntry[] {
  try {
    const stored = localStorage.getItem(MODEL_CONFIGS_KEY);
    const entries: unknown = stored ? JSON.parse(stored) : [];
    if (!Array.isArray(entries)) return [];
    return entries.filter((entry: unknown): entry is ModelEntry => {
      if (!entry || typeof entry !== "object") return false;
      return "id" in entry && typeof entry.id === "string" &&
        "name" in entry && typeof entry.name === "string" &&
        "isDefault" in entry && typeof entry.isDefault === "boolean" &&
        "hasApiKey" in entry && typeof entry.hasApiKey === "boolean" &&
        (!("model" in entry) || typeof entry.model === "string") &&
        (!("apiKey" in entry) || typeof entry.apiKey === "string") &&
        (!("baseUrl" in entry) || entry.baseUrl === null || typeof entry.baseUrl === "string");
    });
  } catch {
    return [];
  }
}

function saveModelConfigs(configs: ModelEntry[]) {
  try {
    // Don't save the default model or API keys
    const toSave = configs
      .filter((c) => !c.isDefault)
      .map(({ apiKey, ...rest }) => ({ ...rest, hasApiKey: !!apiKey }));
    localStorage.setItem(MODEL_CONFIGS_KEY, JSON.stringify(toSave));
  } catch {
    // Ignore storage errors
  }
}

function loadSelectedModelId() {
  try {
    return localStorage.getItem(SELECTED_MODEL_KEY) || "default";
  } catch {
    return "default";
  }
}

function saveSelectedModelId(id: string) {
  try {
    localStorage.setItem(SELECTED_MODEL_KEY, id);
  } catch {
    // Ignore storage errors
  }
}

function computeKbStats(knowledgeBase: KnowledgeBase) {
  const fileCount = knowledgeBase.documents.length;
  const totalSize = knowledgeBase.documents.reduce((sum, doc) => sum + doc.size, 0);

  return {
    totalSize,
    fileCount,
    rankingStrategy: knowledgeBase.rankingStrategy,
    embeddingModel: knowledgeBase.embeddingModel,
    chunkingStrategy: knowledgeBase.chunkingStrategy,
    lastModified: knowledgeBase.lastModified,
  };
}

function useAppStateValue() {
  const [knowledgeBases, setKnowledgeBases] = useState<KnowledgeBase[]>([]);
  const [chatHistory, setChatHistory] = useState<Chat[]>([]);

  // Model configuration state
  const [modelConfigs, setModelConfigs] = useState<ModelEntry[]>(() => {
    const stored = loadStoredModelConfigs();
    // Always include a default model entry
    return [
      { id: "default", name: "Default", isDefault: true, hasApiKey: false },
      ...stored,
    ];
  });
  const [selectedModelId, setSelectedModelId] = useState(loadSelectedModelId);

  const knowledgeBasesRef = useRef(knowledgeBases);
  const chatHistoryRef = useRef(chatHistory);
  const modelConfigsRef = useRef(modelConfigs);
  const selectedModelIdRef = useRef(selectedModelId);

  knowledgeBasesRef.current = knowledgeBases;
  chatHistoryRef.current = chatHistory;
  modelConfigsRef.current = modelConfigs;
  selectedModelIdRef.current = selectedModelId;

  // Fetch default model config from backend
  useEffect(() => {
    let cancelled = false;
    getModelConfig()
      .then((config) => {
        if (cancelled) return;
        setModelConfigs((prev) =>
          prev.map((m) =>
            m.isDefault
              ? { ...m, ...normalizeModelConfig(config) }
              : m
          )
        );
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    listKnowledgeBases()
      .then((kbs) => {
        if (cancelled) return;
        setKnowledgeBases(kbs.map(normalizeKb));
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, []);

  const createKnowledgeBase = useCallback(async (payload: CreateKnowledgeBaseParams) => {
    const created = await apiCreateKnowledgeBase({
      name: payload.name,
      embeddingModel: payload.embeddingModel ?? "text-embedding-3-large",
      files: payload.files ?? [],
    });
    const kb = normalizeKb(created);
    setKnowledgeBases((prev) => [kb, ...prev.filter((k) => k.id !== kb.id)]);
    return kb;
  }, []);

  const deleteKnowledgeBase = useCallback((kbId: string) => {
    setKnowledgeBases((prev) => prev.filter((kb) => kb.id !== kbId));
    setChatHistory((prev) => prev.filter((c) => c.kbId !== kbId));
  }, []);

  const deleteDocument = useCallback((kbId: string, docId: string) => {
    setKnowledgeBases((prev) =>
      prev.map((kb) => {
        if (kb.id !== kbId) return kb;
        const nextDocs = kb.documents.filter((d) => d.id !== docId);
        return { ...kb, documents: nextDocs, lastModified: new Date().toISOString() };
      })
    );
  }, []);

  const createChat = useCallback(({ kbId }: { kbId?: string | null }) => {
    const id = createId("chat");
    const now = new Date().toISOString();

    const kb = knowledgeBasesRef.current.find((k) => k.id === kbId);

    const chat: Chat = {
      id,
      kbId: kbId ?? null,
      title: "New chat",
      updatedAt: now,
      messages: [
        {
          id: createId("m"),
          role: "ai",
          content: kb
            ? `Ask me anything about **${kb.name}**. I’ll cite sources when available.`
            : "Ask me anything. If you attach a knowledge base to this chat, I’ll cite sources.",
          sources: [],
        },
      ],
    };

    setChatHistory((prev) => [chat, ...prev]);
    return chat;
  }, []);

  const setChatKnowledgeBase = useCallback((chatId: string, kbId: string | null) => {
    setChatHistory((prev) =>
      prev.map((c) => {
        if (c.id !== chatId) return c;
        return {
          ...c,
          kbId: kbId || null,
          updatedAt: new Date().toISOString(),
        };
      })
    );
  }, []);

  // Model configuration actions
  const selectModel = useCallback((modelId: string) => {
    setSelectedModelId(modelId);
    saveSelectedModelId(modelId);
  }, []);

  const addModelConfig = useCallback((config: ModelSettings & { name: string }) => {
    const newModel = {
      id: createId("model"),
      name: config.name,
      apiKey: config.apiKey,
      model: config.model,
      baseUrl: config.baseUrl,
      hasApiKey: !!config.apiKey,
      isDefault: false,
    };
    setModelConfigs((prev) => {
      const next = [...prev, newModel];
      saveModelConfigs(next);
      return next;
    });
    // Auto-select the newly added model
    selectModel(newModel.id);
    return newModel;
  }, [selectModel]);

  const updateModelConfig = useCallback((modelId: string, config: ModelSettings & { name?: string }) => {
    setModelConfigs((prev) => {
      const next = prev.map((m) => {
        if (m.id !== modelId) return m;
        return {
          ...m,
          name: config.name ?? m.name,
          apiKey: config.apiKey ?? m.apiKey,
          model: config.model ?? m.model,
          baseUrl: config.baseUrl ?? m.baseUrl,
          hasApiKey: config.apiKey ? true : m.hasApiKey,
        };
      });
      saveModelConfigs(next);
      return next;
    });
  }, []);

  const deleteModelConfig = useCallback((modelId: string) => {
    setModelConfigs((prev) => {
      const next = prev.filter((m) => m.id !== modelId);
      saveModelConfigs(next);
      return next;
    });
    // If deleted model was selected, switch to default
    if (selectedModelIdRef.current === modelId) {
      selectModel("default");
    }
  }, [selectModel]);

  // Get the current model config for API calls
  const getSelectedModelConfig = useCallback(() => {
    const model = modelConfigsRef.current.find((m) => m.id === selectedModelIdRef.current);
    if (!model || model.isDefault) {
      return null; // Use backend defaults
    }
    return {
      apiKey: model.apiKey,
      model: model.model,
      baseUrl: model.baseUrl,
    };
  }, []);

  const sendMessage = useCallback(async (chatId: string, prompt: string) => {
    const trimmed = prompt.trim();
    if (!trimmed) return;

    const chat = chatHistoryRef.current.find((c) => c.id === chatId);
    const kbId = chat?.kbId ?? null;

    // Create user message
    const userMsgId = createId("m");
    setChatHistory((prev) =>
      prev.map((chat) => {
        if (chat.id !== chatId) return chat;
        const now = new Date().toISOString();
        const next = {
          ...chat,
          title: chat.title === "New chat" ? trimmed.slice(0, 32) : chat.title,
          updatedAt: now,
          messages: [
            ...chat.messages,
            {
              id: userMsgId,
              role: "user",
              content: trimmed,
              sources: [],
            },
          ],
        };
        return next;
      })
    );

    // Create placeholder AI message for streaming
    const aiMsgId = createId("m");
    setChatHistory((prev) =>
      prev.map((c) => {
        if (c.id !== chatId) return c;
        return {
          ...c,
          updatedAt: new Date().toISOString(),
          messages: [
            ...c.messages,
            {
              id: aiMsgId,
              role: "ai",
              content: "",
              sources: [],
              isStreaming: true,
              reasoningSteps: [],
            },
          ],
        };
      })
    );

    // Helper to update the streaming message
    const updateStreamingMessage = (updates: Partial<Message>) => {
      setChatHistory((prev) =>
        prev.map((c) => {
          if (c.id !== chatId) return c;
          return {
            ...c,
            updatedAt: new Date().toISOString(),
            messages: c.messages.map((m) =>
              m.id === aiMsgId ? { ...m, ...updates } : m
            ),
          };
        })
      );
    };

    try {
      // Get the selected model config for API calls
      const modelConfig = getSelectedModelConfig();

      if (!kbId) {
        // Chat without knowledge base
        const history = (chat?.messages ?? [])
          .filter((m) => typeof m?.content === "string" && m.content.trim().length > 0)
          .map((m) => ({
            role: m.role === "ai" ? "assistant" : "user",
            content: m.content,
          }));

        let content = "";
        let steps: Dto<"StepEvent">[] = [];

        await chatWithLlmStream({
          messages: [...history, { role: "user", content: trimmed }],
          modelConfig,
          onEvent: (event) => {
            switch (event.type) {
              case "step":
                steps = [...steps, event.data];
                updateStreamingMessage({ reasoningSteps: steps });
                break;
              case "token":
                content += event.data.token;
                updateStreamingMessage({ content });
                break;
              case "sources":
                break;
              case "complete":
                updateStreamingMessage({
                  content: event.data.answer,
                  isStreaming: false,
                });
                break;
              default:
                assertNever(event);
            }
          },
        });
      } else {
        // Query with knowledge base
        let content = "";
        let sources: Source[] = [];
        let steps: Dto<"StepEvent">[] = [];

        await queryKnowledgeBaseStream({
          kbId,
          question: trimmed,
          modelConfig,
          onEvent: (event) => {
            switch (event.type) {
              case "step":
                steps = [...steps, event.data];
                updateStreamingMessage({ reasoningSteps: steps });
                break;
              case "token":
                content += event.data.token;
                updateStreamingMessage({ content });
                break;
              case "sources":
                sources = event.data.sources.map(normalizeSource);
                updateStreamingMessage({ sources });
                break;
              case "complete":
                updateStreamingMessage({
                  content: event.data.answer,
                  isStreaming: false,
                });
                break;
              default:
                assertNever(event);
            }
          },
        });
      }
    } catch (err) {
      updateStreamingMessage({
        content: describeApiError(err),
        error: err instanceof ApiError ? {
          code: err.code, message: err.message, retryable: err.retryable,
          correlationId: err.correlationId, details: err.details, httpStatus: err.httpStatus,
        } : null,
        isStreaming: false,
      });
    }
  }, [getSelectedModelConfig]);

  const value = useMemo(() => {
    return {
      knowledgeBases,
      chatHistory,
      modelConfigs,
      selectedModelId,
      actions: {
        computeKbStats,
        createKnowledgeBase,
        deleteKnowledgeBase,
        deleteDocument,
        createChat,
        setChatKnowledgeBase,
        sendMessage,
        // Model config actions
        selectModel,
        addModelConfig,
        updateModelConfig,
        deleteModelConfig,
      },
    };
  }, [
    knowledgeBases,
    chatHistory,
    modelConfigs,
    selectedModelId,
    createKnowledgeBase,
    deleteKnowledgeBase,
    deleteDocument,
    createChat,
    setChatKnowledgeBase,
    sendMessage,
    selectModel,
    addModelConfig,
    updateModelConfig,
    deleteModelConfig,
  ]);

  return value;
}

export function AppStateProvider({ children }: { children: ReactNode }) {
  const value = useAppStateValue();
  return <AppStateContext.Provider value={value}>{children}</AppStateContext.Provider>;
}

export function useAppState() {
  const ctx = useContext(AppStateContext);
  if (!ctx) {
    throw new Error("useAppState must be used within AppStateProvider");
  }
  return ctx;
}
