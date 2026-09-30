/**
 * "Why seventeen phases" — the editorial argument for the project's shape,
 * drawn from what the phase docs actually do.
 */
const principles = [
  {
    title: "Each phase answers a real problem",
    body: "Kafka did not arrive because event streaming was trendy; balances were committed but consumers could not know about them. Neo4j did not arrive for graph fashion; one event cannot see relationships. Every phase in the timeline walks into a problem its predecessor actually had.",
  },
  {
    title: "Nothing gets re-diagrammed",
    body: "A phase adds a seam, it does not repaint the map. The domain core from Phase 01 still sits under the API in Phase 16; PostgreSQL has not moved since Phase 03. When a component's role changes, the honest diagram says so: the fraud box grows from rules, to rules plus model, to rules, model and graph.",
  },
  {
    title: "Tradeoffs are written down",
    body: "Every phase ends with its bill: at-least-once means duplicate events, a service split means eventual consistency, a cache can be stale. The docs list these as costs, not footnotes — and this site carries them on every phase card.",
  },
  {
    title: "Each phase ends with proof",
    body: "Health checks, deterministic locks proven against real PostgreSQL, a smoke test that walks a whole transfer, CI that refuses to publish an unvalidated commit, and an E2E gate marked NOT VERIFIED until the day it actually existed.",
  },
];

export function WhySection() {
  return (
    <section className="why" id="why">
      <header className="section-head">
        <h2>Why seventeen phases</h2>
        <p>
          Because a system is reviewable when its growth is reviewable. Four rules held on every
          one of them.
        </p>
      </header>
      <div className="why__grid">
        {principles.map((principle, index) => (
          <article className="why__item" key={principle.title}>
            <span className="why__number" aria-hidden="true">
              {String(index + 1).padStart(2, "0")}
            </span>
            <h3>{principle.title}</h3>
            <p>{principle.body}</p>
          </article>
        ))}
      </div>
    </section>
  );
}
