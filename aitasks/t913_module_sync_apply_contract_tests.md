---
priority: medium
effort: medium
depends: []
issue_type: test
status: Implementing
labels: [ait_brainstorm, brainstom_modules]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-06-02 12:50
updated_at: 2026-06-02 12:54
---

## Origin

Risk-mitigation ("after") follow-up for t756_4, created at Step 8d after implementation landed.

## Risk addressed

code-health: new apply path + git-scan/explain-context bundling.

> The git-scan (`git log --grep`/`git diff`) + `aitask_explain_context.sh` shell-out
> bundling inside `register_module_syncer` is genuinely new logic with no prior
> analog in `crew.py` (new subprocess + large-bundle failure surface, not covered
> by t906's decompose/merge contract tests) · severity: medium.

## Goal

Add integration/contract coverage for the `module_sync` apply + scan-bundle path,
paralleling t906's coverage for decompose/merge. Specifically:

- `apply_module_syncer_output`: drive a real worktree fixture through the
  single-parent node creation, module-HEAD advance, and `last_synced_at` stamp;
  assert the umbrella HEAD is untouched and the group↔agent round-trip resolves.
- `register_module_syncer` scan bundling: exercise `_sync_touched_files` /
  `_sync_scoped_diff` / `_sync_explain_context` against a stubbed
  `aitask_explain_context.sh` (subprocess + stdout boundary, like t906 Group D's
  stubbed `aitask_create.sh`), including the `--since last_synced_at` horizon and
  the 60k-char diff truncation cap.
- Refuse path: assert `register_module_syncer` raises when `module_tasks` lacks the
  module, and that the wizard disables Next (decision-contract level, mirroring
  t906 Group B's headless-poller note).

t756_4's unit tests (`tests/test_brainstorm_module_sync.py`) cover the happy path
and refusal at unit level; this task hardens the subprocess/large-bundle surface
the risk evaluation flagged.
