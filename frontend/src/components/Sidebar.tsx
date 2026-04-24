import React, { useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { FolderPlus, Loader2, PlayCircle, Plus, Trash2, X } from "lucide-react";
import type { Workspace } from "../services/WorkspaceService";
import type { Session } from "../services/SessionService";

type SidebarProps = {
  workspaces: Workspace[];
  activeWorkspaceId: number | null;
  activeSessions: Session[];
  activeSessionId: number | null;
  isIndexing: boolean;
  isLoadingWorkspaces: boolean;
  onSelectWorkspace: (id: number) => void;
  onDeleteWorkspace: (id: number) => Promise<void>;
  onDeleteSession: (id: number) => Promise<void>;
  onOpenModal: () => void;
  onNewSession: () => Promise<void>;
  onSelectSession: (id: number) => void;
  onIndex: () => Promise<void>;
};

const Sidebar: React.FC<SidebarProps> = ({
  workspaces,
  activeWorkspaceId,
  activeSessions,
  activeSessionId,
  isIndexing,
  isLoadingWorkspaces,
  onSelectWorkspace,
  onDeleteWorkspace,
  onDeleteSession,
  onOpenModal,
  onNewSession,
  onSelectSession,
  onIndex,
}) => {
  // id of the workspace awaiting inline delete confirmation; null = none pending
  const [pendingDeleteId, setPendingDeleteId] = useState<number | null>(null);
  // id of the session awaiting inline delete confirmation; null = none pending
  const [pendingDeleteSessionId, setPendingDeleteSessionId] = useState<number | null>(null);

  const confirmDelete = async (id: number) => {
    setPendingDeleteId(null);
    await onDeleteWorkspace(id);
  };

  return (
    <aside className="flex w-full max-w-sm flex-col border-r border-zinc-800 bg-zinc-950/70 p-6 backdrop-blur">
      <div className="flex items-center justify-between text-xs uppercase tracking-[0.28em] text-zinc-500">
        Workspaces
        <button
          onClick={onOpenModal}
          aria-label="Add workspace"
          className="flex h-7 w-7 items-center justify-center rounded-lg border border-zinc-800 bg-zinc-950/70 text-zinc-400 transition hover:border-zinc-600 hover:text-zinc-200"
        >
          <Plus className="h-4 w-4" />
        </button>
      </div>

      <motion.div layout className="mt-4 flex flex-col gap-2">
        {isLoadingWorkspaces && workspaces.length === 0 && (
          <>
            {[1, 2].map((i) => (
              <div
                key={i}
                className="h-14 animate-pulse rounded-xl border border-zinc-800 bg-zinc-900/50"
              />
            ))}
          </>
        )}
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
              {pendingDeleteId === workspace.id ? (
                /* Inline confirm row — replaces the card content while pending */
                <div className="flex items-center justify-between gap-2">
                  <span className="text-xs text-zinc-400">Delete "{workspace.name}"?</span>
                  <div className="flex gap-1">
                    <button
                      type="button"
                      onClick={() => void confirmDelete(workspace.id)}
                      aria-label="Confirm delete"
                      className="rounded-md border border-rose-700/60 bg-rose-950/60 px-2 py-1 text-xs text-rose-300 transition hover:bg-rose-900/60"
                    >
                      Delete
                    </button>
                    <button
                      type="button"
                      onClick={() => setPendingDeleteId(null)}
                      aria-label="Cancel delete"
                      className="flex h-6 w-6 items-center justify-center rounded-md border border-zinc-700 text-zinc-400 transition hover:text-zinc-200"
                    >
                      <X className="h-3 w-3" />
                    </button>
                  </div>
                </div>
              ) : (
                <>
                  <button
                    type="button"
                    onClick={() => onSelectWorkspace(workspace.id)}
                    className="w-full pr-10 text-left"
                  >
                    <div className="font-medium text-zinc-100">{workspace.name}</div>
                    <div className="mt-1 text-xs text-zinc-500">{workspace.root_path}</div>
                  </button>

                  <button
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation();
                      setPendingDeleteId(workspace.id);
                    }}
                    aria-label={`Delete ${workspace.name}`}
                    className="absolute right-2 top-2 flex h-7 w-7 items-center justify-center rounded-md border border-zinc-800/70 text-zinc-500 opacity-40 transition hover:border-rose-500/50 hover:text-rose-300 group-hover:opacity-100"
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                </>
              )}
            </motion.div>
          ))}
        </AnimatePresence>
      </motion.div>

      <div className="mt-8 flex items-center justify-between text-xs uppercase tracking-[0.28em] text-zinc-500">
        <span>
          Sessions
          {activeWorkspaceId && (
            <span className="ml-1.5 normal-case text-zinc-600">
              — {workspaces.find((w) => w.id === activeWorkspaceId)?.name ?? ""}
            </span>
          )}
        </span>
        <button
          onClick={() => void onNewSession()}
          aria-label="New session"
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
            <div
              key={session.id}
              className={`group relative rounded-xl border px-3 py-2 text-left text-sm transition ${
                session.id === activeSessionId
                  ? "border-zinc-600 bg-zinc-900/70"
                  : "border-zinc-800 bg-zinc-950/40 hover:border-zinc-700"
              }`}
            >
              {pendingDeleteSessionId === session.id ? (
                <div className="flex items-center justify-between gap-2">
                  <span className="text-xs text-zinc-400">Delete "{session.title}"?</span>
                  <div className="flex gap-1">
                    <button
                      type="button"
                      onClick={() => {
                        setPendingDeleteSessionId(null);
                        void onDeleteSession(session.id);
                      }}
                      aria-label="Confirm delete session"
                      className="rounded-md border border-rose-700/60 bg-rose-950/60 px-2 py-1 text-xs text-rose-300 transition hover:bg-rose-900/60"
                    >
                      Delete
                    </button>
                    <button
                      type="button"
                      onClick={() => setPendingDeleteSessionId(null)}
                      aria-label="Cancel delete session"
                      className="flex h-6 w-6 items-center justify-center rounded-md border border-zinc-700 text-zinc-400 transition hover:text-zinc-200"
                    >
                      <X className="h-3 w-3" />
                    </button>
                  </div>
                </div>
              ) : (
                <>
                  <button
                    type="button"
                    onClick={() => onSelectSession(session.id)}
                    className="w-full pr-8 text-left"
                  >
                    <div className="font-medium text-zinc-200">{session.title}</div>
                    <div className="mt-1 text-xs text-zinc-500">
                      {new Date(session.createdAt).toLocaleString()}
                    </div>
                  </button>
                  <button
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation();
                      setPendingDeleteSessionId(session.id);
                    }}
                    aria-label={`Delete ${session.title}`}
                    className="absolute right-2 top-2 flex h-7 w-7 items-center justify-center rounded-md border border-zinc-800/70 text-zinc-500 opacity-40 transition hover:border-rose-500/50 hover:text-rose-300 group-hover:opacity-100"
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                </>
              )}
            </div>
          ))
        )}
      </div>

      <div className="mt-6 rounded-xl border border-zinc-800 bg-zinc-950/60 p-4 text-xs text-zinc-500">
        <div className="flex items-center justify-between">
          <span>Indexing</span>
          <span className="text-zinc-300">{isIndexing ? "Running" : "Idle"}</span>
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
          onClick={() => void onIndex()}
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
  );
};

export default Sidebar;
