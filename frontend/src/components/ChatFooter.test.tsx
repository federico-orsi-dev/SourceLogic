import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import { vi, describe, it, expect } from "vitest";
import ChatFooter from "./ChatFooter";

const defaultProps = {
  input: "",
  selectedModel: "gpt-4o" as const,
  isStreaming: false,
  canSend: false,
  onInputChange: vi.fn(),
  onModelChange: vi.fn(),
  onKeyDown: vi.fn(),
  onPrimaryAction: vi.fn(),
};

describe("ChatFooter", () => {
  it("send button is disabled when canSend is false and not streaming", () => {
    render(<ChatFooter {...defaultProps} canSend={false} isStreaming={false} />);
    expect(screen.getByRole("button", { name: /send message/i })).toBeDisabled();
  });

  it("calls onPrimaryAction when send button is clicked with canSend true", () => {
    const onPrimaryAction = vi.fn();
    render(
      <ChatFooter
        {...defaultProps}
        input="what is this?"
        canSend={true}
        onPrimaryAction={onPrimaryAction}
      />
    );
    fireEvent.click(screen.getByRole("button", { name: /send message/i }));
    expect(onPrimaryAction).toHaveBeenCalledOnce();
  });
});
