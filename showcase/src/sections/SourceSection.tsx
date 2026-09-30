/**
 * Source: where every fact on this page comes from, and how the frames are
 * compiled. The site never hand-draws a diagram or hand-writes a number.
 */
const steps = [
  {
    label: "1 · The facts",
    body: "docs/architecture/phase-0.md through phase-16.md in the banking repository. The phase cards, stack lists and doc links on this site are condensed from those files — nothing is invented.",
  },
  {
    label: "2 · The topology",
    body: "showcase/tools/evolution.mjs declares each component with the phase it was born in and each connection with the phases it lives through, then emits one cumulative Archify IR per phase, all sharing a single authored canvas.",
  },
  {
    label: "3 · The frames",
    body: "npm run archify:validate referees every frame against the Archify showcase quality profile; npm run archify:deliver compiles the seventeen IRs into static HTML in public/archify/evolution/ — loaded lazily in iframes, never bundled.",
  },
];

export function SourceSection() {
  return (
    <section className="source" id="source">
      <header className="section-head">
        <h2>Source</h2>
        <p>
          This page is a compiled view of one repository. Three steps, all reproducible on your
          machine.
        </p>
      </header>
      <ol className="source__steps">
        {steps.map((step) => (
          <li key={step.label}>
            <h3>{step.label}</h3>
            <p>{step.body}</p>
          </li>
        ))}
      </ol>
      <p className="source__links">
        <a href="https://github.com/imrohit44/PyBank" target="_blank" rel="noreferrer">
          github.com/imrohit44/PyBank
        </a>
        {" · "}
        <a
          href="https://github.com/imrohit44/PyBank/tree/main/docs/architecture"
          target="_blank"
          rel="noreferrer"
        >
          the seventeen phase documents
        </a>
        {" · "}
        <a
          href="https://github.com/imrohit44/PyBank/blob/main/showcase/tools/evolution.mjs"
          target="_blank"
          rel="noreferrer"
        >
          showcase/tools/evolution.mjs
        </a>
      </p>
    </section>
  );
}
