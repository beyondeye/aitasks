---
Task: t928_create_pickn_workflown_hardening_sandbox.md
Worktree: current
Branch: current
Base branch: current
---

# Implementation Plan

Create an experimental workflow-hardening sandbox without modifying production
`aitask-pick` or `task-workflow` behavior.

## Summary

- Duplicate `aitask-pick` into `aitask-pickn` across Claude, Codex, OpenCode
  command, and OpenCode skill surfaces.
- Duplicate `task-workflow` into `task-workflown` with all referenced procedure
  files so the experimental workflow can run independently.
- Wire `aitask-pickn` to render and dispatch into `task-workflown`.
- Add fail-closed plan-risk, pre-implementation, archive-time, and satisfaction
  feedback gates only inside the experimental copies.
- Add focused tests that prove the experimental wiring and gates exist while
  production skill definitions remain unchanged.

## Implementation Steps

1. Copy the current profile-aware `aitask-pick` source/stub surfaces into
   `aitask-pickn`.
2. Copy the full `task-workflow` source procedure directory into
   `task-workflown`.
3. Rewrite the experimental copies so all sandbox re-entry paths use
   `/aitask-pickn` and all shared workflow references use `task-workflown`.
4. Add explicit experimental staging markers to the new stubs and workflow.
5. Add risk-section, pre-implementation, risk-frontmatter, and archive-time
   gates to `task-workflown`.
6. Extend the sandbox satisfaction feedback procedure with a return contract
   (`satisfaction_feedback_status` and `satisfaction_skip_reason`) and gate the
   final response on that contract.
7. Document the staging-only nature of the experiment in `aidocs/`.
8. Add render tests for `aitask-pickn` and `task-workflown`.

## Verification

- `bash tests/test_skill_render_aitask_pickn.sh`
- `bash tests/test_skill_render_task_workflown.sh`
- `bash tests/test_skill_render_aitask_pick.sh`
- `bash tests/test_skill_render_task_workflow.sh`
- `bash tests/test_skill_verify.sh`

## Risk

### Code-health risk: medium
- The workflow copy is intentionally large and can drift from production over
  time. Mitigation: tests verify the copied file set, production files remain
  untouched, and the sandbox is documented as temporary staging. · severity:
  medium · -> mitigation: documented staging and render coverage

### Goal-achievement risk: low
- The task is documentation/procedure-heavy rather than runtime-code-heavy, so
  the main delivery risk is missing a production reference inside the sandbox.
  Mitigation: render tests assert `pickn` dispatches to `task-workflown`, sandbox
  re-entry paths use `/aitask-pickn`, and production workflow files do not carry
  the experimental gates. · severity: low · -> mitigation: targeted reference
  tests

## Final Implementation Notes

- **Actual work done:** Added the `aitask-pickn` staging skill, full
  `task-workflown` staging workflow copy, stricter fail-closed risk and
  feedback gates, staging documentation, and targeted regression tests.
- **Deviations from plan:** The `default_profiles.pickn: fast` entry landed in
  the separate `.aitask-data` worktree because `aitasks/` is a symlink to task
  data, not a tracked path in the main code worktree.
- **Issues encountered:** The sandbox initially blocked writes under
  `.agents/skills`; escalated permissions were used only for the new Codex
  `aitask-pickn` stub and tests that intentionally create/generated `.agents`
  skill files.
- **Key decisions:** Production `aitask-pick` and `task-workflow` source files
  were left unchanged; new tests assert the experimental gate strings are absent
  from production workflow files.
- **Upstream defects identified:** None
