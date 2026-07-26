---
priority: medium
effort: medium
depends: [t635_14]
issue_type: refactor
status: Ready
labels: [gates, task_workflow]
anchor: 635
created_at: 2026-06-25 10:41
updated_at: 2026-07-26 00:00
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
   - **Scope boundary (t635_30 / t635_29):** this task's settings-TUI gate config
     is at the **profile / registry** level (which gates a *profile* declares via
     `default_gates`, and per-gate registry settings). Editing an individual
     **task's** `gates:` interactively (board + `ait gate` CLI) is **t635_30**
     (task_gate_editing_surface); **per-gate code-agent/model selection** in the
     settings TUI is **t635_31** (per_gate_agent_model_selection, split out of
     t635_29). Coordinate so the three settings-TUI gate surfaces compose rather
     than duplicate.

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

## Premise refresh (2026-07-26 — t635_33 active-gates model)

This task was last updated 2026-06-29; **t635_33 landed 2026-07-19** and
reshaped the profile side that Scope item 2 targets. Verified against live
source:

- **The profile side is now TWO keys, not one.** Scope item 2 says the settings
  surface should configure "which gates a *profile* declares via
  `default_gates`". Since t635_33 a profile also has `rendered_gates` — the
  render-time ceiling — with **presence-sensitive** semantics:
  `gate_ledger._read_profile_rendered_gates` uses `rendered_gates` whenever the
  KEY exists (including an explicit `[]`, the render-nothing override) and only
  otherwise falls back to `default_gates`. There are three distinct states to
  represent, not a single list. Live examples: `fast.yaml` sets `default_gates`
  with no `rendered_gates`; `remote.yaml` sets `rendered_gates: []` with no
  `default_gates`; `default.yaml` sets neither.
- **Scope item 2 is substantively superseded by t635_37, not merely adjacent.**
  **t635_37** (`settings_registry_gate_picker`, authored 2026-07-19 — the same
  day t635_33 landed) owns exactly this surface: a registry-driven picker for
  `default_gates` / `rendered_gates` that preserves the three presence states,
  flags unknown names, and shows the effective render/enforce interplay. Note
  t635_37 references t635_30 but **not** this task, and this task predates it —
  neither cross-references the other.
  **Recommended resolution at plan time:** cede profile gate-*list* editing to
  t635_37 and narrow this task's item 2 to **registry-level per-gate settings**
  (verifier, retries, timeout) plus removal of the orphaned `verify_build`
  field. Confirm with whoever plans t635_37 rather than building both.
- **Some of the surface already exists.** `.aitask-scripts/lib/profile_editor.py`
  already carries a "Gates" `PROFILE_FIELD_GROUPS` entry with `record_gates`,
  `default_gates` and `rendered_gates` (edited today as free comma-separated
  text — the deficiency t635_37 exists to fix). Item 2 is an *improvement* to a
  live surface, not a greenfield build.
- **Item 1 (the removal) is unaffected** by any of the above and remains the
  unambiguous core of this task.

## Coordination (from t635_25)

t635_14 (the `depends` blocker) has **landed** (2026-06-29) — profiles now declare
gates via `default_gates`, so this task is unblocked.

**t635_25 (leaner gate check invocation)** scopes the extraction of the Step-9
gate-RUN glue (the `ait gates run` dispatch + status-handling block) into a
procedure file to **this** task, because both rewrite the same Step-9 region: this
task removes the legacy inline `verify_build` fallback there, and the natural
follow-through is to lift the remaining inline dispatch into a `gate-run` procedure
(one-line pointer from Step 9). Do them together to avoid double-editing /
re-rendering Step 9. The complementary call-shape work (decision/action verbs,
self-gating procedures in planning + Step 7) lives in t635_25.

## Reverse links

- t635_12 plan: `aiplans/archived/p635/p635_12_build_test_machine_gates.md`
  (this task is the convergence follow-up it scheduled).
- t635_25 (`aitasks/t635/t635_25_leaner_gate_check_invocation.md`) — gate-run
  dispatch extraction coordinates here; call-shape optimization there.
