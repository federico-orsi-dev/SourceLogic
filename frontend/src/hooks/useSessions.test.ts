import { act, renderHook } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { SessionService } from "../services/SessionService";
import { useSessions } from "./useSessions";

vi.mock("../services/SessionService");

const showToast = vi.fn();

beforeEach(() => {
  vi.clearAllMocks();
});

describe("useSessions.handleDeleteSession", () => {
  it("removes session from list on success", async () => {
    vi.mocked(SessionService.list).mockResolvedValue([
      { id: 1, title: "S1", workspaceId: 1, createdAt: "" },
    ]);
    vi.mocked(SessionService.delete).mockResolvedValue(undefined);

    const { result } = renderHook(() =>
      useSessions({ activeWorkspaceId: 1, showToast })
    );

    // Wait for the list to load
    await act(async () => {});

    await act(async () => {
      await result.current.handleDeleteSession(1);
    });

    expect(SessionService.delete).toHaveBeenCalledWith(1);
    expect(result.current.sessions.find((s) => s.id === 1)).toBeUndefined();
  });

  it("shows toast on delete failure", async () => {
    vi.mocked(SessionService.list).mockResolvedValue([]);
    vi.mocked(SessionService.delete).mockRejectedValue(new Error("net"));

    const { result } = renderHook(() =>
      useSessions({ activeWorkspaceId: 1, showToast })
    );

    await act(async () => {
      await result.current.handleDeleteSession(99);
    });

    expect(showToast).toHaveBeenCalledWith(
      expect.stringContaining("Failed")
    );
  });

  it("clears activeSessionId when the active session is deleted", async () => {
    vi.mocked(SessionService.list).mockResolvedValue([
      { id: 5, title: "S5", workspaceId: 1, createdAt: "" },
    ]);
    vi.mocked(SessionService.delete).mockResolvedValue(undefined);

    const { result } = renderHook(() =>
      useSessions({ activeWorkspaceId: 1, showToast })
    );
    await act(async () => {});

    act(() => result.current.setActiveSessionId(5));

    await act(async () => {
      await result.current.handleDeleteSession(5);
    });

    expect(result.current.activeSessionId).toBeNull();
  });
});

describe("useSessions.isLoadingSessions", () => {
  it("is false after sessions finish loading", async () => {
    vi.mocked(SessionService.list).mockResolvedValue([]);

    const { result } = renderHook(() =>
      useSessions({ activeWorkspaceId: 1, showToast })
    );

    await act(async () => {});

    expect(result.current.isLoadingSessions).toBe(false);
  });
});

describe("useSessions.handleWorkspaceDeleted", () => {
  it("removes sessions belonging to the deleted workspace", async () => {
    vi.mocked(SessionService.list).mockResolvedValue([
      { id: 1, title: "S1", workspaceId: 1, createdAt: "" },
      { id: 2, title: "S2", workspaceId: 2, createdAt: "" },
    ]);

    const { result } = renderHook(() =>
      useSessions({ activeWorkspaceId: 1, showToast })
    );
    await act(async () => {});

    act(() => result.current.handleWorkspaceDeleted(1));

    expect(result.current.sessions.every((s) => s.workspaceId !== 1)).toBe(true);
  });
});
