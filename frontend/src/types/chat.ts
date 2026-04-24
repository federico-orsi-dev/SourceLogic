import type { Citation } from "../hooks/useStreaming";

export type ChatModel = "gpt-3.5-turbo" | "gpt-4o" | "gpt-4-turbo";

export const MODEL_OPTIONS: { value: ChatModel; label: string }[] = [
  { value: "gpt-3.5-turbo", label: "GPT-3.5 Turbo" },
  { value: "gpt-4o", label: "GPT-4o" },
  { value: "gpt-4-turbo", label: "GPT-4 Turbo" },
];

export type ChatMessageModel = {
  id?: string;
  role: "user" | "bot";
  content: string;
  sources?: Citation[] | null;
};
