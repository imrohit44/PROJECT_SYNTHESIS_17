/**
 * The Evolution Engine generator.
 *
 * One system, growing in place. This file is the single source of truth for
 * the topology shown by the "System Evolution" stage on the site. Every node
 * carries the phase it was born in; every connection carries the phase range
 * it exists for. The generator emits one cumulative Archify architecture IR
 * per phase (`archify/evolution-NN.architecture.json`) and every frame shares
 * the same authored `meta.viewBox`, so the vendored Archify renderer draws
 * each component at the exact same pixel position forever after it appears.
 * PostgreSQL shows up at Phase 03 and never moves again; the ML signal lands
 * beside the Fraud Service at Phase 12; nothing re-flows.
 *
 * Semantics are carried by supported schema fields only: each node's `type`
 * picks one of Archify's seven kinds (colour class + drawn sigil), four authored
 * group boundaries (`kind: region` / `security-group`) grow with their members,
 * `meta.legend` renames the seven kinds in the site's own words, and a birth
 * phase emphasises what it added — a `· new` tag suffix plus its edges lit
 * `emphasis`. Node text is held to the renderer's own text-unit budgets so a
 * violation fails here with a structured error, not at validate time.
 *
 * Facts come from `docs/architecture/phase-N.md` in the banking repository.
 *
 * Usage:
 *   node tools/evolution.mjs            regenerate all 17 IR files
 *   node tools/evolution.mjs --check    fail if the files on disk are stale
 *
 * Afterwards run `npm run archify:validate` and `npm run archify:deliver` —
 * the frames are ordinary Archify IR files, so the normal tooling picks them
 * up, and the HTML stays a build-time artifact served from public/.
 */
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { textUnits } from "../vendor/archify/renderers/shared/utils.mjs";

const here = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(here, "..");
const irDir = path.join(repoRoot, "archify");

/** Phase titles, verbatim from src/content/phases.ts and the phase docs. */
export const PHASE_TITLES = [
  "A skeleton with a spine",
  "Money rules before databases",
  "The API boundary",
  "Persistence without leaking the ORM",
  "Identity, modelled separately",
  "A frontend that trusts nothing",
  "A feedback system, not a test count",
  "Three containers, one private network",
  "A cache that PostgreSQL outranks",
  "Kafka behind a transactional outbox",
  "The first real service boundary",
  "Seeing the system work",
  "A learned signal beside the rules",
  "Relationships as a read model",
  "An assistant that can only read",
  "Kafka talks to services, WebSockets talk to people",
  "From a laptop to a public URL",
];

/**
 * Fixed canvas. The grid math is deterministic (origin 40,80; cell 130x64;
 * stepX 130+gapX; stepY 64+gapY), so an authored viewBox pins every frame to
 * the same 1330x820 canvas and the system visibly grows inside it.
 */
const VIEW_BOX = [1330, 820];
const LAYOUT = { mode: "grid", cols: 6, gapX: 92, gapY: 112 };

/**
 * Text budgets, derived from the vendored renderer's own math so a violation
 * fails here with a structured error instead of at `npm run archify:validate`:
 *
 * - At the 930px desktop reader width a 1330px viewBox must keep 6px of
 *   projected text, so source font ≥ 6 * 1330 / 930 = 8.58px. Node text fits
 *   with `units * 0.6 * font ≤ cellWidth - 8`; the grid's 120px cells leave
 *   112px, and the 9px-prefitted sublabel therefore allows
 *   `112 / (0.6 * 8.58) = 21` text units. "pybank + pybank_fraud" sits exactly
 *   at 21 — one more unit and check-render-output reports 5.87px projected.
 * - Labels use the validator's `units * 6.6 ≤ width + 8` (128 / 6.6 → 19).
 * - Tags render as fine detail (no readability floor) but must clear the
 *   legible-minimum fit: `units * 6 * 0.6 ≤ 112` → 31.
 */
export const SUBLABEL_MAX_TEXT_UNITS = 21;
export const LABEL_MAX_TEXT_UNITS = 19;
export const TAG_MAX_TEXT_UNITS = 31;

/**
 * The final topology, declared once. `born` is the phase the component first
 * exists in. `changes` rewrites labels at a later phase, which is how the
 * Fraud Service honestly grows "rules" -> "rules + model" -> "rules, model,
 * graph" without ever changing position.
 */
