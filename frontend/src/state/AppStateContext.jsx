import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import {
  createKnowledgeBase as apiCreateKnowledgeBase,
  listKnowledgeBases,
  getModelConfig,
  chatWithLlmStream,
  queryKnowledgeBaseStream,
} from "../api/client";
import { createId } from "../utils/id";

const AppStateContext = createContext(null);

// LocalStorage key for persisting model configs
const MODEL_CONFIGS_KEY = "agentic-rag-model-configs";
const SELECTED_MODEL_KEY = "agentic-rag-selected-model";

function loadStoredModelConfigs() {
  try {
    const stored = localStorage.getItem(MODEL_CONFIGS_KEY);
    return stored ? JSON.parse(stored) : [];
  } catch {
    return [];
  }
}

function saveModelConfigs(configs) {
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

function saveSelectedModelId(id) {
  try {
    localStorage.setItem(SELECTED_MODEL_KEY, id);
  } catch {
    // Ignore storage errors
  }
}

function computeKbStats(knowledgeBase) {
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

function normalizeKb(kb) {
  // Map backend snake_case to frontend camelCase
  const documents = Array.isArray(kb.documents)
    ? kb.documents.map((d) => ({
        id: d.id,
        name: d.name,
        type: d.type,
        size: d.size,
        status: "Indexed",
        uploadedAt: String(d.uploaded_at || d.uploadedAt || new Date().toISOString()),
      }))
    : [];

  return {
    id: kb.id,
    name: kb.name,
    embeddingModel: kb.embedding_model || kb.embeddingModel || "text-embedding-3-large",
    rankingStrategy: kb.ranking_strategy || kb.rankingStrategy || "Hybrid",
    chunkingStrategy: kb.chunking_strategy || kb.chunkingStrategy || "Recursive (800/120)",
    createdAt: String(kb.created_at || kb.createdAt || new Date().toISOString()),
    lastModified: String(kb.last_modified || kb.lastModified || kb.created_at || new Date().toISOString()),
    fileCount: kb.file_count || kb.fileCount || documents.length,
    totalSize: kb.total_size || kb.totalSize || 0,
    documents,
  };
}

function normalizeSource(src) {
  // Map backend snake_case to frontend camelCase
  return {
    fileName: src.file_name || src.fileName || "Unknown",
    pageNumber: src.page ?? src.pageNumber ?? null,
    chunkIndex: src.chunk ?? src.chunkIndex ?? null,
    snippetText: src.snippet || src.snippetText || "",
    highlight: src.highlight || null,
    score: src.score ?? null,
    metadata: src.metadata || {},
  };
}

export function AppStateProvider({ children }) {
  const [knowledgeBases, setKnowledgeBases] = useState([]);
  const [chatHistory, setChatHistory] = useState([]);
  
  // Model configuration state
  const [modelConfigs, setModelConfigs] = useState(() => {
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
              ? { ...m, model: config.model, baseUrl: config.base_url, hasApiKey: config.has_api_key }
              : m
          )
        );
      })
      .catch((err) => {
        console.error("Failed to fetch model config:", err);
      });
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
      .catch((err) => {
        // Keep the UI usable even if the backend isn't running.
        console.error(err);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const createKnowledgeBase = useCallback(async (payload) => {
    const created = await apiCreateKnowledgeBase({
      name: payload.name,
      rankingStrategy: payload.rankingStrategy ?? "Hybrid",
      embeddingModel: payload.embeddingModel ?? "text-embedding-3-large",
      chunkingStrategy: payload.chunkingStrategy ?? "Recursive (800/120)",
      files: payload.files ?? [],
    });
    const kb = normalizeKb(created);
    setKnowledgeBases((prev) => [kb, ...prev.filter((k) => k.id !== kb.id)]);
    return kb;
  }, []);

  const deleteKnowledgeBase = useCallback((kbId) => {
    setKnowledgeBases((prev) => prev.filter((kb) => kb.id !== kbId));
    setChatHistory((prev) => prev.filter((c) => c.kbId !== kbId));
  }, []);

  const deleteDocument = useCallback((kbId, docId) => {
    setKnowledgeBases((prev) =>
      prev.map((kb) => {
        if (kb.id !== kbId) return kb;
        const nextDocs = kb.documents.filter((d) => d.id !== docId);
        return { ...kb, documents: nextDocs, lastModified: new Date().toISOString() };
      })
    );
  }, []);

  const createChat = useCallback(({ kbId }) => {
    const id = createId("chat");
    const now = new Date().toISOString();

    const kb = knowledgeBasesRef.current.find((k) => k.id === kbId);

    const chat = {
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

  const setChatKnowledgeBase = useCallback((chatId, kbId) => {
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
  const selectModel = useCallback((modelId) => {
    setSelectedModelId(modelId);
    saveSelectedModelId(modelId);
  }, []);

  const addModelConfig = useCallback((config) => {
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

  const updateModelConfig = useCallback((modelId, config) => {
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

  const deleteModelConfig = useCallback((modelId) => {
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

  const sendMessage = useCallback(async (chatId, prompt) => {
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
    const updateStreamingMessage = (updates) => {
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
        let steps = [];

        console.log("[sendMessage] Calling chatWithLlmStream...");
        await chatWithLlmStream({
          messages: [...history, { role: "user", content: trimmed }],
          modelConfig,
          onEvent: (event) => {
            console.log("[sendMessage] Received event:", event.type, event.data);
            switch (event.type) {
              case "step":
                steps = [...steps, event.data];
                updateStreamingMessage({ reasoningSteps: steps });
                break;
              case "token":
                content += event.data.token;
                updateStreamingMessage({ content });
                break;
              case "complete":
                updateStreamingMessage({
                  content: event.data.answer || content,
                  isStreaming: false,
                });
                break;
              case "error":
                updateStreamingMessage({
                  content: `Error: ${event.data.message}`,
                  isStreaming: false,
                });
                break;
            }
          },
        });
      } else {
        // Query with knowledge base
        let content = "";
        let sources = [];
        let steps = [];

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
                sources = (event.data.sources || []).map(normalizeSource);
                updateStreamingMessage({ sources });
                break;
              case "complete":
                updateStreamingMessage({
                  content: event.data.answer || content,
                  isStreaming: false,
                });
                break;
              case "error":
                updateStreamingMessage({
                  content: `Error: ${event.data.message}`,
                  isStreaming: false,
                });
                break;
            }
          },
        });
      }
    } catch (err) {
      console.error("[sendMessage] Error:", err);
      updateStreamingMessage({
        content: `Query failed: ${err?.message || String(err)}`,
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

  return <AppStateContext.Provider value={value}>{children}</AppStateContext.Provider>;
}

export function useAppState() {
  const ctx = useContext(AppStateContext);
  if (!ctx) {
    throw new Error("useAppState must be used within AppStateProvider");
  }
  return ctx;
}
