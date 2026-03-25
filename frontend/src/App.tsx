import React, { useEffect, useMemo, useRef, useState } from "react";
import apiClient from "./services/apiClient";
import { AnimatePresence, motion } from "framer-motion";
import {
  Command,
  FolderPlus,
  Loader2,
  PlayCircle,
  Plus,
  Search,
  Square,
  Trash2,
} from "lucide-react";

import ChatMessage, { ChatMessageModel } from "./components/ChatMessage";
import { Citation, useStreaming } from "./hooks/useStreaming";

type Workspace = {
  id: number;
  name: string;
  root_path: string;
  status: "IDLE" | "INDEXING" | "FAILED";
  created_at: string;
  last_indexed_at?: string | null;
};

type Session = {
  id: number;
  title: string;
  workspaceId: number;
  createdAt: string;
};

type ChatModel = "gpt-3.5-turbo" | "gpt-4o" | "gpt-4-turbo";

type ChatHistoryItem = {
  role: string;
  content: string;
  sources?: { citations?: Citation[] } | Citation[] | null;
};

const MODEL_OPTIONS: Array<{ value: ChatModel; label: string }> = [
  { value: "gpt-3.5-turbo", label: "gpt-3.5-turbo (Fast)" },
  { value: "gpt-4o", label: "gpt-4o (Smart)" },
  { value: "gpt-4-turbo", label: "gpt-4-turbo" },
];

const normalizeCitations = (
  raw: { citations?: Citation[] } | Citation[] | null | undefined
): Citation[] | undefined => {
  if (!raw) {
    return undefined;
  }
  if (Array.isArray(raw)) {
    return raw;
  }
  if (Array.isArray(raw.citations)) {
    return raw.citations;
  }
  return undefined;
};

