---
priority: medium
effort: high
depends: [t635_19]
issue_type: feature
status: Ready
labels: [gates]
anchor: 635
created_at: 2026-07-01 10:46
updated_at: 2026-07-01 10:46
---

## Context

t635_19 shipped `docs_updated` as the FIRST concrete procedure-backed gate
(`kind: procedure`) with a MINIMAL attended-dispatch seam. This task generalizes
procedure-backed / skill-backed gates into a full framework capability (the
original gate design's "gates as user-customizable skills").

## Scope
- **External / custom skill resolution** for procedure gates (plugins, project-
  local gate skills), richer registry schema for `kind` (procedure/external/plugin).
- **Async / headless behavior** for procedure gates; complete dispatch semantics
  across autonomous lanes (`aitask-pickrem`/`aitask-pickweb`) + `aitask-resume`.
- **Agent-aware dispatch resolution** — the task-workflow Step-8/Step-9 seam must
  resolve a gate skill in the RUNNING agent's tree (today it points at the Claude
  tree; procedure gates are Claude-only until the wrappers land). Coordinate with
  t635_23 (which ports the wrapper FILES for Codex/OpenCode).
- **Per-gate code-agent + model selection** — configure which agent/model runs a
  procedure gate's skill, with a **settings-TUI** surface. General to all proper gates.
- **Interactive task-gate configuration surface** — today a task's `gates:` field
  is only settable via `ait update --batch --gates`, hand-edit, or profile
  `default_gates` backfill; the board shows gate status + records human sign-offs
  but cannot edit declared gates, and the settings TUI only edits profile
  `default_gates`. Add a board/settings surface to view/add/remove a task's gates
  (general to all gates). `aitask_gate.sh:11` flags this as the deferred user-facing
  gate surface.
- Remote / comment-signal integration for procedure gates.

## Coordination
Depends on t635_19 (first concrete procedure gate). Coordinate the per-agent
wrapper half with t635_23.
