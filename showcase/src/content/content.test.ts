/**
 * Content integrity: the story, the generator output and the delivered
 * artifacts must agree, or the site lies.
 */
import { existsSync, readFileSync } from "node:fs";

import { describe, expect, it } from "vitest";

import { artifacts } from "./artifacts";
import { evolutionFrameSrc, PHASE_COUNT } from "./evolution";
import { phases } from "./phases";

interface IrComponent {
  id: string;
}

interface IrFrame {
  meta: { title: string; viewBox: [number, number] };
  components: IrComponent[];
  connections: { from: string; to: string }[];
}

function readFrame(phase: number): IrFrame {
  const file = `archify/evolution-${String(phase).padStart(2, "0")}.architecture.json`;
  return JSON.parse(readFileSync(file, "utf8")) as IrFrame;
}

describe("phase content", () => {
  it("covers 17 stages numbered 0 to 16 with unique ids", () => {
    expect(phases).toHaveLength(17);
    expect(phases.map((phase) => phase.number)).toEqual(Array.from({ length: 17 }, (_, i) => i));
    expect(new Set(phases.map((phase) => phase.id)).size).toBe(17);
  });

  it("tells every phase as problem, change, result and cost", () => {
    for (const phase of phases) {
      for (const field of [phase.problem, phase.change, phase.result, phase.tradeoff]) {
        expect(field.length).toBeGreaterThan(20);
      }
      expect(phase.stack.length).toBeGreaterThan(0);
      expect(phase.docPath).toBe(`docs/architecture/phase-${phase.number}.md`);
    }
  });
});

describe("evolution frames", () => {
  it("exist as IR files whose titles match the phase content", () => {
    expect(PHASE_COUNT).toBe(phases.length);
    for (const phase of phases) {
      const frame = readFrame(phase.number);
      expect(frame.meta.title).toContain(phase.title);
    }
  });

  it("keep one fixed canvas so components never move", () => {
    for (const phase of phases) {
      expect(readFrame(phase.number).meta.viewBox).toEqual([1330, 820]);
    }
  });

  it("only ever grow: components and edges are never lost between phases", () => {
    let previousComponents = new Set<string>();
    let previousConnections = new Set<string>();
    for (const { number } of phases) {
      const frame = readFrame(number);
      const components = new Set(frame.components.map((c) => c.id));
      const connections = new Set(frame.connections.map((c) => `${c.from}->${c.to}`));
      for (const id of previousComponents) expect(components.has(id)).toBe(true);
      for (const key of previousConnections) {
        // The customer's direct HTTP edge is the one honest exception: it
        // dies when the Phase 16 edge proxy replaces the direct request path.
        if (key === "client->api" && number === 16) continue;
        expect(connections.has(key)).toBe(true);
      }
      for (const connection of frame.connections) {
        expect(components.has(connection.from)).toBe(true);
        expect(components.has(connection.to)).toBe(true);
      }
      previousComponents = components;
      previousConnections = connections;
    }
  });

  it("references the frames the stage will actually load", () => {
    expect(evolutionFrameSrc(3)).toBe("/archify/evolution/phase-03.html");
    expect(evolutionFrameSrc(16)).toBe("/archify/evolution/phase-16.html");
  });
});

describe("deep-dive artifacts", () => {
  it("keeps exactly the two diagrams the stage cannot show", () => {
    expect(artifacts.map((artifact) => artifact.id)).toEqual(["fraud-pipeline", "transfer-journey"]);
    for (const artifact of artifacts) {
      expect(existsSync(artifact.irPath.replace("showcase/", ""))).toBe(true);
      expect(artifact.views.length).toBeGreaterThan(0);
    }
  });
});