const App: React.FC = () => {
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [activeWorkspaceId, setActiveWorkspaceId] = useState<number | null>(null);
  const [sessions, setSessions] = useState<Session[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<number | null>(null);

  const [messages, setMessages] = useState<ChatMessageModel[]>([]);
  const [input, setInput] = useState("");
  const [showWorkspaceModal, setShowWorkspaceModal] = useState(false);
  const [newWorkspaceName, setNewWorkspaceName] = useState("");
  const [newWorkspacePath, setNewWorkspacePath] = useState("");

  const [showFilters, setShowFilters] = useState(false);
  const [includeFilter, setIncludeFilter] = useState("");
  const [excludeFilter, setExcludeFilter] = useState("");
  const [toast, setToast] = useState<string | null>(null);
  const [selectedModel, setSelectedModel] = useState<ChatModel>("gpt-4o");
  const [isSyncing, setIsSyncing] = useState(false);
  const [syncTaskId, setSyncTaskId] = useState<string | null>(null);
  const [tenant, setTenant] = useState<string>("tenant-a");

  const bottomRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    apiClient.defaults.headers.common["X-Tenant-ID"] = tenant;
    setWorkspaces([]);
    setActiveWorkspaceId(null);
    setSessions([]);
    setActiveSessionId(null);
    setMessages([]);
  }, [tenant]);

  const { isStreaming, error, stream, abort } = useStreaming<{
    query: string;
    workspace_id: number;
    model: ChatModel;
    filters?: {
      include_extensions: string[];
      exclude_folders: string[];
    };
  }>();

  const activeWorkspace = useMemo(
    () => workspaces.find((workspace) => workspace.id === activeWorkspaceId),
    [workspaces, activeWorkspaceId]
  );
  const isIndexing = isSyncing || activeWorkspace?.status === "INDEXING";

  const activeSessions = useMemo(
    () => sessions.filter((session) => session.workspaceId === activeWorkspaceId),
    [sessions, activeWorkspaceId]
  );

  useEffect(() => {
    const loadWorkspaces = async () => {
      try {
        const response = await apiClient.get<Workspace[]>("/workspaces");
        setWorkspaces(response.data);
        if (response.data.length > 0 && activeWorkspaceId === null) {
          setActiveWorkspaceId(response.data[0].id);
        }
      } catch (loadError) {
        console.error(loadError);
      }
    };

    loadWorkspaces();
  }, [activeWorkspaceId, tenant]);

  useEffect(() => {
    if (!activeWorkspaceId || activeWorkspace?.status !== "INDEXING") {
      return;
    }

    const interval = setInterval(async () => {
      try {
        const response = await apiClient.get<{ status: Workspace["status"] }>(
          `/workspaces/${activeWorkspaceId}/status`
        );
        setWorkspaces((prev) =>
          prev.map((workspace) =>
            workspace.id === activeWorkspaceId
              ? { ...workspace, status: response.data.status }
              : workspace
          )
        );
      } catch (pollError) {
        console.error(pollError);
      }
    }, 3000);

    return () => clearInterval(interval);
  }, [activeWorkspaceId, activeWorkspace?.status]);

  useEffect(() => {
    if (!error) return;
    setToast(error);
  }, [error]);

  useEffect(() => {
    if (!toast) return;
    const timeout = setTimeout(() => setToast(null), 4000);
    return () => clearTimeout(timeout);
  }, [toast]);

  useEffect(() => {
    if (!syncTaskId) {
      return;
    }

    let polling = true;
    const interval = setInterval(async () => {
      if (!polling) {
        return;
      }
      try {
        const response = await apiClient.get(`/workspaces/ingest/${syncTaskId}`);
        const status = String(response.data?.status || "unknown");

        if (status === "queued" || status === "running") {
          return;
        }

        if (status === "completed") {
          const chunksRaw = response.data?.result?.chunks_created;
          const chunksCreated =
            typeof chunksRaw === "number"
              ? chunksRaw
              : Number.parseInt(String(chunksRaw ?? "0"), 10) || 0;
          setToast(`Codebase indexed successfully! (${chunksCreated} chunks created)`);
          setIsSyncing(false);
          setSyncTaskId(null);
          return;
        }

        if (status === "failed") {
          const detail = String(response.data?.error || "Unknown error");
          setToast(`Indexing failed: ${detail}`);
          setIsSyncing(false);
          setSyncTaskId(null);
          return;
        }
      } catch (pollError) {
        setToast("Indexing failed: Unable to fetch task status");
        setIsSyncing(false);
        setSyncTaskId(null);
      }
    }, 1800);

    return () => {
      polling = false;
      clearInterval(interval);
    };
  }, [syncTaskId]);

  useEffect(() => {
    if (!activeSessionId) return;

    const loadHistory = async () => {
      try {
        const response = await apiClient.get(`/sessions/${activeSessionId}/history`);
        const history = response.data as ChatHistoryItem[];
        setMessages(
          history.map((item) => ({
            role: item.role === "user" ? "user" : "bot",
            content: item.content,
            sources: normalizeCitations(item.sources),
          }))
        );
      } catch (historyError) {
        console.error(historyError);
      }
    };

    loadHistory();
  }, [activeSessionId]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isStreaming]);

  const handleCreateWorkspace = async () => {
    if (!newWorkspaceName.trim() || !newWorkspacePath.trim()) {
      alert("Provide name and absolute path.");
      return;
    }

    try {
      const response = await apiClient.post<Workspace>("/workspaces", {
        name: newWorkspaceName,
        root_path: newWorkspacePath,
      });
      setWorkspaces((prev) => {
        const exists = prev.some((workspace) => workspace.id === response.data.id);
        if (exists) {
          return prev;
        }
        return [...prev, response.data];
      });
      setActiveWorkspaceId(response.data.id);
      setShowWorkspaceModal(false);
      setNewWorkspaceName("");
      setNewWorkspacePath("");
    } catch (createError) {
      alert("Failed to register workspace.");
    }
  };

  const handleIndex = async () => {
    if (!activeWorkspaceId || isSyncing) {
      return;
    }

    try {
      setToast("Indexing started...");
      setIsSyncing(true);
      setWorkspaces((prev) =>
        prev.map((workspace) =>
          workspace.id === activeWorkspaceId
            ? { ...workspace, status: "INDEXING" }
            : workspace
        )
      );
      const response = await apiClient.post(`/workspaces/${activeWorkspaceId}/ingest`);
      const taskId = response.data?.task_id as string | undefined;
      if (!taskId) {
        throw new Error("Missing task id");
      }
      setSyncTaskId(taskId);
    } catch (indexError) {
      setWorkspaces((prev) =>
        prev.map((workspace) =>
          workspace.id === activeWorkspaceId
            ? { ...workspace, status: "FAILED" }
            : workspace
        )
      );
      setIsSyncing(false);
      setSyncTaskId(null);
      setToast("Indexing failed: Failed to start indexing task");
    }
  };

  const handleDeleteWorkspace = async (workspaceId: number) => {
    const workspace = workspaces.find((item) => item.id === workspaceId);
    if (!workspace) {
      return;
    }

    const confirmed = window.confirm(
      `Delete workspace \"${workspace.name}\" and all related indexed data?`
    );
    if (!confirmed) {
      return;
    }

    const previousWorkspaces = workspaces;
    const previousSessions = sessions;
    const previousActiveWorkspaceId = activeWorkspaceId;
    const previousActiveSessionId = activeSessionId;
    const previousMessages = messages;

    const updatedWorkspaces = previousWorkspaces.filter(
      (item) => item.id !== workspaceId
    );
    const updatedSessions = previousSessions.filter(
      (session) => session.workspaceId !== workspaceId
    );
    const nextActiveWorkspaceId =
      previousActiveWorkspaceId === workspaceId
        ? (updatedWorkspaces[0]?.id ?? null)
        : previousActiveWorkspaceId;
    const nextActiveSessionId = updatedSessions.some(
      (session) => session.id === previousActiveSessionId
    )
      ? previousActiveSessionId
      : null;

    setWorkspaces(updatedWorkspaces);
    setSessions(updatedSessions);
    setActiveWorkspaceId(nextActiveWorkspaceId);
    setActiveSessionId(nextActiveSessionId);
    if (!nextActiveSessionId) {
      setMessages([]);
    }

    try {
      await apiClient.delete(`/workspaces/${workspaceId}`);
      setToast("Workspace deleted");
    } catch (deleteError) {
      setWorkspaces(previousWorkspaces);
      setSessions(previousSessions);
      setActiveWorkspaceId(previousActiveWorkspaceId);
      setActiveSessionId(previousActiveSessionId);
      setMessages(previousMessages);
      setToast("Failed to delete workspace");
    }
  };

  const handleNewSession = async () => {
    if (!activeWorkspaceId) return;
    const title = `Session ${activeSessions.length + 1}`;
    try {
      const response = await apiClient.post(
        `/workspaces/${activeWorkspaceId}/sessions`,
        { title }
      );
      const sessionId = response.data?.session_id as number;
      const now = new Date();
      const newSession: Session = {
        id: sessionId,
        title,
        workspaceId: activeWorkspaceId,
        createdAt: now.toISOString(),
      };
      setSessions((prev) => [newSession, ...prev]);
      setActiveSessionId(sessionId);
      setMessages([]);
    } catch (sessionError) {
      alert("Failed to create session.");
    }
  };

  const buildQuery = (raw: string) => {
    if (!showFilters || (!includeFilter.trim() && !excludeFilter.trim())) {
      return raw;
    }
    return `${raw}\n\nFilters:\n- include: ${includeFilter || "none"}\n- exclude: ${
      excludeFilter || "none"
    }`;
  };

  const parseFilterList = (value: string) =>
    value
      .split(",")
      .map((item) => item.trim())
      .filter(Boolean);

  const handleSend = async () => {
    const trimmed = input.trim();
    if (!trimmed || !activeWorkspaceId || !activeSessionId || isStreaming) return;

    const effectiveQuery = buildQuery(trimmed);
    setInput("");
    setMessages((prev) => [...prev, { role: "user", content: trimmed }]);
    setMessages((prev) => [...prev, { role: "bot", content: "", sources: [] }]);

    await stream({
      url: `/chat/${activeSessionId}/stream`,
      body: {
        query: effectiveQuery,
        workspace_id: activeWorkspaceId,
        model: selectedModel,
        filters: showFilters
          ? {
              include_extensions: parseFilterList(includeFilter),
              exclude_folders: parseFilterList(excludeFilter),
            }
          : undefined,
      },
      onToken: (token) => {
        setMessages((prev) => {
          const updated = [...prev];
          const lastIndex = updated.length - 1;
          const last = updated[lastIndex];
          if (last && last.role === "bot") {
            updated[lastIndex] = {
              ...last,
              content: `${last.content}${token}`,
            };
          }
          return updated;
        });
      },
      onCitations: (citations) => {
        setMessages((prev) => {
          const updated = [...prev];
          const lastIndex = updated.length - 1;
          const last = updated[lastIndex];
          if (last && last.role === "bot") {
            updated[lastIndex] = {
              ...last,
              sources: citations,
            };
          }
          return updated;
        });
      },
      onDone: () => {
        setToast(null);
      },
    });
  };

  const handlePrimaryAction = () => {
    if (isStreaming) {
      abort();
      setToast("Generation stopped");
      return;
    }
    void handleSend();
  };

  const handleEnter = (event: React.KeyboardEvent<HTMLInputElement>) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      if (!isStreaming) {
        void handleSend();
      }
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-zinc-950 via-zinc-950 to-zinc-900 text-zinc-100">
      <div className="flex min-h-screen">
        <aside className="flex w-full max-w-sm flex-col border-r border-zinc-800 bg-zinc-950/70 p-6 backdrop-blur">
          <div className="flex items-center justify-between text-xs uppercase tracking-[0.28em] text-zinc-500">
            Workspaces
            <button
              onClick={() => setShowWorkspaceModal(true)}
              className="flex h-7 w-7 items-center justify-center rounded-lg border border-zinc-800 bg-zinc-950/70 text-zinc-400 transition hover:border-zinc-600 hover:text-zinc-200"
            >
              <Plus className="h-4 w-4" />
            </button>
          </div>

          <motion.div layout className="mt-4 flex flex-col gap-2">
            <AnimatePresence mode="popLayout">
              {workspaces.map((workspace) => (
                <motion.div
                  key={workspace.id}
                  layout
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -8 }}
                  className={`group relative rounded-xl border px-3 py-3 text-left text-sm transition ${
                    workspace.id === activeWorkspaceId
                      ? "border-zinc-600 bg-zinc-900/70"
                      : "border-zinc-800 bg-zinc-950/40 hover:border-zinc-700"
                  }`}
                >
                  <button
                    type="button"
                    onClick={() => setActiveWorkspaceId(workspace.id)}
                    className="w-full pr-10 text-left"
                  >
                    <div className="font-medium text-zinc-100">
                      {workspace.name}
                    </div>
                    <div className="mt-1 text-xs text-zinc-500">
                      {workspace.root_path}
                    </div>
                  </button>

                  <button
                    type="button"
                    onClick={(event) => {
                      event.stopPropagation();
                      void handleDeleteWorkspace(workspace.id);
                    }}
                    className="absolute right-2 top-2 flex h-7 w-7 items-center justify-center rounded-md border border-zinc-800/70 text-zinc-500 opacity-40 transition hover:border-rose-500/50 hover:text-rose-300 group-hover:opacity-100"
                    title={`Delete workspace ${workspace.name}`}
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                </motion.div>
              ))}
            </AnimatePresence>
          </motion.div>

          <div className="mt-8 flex items-center justify-between text-xs uppercase tracking-[0.28em] text-zinc-500">
            Sessions
            <button
              onClick={handleNewSession}
              className="flex h-7 w-7 items-center justify-center rounded-lg border border-zinc-800 bg-zinc-950/70 text-zinc-400 transition hover:border-zinc-600 hover:text-zinc-200"
            >
              <FolderPlus className="h-4 w-4" />
            </button>
          </div>

          <div className="mt-3 flex-1 space-y-2 overflow-y-auto pr-1">
            {activeSessions.length === 0 ? (
              <div className="rounded-xl border border-zinc-800 bg-zinc-950/60 p-3 text-xs text-zinc-500">
                Create a session to begin chatting.
              </div>
            ) : (
              activeSessions.map((session) => (
                <button
                  key={session.id}
                  onClick={() => setActiveSessionId(session.id)}
                  className={`w-full rounded-xl border px-3 py-2 text-left text-sm transition ${
                    session.id === activeSessionId
                      ? "border-zinc-600 bg-zinc-900/70"
                      : "border-zinc-800 bg-zinc-950/40 hover:border-zinc-700"
                  }`}
                >
                  <div className="font-medium text-zinc-200">
                    {session.title}
                  </div>
                  <div className="mt-1 text-xs text-zinc-500">
                    {new Date(session.createdAt).toLocaleString()}
                  </div>
                </button>
              ))
            )}
          </div>

          <div className="mt-6 rounded-xl border border-zinc-800 bg-zinc-950/60 p-4 text-xs text-zinc-500">
            <div className="flex items-center justify-between">
              <span>Indexing</span>
              <span className="text-zinc-300">
                {isIndexing ? "Running" : "Idle"}
              </span>
            </div>
            <div className="mt-3 h-1 overflow-hidden rounded-full bg-zinc-900">
              <motion.div
                animate={{
                  x: isIndexing ? ["-100%", "100%"] : "0%",
                  opacity: isIndexing ? 1 : 0.3,
                }}
                transition={{
                  duration: 1.6,
                  repeat: isIndexing ? Infinity : 0,
                  ease: "easeInOut",
                }}
                className="h-full w-1/2 bg-gradient-to-r from-zinc-600 via-zinc-400 to-zinc-600"
              />
            </div>
            <button
              onClick={handleIndex}
              disabled={!activeWorkspaceId || isIndexing}
              className="mt-3 flex w-full items-center justify-center gap-2 rounded-lg border border-zinc-800 bg-zinc-900/60 px-3 py-2 text-xs text-zinc-200 transition hover:border-zinc-700 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {isIndexing ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <PlayCircle className="h-4 w-4" />
              )}
              {isIndexing ? "Indexing..." : "Sync Codebase"}
            </button>
          </div>
        </aside>

        <main className="flex flex-1 flex-col">
          <header className="border-b border-zinc-800 bg-zinc-950/60 px-8 py-6 backdrop-blur">
            <div className="flex items-center justify-between">
              <div>
                <div className="flex items-center gap-3 text-xs uppercase tracking-[0.4em] text-zinc-500">
                  <span>Chat Console</span>
                  <select 
                    value={tenant}
                    onChange={(e) => setTenant(e.target.value)}
                    className="ml-4 rounded-md border border-zinc-700 bg-zinc-900 px-2 py-1 text-zinc-300 outline-none"
                  >
                    <option value="tenant-a">Tenant A (ACME Corp)</option>
                    <option value="tenant-b">Tenant B (Tech LLC)</option>
                    <option value="tenant-c">Tenant C (Startup Inc)</option>
                  </select>
                </div>
                <h1 className="mt-2 text-2xl font-semibold text-zinc-100">
                  {activeWorkspace?.name ?? "SourceLogic"}
                </h1>
              </div>
              <button
                onClick={() => setShowFilters((prev) => !prev)}
                className="flex items-center gap-2 rounded-full border border-zinc-800 bg-zinc-900/70 px-4 py-2 text-xs uppercase tracking-[0.2em] text-zinc-300 transition hover:border-zinc-700"
              >
                <Search className="h-4 w-4" />
                Filters
              </button>
            </div>

            <AnimatePresence>
              {showFilters && (
                <motion.div
                  initial={{ opacity: 0, y: -10 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -10 }}
                  className="mt-4 grid grid-cols-1 gap-3 rounded-2xl border border-zinc-800 bg-zinc-950/70 p-4 text-sm text-zinc-300"
                >
                  <div>
                    <label className="text-xs uppercase tracking-[0.2em] text-zinc-500">
                      Include Paths / Extensions
                    </label>
                    <input
                      value={includeFilter}
                      onChange={(event) => setIncludeFilter(event.target.value)}
                      placeholder="src, .ts, .tsx"
                      className="mt-2 w-full rounded-xl border border-zinc-800 bg-zinc-950/60 px-3 py-2 text-sm text-zinc-100 placeholder:text-zinc-600"
                    />
                  </div>
                  <div>
                    <label className="text-xs uppercase tracking-[0.2em] text-zinc-500">
                      Exclude Paths / Extensions
                    </label>
                    <input
                      value={excludeFilter}
                      onChange={(event) => setExcludeFilter(event.target.value)}
                      placeholder="node_modules, dist"
                      className="mt-2 w-full rounded-xl border border-zinc-800 bg-zinc-950/60 px-3 py-2 text-sm text-zinc-100 placeholder:text-zinc-600"
                    />
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </header>

          <section className="flex-1 overflow-y-auto px-8 py-6">
            <div className="flex flex-col gap-4">
              {!activeSessionId && (
                <div className="flex min-h-[40vh] flex-col items-center justify-center rounded-2xl border border-zinc-800 bg-zinc-950/60 p-8 text-center text-sm text-zinc-400">
                  <div className="flex h-12 w-12 items-center justify-center rounded-full border border-zinc-800 bg-zinc-900/60 text-zinc-300">
                    <Command className="h-5 w-5" />
                  </div>
                  <h3 className="mt-4 text-base font-semibold text-zinc-200">
                    Select a Workspace to begin
                  </h3>
                  <p className="mt-2 max-w-md text-xs text-zinc-500">
                    Choose a codebase on the left, create a session, and start
                    asking questions about your architecture.
                  </p>
                </div>
              )}

              {activeSessionId && messages.length === 0 && (
                <div className="rounded-2xl border border-zinc-800 bg-zinc-950/60 p-6 text-sm text-zinc-400">
                  Select a workspace, start a session, and ask about your
                  codebase.
                </div>
              )}

              {messages.map((message, index) => (
                <ChatMessage key={`${message.role}-${index}`} message={message} />
              ))}

              {isStreaming && (
                <div className="flex justify-start">
                  <div className="rounded-2xl border border-zinc-800 bg-zinc-950/50 px-4 py-3 text-sm text-zinc-400 backdrop-blur">
                    <span className="inline-flex items-center gap-2">
                      <Loader2 className="h-4 w-4 animate-spin" />
                      Streaming...
                    </span>
                  </div>
                </div>
              )}
              <div ref={bottomRef} />
            </div>
          </section>

          <footer className="sticky bottom-0 border-t border-zinc-800 bg-zinc-950/70 px-8 py-5 backdrop-blur">
            <div className="flex flex-wrap items-center gap-3 rounded-2xl border border-zinc-800 bg-zinc-950/80 px-4 py-3 shadow-[0_0_30px_rgba(24,24,27,0.6)]">
              <Command className="h-4 w-4 text-zinc-500" />

              <select
                value={selectedModel}
                onChange={(event) => setSelectedModel(event.target.value as ChatModel)}
                className="rounded-lg border border-zinc-800 bg-zinc-900/70 px-2 py-2 text-xs text-zinc-200 focus:border-zinc-600 focus:outline-none"
              >
                {MODEL_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>

              <input
                value={input}
                onChange={(event) => setInput(event.target.value)}
                onKeyDown={handleEnter}
                placeholder="Ask the codebase..."
                className="min-w-[220px] flex-1 bg-transparent text-sm text-zinc-100 placeholder:text-zinc-600 focus:outline-none"
              />

              <button
                onClick={handlePrimaryAction}
                disabled={!isStreaming && (!input.trim() || !activeWorkspaceId || !activeSessionId)}
                className="flex items-center gap-2 rounded-full border border-zinc-800 bg-zinc-900/70 px-4 py-2 text-xs font-semibold uppercase tracking-[0.2em] text-zinc-200 transition hover:border-zinc-700 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {isStreaming ? <Square className="h-4 w-4" /> : <SendIcon />}
                {isStreaming ? "Stop" : "Send"}
              </button>
            </div>
          </footer>
        </main>
      </div>

      <AnimatePresence>
        {toast && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 20 }}
            className="fixed bottom-6 right-6 z-50 rounded-xl border border-rose-500/40 bg-rose-950/90 px-4 py-3 text-xs text-rose-100 shadow-lg"
          >
            {toast}
          </motion.div>
        )}
      </AnimatePresence>

      <AnimatePresence>
        {showWorkspaceModal && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 px-6"
          >
            <motion.div
              initial={{ y: 20, opacity: 0 }}
              animate={{ y: 0, opacity: 1 }}
              exit={{ y: 20, opacity: 0 }}
              className="w-full max-w-md rounded-2xl border border-zinc-800 bg-zinc-950/90 p-6 text-zinc-100"
            >
              <div className="text-xs uppercase tracking-[0.3em] text-zinc-500">
                Add Workspace
              </div>
              <div className="mt-4 space-y-3">
                <input
                  value={newWorkspaceName}
                  onChange={(event) => setNewWorkspaceName(event.target.value)}
                  placeholder="Workspace name"
                  className="w-full rounded-xl border border-zinc-800 bg-zinc-950/60 px-3 py-2 text-sm text-zinc-100"
                />
                <input
                  value={newWorkspacePath}
                  onChange={(event) => setNewWorkspacePath(event.target.value)}
                  placeholder="C:\\path\\to\\repo"
                  className="w-full rounded-xl border border-zinc-800 bg-zinc-950/60 px-3 py-2 text-sm text-zinc-100"
                />
              </div>
              <div className="mt-6 flex gap-3">
                <button
                  onClick={() => setShowWorkspaceModal(false)}
                  className="flex-1 rounded-xl border border-zinc-800 bg-zinc-950/60 px-4 py-2 text-sm text-zinc-300"
                >
                  Cancel
                </button>
                <button
                  onClick={handleCreateWorkspace}
                  className="flex flex-1 items-center justify-center gap-2 rounded-xl border border-zinc-700 bg-zinc-900 px-4 py-2 text-sm text-zinc-100"
                >
                  <Plus className="h-4 w-4" />
                  Create
                </button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};

const SendIcon = () => (
  <svg
    viewBox="0 0 24 24"
    className="h-4 w-4"
    fill="none"
    stroke="currentColor"
    strokeWidth="1.6"
  >
    <path d="M7 7l10 5-10 5V7z" />
  </svg>
);

export default App;
