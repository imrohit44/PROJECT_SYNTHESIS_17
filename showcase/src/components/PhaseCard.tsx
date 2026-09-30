/**
 * The narrative card that rides on the stage: the phase the canvas is
 * showing, told as problem, change, result — and the cost that came with it.
 * All copy comes from src/content/phases.ts, condensed from the phase docs.
 */
import type { Phase } from "../content/types";

export function PhaseCard({ phase }: { phase: Phase }) {
  return (
    <aside className={`phase-card phase-card--${phase.track}`} aria-live="polite">
      <p className="phase-card__eyebrow">
        Phase {String(phase.number).padStart(2, "0")} · {phase.track}
      </p>
      <h3 className="phase-card__title">{phase.title}</h3>
      <dl className="phase-card__body">
        <div>
          <dt>Problem</dt>
          <dd>{phase.problem}</dd>
        </div>
        <div>
          <dt>Change</dt>
          <dd>{phase.change}</dd>
        </div>
        <div>
          <dt>Result</dt>
          <dd>{phase.result}</dd>
        </div>
        <div>
          <dt>Cost</dt>
          <dd>{phase.tradeoff}</dd>
        </div>
      </dl>
      <p className="phase-card__stack">{phase.stack.join(" · ")}</p>
      <a
        className="phase-card__doc"
        href={`https://github.com/imrohit44/PyBank/blob/main/${phase.docPath}`}
        target="_blank"
        rel="noreferrer"
      >
        Read {phase.docPath}
      </a>
    </aside>
  );
}
