/**
 * Deep dives: the two diagrams the growing canvas cannot show — the fraud
 * pipeline internals and the full life of one transfer.
 */
import { ArtifactFrame } from "../components/ArtifactFrame";
import { artifacts } from "../content/artifacts";

export function DeepDiveSection() {
  return (
    <section className="deep-dive" id="deep-dive">
      <header className="section-head">
        <h2>Deep dives</h2>
        <p>
          The evolution canvas shows where components live. These two compiled Archify artifacts
          show how the interesting requests actually move — each one lazy-loaded, interactive,
          and compiled from the same kind of JSON the timeline above is built from.
        </p>
      </header>
      <div className="deep-dive__stack">
        {artifacts.map((artifact) => (
          <ArtifactFrame key={artifact.id} artifact={artifact} />
        ))}
      </div>
    </section>
  );
}
