---
priority: medium
risk_code_health: low
risk_goal_achievement: low
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [framework, documentation]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1657
followup_kind: upstream_defect
implemented_with: claudecode/opus5
created_at: 2026-09-07 10:58
updated_at: 2026-09-07 13:23
---

## Origin

Spawned from t1717 during Step 8b review.

## Upstream defect

- `.claude/skills/aitask-audit-wrappers/SKILL.md:15,181` — points readers at
  CLAUDE.md "Adding a New Helper Script"; that section now lives in
  `aidocs/framework/aitasks_extension_points.md`, and the same stale pointer is
  replicated across the rendered Codex/OpenCode wrapper trees.

## Diagnostic context

t1717 fixed a stale touchpoint count in
`aidocs/framework/aitasks_extension_points.md` and, while sweeping every surface
that enumerates the helper-permission touchpoints, found the audit-wrappers
skill still naming CLAUDE.md as the defining document for them. CLAUDE.md now
only *points* at `aidocs/framework/aitasks_extension_points.md`; the "Adding a
new helper script" section — the table, the entry shapes, and the count — lives
there. A reader following the skill's reference lands on a file that no longer
contains what it promises.

The identical pointer in `aitask_audit_wrappers.sh::usage()` was corrected in
t1717, because that line was already being edited for the new `touchpoints`
subcommand. The skill copies were left alone: skill edits go to the Claude Code
source of truth first and then fan out to `.agents/` and `.opencode/` via the
rerender driver, which is its own change with its own goldens — out of scope for
a one-word count fix.

Two known sites in the source skill (lines 15 and 181). Both are inside
non-templated prose, so the rendered per-profile/per-agent variants under
`.claude/skills/`, `.agents/skills/` and `.opencode/skills/` carry the same text
and must be refreshed, not hand-edited.

## Suggested fix

Correct both references in `.claude/skills/aitask-audit-wrappers/SKILL.md` to
name `aidocs/framework/aitasks_extension_points.md` "Adding a new helper
script", then fan the change out with
`./.aitask-scripts/aitask_skill_rerender.sh <profile>` for every profile and
regenerate any affected goldens in the same commit. Run
`./.aitask-scripts/aitask_skill_verify.sh` before committing. Re-grep for
`CLAUDE.md "Adding a New Helper Script"` afterwards to confirm no wrapper tree
still carries it.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-09-07T10:20:39Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-09-07T10:38:03Z status=pass attempt=1 type=human
