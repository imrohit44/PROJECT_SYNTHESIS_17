/**
 * Content model for the Synthesis Explorer.
 *
 * The site describes one real repository: Project Synthesis 17.
 * Its 17 engineering stages, Phase 0 through Phase 16, are documented in
 * `docs/architecture/phase-N.md`; the "System Evolution" frames are generated from
 * `showcase/tools/evolution.mjs`, which compiles the same topology into Archify IR files.
 */

/** Why a phase exists in the story of the system. */
export type PhaseTrack = "foundation" | "platform" | "intelligence" | "delivery";

export interface Phase {
  /** 0-16, matching docs/architecture/phase-N.md. */
  number: number;
  /** Stable slug, e.g. "event-backbone". */
  id: string;
  title: string;
  track: PhaseTrack;
  /** One sentence a reviewer can repeat. */
  tagline: string;
  /** The situation the phase walked into. */
  problem: string;
  /** What the phase actually changed about the system. */
  change: string;
  /** What is true afterwards that was not before. */
  result: string;
  /** The cost the phase accepted, stated in the open. */
  tradeoff: string;
  /** Technologies this phase actually introduced. */
  stack: string[];
  /** Repository-relative documentation path. */
  docPath: string;
}

export type ArtifactType = "architecture" | "sequence" | "dataflow" | "workflow" | "lifecycle";

/** A guided view authored inside the Archify IR, mirrored here for the app chrome. */
export interface ArtifactView {
  id: string;
  label: string;
  note: string;
}

export interface Artifact {
  id: string;
  type: ArtifactType;
  title: string;
  blurb: string;
  /** App-relative URL of the delivered artifact, served from public/. */
  url: string;
  /** Repository-relative IR path, so a reader can see the source of truth. */
  irPath: string;
  views: ArtifactView[];
  phaseNumbers: number[];
}
