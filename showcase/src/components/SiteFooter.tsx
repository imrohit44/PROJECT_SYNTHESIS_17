/**
 * The footer: provenance and the exact commands that regenerate everything
 * on the page. The backend, services and frontend of Project Synthesis 17 are
 * untouched by this project; Archify runs only as a build-time compiler.
 */
export function SiteFooter() {
  return (
    <footer className="site-footer">
      <div className="site-footer__inner">
        <div>
          <h2>Provenance</h2>
          <p>
            Every frame on the evolution stage is compiled from JSON authored against{" "}
            <code>docs/architecture/phase-N.md</code> in the banking repository. No diagram on
            this page was hand-drawn, and no component appears in a phase where it did not exist.
          </p>
        </div>
        <div>
          <h2>Regenerating</h2>
          <ul>
            <li>
              <code>node tools/evolution.mjs</code> — recompile the 17 cumulative frames from the
              topology declaration
            </li>
            <li>
              <code>npm run archify:validate</code> — referee every frame at showcase quality
            </li>
            <li>
              <code>npm run archify:deliver</code> — compile all IRs into public/archify
            </li>
          </ul>
        </div>
        <div>
          <h2>Read-only by design</h2>
          <p>
            The banking repository is never modified by this showcase. Archify runs at build time;
            its output is static HTML loaded lazily in iframes, never part of the app bundle.
          </p>
        </div>
      </div>
    </footer>
  );
}
