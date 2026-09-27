# Phase 16 — Learning Notes: CI/CD and Cloud

The interview question this phase answers: **"How does code get from my laptop
to a running cloud application?"**

The honest answer is a chain of five hand-offs, each of which can fail. Every
technology below exists because that chain was previously done by one person
with a laptop and an SSH key.

## 1. CI — Continuous Integration

**WHAT** — Code is automatically built and tested every time it is pushed or
proposed for merge.

**WHY** — "It worked on my machine" is the single most expensive sentence in
software. Tests that only run on one developer's laptop run when that
developer remembers to run them.

**PROBLEM SOLVED** — Finds a broken test in minutes instead of at the next
release.

**ALTERNATIVES** — Jenkins, GitLab CI, CircleCI, Bitbucket Pipelines.

**WHY THIS ONE** — GitHub Actions needs no extra server, no agent to install
and no separate account. The code is already on GitHub, so the workflow file
lives beside the code it checks. For a project of this size the setup cost is
close to zero.

**AT LARGER SCALE** — Jobs split across runners, caching, matrix builds, and
test partitioning to cut wall-clock time.

## 2. CD — Continuous Delivery / Deployment

**WHAT** — After CI passes, the tested artefact is promoted automatically.

**PROBLEM SOLVED** — Shrinks the gap between "finished" and "released". Code
that sits in a branch for a week is code nobody remembers.

**WHY CI alone is not enough** — Passing tests do not mean the image exists in
a registry, or that the server was told to run it. That is a separate chain.

## 3. GitHub Actions

**WHAT** — A workflow is a YAML file in `.github/workflows/` describing events
(triggers) and jobs (steps on a runner).

**KEY CONCEPT — the trigger is the design.** The single most important decision
in this phase was that `docker-publish.yml` listens to `workflow_run` for the
`CI` workflow, not to `push`:

```yaml
on:
  workflow_run:
    workflows: ["CI"]
    branches: [main]
    types: [completed]
```

plus a job guard on the conclusion. That is what turns "CI and deploy run in
parallel" into "deploy cannot happen unless CI was green".

**TRAP WORTH KNOWING** — on a `workflow_run` event, `github.sha` is the
default branch HEAD, which may have moved past what you tested. Always use
`github.event.workflow_run.head_sha`.

## 4. Docker images

**WHAT** — A build of the application plus its dependencies into one artefact.

**PROBLEM SOLVED** — "Works on my machine" becomes "works on the runner",
because the image carries the runtime with it.

**ALTERNATIVES** — tarballs, zipapps, PEX, native binaries, serverless.

**WHY IMAGES** — The artefact that CI tested is byte-for-byte the artefact that
runs in production. There is no second build step that can differ.

## 5. GHCR — GitHub Container Registry

**WHAT** — A registry attached to the GitHub account, at `ghcr.io`.

**PROBLEM SOLVED** — Somewhere for the tested image to live so a server can
fetch it without a human copying files around.

**ALTERNATIVES** — Docker Hub, Amazon ECR, Google Artifact Registry, Azure ACR.

**WHY GHCR** — No extra account, no extra billing, and the auth token is
already available to the workflow via `GITHUB_TOKEN`. For an educational
project that is the smallest possible working answer.

## 6. Immutable image tags

**WHAT** — Every release is tagged with the full commit SHA.

```
ghcr.io/imrohit44/pybank-backend:bf1f96dedcdc5875329480b4096c652c6b3049c5
```

**PROBLEM SOLVED** — `latest` is a moving target. Ask "which code is running?"
six months later and `latest` cannot answer. It can also change underneath you
during a deployment, so two servers can silently run different code.

**WHY IT MATTERS** — It also makes rollback trivial: deploying the previous
release is the *same command* as deploying a new one, just with a different
SHA. There is no separate rollback mechanism to get wrong.

`deploy/deploy.sh` refuses any argument that is not a SHA, so a mutable tag
can never be deployed by accident.

## 7. AWS EC2

**WHAT** — A single virtual machine running Docker.

**PROBLEM SOLVED** — Somewhere the application runs that a real user can
reach over the internet.

**ALTERNATIVES** — Kubernetes, ECS, Heroku, Render, Fly.io, Lambda.

**WHY NOT KUBERNETES** — A control plane that schedules containers across many
machines. PyBank is one educational stack. Kubernetes would add a large
operational surface (etcd, control plane, manifests, ingress controllers) and
teach nothing about CI/CD that Compose does not. It is Phase 17+ at the earliest,
and probably not even then for this project.

**WHY NOT MANAGED DATABASES** — RDS would simplify operations, but it also
splits the data across an AWS boundary and hides exactly the volume, backup
and networking behaviour this phase is meant to make visible.

**SIZING** — Start with an instance that has enough memory for Kafka, Neo4j and
three observability components at once. If the stack is being OOM-killed,
resize upward. Do not pre-optimise; measure.

## 8. Docker Compose in the cloud

**WHAT** — The same `compose.yaml` that runs on a laptop, plus a production
overlay.

**PROBLEM SOLVED** — One declarative description of eleven services instead of
eleven SSH sessions and eleven sets of `docker run` flags.

**KEY IDEA** — Production is an *overlay*, not a fork. Layering
`docker-compose.prod.yml` on top of `compose.yaml` means local and production
run the same services, migrations and health checks. Only the image source, the
port exposure and the secrets differ. A forked production file inevitably
drifts from the development one.

Compose's `!reset` and `!override` tags are what make "remove the published
port entirely" expressible, which the base file alone cannot do.

