---
priority: medium
effort: medium
depends: []
issue_type: refactor
status: Ready
labels: [brainstorm]
created_at: 2026-05-20 12:10
updated_at: 2026-05-21 16:47
boardidx: 60
---

Single-source the implementation-plan content contract shared by the brainstorm
detailer template and the task-workflow `planning.md` procedure.

## Background

Two pipelines author implementation plans and both feed `aiplans/`:

- `.claude/skills/task-workflow/planning.md` — a code agent's plan, written
  directly to `aiplans/p<task>.md`.
- `.aitask-scripts/brainstorm/templates/detailer.md` — a brainstorm detailer
  agent's plan, written to `br_plans/<node>_plan.md`; `finalize_session()` in
  `brainstorm_session.py` then copies HEAD's `plan_file` to
  `aiplans/p<task>_<node>.md`.

So a code agent later picking that task (planning.md Step 6.0 "Check for
Existing Plan") can consume a brainstorm-detailer-authored plan. The two share
an "implementation-plan content contract" — specific file paths, exact per-file
changes, code snippets for non-trivial changes, dependency-ordered steps (no
forward refs), prerequisites, testing strategy, verification checklist — that
is currently duplicated across `planning.md`, `detailer.md`, and partly
`aidocs/planning_conventions.md`. Improving one does not propagate to the
other; they will drift.

Surfaced during t741 (`apply_detailer_output`). t741's delimiter change to
`detailer.md` is purely structural and introduced no new drift; this
de-duplication is the separate cross-cutting refactor.

## What to implement

1. Extract the shared plan-content contract into one canonical fragment,
   `.aitask-scripts/brainstorm/templates/_plan_contract.md`.
2. Have `detailer.md` pull it via `<!-- include: _plan_contract.md -->` —
   resolved by `resolve_template_includes()` in
   `.aitask-scripts/lib/agentcrew_utils.sh` (base dir = `templates/`).
3. Embed the same canonical content into `planning.md` at skill-render time
   (the task-workflow skill is rendered per-profile). Decide and document the
   bridge between the two include mechanisms (bash `<!-- include -->` vs. the
   skill Jinja renderer).
4. Regenerate the task-workflow skill goldens
   (`./.aitask-scripts/aitask_skill_verify.sh` + golden regeneration per
   `aidocs/skill_authoring_conventions.md`).
5. Port the change to the Codex CLI / Gemini CLI / OpenCode skill trees.

## References

- t741 plan: `aiplans/archived/p741_brainstorm_apply_detailer_output.md`
  (or `aiplans/p741_*` before archival).
- `aidocs/planning_conventions.md` — opens with a "promote these rules into
  planning.md" note; this refactor is the same class of consolidation.
- CLAUDE.md "Working on Skills / Custom Commands" and "Documentation Writing".
