import React from "react";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi, describe, it, expect } from "vitest";
import WorkspaceModal from "./WorkspaceModal";

describe("WorkspaceModal", () => {
  it("renders the title when isOpen is true", () => {
    render(<WorkspaceModal isOpen={true} onClose={vi.fn()} onCreate={vi.fn()} />);
    expect(screen.getByText(/add workspace/i)).toBeInTheDocument();
  });

  it("does not render content when isOpen is false", () => {
    render(<WorkspaceModal isOpen={false} onClose={vi.fn()} onCreate={vi.fn()} />);
    expect(screen.queryByText(/add workspace/i)).not.toBeInTheDocument();
  });

  it("calls onCreate with the name and path entered by the user", async () => {
    const user = userEvent.setup();
    const onCreate = vi.fn().mockResolvedValue(undefined);
    render(<WorkspaceModal isOpen={true} onClose={vi.fn()} onCreate={onCreate} />);

    await user.type(screen.getByPlaceholderText("Workspace name"), "My Repo");
    await user.type(screen.getByPlaceholderText(/path/i), "/home/user/repo");
    await user.click(screen.getByRole("button", { name: /create/i }));

    expect(onCreate).toHaveBeenCalledWith("My Repo", "/home/user/repo");
  });
});
