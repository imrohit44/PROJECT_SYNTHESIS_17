/**
 * The Evolution Engine's state machine.
 *
 * Holds the phase currently shown on the stage plus playback state. Playing
 * advances on a timer; reaching the last phase stops playback instead of
 * looping, because the story ends at Phase 16 rather than restarting. The
 * scrubber is a native range input, so seek() takes any phase directly.
 */
import { useCallback, useEffect, useState } from "react";

import { FIRST_PHASE, PHASE_COUNT } from "../content/evolution";

const LAST_PHASE = PHASE_COUNT - 1;
const BASE_INTERVAL_MS = 5200;

export interface EvolutionController {
  phase: number;
  playing: boolean;
  atStart: boolean;
  atEnd: boolean;
  play: () => void;
  pause: () => void;
  next: () => void;
  prev: () => void;
  seek: (phase: number) => void;
}

export function useEvolution(): EvolutionController {
  const [phase, setPhase] = useState(FIRST_PHASE);
  const [playing, setPlaying] = useState(false);

  useEffect(() => {
    if (!playing) return undefined;
    if (phase >= LAST_PHASE) {
      setPlaying(false);
      return undefined;
    }
    const timer = window.setTimeout(() => setPhase((current) => current + 1), BASE_INTERVAL_MS);
    return () => window.clearTimeout(timer);
  }, [playing, phase]);

  const seek = useCallback((target: number) => {
    setPhase(Math.min(LAST_PHASE, Math.max(FIRST_PHASE, target)));
  }, []);
  const next = useCallback(() => setPhase((current) => Math.min(LAST_PHASE, current + 1)), []);
  const prev = useCallback(() => setPhase((current) => Math.max(FIRST_PHASE, current - 1)), []);
  const play = useCallback(() => {
    setPhase((current) => (current >= LAST_PHASE ? FIRST_PHASE : current));
    setPlaying(true);
  }, []);
  const pause = useCallback(() => setPlaying(false), []);

  return {
    phase,
    playing,
    atStart: phase <= FIRST_PHASE,
    atEnd: phase >= LAST_PHASE,
    play,
    pause,
    next,
    prev,
    seek,
  };
}