const NODES = [
  { id: "react", type: "frontend", row: 0, col: 1, born: 5, label: "React SPA", sublabel: "Vite build", tag: "presentation only" },
  { id: "redis", type: "database", row: 0, col: 2, born: 8, label: "Redis", sublabel: "cache-aside reads", tag: "never the ledger" },
  {
    id: "consumers", type: "backend", row: 0, col: 3, born: 9, label: "Consumers", sublabel: "audit consumer",
    changes: [
      { from: 15, sublabel: "audit + WhatsApp push" },
    ],
  },
  { id: "observ", type: "cloud", row: 0, col: 4, born: 11, label: "Observability", sublabel: "metrics + dashboards", tag: "outside the request path" },
  {
    id: "client", type: "external", row: 1, col: 0, born: 0, label: "Customer", sublabel: "browser",
    changes: [
      { from: 15, sublabel: "browser, WebSocket" },
    ],
  },
  { id: "nginx", type: "cloud", row: 1, col: 1, born: 16, label: "Nginx", sublabel: "TLS :443", tag: "production edge" },
  {
    id: "api", type: "backend", row: 1, col: 2, born: 0, label: "Banking API", sublabel: "FastAPI :8000",
    changes: [
      { from: 2, sublabel: ":8000 /api/v1", tag: "translate; domain decides" },
      { from: 9, sublabel: ":8000 /api/v1", tag: "auth, money, outbox" },
      { from: 15, sublabel: ":8000 /api/v1, /ws", tag: "auth, money, events, WS" },
    ],
  },
  { id: "kafka", type: "messagebus", row: 1, col: 3, born: 9, label: "Kafka", sublabel: "topic pybank.events", tag: "at-least-once" },
  {
    id: "fraud", type: "backend", row: 1, col: 4, born: 10, label: "Fraud Service", sublabel: "rules", tag: "own consumer group",
    changes: [
      { from: 12, sublabel: "rules + model" },
      { from: 13, sublabel: "rules, model, graph" },
    ],
  },
  { id: "neo4j", type: "database", row: 1, col: 5, born: 13, label: "Neo4j", sublabel: "money-movement graph", tag: "advisory only" },
  { id: "agent", type: "backend", row: 2, col: 0, born: 14, label: "AI Assistant", sublabel: "read-only tools", tag: "backend enforces limits" },
  { id: "tests", type: "external", row: 2, col: 1, born: 6, label: "Test suite", sublabel: "pytest, ruff, mypy", tag: "gates every change" },
  { id: "domain", type: "backend", row: 2, col: 2, born: 1, label: "Domain core", sublabel: "framework-free rules", tag: "no web or ORM imports" },
  {
    id: "postgres", type: "database", row: 2, col: 3, born: 3, label: "PostgreSQL", sublabel: "money + outbox", tag: "the only ledger",
    changes: [
      { from: 10, sublabel: "pybank + pybank_fraud" },
    ],
  },
  { id: "ml", type: "database", row: 2, col: 4, born: 12, label: "ML model", sublabel: "fraud-model-v1", tag: "threshold-gated" },
  { id: "security", type: "security", row: 3, col: 1, born: 4, label: "Auth", sublabel: "JWT, Argon2id", tag: "identity is not money" },
];

/**
 * Connections with their honest lifetime. `born`/`dies` are inclusive phases.
 * The customer-to-API direct edge dies when Nginx arrives at Phase 16 — the
 * request path genuinely changes, so the diagram is allowed to forget it.
 * Sides and vias are authored against the fixed canvas above; the Archify
 * validator is the referee (npm run archify:validate).
 */
