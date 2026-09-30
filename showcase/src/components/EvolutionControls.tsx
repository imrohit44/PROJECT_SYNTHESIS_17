/**
 * Transport for the Evolution Engine.
 *
 * One row: step back, play or pause, step forward, a range scrubber spanning
 * all seventeen phases, and the current phase's number and title. The native
 * range input carries keyboard scrubbing (arrows, Home/End, PageUp/PageDown)
 * and screen-reader semantics with it, so the row needs no extra key handling.
 */
import { phases } from "../content/phases";
import { FIRST_PHASE, PHASE_COUNT } from "../content/evolution";
import type { EvolutionController } from "../hooks/useEvolution";

const padded = (phase: number) => String(phase).padStart(2, "0");

export function EvolutionControls({ controller }: { controller: EvolutionController }) {
  const { phase, playing, atStart, atEnd } = controller;
  const current = phases[phase];

  return (
    <div className="controls">
      <div className="controls__transport">
        <button type="button" className="transport" onClick={controller.prev} disabled={atStart} aria-label="Previous phase">
          ←
        </button>
        <button
          type="button"
          className="transport transport--play"
          onClick={playing ? controller.pause : controller.play}
          aria-label={playing ? "Pause the evolution" : "Play the evolution from the current phase"}
        >
          {playing ? "Pause" : "Play"}
        </button>
        <button type="button" className="transport" onClick={controller.next} disabled={atEnd} aria-label="Next phase">
          →
        </button>
        <input
          className="controls__slider"
          type="range"
          min={FIRST_PHASE}
          max={PHASE_COUNT - 1}
          step={1}
          value={phase}
          onChange={(event) => controller.seek(Number(event.target.value))}
          aria-label={`Phase scrubber, currently phase ${padded(phase)}`}
        />
        <span className="controls__phase">
          <strong>
            Phase {padded(phase)} / {padded(PHASE_COUNT - 1)}
          </strong>
          <span>{current.title}</span>
        </span>
      </div>
    </div>
  );
}
