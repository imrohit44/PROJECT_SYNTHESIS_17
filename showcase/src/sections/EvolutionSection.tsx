/**
 * The Evolution Engine: the dominant canvas of the site.
 *
 * A full-bleed Archify frame of the whole system per phase, cross-faded on a
 * fixed canvas. The transport, the semantic legend and the phase narrative
 * all sit outside the frame — the canvas shows the system, the caption tells
 * its story.
 */
import { CrossfadeStage } from "../components/CrossfadeStage";
import { EvolutionControls } from "../components/EvolutionControls";
import { PhaseCard } from "../components/PhaseCard";
import { phases } from "../content/phases";
import { useEvolution } from "../hooks/useEvolution";

/**
 * The seven semantic kinds exactly as the renderer paints them: one stroke
 * colour per kind plus a drawn sigil (window, chevrons, cylinders, cloud,
 * shield, rails, devices), mirrored from the frames' own theme variables.
 */
const KINDS = [
  { kind: "frontend", label: "Browser UI", sigil: "window" },
  { kind: "backend", label: "Services", sigil: "chevrons" },
  { kind: "database", label: "State stores", sigil: "cylinders" },
  { kind: "cloud", label: "Edge & ops", sigil: "cloud" },
  { kind: "security", label: "Identity", sigil: "shield" },
  { kind: "messagebus", label: "Event bus", sigil: "rails" },
  { kind: "external", label: "People & gates", sigil: "devices" },
];

export function EvolutionSection() {
  const controller = useEvolution();
  const phase = phases[controller.phase];

  return (
    <section className="evolution" id="evolution" aria-label="System evolution">
      <header className="section-head">
        <h2>System evolution</h2>
        <p>
          One architecture, growing in place. Every component sits where it was first built and
          never moves — PostgreSQL arrives at Phase 03, Kafka at 09, the model lands beside the
          Fraud Service at 12. Colour and shape are semantic, groups ride dashed frames, and each
          phase badges what it added. Scrub, step, or press play.
        </p>
      </header>
      <div className="evolution__canvas">
        <CrossfadeStage phase={controller.phase} />
      </div>
      <EvolutionControls controller={controller} />
      <ul className="canvas-legend" aria-label="Canvas legend">
        {KINDS.map((entry) => (
          <li className={`canvas-legend__item canvas-legend__item--${entry.kind}`} key={entry.kind}>
            <span className="canvas-legend__swatch" aria-hidden="true" />
            <span className="canvas-legend__label">{entry.label}</span>
            <span className="canvas-legend__sigil" aria-hidden="true">
              {entry.sigil}
            </span>
          </li>
        ))}
        <li className="canvas-legend__note">Dashed frame = group · “· new” = added that phase</li>
      </ul>
      <PhaseCard key={phase.number} phase={phase} />
    </section>
  );
}