const EDGES = [
  { id: "client-to-api", from: "client", to: "api", label: "HTTP", variant: "emphasis", born: 0, dies: 15 },
  { id: "client-to-nginx", from: "client", to: "nginx", label: "HTTPS :443", variant: "emphasis", born: 16 },
  { id: "nginx-to-api", from: "nginx", to: "api", label: "proxies API", variant: "emphasis", born: 16 },
  { id: "nginx-to-react", from: "nginx", to: "react", label: "serves the build", born: 16, fromSide: "top", toSide: "bottom" },
  { id: "api-to-react", from: "api", to: "react", label: "REST", born: 5, fromSide: "top", toSide: "bottom" },
  // The label rides 28px below the default anchor so it clears the API box
  // instead of overlapping it (the validator's own suggestion, +24, leaves no
  // margin for the 4px minimum).
  { id: "api-to-domain", from: "api", to: "domain", label: "domain rules", born: 1, fromSide: "bottom", toSide: "top", labelDy: 28 },
  { id: "api-to-postgres", from: "api", to: "postgres", label: "tx + outbox", variant: "emphasis", born: 3, fromSide: "right", toSide: "top", labelSegment: 2 },
  { id: "api-to-security", from: "api", to: "security", label: "verifies JWT", variant: "dashed", born: 4, labelDy: 20 },
  { id: "tests-to-api", from: "tests", to: "api", label: "gates every change", variant: "dashed", born: 6, labelSegment: 2, labelDy: -32 },
  { id: "api-to-redis", from: "api", to: "redis", label: "cache reads", variant: "dashed", born: 8, fromSide: "top", toSide: "bottom", labelDx: 24 },
  { id: "api-to-kafka", from: "api", to: "kafka", label: "outbox rows", variant: "emphasis", born: 9 },
  { id: "kafka-to-consumers", from: "kafka", to: "consumers", label: "consume", born: 9, fromSide: "top", toSide: "bottom" },
  // "transfer.completed" is 96px wide and the Kafka/Fraud gap is 102px, so the
  // label rides 28px below its own edge: above it, it would sit on
  // fraud-to-kafka's line.
  { id: "kafka-to-fraud", from: "kafka", to: "fraud", label: "transfer.completed", variant: "emphasis", born: 10, labelDy: 28 },
  { id: "fraud-to-kafka", from: "fraud", to: "kafka", label: "risk.assessed", variant: "dashed", born: 10, fromSide: "left", toSide: "right" },
  { id: "fraud-to-ml", from: "fraud", to: "ml", label: "scores with model", variant: "dashed", born: 12, fromSide: "bottom", toSide: "top", labelDy: 28 },
  { id: "fraud-to-neo4j", from: "fraud", to: "neo4j", label: "projects graph", variant: "dashed", born: 13 },
  { id: "fraud-to-observ", from: "fraud", to: "observ", label: "metrics", variant: "dashed", born: 11, fromSide: "top", toSide: "bottom",
    // The two-point label anchors at the start point's y-10 (246), which sits
    // on the "Fraud intelligence" title rail once Neo4j widens that frame at
    // Phase 13 — lift it into the gap between Observability and the rail.
    labelDy: -44 },
  {
    // Authored route: no corridor exists in the top half. Every ascent between
    // the API and Kafka climbs through x=604..706, and from Phase 15 the
    // consumer push spans that band on its way back to the browser, so the two
    // would cross. This advisory edge takes the empty lane under row 2 and the
    // right margin instead: leave the API's right edge, drop through the
    // Domain/PostgreSQL gap, run below row 2, and climb the margin to the right
    // of Neo4j into Observability's right edge. It crosses nothing in any frame.
    // The climb rides x=1316: the Fraud-intelligence frame (Neo4j in the wrap
    // from Phase 13) owns x=898..1300, so 16px of margin keeps the vertical
    // leg off its right border — the same clearance the x=650 corridor keeps
    // from the Request-path frame.
    id: "api-to-observ", from: "api", to: "observ", label: "metrics + traces", variant: "dashed", born: 11,
    fromSide: "right", toSide: "right", labelSegment: 2,
    via: [[650, 286], [650, 550], [1316, 550], [1316, 110]],
  },
  {
    // Authored route: the automatic one slid up agent's right edge and into
    // api's left edge, both against the inferred sides. This route goes right,
    // up the gap between Agent and Test suite, along the row 1/2 lane, then up
    // the gap between Nginx and the API before turning into the API's left edge.
    id: "agent-to-api", from: "agent", to: "api", label: "read-only tools", variant: "dashed", born: 14,
    fromSide: "right", toSide: "left", labelSegment: 2,
    via: [[200, 462], [200, 360], [440, 360], [440, 286]],
  },
  {
    // Authored route: the automatic one used the row 0/1 lane at y=194.5, which
    // every vertical spoke from row 1 to row 0 has to cross. Going over the top
    // band keeps this the only relationship up there, so it crosses nothing.
    id: "consumers-to-client", from: "consumers", to: "client", label: "pushes updates", variant: "dashed", born: 15,
    fromSide: "top", toSide: "top", labelSegment: 1,
    via: [[766, 60], [100, 60]],
  },
];

