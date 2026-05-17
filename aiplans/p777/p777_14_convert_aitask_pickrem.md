---
Task: t777_14_convert_aitask_pickrem.md
Parent Task: aitasks/t777_modular_pick_skill.md
Sibling Tasks: aitasks/t777/t777_*_*.md
Parent Plan: aiplans/p777_modular_pick_skill.md
Base branch: main
---

# Plan: t777_14 — Convert `aitask-pickrem` across all 4 agents (LARGEST per-skill)

## Scope

Largest per-skill conversion. Heavy consumer of remote-only profile keys: `force_unlock_stale`, `done_task_action`, `orphan_parent_action`, `complexity_action`, `review_action`, `issue_action`, `abort_plan_action`, `abort_revert_status`. Likely all are enums needing multi-branch `{% if %}/{% elif %}`.

## Step Order

1. Audit `aitask-pickrem/SKILL.md` for all profile-key references. Build a per-key value table from `aitasks/metadata/profiles/remote.yaml`.
2. Author `.claude/skills/aitask-pickrem/SKILL.md.j2` — convert every block; use enum-style multi-branch where applicable.
3. Replace `<each-agent>/skills/aitask-pickrem/SKILL.md` with stubs.
4. Render with `remote` profile and confirm the rendered output contains ZERO `AskUserQuestion` instructions (the whole point of remote mode is non-interactive).
5. Render + verify across all 4 agents.

## Critical Files

- `.claude/skills/aitask-pickrem/SKILL.md.j2` (new — largest of the per-skill .j2 files)
- 4 × `<agent>/skills/aitask-pickrem/SKILL.md` (replace with stubs)

## Pitfalls

- **Remote-only keys** — these keys don't exist in `default.yaml`/`fast.yaml`. Renderer's strict-undefined will fail on `default` profile renders of pickrem. Mitigation: either supply sensible fallbacks via `{{ profile.X | default("Y") }}` (verify minijinja supports the `default` filter — it does in minijinja 2.x), or extend `default.yaml` to include null values for the remote-only keys with safe fallback behavior in the template.
- **Confirm no AskUserQuestion in `remote` rendered output** — this is the verification that proves the redesign goal for headless mode.

## Verification

`ait skill verify` passes; render for `remote` profile contains zero `AskUserQuestion`; stub-dispatch end-to-end.
