import React from "react";
import { Command, Square } from "lucide-react";
import type { ChatModel } from "../types/chat";
import { MODEL_OPTIONS } from "../types/chat";

type ChatFooterProps = {
  input: string;
  selectedModel: ChatModel;
  isStreaming: boolean;
  canSend: boolean;
  onInputChange: (v: string) => void;
  onModelChange: (m: ChatModel) => void;
  onKeyDown: (e: React.KeyboardEvent<HTMLInputElement>) => void;
  onPrimaryAction: () => void;
};

const SendIcon = () => (
  <svg
    viewBox="0 0 24 24"
    className="h-4 w-4"
    fill="none"
    stroke="currentColor"
    strokeWidth="1.6"
  >
    <path d="M7 7l10 5-10 5V7z" />
  </svg>
);

const ChatFooter: React.FC<ChatFooterProps> = ({
  input,
  selectedModel,
  isStreaming,
  canSend,
  onInputChange,
  onModelChange,
  onKeyDown,
  onPrimaryAction,
}) => (
  <footer className="sticky bottom-0 border-t border-zinc-800 bg-zinc-950/70 px-8 py-5 backdrop-blur">
    <div className="flex flex-wrap items-center gap-3 rounded-2xl border border-zinc-800 bg-zinc-950/80 px-4 py-3 shadow-[0_0_30px_rgba(24,24,27,0.6)]">
      <Command className="h-4 w-4 text-zinc-500" />

      <select
        value={selectedModel}
        onChange={(e) => onModelChange(e.target.value as ChatModel)}
        className="rounded-lg border border-zinc-800 bg-zinc-900/70 px-2 py-2 text-xs text-zinc-200 focus:border-zinc-600 focus:outline-none"
      >
        {MODEL_OPTIONS.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>

      <input
        value={input}
        onChange={(e) => onInputChange(e.target.value)}
        onKeyDown={onKeyDown}
        placeholder="Ask the codebase..."
        className="min-w-[220px] flex-1 bg-transparent text-sm text-zinc-100 placeholder:text-zinc-600 focus:outline-none"
      />

      <button
        onClick={onPrimaryAction}
        disabled={!isStreaming && !canSend}
        aria-label={isStreaming ? "Stop generation" : "Send message"}
        className="flex items-center gap-2 rounded-full border border-zinc-800 bg-zinc-900/70 px-4 py-2 text-xs font-semibold uppercase tracking-[0.2em] text-zinc-200 transition hover:border-zinc-700 disabled:cursor-not-allowed disabled:opacity-60"
      >
        {isStreaming ? <Square className="h-4 w-4" /> : <SendIcon />}
        {isStreaming ? "Stop" : "Send"}
      </button>
    </div>
  </footer>
);

export default ChatFooter;