/**
 * Authored group boundaries. The renderer derives each frame from `wraps`
 * (30px pad, 20px extra bottom, title rail above the top edge), so membership
 * is filtered per phase and a group only ships once one member exists. All
 * four boxes are disjoint in every frame — A request-path vs. B event-backbone
 * vs. D fraud-intelligence are separated on x, C private-state sits a full row
 * lower — which keeps the title-vs-frame and title-vs-title contracts green
 * under `quality_profile: showcase` (enforcesBoundaryTitleComposition).
 */
const GROUPS = [
  // Phase 0: client + api. Nginx joins at 16 inside the same span, so the box
  // never moves. Rows 0-2 never reach into x 10..634 at y 226..336.
  { kind: "region", label: "Request path", wraps: ["client", "nginx", "api"], born: 0 },
  // Phase 9: the outbox relay column (kafka x706 with consumers above it).
  // Frame x 676..856 clears the API (ends x604) and Observability (starts x928).
  { kind: "region", label: "Event backbone", wraps: ["kafka", "consumers"], born: 9 },
  // Phase 3: PostgreSQL; ML joins at 12 in the same row span. Row 2 only —
  // frame y 402..552 clears every other frame's y 50..336.
  { kind: "security-group", label: "Private state", wraps: ["postgres", "ml"], born: 3 },
  // Phase 10: Fraud Service; Neo4j joins at 13. Frame x 898..1300 starts
  // 42px right of the event-backbone frame, so the two never touch.
  { kind: "region", label: "Fraud intelligence", wraps: ["fraud", "neo4j"], born: 10 },
];

/**
 * In-frame legend: schema-supported `meta.legend.entries` renames the seven
 * component kinds in the site's own words. Mode `auto` shows only kinds that
 * exist in the current phase, so Phase 01 lists two entries and Phase 16
 * lists seven.
 */
const LEGEND_ENTRIES = {
  mode: "auto",
  entries: {
    frontend: { label: "Browser UI" },
    backend: { label: "Services" },
    database: { label: "State stores" },
    cloud: { label: "Edge & ops" },
    security: { label: "Identity" },
    messagebus: { label: "Event bus" },
    external: { label: "People & gates" },
  },
};

function nodeAt(node, phase, bornThisPhase) {
  const current = { id: node.id, type: node.type, label: node.label, sublabel: node.sublabel };
  if (node.tag) current.tag = node.tag;
  for (const change of node.changes ?? []) {
    if (phase >= change.from) {
      const { from, ...patch } = change;
      Object.assign(current, patch);
    }
  }
  // New-component emphasis: in its birth frame only (phase 00 is all-new, so
  // it stays clean). The suffix rides the accent-coloured tag line and reverts
  // to the authored tag the moment the next phase renders.
  if (bornThisPhase && node.born > 0) {
    current.tag = current.tag ? `${current.tag} · new` : "new";
  }
  return { ...current, row: node.row, col: node.col };
}

function edgeAt(edge, emphasize = false) {
  const out = { id: edge.id, from: edge.from, to: edge.to, label: edge.label };
  if (edge.variant) out.variant = edge.variant;
  // New-component emphasis for wiring: every edge arriving at (or carrying the
  // story of) a component born this phase lights up as emphasis in this frame.
  if (emphasize && edge.variant !== "emphasis") out.variant = "emphasis";
  if (edge.fromSide) out.fromSide = edge.fromSide;
  if (edge.toSide) out.toSide = edge.toSide;
  if (edge.route) out.route = edge.route;
  if (edge.via) out.via = edge.via;
  if (edge.labelAt) out.labelAt = edge.labelAt;
  if (edge.labelDx !== undefined) out.labelDx = edge.labelDx;
  if (edge.labelDy !== undefined) out.labelDy = edge.labelDy;
  if (edge.labelSegment !== undefined) out.labelSegment = edge.labelSegment;
  return out;
}

