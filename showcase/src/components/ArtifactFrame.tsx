import { useState } from "react";

import type { Artifact } from "../content/types";

export interface ArtifactFrameProps {
  artifact: Artifact;
  /** Viewer height in pixels. */
  height?: number;
  /** Load the artifact immediately instead of waiting for a reader to ask. */
  eager?: boolean;
}

/**
 * Embeds one compiled Archify artifact.
 *
 * The artifact is a self-contained HTML file in public/archify (roughly 800 KB),
 * so it is never bundled: the iframe is created only when the reader asks for
 * it, or immediately when a page is built around a single diagram.
 */
export function ArtifactFrame({ artifact, height = 640, eager = false }: ArtifactFrameProps) {
  const [loaded, setLoaded] = useState(eager);

  return (
    <section className="artifact" aria-labelledby={`artifact-${artifact.id}`}>
      <div className="artifact__head">
        <h3 id={`artifact-${artifact.id}`}>{artifact.title}</h3>
        <a className="button button--ghost" href={artifact.url} target="_blank" rel="noreferrer">
          Open in a new tab
        </a>
      </div>
      <p>{artifact.blurb}</p>
      <div className="artifact__frame">
        {loaded ? (
          <iframe
            title={`${artifact.title} — interactive Archify artifact`}
            src={artifact.url}
            loading="lazy"
            style={{ height: `${height}px`, maxHeight: "78vh" }}
          />
        ) : (
          <div className="artifact__placeholder">
            <p>
              This is an interactive artifact of about 800 KB with its own guided views, legend and
              search. Load it only when you want to read it — it is never part of the app bundle.
            </p>
            <button type="button" className="button button--primary" onClick={() => setLoaded(true)}>
              Load interactive diagram
            </button>
            <p className="chip chip--mono">{artifact.irPath}</p>
          </div>
        )}
      </div>
      <ul className="artifact__views">
        {artifact.views.map((view) => (
          <li className="artifact__view" key={view.id}>
            <strong>{view.label}</strong>
            {view.note}
          </li>
        ))}
      </ul>
    </section>
  );
}
