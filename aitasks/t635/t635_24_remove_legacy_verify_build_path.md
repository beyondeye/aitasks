---
priority: medium
effort: medium
depends: [t635_14]
issue_type: refactor
status: Ready
labels: [gates, task_workflow]
anchor: 635
created_at: 2026-06-25 10:41
updated_at: 2026-06-25 10:41
---

## Context

Once gate declaration becomes the universal verify path (t635_14 — profiles
declare gates; tasks carry `gates:`), the **legacy inline `verify_build`
procedure** kept as a transitional fallback by t635_12 becomes dead weight, and
the project-side `verify_build` *configuration surface* should be folded into
gate configuration. This task removes the fallback and migrates its config UI.

t635_12 wired task-workflow Step 9 to dispatch `ait gates run <task-id>` and only
fall back to the inline `verify_build` block when the orchestrator reports
`No gates declared; nothing to do.`. That fallback exists solely for tasks that
have not opted into gates — which is every task until t635_14 lands.

## Depends

- **t635_14** (profile→gate-declaration unification) — MUST land first; the
  fallback cannot be removed until every task declares its gates. (Set in
  frontmatter `depends`.)
- References **t635_12** (introduced the gate verify path + the build/tests/lint
  verifiers) and **t635_18** (website docs sweep — coordinate the doc updates).

## Scope

1. **Remove the legacy inline `verify_build` procedure** from task-workflow
   Step 9 in `.claude/skills/task-workflow/SKILL.md` (the `No gates declared`
   fallback branch + its `{% if profile.record_gates %}` manual `build_verified`
   recording), leaving `ait gates run` as the single verify path. Re-render the
   per-profile variants and regenerate the goldens under
   `tests/golden/procs/task-workflow/` in the same commit; run
   `./.aitask-scripts/aitask_skill_verify.sh`.

2. **Replace the settings-TUI `verify_build` configuration** with new ad-hoc
   **gate-configuration UIs** in the settings TUI: configure which gates a
   project/profile declares and per-gate settings (verifier, retries, timeout)
   instead of a standalone `verify_build` field.
   - **First locate the surface:** find where `verify_build` (and
     `test_command`/`lint_command`) are configured today — the settings TUI
     and/or the `project_config.yaml` editor. (See
     `aidocs/framework/tui_conventions.md` for TUI patterns.)
   - Redesign that surface as gate config (the registry is
     `aitasks/metadata/gates.yaml`; profile gate declaration lands in t635_14).

3. **Update documentation** to the post-removal current state:
   - The Project Configuration table in `.claude/skills/task-workflow/SKILL.md`
     (`verify_build` row — drop/redefine now that the inline path is gone).
   - Any verify-build prose; the gates configuration reference (coordinate with
     t635_18's website sweep — current-state-only rule).

## Key files

- `.claude/skills/task-workflow/SKILL.md` (Step 9 verify region + Project
  Configuration table; Jinja source → re-render + goldens)
- Settings TUI + `project_config` editor (locate during implementation)
- `aitasks/metadata/gates.yaml` (registry; reference)
- `tests/golden/procs/task-workflow/` (regenerate)

## Verification

- `bash tests/test_skill_render_task_workflow.sh` (goldens updated),
  `./.aitask-scripts/aitask_skill_verify.sh` passes.
- A task with no `gates:` no longer runs an inline `verify_build` — it goes
  through `ait gates run` (which skips when no build gate is declared).
- Settings TUI exposes gate configuration; no orphaned `verify_build`-only field.

## Reverse links

- t635_12 plan: `aiplans/archived/p635/p635_12_build_test_machine_gates.md`
  (this task is the convergence follow-up it scheduled).
