/**
 * The System Evolution frames.
 *
 * `tools/evolution.mjs` generates one cumulative Archify IR per phase and
 * `npm run archify:deliver` compiles each IR into the HTML file referenced
 * here. Because every frame shares the same authored viewBox, the same
 * component sits at the same pixel position in every frame it appears in:
 * the visualization is one system growing, not seventeen diagrams.
 */
export const PHASE_COUNT = 17;

/** The first frame a visitor should see. */
export const FIRST_PHASE = 0;

export function evolutionFrameSrc(phase: number): string {
  return `/archify/evolution/phase-${String(phase).padStart(2, "0")}.html`;
}

/** Every frame src, in phase order. */
export const evolutionFrames: string[] = Array.from({ length: PHASE_COUNT }, (_, phase) =>
  evolutionFrameSrc(phase),
);
