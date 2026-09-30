/**
 * The deep-dive Archify artifacts.
 *
 * The platform view itself lives in the Evolution Engine (see evolution.ts);
 * these two diagrams zoom into machinery the growing map cannot show: the
 * asynchronous fraud pipeline and the full life of one transfer.
 *
 * Regenerate with: `npm run archify:deliver`.
 */
import type { Artifact } from "./types";

export const artifacts: Artifact[] = [
  {
    id: "fraud-pipeline",
    type: "dataflow",
    title: "Fraud scoring pipeline",
    blurb:
      "How a committed row becomes a stored assessment: transport, feature building, three independent signals, and one auditable outcome.",
    url: "/archify/fraud-pipeline.html",
    irPath: "showcase/archify/fraud-pipeline.dataflow.json",
    phaseNumbers: [9, 10, 12, 13],
    views: [
      {
        id: "primary-path",
        label: "Primary path",
        note: "A committed row becomes an event, then a score, then a stored assessment.",
      },
      {
        id: "model-signal",
        label: "Model signal",
        note: "The ML probability only counts when it clears the trained threshold.",
      },
      {
        id: "graph-signal",
        label: "Graph signal",
        note: "Relationship evidence can only ever add a bounded bonus.",
      },
      {
        id: "signal-fan-in",
        label: "Signal fan-in",
        note: "Three independent signals land in one auditable assessment row.",
      },
    ],
  },
  {
    id: "transfer-journey",
    type: "sequence",
    title: "One transfer, end to end",
    blurb:
      "A single ₹18,200 transfer at 02:10: the synchronous commit, the asynchronous scoring, and the live update that reaches the customer.",
    url: "/archify/transfer-journey.html",
    irPath: "showcase/archify/transfer-journey.sequence.json",
    phaseNumbers: [9, 10, 12, 13, 15],
    views: [
      {
        id: "commit-path",
        label: "Commit path",
        note: "The customer's money moves synchronously, before any fraud work starts.",
      },
      {
        id: "fraud-plane",
        label: "Fraud intelligence",
        note: "Rules and the model score the transfer; the graph adds at most 0.15.",
      },
      {
        id: "delivery",
        label: "Delivery back to the customer",
        note: "risk.assessed reaches the browser over the WebSocket the customer already holds.",
      },
    ],
  },
];

export function artifactById(id: string): Artifact | undefined {
  return artifacts.find((artifact) => artifact.id === id);
}
