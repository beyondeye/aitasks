---
priority: medium
effort: low
depends: [t1162_1]
issue_type: feature
status: Implementing
labels: [reporting]
gates: [risk_evaluated]
assigned_to: dario-e@beyond-eye.com
anchor: 1162
created_at: 2026-07-22 10:45
updated_at: 2026-07-22 16:44
---

## Context

Second child of t1162. Registers `work-report` as a configurable read-only code-agent operation for Claude Code, Codex, and OpenCode, seeds its lightweight default model, and whitelists the t1162_1 gatherer helper. Parent plan: `aiplans/p1162_add_manager_facing_work_report_skill_and_board_flow.md` (t1162_2 section).

## Key Files to Modify

- `.aitask-scripts/aitask_codeagent.sh` — add `work-report` to `SUPPORTED_OPERATIONS` (line ~26); add case arm in `build_invoke_command` (~405-548) for claudecode/codex/opencode composing `/aitask-work-report <args>` (model: the `explain` arms at ~435-438, ~500-521, ~528-529). Codex uses the standard default-mode skill launch — NO plan-mode forcing (this IS the "read-only analysis → default mode" requirement; pin with a test).
- `.aitask-scripts/lib/agent_command_screen.py` — add `"work-report"` to `_FRESH_WINDOW_OPERATIONS` (~lines 64-66).
- `seed/codeagent_config.json` AND live `aitasks/metadata/codeagent_config.json` — add `"work-report": "claudecode/sonnet4_6"` to `.defaults` (mirrors `explain`; without it the chain silently falls through to the heavier `DEFAULT_AGENT_STRING` claudecode/opus4_8 — this seeded entry IS the "lightweight model class used by explain").
- `seed/models_claudecode.json`, `seed/models_codex.json`, `seed/models_opencode.json` (+ any live `aitasks/metadata/models_*.json`) — add `work-report` verified-score entries mirroring each model's `explain` values.
- Whitelist `aitask_work_report_gather.sh` in all 5 touchpoints: `.claude/settings.local.json`, `.codex/rules/default.rules`, `seed/claude_settings.local.json`, `seed/codex_rules.default.rules`, `seed/opencode_config.seed.json`. Verify with `./.aitask-scripts/aitask_audit_wrappers.sh` (see its Phase 2 helper discovery).

## Reference Files for Patterns

- `tests/test_codeagent.sh` — dry-run invoke + resolution test model (`--dry-run invoke`, `AGENT_STRING:` assertions).
- `.aitask-scripts/lib/agent_string.sh:26` — `DEFAULT_AGENT_STRING`.

## Verification

- Extend `tests/test_codeagent.sh` (or add `tests/test_codeagent_work_report.sh`): dry-run invoke for each of the 3 agents with `--columns now,next --tasks 12,34` passed through verbatim into the slash command; assert the codex command contains no plan-mode flag; assert `resolve work-report` returns the same agent string as `resolve explain` BOTH under the seeded config (both `claudecode/sonnet4_6`) AND in a no-config environment (both fall to `DEFAULT_AGENT_STRING`).
- `bash tests/test_codeagent.sh`; `./.aitask-scripts/aitask_audit_wrappers.sh` clean for the new helper; `shellcheck .aitask-scripts/aitask_codeagent.sh`.
