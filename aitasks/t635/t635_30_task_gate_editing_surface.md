---
priority: medium
effort: medium
depends: [t635_11]
issue_type: feature
status: Implementing
labels: [gates]
assigned_to: dario-e@beyond-eye.com
anchor: 635
created_at: 2026-07-01 11:03
updated_at: 2026-07-20 10:31
---

## Context

There is **no interactive surface to edit which gates a task declares** (its
`gates:` frontmatter list). Today gate declaration is only possible via
`ait update --batch --gates <csv> <id>` or hand-editing the task file (the
former Step-7 `default_gates` backfill was retired by t635_33 — a picked task
now gets a derived `active_gates` tuple at Step 4 while its raw `gates:` stays
declared intent; an editing surface here changes that declared intent, and the
next pick re-materializes the enforced set from it). The board
*displays* gate-run status and *records* human gate sign-offs (t635_9) but cannot
add/remove a task's gates; the settings TUI edits only the PROFILE-side keys (`default_gates` /
`rendered_gates`; registry-driven picker tracked as t635_37), not a task's own
`gates:`.
`aitask_gate.sh:11` explicitly flags the "user-facing gate surface" as deferred
("Phase 1 has no human consumer"). This task builds that surface.

General to ALL gates (command, human, and procedure-backed like `docs_updated`).

## Scope

1. **Board (primary surface):** on the focused task, view its declared `gates:`
   and add/remove gates from the registry (`aitasks/metadata/gates.yaml`). Reuse
   the existing gate display in the In-Flight view (t635_9) and the board's
   context-scoped single-key action pattern. Persist via
   `aitask_update.sh --batch --gates` (path-scoped commit) — do not hand-write the
   frontmatter. Respect an explicit `gates: []` opt-out (see `has-gates-field`).
2. **User-facing `ait gate` CLI:** add human commands to declare/undeclare a
   task's gates (e.g. `ait gate add <task> <gate>` / `ait gate remove <task> <gate>`),
   the deferred surface `aitask_gate.sh:11` anticipates. Validate gate names against
   the registry; refuse unknown gates. Whitelist any new helper.
3. Tests + docs (coordinate with t635_18 website sweep, current-state-only).

## Delineation / coordination (checked against existing tasks)

- **t635_24** owns the **settings-TUI** gate configuration at the **profile /
  registry** level (which gates a *profile* declares via `default_gates`, and
  per-gate registry settings: verifier/retries/timeout) — as part of removing the
  legacy `verify_build` config surface. THIS task owns **per-task** `gates:`
  editing (board + `ait gate` CLI). If a per-task gate editor also belongs in the
  settings TUI, coordinate with t635_24 so the two surfaces compose rather than
  collide. (Reverse pointer added to t635_24.)
- Extracted from **t635_29** (procedure_gate_generalization) — the "interactive
  task-gate configuration surface" bullet moves here. t635_29 was later narrowed to
  its ripe core (async/headless dispatch + agent-aware resolution); **per-gate
  agent/model selection** (which composes with this task's settings-TUI surface) is
  now **t635_31** (`depends: [t635_24, t635_30]`), and external-gate resolution is a
  deferred doc-only extension point.
- Builds on **t635_9** (board In-Flight gate view) and the **t635_11** substrate.

## Depends
- t635_11 (gate substrate / orchestrator + registry).
