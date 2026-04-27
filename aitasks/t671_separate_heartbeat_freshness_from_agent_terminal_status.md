---
priority: medium
effort: high
depends: []
issue_type: refactor
status: Implementing
labels: [ait_brainstorm, agentcrew]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-04-27 12:59
updated_at: 2026-04-27 13:02
---

The agent-crew runner currently flips a still-running agent's
`<agent>_status.yaml` to `Error` when its heartbeat hasn't arrived in
time. This conflates two distinct concepts — agent lifecycle (Running /
Completed / Aborted / Error) and heartbeat freshness — and corrupts
what `status` is supposed to mean: an Error status no longer reliably
indicates that the agent itself failed.

This is the root cause that forced t653_1 (Brainstorm TUI self-heal on
session reopen) to soften `_poll_initializer`'s Error/Aborted branch
into a 30 s slow-watcher fallback that re-attempts apply purely from
file-content signals — distrusting status. t670 then had to harden
`n000_needs_apply` to gate on output-file delimiters rather than
status, because adding a status-Completed gate would regress that
self-heal path. Every consumer of `_status.yaml` carries a similar
trust deficit.

## Proposed redesign

Keep `status` reflecting the agent's own self-reported lifecycle:
`Running` / `Completed` / `Error` / `Aborted`. Surface heartbeat
freshness as a separate field, e.g.:

```yaml
status: Running                 # agent's own state
last_heartbeat_at: 2026-04-27 15:42
heartbeat_stale: false          # derived; or compute on read
```

Once `status` is trustworthy:
- `_poll_initializer`'s Error/Aborted branch can stop installing the
  30 s slow-watcher fallback (or keep it as belt-and-suspenders).
- `n000_needs_apply` could simplify to a status-based gate.
- Other consumers that currently second-guess `status` can simplify.

## Required deliverables

1. **Audit** every consumer of `_status.yaml` (grep for `status_path`,
   `_status.yaml`, `read_yaml(... + "_status.yaml")`). Brainstorm TUI
   `_poll_initializer` is one; there are likely more in the agent-crew
   runner and other TUIs.
2. **Schema change** to `_status.yaml` — add `last_heartbeat_at` (and
   optionally `heartbeat_stale`); remove the heartbeat-driven Error
   write-path.
3. **Migration** for existing in-flight `_status.yaml` files (most
   are short-lived inside `.aitask-crews/`, but document the upgrade
   path).
4. **Update consumers** to read the new field where they currently
   second-guess `status`.
5. **Tests** covering: agent ends genuinely with Error → status
   reflects it; agent stops sending heartbeats but eventually
   completes → status correctly transitions through fresh ↔ stale
   without ever flipping to Error.

## References

- `aiplans/archived/p653/p653_1_brainstorm_tui_self_heal_apply.md` —
  motivation behind the slow-watcher fallback and the status-distrust
  pattern this redesign should remove.
- `aitasks/archived/t670*` (this task is the planning conversation
  where the redesign was surfaced) — t670's `n000_needs_apply` fix
  documents why it had to gate on file content rather than status.

## Out of scope

- The placeholder-on-mount banner symptom — already fixed by t670.
- TUI rendering of heartbeat staleness (could be a small follow-up
  child once the schema lands).
