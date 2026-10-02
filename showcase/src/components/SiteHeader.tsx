/**
 * The single-page header: a wordmark and four anchors. No router — the whole
 * site is one page, so navigation is a hash.
 */
const links = [
  { href: "#why", label: "Why 17 stages" },
  { href: "#evolution", label: "Evolution" },
  { href: "#deep-dive", label: "Deep dives" },
  { href: "#source", label: "Source" },
];

export function SiteHeader() {
  return (
    <header className="site-header">
      <a className="skip-link" href="#main">
        Skip to content
      </a>
      <div className="site-header__inner">
        <a className="brand" href="#top">
          <span className="brand__mark" aria-hidden="true">
            PB
          </span>
          <span className="brand__text">
            <strong>Synthesis Explorer</strong>
            <span>Project Synthesis 17 · Phase 0 → Phase 16</span>
          </span>
        </a>
        <nav className="site-nav" aria-label="Sections">
          {links.map((link) => (
            <a key={link.href} className="site-nav__link" href={link.href}>
              {link.label}
            </a>
          ))}
        </nav>
      </div>
    </header>
  );
}
