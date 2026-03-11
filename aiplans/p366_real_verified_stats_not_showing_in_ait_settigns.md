---
Task: t366_real_verified_stats_not_showing_in_ait_settigns.md
Worktree: (none — current branch)
Branch: (current)
Base branch: main
---

# Plan: Use skill names for verified stats — rename task-pick to pick

## Context

opencode/zen_gpt_5_4 had verified stats (score 95) stored under `"pick"` key, but TUI looked up `"task-pick"`. Fix: rename `task-pick` operation to `pick` everywhere so verified keys match. `batch-review` kept as-is (it's a distinct skill).

## Changes

1. **codeagent_config.json** (seed + data): Renamed `"task-pick"` → `"pick"` operation key
2. **Model JSON files** (all 8): Renamed `"task-pick"` → `"pick"` in verified dicts. zen_gpt_5_4's `"pick": 95` preserved.
3. **settings_app.py**: Updated OPERATION_DESCRIPTIONS key
4. **aitask_codeagent.sh**: Updated SUPPORTED_OPERATIONS, case statements, help text
5. **aitask_board.py**: Updated invoke call
6. **aitask_opencode_models.sh**: Updated default verified keys for new models
7. **aitask-refresh-code-models SKILL.md**: Updated default verified keys
8. **Tests**: Updated test fixtures and assertions; fixed pre-existing test failure (test used live config instead of seed)

## Final Implementation Notes
- **Actual work done:** Renamed `task-pick` operation to `pick` across codeagent config, model JSON files, core scripts, TUI, and tests. `batch-review` kept unchanged per user decision.
- **Deviations from plan:** Initially planned to also rename `batch-review` → `review`, but user clarified that `batch-review` is a distinct new skill, not the existing review skill.
- **Issues encountered:** Codeagent test was pre-existing broken — it copied live config (with opencode defaults) but asserted claudecode defaults. Fixed by using seed config.
- **Key decisions:** Only rename `task-pick` → `pick`. Keep `batch-review` as-is. Docs/website/other-agent variants deferred.
