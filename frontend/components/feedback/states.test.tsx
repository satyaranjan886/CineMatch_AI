import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ErrorState } from "@/components/feedback/states";

describe("ErrorState", () => {
  it("renders accessible alert and retry action", () => {
    const onRetry = vi.fn();
    render(<ErrorState title="Failed" message="Network down" onRetry={onRetry} />);
    expect(screen.getByRole("alert")).toBeInTheDocument();
    expect(screen.getByText("Failed")).toBeInTheDocument();
    screen.getByRole("button", { name: /try again/i }).click();
    expect(onRetry).toHaveBeenCalled();
  });
});
