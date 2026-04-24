import { act, renderHook } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { WorkspaceService } from "../services/WorkspaceService";
import { useWorkspaces } from "./useWorkspaces";

vi.mock("../services/WorkspaceService");

const showToast = vi.fn();
const onWorkspaceDeleted = vi.fn();

const defaultParams = {
  tenant: "tenant-a",
  showToast,
  onWorkspaceDeleted,
};

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(WorkspaceService.list).mockResolvedValue([]);
});

describe("useWorkspaces.handleCreateWorkspace", () => {
  it("adds workspace to list and sets it active on success", async () => {
    const ws = { id: 1, name: "Repo", root_path: "/tmp", status: "IDLE" as const, tenant_id: "t", created_at: "" };
    vi.mocked(WorkspaceService.create).mockResolvedValue(ws);

    const { result } = renderHook(() => useWorkspaces(defaultParams));
    await act(async () => {});

    await act(async () => {
      await result.current.handleCreateWorkspace("Repo", "/tmp");
    });

    expect(result.current.workspaces).toHaveLength(1);
    expect(result.current.activeWorkspaceId).toBe(1);
  });

  it("shows toast on create failure", async () => {
    vi.mocked(WorkspaceService.create).mockRejectedValue(new Error("err"));

    const { result } = renderHook(() => useWorkspaces(defaultParams));
    await act(async () => {});

    await act(async () => {
      await result.current.handleCreateWorkspace("Bad", "/bad");
    });

    expect(showToast).toHaveBeenCalledWith(expect.stringContaining("Failed"));
  });
});

describe("useWorkspaces.handleDeleteWorkspace", () => {
  it("removes workspace and calls onWorkspaceDeleted on success", async () => {
    const ws = { id: 1, name: "R", root_path: "/r", status: "IDLE" as const, tenant_id: "t", created_at: "" };
    vi.mocked(WorkspaceService.list).mockResolvedValue([ws]);
    vi.mocked(WorkspaceService.delete).mockResolvedValue(undefined);

    const { result } = renderHook(() => useWorkspaces(defaultParams));
    await act(async () => {});

    await act(async () => {
      await result.current.handleDeleteWorkspace(1);
    });

    expect(WorkspaceService.delete).toHaveBeenCalledWith(1);
    expect(result.current.workspaces).toHaveLength(0);
    expect(onWorkspaceDeleted).toHaveBeenCalledWith(1);
  });

  it("restores workspace list and shows toast on delete failure", async () => {
    const ws = { id: 1, name: "R", root_path: "/r", status: "IDLE" as const, tenant_id: "t", created_at: "" };
    vi.mocked(WorkspaceService.list).mockResolvedValue([ws]);
    vi.mocked(WorkspaceService.delete).mockRejectedValue(new Error("err"));

    const { result } = renderHook(() => useWorkspaces(defaultParams));
    await act(async () => {});

    await act(async () => {
      await result.current.handleDeleteWorkspace(1);
    });

    expect(result.current.workspaces).toHaveLength(1);
    expect(showToast).toHaveBeenCalledWith(expect.stringContaining("Failed"));
  });
});
