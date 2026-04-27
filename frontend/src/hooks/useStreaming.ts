import { useCallback, useRef, useState } from "react";

const API_BASE_URL = (import.meta.env.VITE_API_URL || "http://localhost:8000").replace(/\/+$/, "");

const resolveApiUrl = (url: string) => {
  if (/^https?:\/\//i.test(url)) {
    return url;
  }
  const normalizedPath = url.startsWith("/") ? url : `/${url}`;
  return `${API_BASE_URL}${normalizedPath}`;
};

export type Citation = {
  chunk_id: number;
  file_path?: string | null;
  file_name?: string | null;
  line_start?: number | null;
  extension?: string | null;
};

type StreamParams<T> = {
  url: string;
  body: T;
  tenantId: string;
  apiKey?: string;
  onToken: (token: string) => void;
  onCitations?: (citations: Citation[]) => void;
  onDone?: () => void;
};

type UseStreamingResult<T> = {
  isStreaming: boolean;
  error: string | null;
  stream: (params: StreamParams<T>) => Promise<void>;
  abort: () => void;
};

export const useStreaming = <T,>(): UseStreamingResult<T> => {
  const [isStreaming, setIsStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const controllerRef = useRef<AbortController | null>(null);
  const cancelledRef = useRef(false);

  const abort = useCallback(() => {
    cancelledRef.current = true;
    controllerRef.current?.abort();
    controllerRef.current = null;
    setIsStreaming(false);
  }, []);

  const handleSseEvent = useCallback(
    (
      eventType: string,
      rawData: string,
      handlers: Pick<StreamParams<T>, "onToken" | "onCitations" | "onDone">
    ): boolean => {
      let parsed: unknown = rawData;
      if (rawData) {
        try {
          parsed = JSON.parse(rawData);
        } catch {
          parsed = rawData;
        }
      }

      if (eventType === "token") {
        const token =
          typeof parsed === "object" && parsed !== null && "token" in parsed
            ? String((parsed as { token?: unknown }).token ?? "")
            : String(parsed ?? "");
        if (token) {
          handlers.onToken(token);
        }
        return false;
      }

      if (eventType === "citations") {
        const citations =
          typeof parsed === "object" &&
          parsed !== null &&
          "citations" in parsed &&
          Array.isArray((parsed as { citations?: unknown }).citations)
            ? ((parsed as { citations: Citation[] }).citations ?? [])
            : [];
        handlers.onCitations?.(citations);
        return false;
      }

      if (eventType === "error") {
        const detail =
          typeof parsed === "object" && parsed !== null && "detail" in parsed
            ? String((parsed as { detail?: unknown }).detail ?? "Streaming error")
            : "Streaming error";
        setError(detail);
        return true;
      }

      if (eventType === "done") {
        handlers.onDone?.();
        return true;
      }

      return false;
    },
    []
  );

  const consumeSseBlock = useCallback(
    (
      block: string,
      handlers: Pick<StreamParams<T>, "onToken" | "onCitations" | "onDone">
    ): boolean => {
      const lines = block.split(/\r?\n/);
      let eventType = "message";
      const dataLines: string[] = [];

      for (const line of lines) {
        if (!line || line.startsWith(":")) {
          continue;
        }
        if (line.startsWith("event:")) {
          eventType = line.slice("event:".length).trim() || "message";
          continue;
        }
        if (line.startsWith("data:")) {
          dataLines.push(line.slice("data:".length).trimStart());
        }
      }

      const data = dataLines.join("\n");
      return handleSseEvent(eventType, data, handlers);
    },
    [handleSseEvent]
  );

  const stream = useCallback(
    async ({ url, body, tenantId, apiKey, onToken, onCitations, onDone }: StreamParams<T>) => {
      if (isStreaming) return;
      setError(null);
      cancelledRef.current = false;
      const controller = new AbortController();
      controllerRef.current = controller;
      setIsStreaming(true);

      try {
        const response = await fetch(resolveApiUrl(url), {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-Tenant-ID": tenantId,
            ...(apiKey ? { "X-API-Key": apiKey } : {}),
          },
          body: JSON.stringify(body),
          signal: controller.signal,
        });

        if (!response.ok || !response.body) {
          throw new Error(`Streaming request failed (${response.status}).`);
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";
        let shouldStop = false;

        while (!shouldStop) {
          const { value, done: readerDone } = await reader.read();
          if (readerDone) {
            buffer += decoder.decode();
            const trailing = buffer.trim();
            if (trailing) {
              consumeSseBlock(trailing, { onToken, onCitations, onDone });
            }
            break;
          }

          if (value) {
            buffer += decoder.decode(value, { stream: true });
            const blocks = buffer.split(/\r?\n\r?\n/);
            buffer = blocks.pop() ?? "";

            for (const block of blocks) {
              if (!block.trim()) {
                continue;
              }
              shouldStop = consumeSseBlock(block, { onToken, onCitations, onDone });
              if (shouldStop) {
                await reader.cancel();
                break;
              }
            }
          }
        }

      } catch (streamError) {
        if ((streamError as Error).name !== "AbortError" && !cancelledRef.current) {
          setError((streamError as Error).message);
        }
      } finally {
        setIsStreaming(false);
        controllerRef.current = null;
      }
    },
    [consumeSseBlock, isStreaming]
  );

  return { isStreaming, error, stream, abort };
};
