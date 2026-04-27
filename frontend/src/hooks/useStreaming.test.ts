import { renderHook, act } from "@testing-library/react";
import { vi, describe, it, expect, afterEach } from "vitest";
import { useStreaming } from "./useStreaming";

type TestBody = { query: string };

const makeSseResponse = (events: string) => {
  const encoder = new TextEncoder();
  const stream = new ReadableStream({
    start(controller) {
      controller.enqueue(encoder.encode(events));
      controller.close();
    },
  });
  return new Response(stream, { status: 200 });
};

describe("useStreaming", () => {
  afterEach(() => vi.restoreAllMocks());

  it("token events invoke onToken callback", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        makeSseResponse(
          'event: token\ndata: {"token":"hello"}\n\nevent: done\ndata: {"status":"complete"}\n\n'
        )
      )
    );

    const onToken = vi.fn();
    const { result } = renderHook(() => useStreaming<TestBody>());

    await act(async () => {
      await result.current.stream({
        url: "/chat/1/stream",
        body: { query: "test" },
        tenantId: "tenant-a",
        onToken,
      });
    });

    expect(onToken).toHaveBeenCalledWith("hello");
    expect(result.current.error).toBeNull();
    expect(result.current.isStreaming).toBe(false);
  });

  it("error event sets error state and stops isStreaming", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        makeSseResponse('event: error\ndata: {"detail":"LLM failed"}\n\n')
      )
    );

    const { result } = renderHook(() => useStreaming<TestBody>());

    await act(async () => {
      await result.current.stream({
        url: "/chat/1/stream",
        body: { query: "test" },
        tenantId: "tenant-a",
        onToken: vi.fn(),
      });
    });

    expect(result.current.error).toBe("LLM failed");
    expect(result.current.isStreaming).toBe(false);
  });
});
