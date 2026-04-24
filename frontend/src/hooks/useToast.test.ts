import { renderHook, act } from "@testing-library/react";
import { vi, describe, it, expect, beforeEach, afterEach } from "vitest";
import { useToast } from "./useToast";

describe("useToast", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it("showToast sets the toast message", () => {
    const { result } = renderHook(() => useToast());
    act(() => {
      result.current.showToast("hello");
    });
    expect(result.current.toast).toBe("hello");
  });

  it("toast clears automatically after 4000ms", () => {
    const { result } = renderHook(() => useToast());
    act(() => {
      result.current.showToast("will clear");
    });
    expect(result.current.toast).toBe("will clear");
    act(() => {
      vi.advanceTimersByTime(4000);
    });
    expect(result.current.toast).toBeNull();
  });
});
