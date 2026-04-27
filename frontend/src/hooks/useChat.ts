import { useCallback, useEffect, useRef, useState } from "react";
import { SessionService } from "../services/SessionService";
import type { Citation } from "./useStreaming";
import { useStreaming } from "./useStreaming";
import type { ChatMessageModel, ChatModel } from "../types/chat";

type ChatRequestBody = {
  query: string;
  workspace_id: number;
  model: ChatModel;
  filters?: { include_extensions: string[]; exclude_folders: string[] };
};

type UseChatParams = {
  activeSessionId: number | null;
  activeWorkspaceId: number | null;
  tenant: string;
  apiKey?: string;
  showToast: (msg: string) => void;
};

const normalizeCitations = (
  raw: { citations?: Citation[] } | Citation[] | null | undefined
): Citation[] | undefined => {
  if (!raw) return undefined;
  if (Array.isArray(raw)) return raw;
  if (Array.isArray(raw.citations)) return raw.citations;
  return undefined;
};

const parseFilterList = (value: string) =>
  value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);

export const useChat = ({
  activeSessionId,
  activeWorkspaceId,
  tenant,
  apiKey,
  showToast,
}: UseChatParams) => {
  const [messages, setMessages] = useState<ChatMessageModel[]>([]);
  const [input, setInput] = useState("");
  const [showFilters, setShowFilters] = useState(false);
  const [includeFilter, setIncludeFilter] = useState("");
  const [excludeFilter, setExcludeFilter] = useState("");
  const [selectedModel, setSelectedModel] = useState<ChatModel>("gpt-4o");

  const bottomRef = useRef<HTMLDivElement | null>(null);
  const { isStreaming, error, stream, abort } = useStreaming<ChatRequestBody>();

  // Load history when session changes; clear messages immediately
  useEffect(() => {
    setMessages([]);
    if (!activeSessionId) return;

    const load = async () => {
      try {
        const history = await SessionService.history(activeSessionId);
        setMessages(
          history.map((item) => ({
            id: String(item.id),
            role: item.role === "user" ? "user" : ("bot" as "user" | "bot"),
            content: item.content,
            sources: normalizeCitations(item.sources),
          }))
        );
      } catch (e) {
        showToast(e instanceof Error ? e.message : "Failed to load chat history.");
      }
    };
    void load();
  }, [activeSessionId]);

  // Scroll to bottom on new messages or streaming state change
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isStreaming]);

  // Show streaming error as toast
  useEffect(() => {
    if (!error) return;
    showToast(error);
  }, [error, showToast]);

  const clearMessages = useCallback(() => setMessages([]), []);

  const handleSend = useCallback(async () => {
    const trimmed = input.trim();
    if (!trimmed || !activeWorkspaceId || !activeSessionId || isStreaming) return;

    setInput("");
    setMessages((prev) => [
      ...prev,
      { id: crypto.randomUUID(), role: "user", content: trimmed },
    ]);

    await stream({
      url: `/chat/${activeSessionId}/stream`,
      body: {
        query: trimmed,
        workspace_id: activeWorkspaceId,
        model: selectedModel,
        filters: showFilters
          ? {
              include_extensions: parseFilterList(includeFilter),
              exclude_folders: parseFilterList(excludeFilter),
            }
          : undefined,
      },
      tenantId: tenant,
      apiKey,
      onToken: (token) => {
        setMessages((prev) => {
          const last = prev[prev.length - 1];
          if (last?.role === "bot") {
            return [
              ...prev.slice(0, -1),
              { ...last, content: last.content + token },
            ];
          }
          // First token: create the bot message
          return [...prev, { id: crypto.randomUUID(), role: "bot" as const, content: token }];
        });
      },
      onCitations: (citations) => {
        setMessages((prev) => {
          const last = prev[prev.length - 1];
          if (last?.role === "bot") {
            return [...prev.slice(0, -1), { ...last, sources: citations }];
          }
          return prev;
        });
      },
      onDone: () => {},
    });
  }, [
    input,
    activeWorkspaceId,
    activeSessionId,
    isStreaming,
    selectedModel,
    showFilters,
    includeFilter,
    excludeFilter,
    tenant,
    apiKey,
    stream,
  ]);

  const handlePrimaryAction = useCallback(() => {
    if (isStreaming) {
      abort();
      showToast("Generation stopped");
      return;
    }
    void handleSend();
  }, [isStreaming, abort, handleSend, showToast]);

  const handleEnter = useCallback(
    (event: React.KeyboardEvent<HTMLInputElement>) => {
      if (event.key === "Enter" && !event.shiftKey) {
        event.preventDefault();
        if (!isStreaming) void handleSend();
      }
    },
    [isStreaming, handleSend]
  );

  return {
    messages,
    input,
    showFilters,
    includeFilter,
    excludeFilter,
    selectedModel,
    isStreaming,
    bottomRef,
    setInput,
    setShowFilters,
    setIncludeFilter,
    setExcludeFilter,
    setSelectedModel,
    clearMessages,
    handleSend,
    handlePrimaryAction,
    handleEnter,
  };
};
