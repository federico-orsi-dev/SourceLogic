import React from "react";
import ReactMarkdown from "react-markdown";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { vscDarkPlus } from "react-syntax-highlighter/dist/esm/styles/prism";

export type ChatMessageRole = "user" | "bot";
export type CitationModel = {
  chunk_id: number;
  file_path?: string | null;
  file_name?: string | null;
  line_start?: number | null;
  extension?: string | null;
};

export type ChatMessageModel = {
  role: ChatMessageRole;
  content: string;
  sources?: CitationModel[];
};

type ChatMessageProps = {
  message: ChatMessageModel;
};

const ChatMessage: React.FC<ChatMessageProps> = ({ message }) => {
  const isUser = message.role === "user";

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div
        className={`max-w-[80%] rounded-2xl border px-4 py-3 text-sm leading-6 shadow-sm ${
          isUser
            ? "border-zinc-700/60 bg-zinc-900 text-zinc-100"
            : "border-zinc-800 bg-zinc-950/50 text-zinc-200 backdrop-blur"
        }`}
      >
        {isUser ? (
          <p className="whitespace-pre-wrap">{message.content}</p>
        ) : (
          <ReactMarkdown
            className="prose prose-invert max-w-none"
            components={{
              code({ inline, className, children, ...props }) {
                const match = /language-(\w+)/.exec(className || "");
                return !inline ? (
                  <SyntaxHighlighter
                    {...props}
                    style={vscDarkPlus}
                    language={match ? match[1] : "text"}
                    PreTag="div"
                    customStyle={{
                      margin: "0.75rem 0",
                      borderRadius: "0.75rem",
                      background: "rgba(9, 9, 11, 0.85)",
                      border: "1px solid rgba(39, 39, 42, 0.8)",
                    }}
                  >
                    {String(children).replace(/\n$/, "")}
                  </SyntaxHighlighter>
                ) : (
                  <code
                    {...props}
                    className="rounded bg-zinc-900 px-1.5 py-0.5 text-[0.85em]"
                  >
                    {children}
                  </code>
                );
              },
            }}
          >
            {message.content}
          </ReactMarkdown>
        )}

        {!isUser && message.sources && message.sources.length > 0 && (
          <div className="mt-4 rounded-xl border border-zinc-800/80 bg-zinc-900/40 p-3">
            <div className="mb-2 text-[11px] uppercase tracking-[0.18em] text-zinc-500">
              Citations
            </div>
            <div className="flex flex-wrap gap-2">
              {message.sources.map((citation) => {
                const sourcePath = citation.file_path || citation.file_name || "unknown";
                const parts = sourcePath.split(/[/\\]+/);
                const tail = parts.slice(-3).join(" / ");
                const line = citation.line_start ? `:${citation.line_start}` : "";
                const label = `[${citation.chunk_id}] ${tail}${line}`;

                return (
                  <button
                    key={`${citation.chunk_id}-${sourcePath}-${line}`}
                    type="button"
                    onClick={() => navigator.clipboard?.writeText(sourcePath)}
                    className="inline-flex items-center gap-1 rounded-full border border-zinc-800 bg-zinc-900/70 px-2.5 py-1 text-[11px] text-zinc-300 transition hover:border-zinc-600 hover:text-zinc-100"
                    title={`Copy path: ${sourcePath}`}
                  >
                    {label}
                  </button>
                );
              })}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default ChatMessage;
