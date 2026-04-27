import { useCallback, useEffect, useMemo, useState } from "react";
import { SessionService } from "../services/SessionService";
import type { Session } from "../services/SessionService";

type UseSessionsParams = {
  activeWorkspaceId: number | null;
  showToast?: (msg: string) => void;
};

export const useSessions = ({ activeWorkspaceId, showToast }: UseSessionsParams) => {
  const [sessions, setSessions] = useState<Session[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<number | null>(null);
  const [isLoadingSessions, setIsLoadingSessions] = useState(false);

  const activeSessions = useMemo(
    () => sessions.filter((s) => s.workspaceId === activeWorkspaceId),
    [sessions, activeWorkspaceId]
  );

  // Load sessions from the API whenever the active workspace changes.
  // Replaces any previously-fetched sessions for this workspace so the list
  // stays in sync with the DB after a page refresh.
  useEffect(() => {
    if (!activeWorkspaceId) return;
    const load = async () => {
      setIsLoadingSessions(true);
      try {
        const fetched = await SessionService.list(activeWorkspaceId);
        setSessions((prev) => [
          ...fetched,
          ...prev.filter((s) => s.workspaceId !== activeWorkspaceId),
        ]);
        // Always select the most-recent session of the newly active workspace
        setActiveSessionId(fetched[0]?.id ?? null);
      } catch (e) {
        showToast?.(e instanceof Error ? e.message : "Failed to load sessions.");
      } finally {
        setIsLoadingSessions(false);
      }
    };
    void load();
  }, [activeWorkspaceId]);

  const handleNewSession = useCallback(async () => {
    if (!activeWorkspaceId) return;
    const title = `Session ${activeSessions.length + 1}`;
    try {
      const { session_id } = await SessionService.create(activeWorkspaceId, title);
      const newSession: Session = {
        id: session_id,
        title,
        workspaceId: activeWorkspaceId,
        createdAt: new Date().toISOString(),
      };
      setSessions((prev) => [newSession, ...prev]);
      setActiveSessionId(session_id);
    } catch {
      showToast?.("Failed to create session. Please try again.");
    }
  }, [activeWorkspaceId, activeSessions.length, showToast]);

  const handleDeleteSession = useCallback(
    async (sessionId: number) => {
      try {
        await SessionService.delete(sessionId);
        setSessions((prev) => prev.filter((s) => s.id !== sessionId));
        if (activeSessionId === sessionId) {
          setActiveSessionId(null);
        }
      } catch {
        showToast?.("Failed to delete session. Please try again.");
      }
    },
    [activeSessionId, showToast]
  );

  const handleWorkspaceDeleted = useCallback(
    (workspaceId: number) => {
      const deletedIds = new Set(
        sessions.filter((s) => s.workspaceId === workspaceId).map((s) => s.id)
      );
      setSessions((prev) => prev.filter((s) => s.workspaceId !== workspaceId));
      if (activeSessionId !== null && deletedIds.has(activeSessionId)) {
        setActiveSessionId(null);
      }
    },
    [sessions, activeSessionId]
  );

  return {
    sessions,
    activeSessionId,
    activeSessions,
    isLoadingSessions,
    setActiveSessionId,
    handleNewSession,
    handleDeleteSession,
    handleWorkspaceDeleted,
  };
};
