/**
 * The hero: one sentence, one question, two ways forward.
 */
export function HeroSection() {
  return (
    <section className="hero">
      <p className="hero__eyebrow">Project Synthesis 17 · PyBank · a working banking system</p>
      <h1 className="hero__title">
        One system.
        <br />
        Seventeen decisions.
      </h1>
      <p className="hero__lead">
        PyBank was grown, not designed. Seventeen phases, each answering a problem the previous
        system actually had — and each writing down what the change cost. Press play and watch
        the architecture arrive in the order it really shipped.
      </p>
      <div className="hero__actions">
        <a className="button button--solid" href="#evolution">
          Watch it grow
        </a>
        <a
          className="button button--ghost"
          href="https://github.com/imrohit44/PyBank"
          target="_blank"
          rel="noreferrer"
        >
          The real repository
        </a>
      </div>
      <dl className="hero__facts">
        <div>
          <dt>Phases</dt>
          <dd>17</dd>
        </div>
        <div>
          <dt>Components on the final canvas</dt>
          <dd>16</dd>
        </div>
        <div>
          <dt>Diagrams redrawn per phase</dt>
          <dd>0</dd>
        </div>
        <div>
          <dt>Phase docs in the repository</dt>
          <dd>17</dd>
        </div>
      </dl>
    </section>
  );
}
