import React, { useCallback, useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";

import { useToast } from "./hooks/useToast";
import { useTenant } from "./hooks/useTenant";
import { useWorkspaces } from "./hooks/useWorkspaces";
import { useSessions } from "./hooks/useSessions";
import { useChat } from "./hooks/useChat";

import Sidebar from "./components/Sidebar";
import ChatHeader from "./components/ChatHeader";
import ChatArea from "./components/ChatArea";
import ChatFooter from "./components/ChatFooter";
import WorkspaceModal from "./components/WorkspaceModal";

const App: React.FC = () => {
  const { toast, showToast } = useToast();
  const { tenant, setTenant } = useTenant();

  // Stable ref used to break the circular dep between useWorkspaces ↔ useSessions
  const onWorkspaceDeletedRef = useRef<(id: number) => void>(() => {});
  const stableOnDeleted = useCallback((id: number) => onWorkspaceDeletedRef.current(id), []);

  const {
    workspaces,
    activeWorkspaceId,
    activeWorkspace,
    isIndexing,
    isLoadingWorkspaces,
    setActiveWorkspaceId,
    handleCreateWorkspace,
    handleDeleteWorkspace,
    handleIndex,
  } = useWorkspaces({ tenant, showToast, onWorkspaceDeleted: stableOnDeleted });

  const {
    activeSessionId,
    activeSessions,
    setActiveSessionId,
    handleNewSession,
    handleDeleteSession,
    handleWorkspaceDeleted,
  } = useSessions({ activeWorkspaceId, showToast });

  // Wire deletion callback after both hooks have been initialised
  useEffect(() => {
    onWorkspaceDeletedRef.current = handleWorkspaceDeleted;
  }, [handleWorkspaceDeleted]);

  const chat = useChat({ activeSessionId, activeWorkspaceId, tenant, showToast });

  const handleSessionSelect = useCallback(
    (id: number) => {
      setActiveSessionId(id);
      chat.clearMessages();
    },
    [setActiveSessionId, chat]
  );

  const handleDeleteSessionAndClear = useCallback(
    async (id: number) => {
      const wasActive = id === activeSessionId;
      await handleDeleteSession(id);
      if (wasActive) chat.clearMessages();
    },
    [activeSessionId, handleDeleteSession, chat]
  );

  const handleTenantChange = useCallback(
    (newTenant: string) => {
      setTenant(newTenant);
      setActiveSessionId(null);
      chat.clearMessages();
    },
    [setTenant, setActiveSessionId, chat]
  );

  const [showModal, setShowModal] = useState(false);

  return (
    <div className="min-h-screen bg-gradient-to-br from-zinc-950 via-zinc-950 to-zinc-900 text-zinc-100">
      <div className="flex min-h-screen">
        <Sidebar
          workspaces={workspaces}
          activeWorkspaceId={activeWorkspaceId}
          activeSessions={activeSessions}
          activeSessionId={activeSessionId}
          isIndexing={isIndexing}
          isLoadingWorkspaces={isLoadingWorkspaces}
          onSelectWorkspace={setActiveWorkspaceId}
          onDeleteWorkspace={handleDeleteWorkspace}
          onDeleteSession={handleDeleteSessionAndClear}
          onOpenModal={() => setShowModal(true)}
          onNewSession={handleNewSession}
          onSelectSession={handleSessionSelect}
          onIndex={handleIndex}
        />

        <main className="flex flex-1 flex-col">
          <ChatHeader
            workspaceName={activeWorkspace?.name}
            sessionTitle={activeSessions.find((s) => s.id === activeSessionId)?.title}
            tenant={tenant}
            onTenantChange={handleTenantChange}
            showFilters={chat.showFilters}
            onToggleFilters={() => chat.setShowFilters((p) => !p)}
            includeFilter={chat.includeFilter}
            excludeFilter={chat.excludeFilter}
            onIncludeChange={chat.setIncludeFilter}
            onExcludeChange={chat.setExcludeFilter}
          />
          <ChatArea
            messages={chat.messages}
            isStreaming={chat.isStreaming}
            activeSessionId={activeSessionId}
            bottomRef={chat.bottomRef}
          />
          <ChatFooter
            input={chat.input}
            selectedModel={chat.selectedModel}
            isStreaming={chat.isStreaming}
            canSend={!!chat.input.trim() && !!activeWorkspaceId && !!activeSessionId}
            onInputChange={chat.setInput}
            onModelChange={chat.setSelectedModel}
            onKeyDown={chat.handleEnter}
            onPrimaryAction={chat.handlePrimaryAction}
          />
        </main>
      </div>

      <AnimatePresence>
        {toast && (
          <motion.div
            role="alert"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 20 }}
            className="fixed bottom-6 right-6 z-50 rounded-xl border border-rose-500/40 bg-rose-950/90 px-4 py-3 text-xs text-rose-100 shadow-lg"
          >
            {toast}
          </motion.div>
        )}
      </AnimatePresence>

      <WorkspaceModal
        isOpen={showModal}
        onClose={() => setShowModal(false)}
        onCreate={handleCreateWorkspace}
        onError={showToast}
      />
    </div>
  );
};

export default App;
