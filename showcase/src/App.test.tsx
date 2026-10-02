import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it } from "vitest";

import { App } from "./App";
import { evolutionFrameSrc } from "./content/evolution";

afterEach(() => {
  cleanup();
});

describe("Synthesis Explorer", () => {
  it("presents the one-page story in order", () => {
    render(<App />);
    expect(screen.getByRole("heading", { level: 1, name: /one system/i })).toBeInTheDocument();
    const level2 = within(screen.getByRole("main"))
      .getAllByRole("heading", { level: 2 })
      .map((heading) => heading.textContent);
    expect(level2).toEqual([
      "Why 17 stages",
      "System evolution",
      "Deep dives",
      "Source",
    ]);
  });

  it("scrubs the evolution engine and updates stage plus card together", async () => {
    render(<App />);

    const scrubber = screen.getByRole("slider", { name: /phase scrubber/i });
    fireEvent.change(scrubber, { target: { value: "9" } });

    expect(screen.getByRole("heading", { name: "Kafka behind a transactional outbox" })).toBeInTheDocument();
    expect(screen.getByText("Phase 09 / 16")).toBeInTheDocument();
    const queued = screen.getByTitle("Project Synthesis 17 architecture after Phase 9 — Archify diagram");
    expect(queued).toHaveAttribute("src", evolutionFrameSrc(9));
  });

  it("plays, pauses and steps with keyboard", async () => {
    const user = userEvent.setup();
    render(<App />);

    // The transport activates from the keyboard like any native button.
    const play = screen.getByRole("button", { name: /play the evolution/i });
    play.focus();
    await user.keyboard("{Enter}");
    expect(screen.getByRole("button", { name: /pause the evolution/i }).textContent).toBe("Pause");
    await user.keyboard("{Enter}");
    expect(screen.getByRole("button", { name: /play the evolution/i }).textContent).toBe("Play");

    // Arrow stepping on a range input is native browser behaviour that jsdom
    // does not simulate; the change event is what seek() listens for either way.
    const scrubber = screen.getByRole("slider", { name: /phase scrubber/i });
    fireEvent.change(scrubber, { target: { value: "2" } });
    expect(screen.getByText("Phase 02 / 16")).toBeInTheDocument();
  });

  it("links the phase card to the phase document in the real repository", () => {
    render(<App />);
    const doc = screen.getByRole("link", { name: /docs\/architecture\/phase-0\.md/ });
    expect(doc).toHaveAttribute("href", expect.stringContaining("github.com/imrohit44/PyBank"));
  });
});
