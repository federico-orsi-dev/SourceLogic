import React from "react";

type State = { hasError: boolean; message: string };

export class ErrorBoundary extends React.Component<React.PropsWithChildren, State> {
  state: State = { hasError: false, message: "" };

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, message: error.message };
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="flex min-h-screen items-center justify-center bg-zinc-950 text-zinc-300">
          <div className="max-w-md rounded-xl border border-zinc-800 bg-zinc-900 p-8 text-center">
            <h1 className="mb-2 text-lg font-semibold text-rose-400">Something went wrong</h1>
            <p className="mb-4 text-xs text-zinc-500">{this.state.message}</p>
            <button
              onClick={() => this.setState({ hasError: false, message: "" })}
              className="rounded-lg border border-zinc-700 px-4 py-2 text-xs transition hover:border-zinc-500 hover:text-zinc-100"
            >
              Try again
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}
