---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Ready
labels: [ait_setup, installation, remote]
created_at: 2026-11-17 12:52
updated_at: 2026-11-17 12:52
---

Give `ait setup` a fully unattended mode, so a fresh clone (cloud session, CI, container) can bring an install to a working state with no prompts.

## Why

Even when all framework files are committed in the repo (an "in-repo install"), a fresh clone is not usable until `ait setup` has run on that machine: the `ait-testmap` engine, the per-user Python venv, CLI tools and the global shim all live outside the project directory. Cloud sessions (`aitask-pickweb`, `aitask-pickrem`) start from exactly such a clone. Today `--yes` is accepted only together with `--hooks-only`, and several setup steps prompt (PyPy, relations activation, code agents, review guides, git TUI, ...), so there is no way to run setup on session start.

## Requirements

- One flag (or `--yes` widened) that makes every prompt take a documented default and never blocks on stdin.
- Per-machine provisioning only by default: venv + Python deps, engine binary, shim. It must not make project-level decisions on the user's behalf (creating branches, activating optional features, committing config) unless those are already decided in committed config. Audit each step in `main()` of `aitask_setup.sh` and classify it as machine-level (run), project-level already decided (verify), or project-level undecided (skip and report).
- Degrade cleanly without network or without a supported engine platform: report what is missing, exit with a distinct status, do not half-install.
- Safe to run repeatedly and fast when nothing is missing.
- Emit parseable result lines so a session-start hook can decide whether to continue.
- Must never convert or restructure a framework source checkout (this repo).

## Notes

- Related: `ait doctor` (read-only check) is the natural pre/post condition for this mode; share predicates, do not duplicate them.
- Document the cloud-session recipe (what to put in a session-start hook / setup script) on the website.
- Tests must run setup's `main()` only under a scratch `HOME` with `AITASKS_HOME` unset or scratch.
