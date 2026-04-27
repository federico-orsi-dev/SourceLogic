import React, { useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Eye, EyeOff, KeyRound, Search } from "lucide-react";

type ChatHeaderProps = {
  workspaceName: string | undefined;
  sessionTitle: string | undefined;
  tenant: string;
  apiKey: string;
  onTenantChange: (t: string) => void;
  onApiKeyChange: (k: string) => void;
  showFilters: boolean;
  onToggleFilters: () => void;
  includeFilter: string;
  excludeFilter: string;
  onIncludeChange: (v: string) => void;
  onExcludeChange: (v: string) => void;
};

const ChatHeader: React.FC<ChatHeaderProps> = ({
  workspaceName,
  sessionTitle,
  tenant,
  apiKey,
  onTenantChange,
  onApiKeyChange,
  showFilters,
  onToggleFilters,
  includeFilter,
  excludeFilter,
  onIncludeChange,
  onExcludeChange,
}) => {
  const [showKey, setShowKey] = useState(false);

  return (
  <header className="border-b border-zinc-800 bg-zinc-950/60 px-8 py-6 backdrop-blur">
    <div className="flex items-center justify-between">
      <div>
        <div className="flex flex-wrap items-center gap-3 text-xs uppercase tracking-[0.4em] text-zinc-500">
          <span>Chat Console</span>
          <input
            value={tenant}
            onChange={(e) => onTenantChange(e.target.value)}
            placeholder="tenant-id"
            aria-label="Tenant ID"
            className="w-32 rounded-md border border-zinc-700 bg-zinc-900 px-2 py-1 text-xs normal-case text-zinc-300 placeholder:text-zinc-600 outline-none focus:border-zinc-500"
          />
          <span className="flex items-center gap-1 text-zinc-600">
            <KeyRound className="h-3 w-3" />
            API Key
          </span>
          <div className="relative flex items-center">
            <input
              value={apiKey}
              onChange={(e) => onApiKeyChange(e.target.value)}
              type={showKey ? "text" : "password"}
              placeholder="sk-…"
              aria-label="API Key"
              autoComplete="off"
              className="w-40 rounded-md border border-zinc-700 bg-zinc-900 py-1 pl-2 pr-7 text-xs normal-case text-zinc-300 placeholder:text-zinc-600 outline-none focus:border-zinc-500"
            />
            <button
              type="button"
              onClick={() => setShowKey((v) => !v)}
              aria-label={showKey ? "Hide API key" : "Show API key"}
              className="absolute right-1.5 text-zinc-500 hover:text-zinc-300"
            >
              {showKey ? <EyeOff className="h-3 w-3" /> : <Eye className="h-3 w-3" />}
            </button>
          </div>
        </div>
        <h1 className="mt-2 text-2xl font-semibold text-zinc-100">
          {workspaceName ?? "SourceLogic"}
        </h1>
        {sessionTitle && (
          <p className="mt-0.5 text-xs text-zinc-500">{sessionTitle}</p>
        )}
      </div>
      <button
        onClick={onToggleFilters}
        className="flex items-center gap-2 rounded-full border border-zinc-800 bg-zinc-900/70 px-4 py-2 text-xs uppercase tracking-[0.2em] text-zinc-300 transition hover:border-zinc-700"
      >
        <Search className="h-4 w-4" />
        Filters
      </button>
    </div>

    <AnimatePresence>
      {showFilters && (
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -10 }}
          className="mt-4 grid grid-cols-1 gap-3 rounded-2xl border border-zinc-800 bg-zinc-950/70 p-4 text-sm text-zinc-300"
        >
          <div>
            <label
              htmlFor="filter-include"
              className="text-xs uppercase tracking-[0.2em] text-zinc-500"
            >
              Include Paths / Extensions
            </label>
            <input
              id="filter-include"
              value={includeFilter}
              onChange={(e) => onIncludeChange(e.target.value)}
              placeholder="src, .ts, .tsx"
              className="mt-2 w-full rounded-xl border border-zinc-800 bg-zinc-950/60 px-3 py-2 text-sm text-zinc-100 placeholder:text-zinc-600"
            />
          </div>
          <div>
            <label
              htmlFor="filter-exclude"
              className="text-xs uppercase tracking-[0.2em] text-zinc-500"
            >
              Exclude Paths / Extensions
            </label>
            <input
              id="filter-exclude"
              value={excludeFilter}
              onChange={(e) => onExcludeChange(e.target.value)}
              placeholder="node_modules, dist"
              className="mt-2 w-full rounded-xl border border-zinc-800 bg-zinc-950/60 px-3 py-2 text-sm text-zinc-100 placeholder:text-zinc-600"
            />
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  </header>
  );
};

export default ChatHeader;