export function irForPhase(phase) {
  const bornThisPhase = new Set(
    NODES.filter((node) => node.born === phase && phase > 0).map((node) => node.id),
  );
  const components = NODES.filter((node) => node.born <= phase).map((node) =>
    nodeAt(node, phase, bornThisPhase.has(node.id)),
  );
  const alive = new Set(components.map((component) => component.id));
  const connections = EDGES.filter(
    (edge) =>
      edge.born <= phase &&
      (edge.dies === undefined || phase <= edge.dies) &&
      alive.has(edge.from) &&
      alive.has(edge.to),
  ).map((edge) => edgeAt(edge, bornThisPhase.has(edge.from) || bornThisPhase.has(edge.to)));
  const boundaries = GROUPS.filter((group) => group.born <= phase)
    .map((group) => ({
      kind: group.kind,
      label: group.label,
      wraps: group.wraps.filter((id) => alive.has(id)),
    }))
    .filter((group) => group.wraps.length > 0);
  const padded = String(phase).padStart(2, "0");
  return {
    schema_version: 1,
    diagram_type: "architecture",
    meta: {
      title: `Phase ${padded} — ${PHASE_TITLES[phase]}`,
      output: `public/archify/evolution/phase-${padded}.html`,
      quality_profile: "showcase",
      locale: "en",
      viewBox: VIEW_BOX,
      legend: LEGEND_ENTRIES,
    },
    layout: LAYOUT,
    components,
    boundaries,
    connections,
    cards: [],
  };
}

const TEXT_BUDGETS = [
  ["label", LABEL_MAX_TEXT_UNITS, "LABEL_MAX_TEXT_UNITS"],
  ["sublabel", SUBLABEL_MAX_TEXT_UNITS, "SUBLABEL_MAX_TEXT_UNITS"],
  ["tag", TAG_MAX_TEXT_UNITS, "TAG_MAX_TEXT_UNITS"],
];

/**
 * Structured text-budget validation. One throw, every violation listed with
 * phase, component, field, measured units, the limit and the constant name —
 * the same numbers the vendored validator and check-render-output would fail
 * on, reported against the node that actually carries the text.
 */
export function validateTextBudgets(ir) {
  const violations = [];
  for (const component of ir.components) {
    for (const [field, limit, constant] of TEXT_BUDGETS) {
      const value = component[field];
      if (value == null || value === "") continue;
      const units = textUnits(value);
      if (units <= limit) continue;
      violations.push(
        `${ir.meta.title}: component "${component.id}" ${field} is ${units} text units `
          + `(max ${limit}, ${constant}): "${value}"`,
      );
    }
  }
  if (violations.length > 0) {
    throw new Error(
      `text-budget invariant violated in ${violations.length} place`
        + `${violations.length === 1 ? "" : "s"}:\n  ${violations.join("\n  ")}`,
    );
  }
  return true;
}

function generate() {
  const check = process.argv.includes("--check");
  mkdirSync(path.join(repoRoot, "public", "archify", "evolution"), { recursive: true });

  const stale = [];
  for (let phase = 0; phase < PHASE_TITLES.length; phase += 1) {
    const ir = irForPhase(phase);
    validateTextBudgets(ir);
    const file = path.join(irDir, `evolution-${String(phase).padStart(2, "0")}.architecture.json`);
    const contents = `${JSON.stringify(ir, null, 2)}\n`;
    let onDisk = null;
    try {
      onDisk = readFileSync(file, "utf8");
    } catch {
      onDisk = null;
    }
    if (onDisk === contents) continue;
    stale.push(path.relative(repoRoot, file));
    if (!check) writeFileSync(file, contents, "utf8");
  }

  if (check && stale.length > 0) {
    console.error(`evolution: stale IR files (run: node tools/evolution.mjs)\n  ${stale.join("\n  ")}`);
    process.exit(1);
  }
  console.log(
    check
      ? `evolution: all ${PHASE_TITLES.length} evolution IRs are up to date.`
      : `evolution: wrote ${PHASE_TITLES.length} cumulative IRs to archify/evolution-NN.architecture.json`,
  );
}

// Side effects only when invoked as a script; tests import the pure builders.
const invokedDirectly = (() => {
  const entry = process.argv[1];
  if (!entry) return false;
  return path.resolve(entry).toLowerCase() === fileURLToPath(import.meta.url).toLowerCase();
})();

if (invokedDirectly) generate();

