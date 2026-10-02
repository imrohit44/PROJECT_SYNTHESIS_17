/**
 * The System Evolution stage.
 *
 * Two stacked Archify iframes cross-fade in place. Because every frame is
 * rendered on the same authored canvas, switching phases keeps every existing
 * component at the same pixel position — the incoming frame only adds what
 * the new phase built. Frames are the same lazy static artifacts as before;
 * at most two are ever loaded.
 */
import { useEffect, useRef, useState } from "react";

import { evolutionFrameSrc } from "../content/evolution";

interface Slot {
  src: string;
  phase: number;
  loaded: boolean;
}

interface CrossfadeStageProps {
  phase: number;
}

export function CrossfadeStage({ phase }: CrossfadeStageProps) {
  const src = evolutionFrameSrc(phase);
  const [slots, setSlots] = useState<[Slot, Slot]>(() => [
    { src, phase, loaded: false },
    { src: "", phase, loaded: false },
  ]);
  const [active, setActive] = useState(0);
  const activeRef = useRef(active);
  activeRef.current = active;
  // The stage mounts with one frame and the idle slot empty. Without this
  // guard the effect's first run — which React fires on mount — would treat
  // that empty slot as a slot waiting for the current phase and mount the same
  // frame twice.
  const servedSrc = useRef(src);

  useEffect(() => {
    if (servedSrc.current === src) return;
    servedSrc.current = src;
    setSlots(([first, second]) => {
      const idle = activeRef.current === 0 ? 1 : 0;
      const idleSlot = idle === 0 ? first : second;
      if (idleSlot.src === src) return [first, second];
      const replacement: Slot = { src, phase, loaded: false };
      return idle === 0 ? [replacement, second] : [first, replacement];
    });
  }, [src, phase]);

  const handleLoad = (index: number) => {
    setSlots((current) =>
      current.map((slot, i) => (i === index ? { ...slot, loaded: true } : slot)) as [Slot, Slot],
    );
    setActive(index);
  };

  return (
    <div className="stage" aria-label={`System architecture at phase ${phase}`}>
      {slots.map((slot, index) =>
        slot.src === "" ? null : (
          <iframe
            key={index}
            className={index === active && slot.loaded ? "stage__frame is-active" : "stage__frame"}
            title={`Project Synthesis 17 architecture after Phase ${slot.phase} — Archify diagram`}
            src={slot.src}
            onLoad={() => handleLoad(index)}
          />
        ),
      )}
    </div>
  );
}
