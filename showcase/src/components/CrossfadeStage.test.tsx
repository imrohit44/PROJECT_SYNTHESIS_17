import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { CrossfadeStage } from "./CrossfadeStage";
import { evolutionFrameSrc } from "../content/evolution";

describe("CrossfadeStage", () => {
  it("mounts the first frame immediately", () => {
    const { container } = render(<CrossfadeStage phase={0} />);
    const frame = screen.getByTitle("PyBank architecture after phase 0 — Archify diagram");
    expect(frame).toHaveAttribute("src", evolutionFrameSrc(0));
    expect(container.querySelectorAll("iframe")).toHaveLength(1);
  });

  it("loads a new phase into the idle slot and switches on load", () => {
    const { container, rerender } = render(<CrossfadeStage phase={0} />);
    const first = screen.getByTitle("PyBank architecture after phase 0 — Archify diagram");
    fireEvent.load(first);
    expect(first.className).toContain("is-active");

    rerender(<CrossfadeStage phase={3} />);
    const second = screen.getByTitle("PyBank architecture after phase 3 — Archify diagram");
    expect(second).toHaveAttribute("src", evolutionFrameSrc(3));
    expect(second.className).not.toContain("is-active");
    expect(first.className).toContain("is-active");

    fireEvent.load(second);
    expect(second.className).toContain("is-active");
    expect(first.className).not.toContain("is-active");
    expect(container.querySelectorAll("iframe")).toHaveLength(2);
  });

  it("recycles the now-idle slot instead of stacking frames", () => {
    const { container, rerender } = render(<CrossfadeStage phase={0} />);
    fireEvent.load(screen.getByTitle("PyBank architecture after phase 0 — Archify diagram"));
    rerender(<CrossfadeStage phase={3} />);
    fireEvent.load(screen.getByTitle("PyBank architecture after phase 3 — Archify diagram"));

    rerender(<CrossfadeStage phase={7} />);
    const recycled = screen.getByTitle("PyBank architecture after phase 7 — Archify diagram");
    expect(recycled).toHaveAttribute("src", evolutionFrameSrc(7));
    expect(container.querySelectorAll("iframe")).toHaveLength(2);
  });
});
