---
priority: high
effort: high
depends: []
issue_type: feature
status: Ready
labels: [gates]
created_at: 2026-06-10 18:52
updated_at: 2026-06-10 18:52
---

## Context

Phase 1 of the gates integration roadmap
(`aidocs/gates/integration-roadmap.md`, decision D1: ledger-first). The
durable-state layer of the gate framework lands first, with no behavior
change anywhere else.

## Scope

- Marker-first Gate Runs block format as specified in
  `aidocs/gates/aitask-gate-framework.md` §"Gate run marker format"
  (append-only blockquotes, `> **<icon> gate:<name>**` marker line,
  back-to-front derivation of current state).
- `ait gate append` / `ait gates status` / `ait gates list` command surface
  (bash + awk primary path; Python stdlib fallback per the framework doc
  §Tooling). Append atomicity via the existing task-level lock.
- Register the `gates:` frontmatter field per
  `aidocs/framework/aitasks_extension_points.md`.
- Minimal `aitasks/metadata/gates.yaml` registry: gate `name`, `type`
  (machine|human), `description` only. Verifier/retries/unlocks schema
  comes with the orchestrator (t635_11).
- Sidecar log directory convention `.aitask-gates/<task-id>/` +
  git-ignore default.

## Out of scope

Orchestrator, verifier skills, any task-workflow change (t635_2 records
checkpoints; t635_11 adds the orchestrator).

## References

- `aidocs/gates/aitask-gate-framework.md` (data model, marker format, tooling)
- `aidocs/gates/integration-roadmap.md` (Phase 1)
