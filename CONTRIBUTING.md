# Contributing to Project Synthesis 17

Thank you for your interest in Project Synthesis 17.

Project Synthesis 17 is a learning-driven engineering project that explores
how a simple banking system can evolve into a distributed, observable and
intelligent system through 17 engineering stages.

Contributions are welcome, particularly those that improve correctness,
clarity, security, testing, documentation, or the learning value of the
project.

---

## Before Contributing

Please read the following first:

- [README.md](README.md) — project overview and setup
- [SECURITY.md](SECURITY.md) — security vulnerability reporting
- [Project Wiki](../../wiki) — architecture and engineering decisions

Please avoid submitting changes that unnecessarily increase the project's
scope or introduce technology without a concrete engineering reason.

---

## What Contributions Are Welcome?

Examples include:

- Bug fixes
- Security improvements
- Test coverage improvements
- Performance improvements
- Documentation improvements
- Architecture corrections
- Developer-experience improvements
- Dependency updates
- Improvements to the Synthesis Explorer
- Corrections to technical explanations
- Improvements that make the project easier to understand or reproduce

For larger architectural changes, please open an issue first so the proposed
direction can be discussed before implementation.

---

## Project Principles

Contributions should generally follow these principles:

### 1. Keep the system understandable

Prefer clear and maintainable solutions over unnecessary abstraction or
complexity.

### 2. Introduce technology for a reason

A new framework, service, dependency, or infrastructure component should solve
a concrete problem or requirement.

### 3. Preserve architectural boundaries

Keep domain logic, application logic, infrastructure, and presentation
concerns appropriately separated.

### 4. Security matters

Do not introduce insecure defaults, hardcoded credentials, unsafe data
handling, or unnecessary privilege.

### 5. Tests are part of the change

Changes to behavior should include appropriate tests.

### 6. Document meaningful architectural changes

If a change affects architecture, system behavior, or an engineering decision,
update the relevant documentation.

---

## Development Workflow

### 1. Fork the repository

Create your own fork of the repository and clone it locally.

```bash
git clone <your-fork-url>
cd PROJECT_SYNTHESIS_17
