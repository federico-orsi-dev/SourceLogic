import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { WorkspaceService } from "../services/WorkspaceService";
import type { Workspace } from "../services/WorkspaceService";

type UseWorkspacesParams = {
  tenant: string;
  showToast: (msg: string) => void;
  onWorkspaceDeleted: (id: number) => void;
};

export const useWorkspaces = ({
  tenant,
  showToast,
  onWorkspaceDeleted,
}: UseWorkspacesParams) => {
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [activeWorkspaceId, setActiveWorkspaceId] = useState<number | null>(null);
  const [isSyncing, setIsSyncing] = useState(false);
  const [syncTaskId, setSyncTaskId] = useState<string | null>(null);
  const [isLoadingWorkspaces, setIsLoadingWorkspaces] = useState(false);

  // Keep callback ref stable so handlers don't need it as a dep
  const onDeletedRef = useRef(onWorkspaceDeleted);
  useEffect(() => {
    onDeletedRef.current = onWorkspaceDeleted;
  });

  const activeWorkspace = useMemo(
    () => workspaces.find((w) => w.id === activeWorkspaceId),
    [workspaces, activeWorkspaceId]
  );
  const isIndexing = isSyncing || activeWorkspace?.status === "INDEXING";

  // Load workspaces whenever tenant changes; reset all local state first
  useEffect(() => {
    setWorkspaces([]);
    setActiveWorkspaceId(null);
    setIsSyncing(false);
    setSyncTaskId(null);
    setIsLoadingWorkspaces(true);

    const load = async () => {
      try {
        const data = await WorkspaceService.list();
        setWorkspaces(data);
        if (data.length > 0) setActiveWorkspaceId(data[0].id);
      } catch (e) {
        showToast(e instanceof Error ? e.message : "Failed to load workspaces.");
      } finally {
        setIsLoadingWorkspaces(false);
      }
    };
    void load();
  }, [tenant]);

  // Poll workspace status every 3 s while INDEXING
  useEffect(() => {
    if (!activeWorkspaceId || activeWorkspace?.status !== "INDEXING") return;

    const interval = setInterval(async () => {
      try {
        const { status } = await WorkspaceService.status(activeWorkspaceId);
        setWorkspaces((prev) =>
          prev.map((w) => (w.id === activeWorkspaceId ? { ...w, status } : w))
        );
      } catch {
        // Transient poll error — silently retry on next tick
      }
    }, 3000);

    return () => clearInterval(interval);
  }, [activeWorkspaceId, activeWorkspace?.status]);

  // Poll ingestion task every 1.8 s
  useEffect(() => {
    if (!syncTaskId) return;

    let active = true;
    const interval = setInterval(async () => {
      if (!active) return;
      try {
        const data = await WorkspaceService.ingestStatus(syncTaskId);
        if (data.status === "queued" || data.status === "running") return;

        if (data.status === "completed") {
          const chunks = data.result?.chunks_created ?? 0;
          showToast(`Codebase indexed successfully! (${chunks} chunks created)`);
        } else {
          showToast(`Indexing failed: ${data.error ?? "Unknown error"}`);
        }
        setIsSyncing(false);
        setSyncTaskId(null);
      } catch {
        showToast("Indexing failed: Unable to fetch task status");
        setIsSyncing(false);
        setSyncTaskId(null);
      }
    }, 1800);

    return () => {
      active = false;
      clearInterval(interval);
    };
  }, [syncTaskId, showToast]);

  const handleCreateWorkspace = useCallback(
    async (name: string, path: string) => {
      try {
        const workspace = await WorkspaceService.create({ name, root_path: path });
        setWorkspaces((prev) => {
          if (prev.some((w) => w.id === workspace.id)) return prev;
          return [...prev, workspace];
        });
        setActiveWorkspaceId(workspace.id);
      } catch {
        showToast("Failed to create workspace. Please try again.");
      }
    },
    [showToast]
  );

  const handleDeleteWorkspace = useCallback(
    async (workspaceId: number) => {
      const workspace = workspaces.find((w) => w.id === workspaceId);
      if (!workspace) return;

      // Optimistic UI: remove from list immediately for snappy feel.
      // onDeletedRef (session cleanup) fires only after the API confirms
      // so session state is never wiped for a delete that ends up failing.
      const snapshot = workspaces;
      const updated = workspaces.filter((w) => w.id !== workspaceId);
      const nextId =
        activeWorkspaceId === workspaceId
          ? (updated[0]?.id ?? null)
          : activeWorkspaceId;

      setWorkspaces(updated);
      setActiveWorkspaceId(nextId);

      try {
        await WorkspaceService.delete(workspaceId);
        onDeletedRef.current(workspaceId); // session cleanup only on success
        showToast("Workspace deleted");
      } catch {
        setWorkspaces(snapshot);
        setActiveWorkspaceId(activeWorkspaceId);
        showToast("Failed to delete workspace");
      }
    },
    [workspaces, activeWorkspaceId, showToast]
  );

  const handleIndex = useCallback(async () => {
    if (!activeWorkspaceId || isSyncing) return;

    try {
      showToast("Indexing started...");
      setIsSyncing(true);
      setWorkspaces((prev) =>
        prev.map((w) =>
          w.id === activeWorkspaceId ? { ...w, status: "INDEXING" as const } : w
        )
      );
      const { task_id } = await WorkspaceService.ingest(activeWorkspaceId);
      setSyncTaskId(task_id);
    } catch {
      setWorkspaces((prev) =>
        prev.map((w) =>
          w.id === activeWorkspaceId ? { ...w, status: "FAILED" as const } : w
        )
      );
      setIsSyncing(false);
      setSyncTaskId(null);
      showToast("Indexing failed: Failed to start indexing task");
    }
  }, [activeWorkspaceId, isSyncing, showToast]);

  return {
    workspaces,
    activeWorkspaceId,
    activeWorkspace,
    isIndexing,
    isLoadingWorkspaces,
    setActiveWorkspaceId,
    handleCreateWorkspace,
    handleDeleteWorkspace,
    handleIndex,
  };
};
