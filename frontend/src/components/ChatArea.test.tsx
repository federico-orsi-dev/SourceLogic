import React, { createRef } from "react";
import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import ChatArea from "./ChatArea";

describe("ChatArea", () => {
  it("renders user and bot messages with correct text content", () => {
    const messages = [
      { role: "user" as const, content: "What does App.tsx do?" },
      { role: "bot" as const, content: "It is the root component." },
    ];
    render(
      <ChatArea
        messages={messages}
        isStreaming={false}
        activeSessionId={1}
        bottomRef={createRef<HTMLDivElement>()}
      />
    );
    expect(screen.getByText("What does App.tsx do?")).toBeInTheDocument();
    expect(screen.getByText(/root component/i)).toBeInTheDocument();
  });
});
