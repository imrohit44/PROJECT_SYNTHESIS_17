/**
 * The final beat: the documentary ends where the running system begins.
 *
 * This is a different deployment from the one serving this page. This site is
 * the Synthesis Explorer — the architecture and its evolution, Phase 0 through
 * Phase 16. The link below opens the deployed banking application on its own
 * host, where a reader signs in and uses the actual system.
 */
const LIVE_APP_URL = "https://frontend-production-b4d5.up.railway.app/";

export function LiveAppSection() {
  return (
    <section className="live-app" id="live-app">
      <header className="section-head">
        <h2>Run it yourself</h2>
      </header>
      <p className="live-app__kicker">The deployed system</p>
      <p className="live-app__statement">The system is not just documented. It&rsquo;s running.</p>
      <p className="live-app__support">
        Explore how Project Synthesis 17 was engineered, then interact with the system itself.
      </p>
      {/* Follows the site convention for external links: a new tab, no referrer. */}
      <a className="button button--solid" href={LIVE_APP_URL} target="_blank" rel="noreferrer">
        Open the Live Banking Application <span aria-hidden="true">→</span>
      </a>
      <p className="live-app__note">
        This page is the documentary. The application above is the same system running as software:
        register an account, open savings or current accounts, move money, and watch fraud scoring,
        events and realtime updates happen for real.
      </p>
    </section>
  );
}