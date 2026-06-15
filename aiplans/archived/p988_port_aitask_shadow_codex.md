---
Task: t988_port_aitask_shadow_codex.md
Worktree: .
Branch: main
Base branch: main
---

# Plan: t988 - Port `aitask-shadow` to Codex

## Context

`t986_4` added the canonical Claude Code `/aitask-shadow` skill under
`.claude/skills/aitask-shadow/`. The `shadow` codeagent operation already builds
a Codex `$aitask-shadow <followed_pane_id> [<source_task_id>]` prompt and keeps
the operation in Codex default mode; the missing piece is the Codex skill
surface under `.agents/skills/`.

## Implementation steps

1. Add `.agents/skills/aitask-shadow/SKILL.md` as a static Codex wrapper.
   Keep `.claude/skills/aitask-shadow/SKILL.md` as the source of truth and point
   Codex to `.agents/skills/codex_tool_mapping.md` for tool-name adaptations.
2. Do not copy the Claude sub-procedure files into `.agents/skills/`. The
   wrapper should read the authoritative Claude skill, whose relative
   `plan-explain.md`, `plan-challenge.md`, `plan-socratic.md`, and
   `plan-assumptions.md` references resolve in that source directory.
3. Keep launcher and plan-policy code unchanged unless verification shows a
   defect. `aitask_codeagent.sh` already emits the Codex `$aitask-shadow`
   prompt, and `codex_plan_policy.sh` already treats `shadow` as a relaxed
   default-mode skill.
4. Add focused dry-run coverage to `tests/test_skillrun_codex_planmode.sh` so
   `ait skillrun shadow --agent-string codex/... --dry-run` is verified to
   bypass the plan-mode helper and forward the pane/task arguments.

## Verification

- `./.aitask-scripts/aitask_skill_verify.sh`
- `bash tests/test_shadow_spawn_config.sh`
- `bash tests/test_skillrun_codex_planmode.sh`
- `bash tests/test_shadow_capture.sh`
- `bash tests/test_shadow_context.sh`

## Step 9 (Post-Implementation)

Standard cleanup, archival, plan final notes, and task closure per
`task-workflow` Step 9.

## Risk

### Code-health risk: low
- The implementation adds one static wrapper and one dry-run assertion using
  existing patterns. No load-bearing launcher code changes are planned.
  severity: low; mitigation: None

### Goal-achievement risk: low
- Automated tests can verify the Codex prompt and helper resolution, but a live
  Codex UI invocation remains manual-verification territory.
  severity: low; mitigation: None

## Post-Review Changes

### Change Request 1 (2026-06-15 10:14)
- **Requested by user:** Create a test cross-repo task with an xdep from
  `aitasks_mobile` so the result can be visually inspected.
- **Changes made:** Created `aitasks/t993_visual_check_cross_repo_xdep.md` with
  `issue_type: test`, `xdeprepo: aitasks_mobile`, and `xdeps: [15]`
  (`aitasks_mobile#15`).
- **Files affected:** `aitasks/t993_visual_check_cross_repo_xdep.md`.

## Final Implementation Notes

- **Actual work done:** Added the Codex `aitask-shadow` skill wrapper under
  `.agents/skills/`, preserving `.claude/skills/aitask-shadow/` as the source of
  truth. Added Codex `skillrun shadow` dry-run coverage and verified the existing
  shadow launch, capture, and context helpers. Created visual-check task `t993`
  for the requested cross-repo xdep inspection.
- **Deviations from plan:** None.
- **Issues encountered:** The sandbox initially blocked creating the new
  `.agents/skills/aitask-shadow/` directory; after elevated directory creation,
  normal patching succeeded.
- **Key decisions:** Used the established static-wrapper pattern instead of
  duplicating the Claude skill closure into `.agents/skills/`.
- **Upstream defects identified:** None.