## 9. Nginx as reverse proxy

**WHAT** — The single process that faces the internet and forwards requests to
the services behind it.

**PROBLEM SOLVED** — Twelve services cannot each bind a public port. One public
port plus internal routing is both simpler and safer.

**ALTERNATIVES** — Traefik, Caddy, HAProxy, a cloud load balancer.

**WHY NGINX** — Ubiquitous, tiny, and its WebSocket and TLS configuration is
well understood. It is also what most interviewers have actually seen.

**WHAT IT MUST GET RIGHT** — WebSocket upgrade needs `proxy_http_version 1.1`
plus `Upgrade` and `Connection` headers, or the Phase 15 realtime channel
silently fails. A reverse proxy that breaks WebSockets is a common and
embarrassing production bug.

## 10. HTTPS and Let's Encrypt

**WHAT** — Traffic between the browser and the server is encrypted, and the
server proves it is who it claims to be.

**WHY IT MATTERS** — Without HTTPS, a JWT is a bearer token: anyone who
intercepts one request can replay it and impersonate that user. It also means
the browser cannot enforce `Secure` cookies, and modern browsers warn on
plain HTTP.

**HOW LET'S ENCRYPT WORKS** — An automated certificate authority issues free
certificates that renew every ~90 days. Validation happens over the ACME
protocol; the common HTTP-01 method requires a public domain pointing at the
host and a reachable port 80. That is why Nginx keeps
`/.well-known/acme-challenge/` on plain HTTP instead of redirecting it.

**WHY CERTIFICATES ARE NEVER COMMITTED** — A private key in git is a permanent
compromise: git history is hard to purge and every clone holds a copy. They
live only in `/etc/letsencrypt` on the host.

**WHY HSTS IS COMMENTED OUT** — `Strict-Transport-Security` tells browsers to
refuse plain HTTP for up to a year. Enabling it before HTTPS genuinely works
locks users out of the site with no easy recovery. Phase 16 leaves it as a
documented, deliberate one-line change after the first successful
certificate.

## 11. Environment variables and secrets

**WHAT** — Configuration is injected at runtime, not baked into the code.

**THE RULE** — A secret never enters the repository, not even "temporarily".
`.env.example` and `.env.production.example` hold placeholders; the real `.env`
is gitignored and lives only on the host.

**HOW PRODUCTION ENFORCS IT** — `docker-compose.prod.yml` uses Compose's
required-variable syntax:

```yaml
JWT_SECRET: ${JWT_SECRET:?JWT_SECRET must be set for production}
```

Compose **refuses to start** if the variable is unset. This is the difference
between documentation ("please set a secret") and enforcement (the deployment
cannot happen without one). A development default that silently reaches
production is how real breaches happen.

**WHAT CI/CD CHANGES** — Secrets come from GitHub Secrets, referenced as
`${{ secrets.NAME }}`. The workflows never echo them, never pass them as build
arguments, and use the automatic `GITHUB_TOKEN` for GHCR instead of a
long-lived personal token. Workflow `permissions:` is reduced to the minimum
each workflow needs.

## 12. Health and readiness

Two different questions, deliberately kept separate since Phase 8:

- **`/health` (liveness)** — is the process running? Failure means restart me.
- **`/ready` (readiness)** — are my dependencies usable? Failure means do not
  send me traffic, but do not restart me.

Conflating them causes real outages. If liveness checked the database, a brief
database blip would restart every container at once, turning a small problem
into a full outage.

`deploy/deploy.sh` waits for **both** before declaring success, so a
deployment that starts but cannot serve traffic is reported as a failure
rather than a success.

## 13. Deployment

**WHAT** — Replacing what runs on the server with a specific released image.

The deployment is deliberately understandable rather than clever: SSH in, pull
the SHA, `compose up -d`, wait for health, smoke test. No blue/green, no
canary, no traffic shifting. A student should be able to read `deploy.sh` and
predict exactly what it will do to the server.

## 14. Rollback

**WHAT** — Going back to the previous known-good release.

**WHY IT IS NEARLY FREE HERE** — Because releases are immutable SHAs, a
rollback is *the same command* as a deployment:

```bash
./deploy/deploy.sh <previous-commit-sha>
```

`deploy/rollback.sh` reads `deploy/RELEASE_HISTORY` and re-invokes
`deploy.sh`, so there is no second code path that could be wrong. The append-
only history also means the sequence of releases stays auditable.

The limitation worth stating honestly: a rollback restores the **code**, not
the data. If release B ran a migration that release A cannot read, rolling
back the image is not enough — which is exactly why migrations stay additive.

## 15. Local vs cloud

| | Local | Cloud |
|---|---|---|
| Started by | `docker compose up` | `deploy/deploy.sh <sha>` |
| Images | built on the host | pulled from GHCR |
| Ports | several published for debugging | only 80/443 public |
| Secrets | `.env` with dev defaults | `.env` that refuses to start if incomplete |
| CORS | permissive, cross-origin | single origin, no wildcard |
| Exposure | databases reachable locally | databases unreachable from the internet |

The most important property: **cloud deployment is additive.** A developer can
still run the whole project on a laptop with one command, and no AWS account
is needed to develop. Cloud is an additional path, not a replacement.

## 16. What this phase deliberately did not do

Kubernetes, ECS, Terraform, Helm, service mesh, autoscaling, canary or
blue/green deployment, managed databases, multi-region, and a secrets manager
are all real tools with real uses. None of them are needed to learn what this
phase teaches, and adding them would mostly add configuration to maintain.
They belong to a later phase, if ever.
