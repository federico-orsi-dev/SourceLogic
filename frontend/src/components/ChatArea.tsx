import React from "react";
import { Command, Loader2 } from "lucide-react";
import ChatMessage from "./ChatMessage";
import type { ChatMessageModel } from "../types/chat";

type ChatAreaProps = {
  messages: ChatMessageModel[];
  isStreaming: boolean;
  activeSessionId: number | null;
  bottomRef: React.RefObject<HTMLDivElement>;
};

const ChatArea: React.FC<ChatAreaProps> = ({
  messages,
  isStreaming,
  activeSessionId,
  bottomRef,
}) => (
  <section className="flex-1 overflow-y-auto px-8 py-6">
    <div
      role="log"
      aria-live="polite"
      aria-label="Chat messages"
      className="flex flex-col gap-4"
    >
      {!activeSessionId && (
        <div className="flex min-h-[40vh] flex-col items-center justify-center rounded-2xl border border-zinc-800 bg-zinc-950/60 p-8 text-center text-sm text-zinc-400">
          <div className="flex h-12 w-12 items-center justify-center rounded-full border border-zinc-800 bg-zinc-900/60 text-zinc-300">
            <Command className="h-5 w-5" />
          </div>
          <h3 className="mt-4 text-base font-semibold text-zinc-200">
            Select a Workspace to begin
          </h3>
          <p className="mt-2 max-w-md text-xs text-zinc-500">
            Choose a codebase on the left, create a session, and start asking
            questions about your architecture.
          </p>
        </div>
      )}

      {activeSessionId && messages.length === 0 && (
        <div className="rounded-2xl border border-zinc-800 bg-zinc-950/60 p-6 text-sm text-zinc-400">
          Select a workspace, start a session, and ask about your codebase.
        </div>
      )}

      {messages.map((message, index) => (
        <ChatMessage key={message.id ?? `${message.role}-${index}`} message={message} />
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
);

export default ChatArea;
