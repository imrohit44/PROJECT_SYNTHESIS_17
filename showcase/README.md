# Synthesis Explorer — Project Synthesis 17 (PyBank)

This folder is a **read-only museum** for the banking system in the repository
root. It visualises PyBank without modifying it: no file outside `showcase/`
(plus `.gitignore` entries for its own build outputs) is touched.

## What lives here

| Path | Purpose |
| --- | --- |
| `archify/*.json` | Authored Archify intermediate representations (the source of truth for diagrams). |
| `public/archify/*.html` | Delivered, standalone Archify artifacts, served statically and embedded as lazy-loaded iframes. Regenerate with `npm run archify:deliver`. |
| `vendor/archify/` | The Archify compiler, vendored so builds never need the network. App code never imports it. |
| `tools/archify.mjs` | Build-time wrapper: `validate-all` / `deliver-all` over every IR in `archify/`. |
| `tools/score_scenarios.py` | Runs the fraud service's own pipeline (rules + committed `fraud-model-v1` + bounded graph maths) and writes `src/content/scenarios.generated.ts`. |
| `src/content/` | Typed museum content: 17 phases, the artifact registry, and the generated scenario scores. |
| `src/components/`, `src/pages/` | The React app (React 19 + Vite 7 + React Router 7). |

## Develop

```powershell
cd showcase
npm install
npm run dev          # local dev server
```

## Verify

```powershell
cd showcase
npm run typecheck    # tsc project references
npm run lint         # eslint
npm test             # vitest, incl. content-model and scoring-maths tests
npm run archify:validate  # validate all Archify IRs at showcase quality
npm run archify:deliver   # recompile artifacts into public/archify
npm run build        # typecheck + production build (copies public/archify into dist)
```

Regenerating scores from the real model:

```powershell
python tools/score_scenarios.py   # from the repository root
```
