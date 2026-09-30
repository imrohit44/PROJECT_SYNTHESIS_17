/**
 * The Evolution Engine's contracts: text budgets, cumulative growth, group
 * boundaries and new-component emphasis — checked against the same pure
 * builders `node tools/evolution.mjs` writes with, so the IR on disk and the
 * rules in the test can never drift apart.
 */
import { describe, expect, it } from "vitest";

import {
  irForPhase,
  LABEL_MAX_TEXT_UNITS,
  PHASE_TITLES,
  SUBLABEL_MAX_TEXT_UNITS,
  TAG_MAX_TEXT_UNITS,
  validateTextBudgets,
} from "./evolution.mjs";

const PHASES = PHASE_TITLES.length;

describe("text budgets", () => {
  it("passes every phase, including the 21-unit sublabel that sits exactly at the limit", () => {
    for (let phase = 0; phase < PHASES; phase += 1) {
      expect(() => validateTextBudgets(irForPhase(phase))).not.toThrow();
    }
    const sublabels = new Set();
    for (let phase = 0; phase < PHASES; phase += 1) {
      for (const component of irForPhase(phase).components) {
        if (component.sublabel) sublabels.add(component.sublabel);
      }
    }
    // "pybank + pybank_fraud" (phases 10+) and "audit + WhatsApp push"
    // (phases 15+) are the binding cases: 21 units, one away from failing
    // desktop readability at the 930px reader width.
    expect(SUBLABEL_MAX_TEXT_UNITS).toBe(21);
    expect(LABEL_MAX_TEXT_UNITS).toBe(19);
    expect(TAG_MAX_TEXT_UNITS).toBe(31);
    expect([...sublabels]).toContain("pybank + pybank_fraud");
  });

  it("reports a violation with phase, component, field, units and limit", () => {
    const ir = irForPhase(7);
    const broken = {
      ...ir,
      components: [
        ...ir.components,
        { id: "overflow", type: "backend", label: "Overflow", sublabel: "x".repeat(22) },
      ],
    };
    let message = "";
    try {
      validateTextBudgets(broken);
    } catch (error) {
      message = String(error && error.message ? error.message : error);
    }
    expect(message).toContain("text-budget invariant violated");
    expect(message).toContain("Phase 07");
    expect(message).toContain('"overflow"');
    expect(message).toContain("sublabel is 22 text units");
    expect(message).toContain(`max ${SUBLABEL_MAX_TEXT_UNITS}, SUBLABEL_MAX_TEXT_UNITS`);
  });
});

describe("cumulative growth", () => {
  it("only ever adds components and connections between phases", () => {
    let previousComponents = new Set();
    let previousConnections = new Set();
    for (let phase = 0; phase < PHASES; phase += 1) {
      const ir = irForPhase(phase);
      const components = new Set(ir.components.map((component) => component.id));
      const connections = new Set(
        ir.connections.map((connection) => `${connection.from}->${connection.to}`),
      );
      for (const id of previousComponents) expect(components.has(id)).toBe(true);
      for (const key of previousConnections) {
        // The customer's direct HTTP edge is the one honest death: Nginx
        // replaces the direct request path at Phase 16.
        if (key === "client->api" && phase === 16) continue;
        expect(connections.has(key)).toBe(true);
      }
      previousComponents = components;
      previousConnections = connections;
    }
    expect(previousComponents.size).toBe(16);
  });
});

describe("group boundaries", () => {
  it("only wraps components that exist in that phase, growing membership over time", () => {
    for (let phase = 0; phase < PHASES; phase += 1) {
      const ir = irForPhase(phase);
      const alive = new Set(ir.components.map((component) => component.id));
      for (const boundary of ir.boundaries) {
        expect(boundary.wraps.length).toBeGreaterThan(0);
        for (const id of boundary.wraps) expect(alive.has(id)).toBe(true);
      }
      // Request path from 0, Private state from 3, Event backbone from 9,
      // Fraud intelligence from 10 — four groups by the final frame.
      const expected = 1 + (phase >= 3 ? 1 : 0) + (phase >= 9 ? 1 : 0) + (phase >= 10 ? 1 : 0);
      expect(ir.boundaries).toHaveLength(expected);
    }
    const final = irForPhase(PHASES - 1);
    expect(final.boundaries.map((boundary) => boundary.kind)).toEqual([
      "region",
      "region",
      "security-group",
      "region",
    ]);
    expect(
      final.boundaries.find((boundary) => boundary.label === "Private state")?.wraps,
    ).toEqual(["postgres", "ml"]);
  });
});

describe("new-component emphasis", () => {
  it("tags every birth phase's component and lights its edges, phase 00 excluded", () => {
    for (let phase = 1; phase < PHASES; phase += 1) {
      const ir = irForPhase(phase);
      const born = ir.components.filter((component) => component.tag?.endsWith("· new"));
      if (born.length === 0) continue; // Phases 02, 07 and 15 add no component.
      for (const component of born) {
        expect(component.tag === "new" || component.tag.includes(" · new")).toBe(true);
      }
      for (const connection of ir.connections) {
        const arrivesNew = born.some(
          (component) => component.id === connection.from || component.id === connection.to,
        );
        if (arrivesNew) expect(connection.variant).toBe("emphasis");
      }
    }
    // Phase 00 is the whole system, not a change — no badges.
    for (const component of irForPhase(0).components) {
      expect(component.tag ?? "").not.toContain("new");
    }
    // Consumers has no authored tag, so its birth frame gets a bare "new".
    expect(irForPhase(9).components.find((component) => component.id === "consumers")?.tag).toBe(
      "new",
    );
    // Phase 04 births Auth: its edge is dashed by design except in the birth
    // frame, where it lights up.
    const phase4 = irForPhase(4);
    expect(phase4.components.find((component) => component.id === "security")?.tag).toContain(
      "· new",
    );
    expect(
      phase4.connections.find((connection) => connection.id === "api-to-security")?.variant,
    ).toBe("emphasis");
    expect(
      irForPhase(5).connections.find((connection) => connection.id === "api-to-security")?.variant,
    ).toBe("dashed");
  });
});

describe("semantic kinds", () => {
  it("uses all seven Archify component types by the final frame", () => {
    const final = irForPhase(PHASES - 1);
    expect(new Set(final.components.map((component) => component.type))).toEqual(
      new Set(["frontend", "backend", "database", "cloud", "security", "messagebus", "external"]),
    );
    expect(final.components.find((component) => component.id === "security")?.type).toBe(
      "security",
    );
  });

  it("ships a schema-shaped legend with site-native labels", () => {
    const legend = irForPhase(PHASES - 1).meta.legend;
    expect(legend.mode).toBe("auto");
    expect(Object.keys(legend.entries)).toHaveLength(7);
    for (const entry of Object.values(legend.entries)) {
      expect(entry.label.length).toBeGreaterThan(0);
      expect(entry.label.length).toBeLessThanOrEqual(80);
    }
    expect(legend.entries.messagebus.label).toBe("Event bus");
    expect(legend.entries.security.label).toBe("Identity");
  });
});

