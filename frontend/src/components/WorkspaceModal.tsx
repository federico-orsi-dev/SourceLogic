import React, { useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Plus } from "lucide-react";

type WorkspaceModalProps = {
  isOpen: boolean;
  onClose: () => void;
  onCreate: (name: string, path: string) => Promise<void>;
  onError?: (msg: string) => void;
};

const WorkspaceModal: React.FC<WorkspaceModalProps> = ({ isOpen, onClose, onCreate, onError }) => {
  const [name, setName] = useState("");
  const [path, setPath] = useState("");
  const nameRef = useRef<HTMLInputElement>(null);

  // Focus first input on open; dismiss on Escape
  useEffect(() => {
    if (!isOpen) return;
    nameRef.current?.focus();

    const handleKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", handleKey);
    return () => document.removeEventListener("keydown", handleKey);
  }, [isOpen, onClose]);

  const handleCreate = async () => {
    if (!name.trim() || !path.trim()) {
      onError?.("Provide workspace name and an absolute path.");
      return;
    }
    try {
      await onCreate(name, path);
      setName("");
      setPath("");
      onClose();
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Failed to register workspace.";
      onError?.(msg);
    }
  };

  return (
    <AnimatePresence>
      {isOpen && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 px-6"
        >
          <motion.div
            role="dialog"
            aria-modal="true"
            aria-labelledby="workspace-modal-title"
            initial={{ y: 20, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            exit={{ y: 20, opacity: 0 }}
            className="w-full max-w-md rounded-2xl border border-zinc-800 bg-zinc-950/90 p-6 text-zinc-100"
          >
            <div
              id="workspace-modal-title"
              className="text-xs uppercase tracking-[0.3em] text-zinc-500"
            >
              Add Workspace
            </div>
            <div className="mt-4 space-y-3">
              <input
                ref={nameRef}
                id="workspace-name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Workspace name"
                className="w-full rounded-xl border border-zinc-800 bg-zinc-950/60 px-3 py-2 text-sm text-zinc-100"
              />
              <input
                id="workspace-path"
                value={path}
                onChange={(e) => setPath(e.target.value)}
                placeholder="C:\\path\\to\\repo"
                className="w-full rounded-xl border border-zinc-800 bg-zinc-950/60 px-3 py-2 text-sm text-zinc-100"
              />
            </div>
            <div className="mt-6 flex gap-3">
              <button
                onClick={onClose}
                className="flex-1 rounded-xl border border-zinc-800 bg-zinc-950/60 px-4 py-2 text-sm text-zinc-300"
              >
                Cancel
              </button>
              <button
                onClick={() => void handleCreate()}
                className="flex flex-1 items-center justify-center gap-2 rounded-xl border border-zinc-700 bg-zinc-900 px-4 py-2 text-sm text-zinc-100"
              >
                <Plus className="h-4 w-4" />
                Create
              </button>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
};

export default WorkspaceModal;
