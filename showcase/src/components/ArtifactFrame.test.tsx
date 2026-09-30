import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { ArtifactFrame } from "./ArtifactFrame";
import { artifactById } from "../content/artifacts";

describe("ArtifactFrame", () => {
  it("stays unloaded until the reader asks, then embeds the artifact", async () => {
    const artifact = artifactById("transfer-journey");
    expect(artifact).toBeDefined();
    if (!artifact) return;

    const user = userEvent.setup();
    render(<ArtifactFrame artifact={artifact} />);

    expect(screen.queryByTitle(/interactive Archify artifact/i)).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /Load interactive diagram/i }));

    const frame = screen.getByTitle(/interactive Archify artifact/i);
    expect(frame).toHaveAttribute("src", artifact.url);
    expect(screen.getAllByText(/Commit path/i).length).toBeGreaterThan(0);
  });
});
