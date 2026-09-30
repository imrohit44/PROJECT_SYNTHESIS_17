# Repository Release

Recommended GitHub repository metadata for Project Synthesis 17.

## Description

A learning-driven banking platform that evolves from a simple OOP core into a
distributed, observable and intelligent system through 17 engineering stages.

## Topics

python, fastapi, react, typescript, postgresql, redis, kafka,
event-driven-architecture, microservices, machine-learning, neo4j, llm,
docker, system-design, software-engineering

## License and security

- License: MIT (`LICENSE`)
- Vulnerability reporting: `SECURITY.md` (GitHub private vulnerability
  reporting; do not disclose publicly before review)

## Identity notes

- Official project name: Project Synthesis 17
- Stages: 17 total, Phase 0 through Phase 16 (Phase 17 files are hardening
  audits, not an implementation phase)
- The repository is an engineering-learning and system-design project, not a
  real banking product.

## Manual GitHub settings (Settings → Security)

Enable manually; none of these can be verified from the local tree:

- Security policy
- Security advisories, including private vulnerability reporting
- Dependabot alerts (configuration is checked in at
  `.github/dependabot.yml`; alerts still require the repo setting)
- Code scanning (workflow checked in at `.github/workflows/codeql.yml`;
  findings require the repo setting)
- Secret scanning and push protection
