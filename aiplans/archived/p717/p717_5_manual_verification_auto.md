---
Task: t717_5_manual_verification_codeagent_usage_stats.md
Parent Task: aitasks/t717_codeagent_usage_stats_improvements.md
Worktree: (current branch - fast profile)
Branch: main
Base branch: main
Verified by: codex
Verified at: 2026-06-28 10:09
---

# t717_5 - Manual verification: code-agent usage statistics

## Execution Log

### Summary

- Checklist result after geminicli cleanup: 18 pass, 2 fail, 2 skip, 0 defer.
- Obsolete follow-up tasks removed:
  - t1081: removed because Gemini/geminicli whitelist touchpoints are obsolete.
  - t1080: removed because geminicli provider/mode is no longer supported.
- Follow-up bug tasks retained for real failed items:
  - t1082: top-verified recent mode still lets no-recent flat verified scores outrank recent data.
  - t1083: `./ait stats tui` is not routed by the `ait` dispatcher; the working entrypoint is `./ait stats-tui` / `.aitask-scripts/aitask_stats_tui.sh`.

### Item 1

- Item text: Run `bash tests/test_verified_update.sh` - all rollover test cases pass.
- Approach: CLI test.
- Action run: `bash tests/test_verified_update.sh`
- Output: 86 passed, 0 failed.
- Verdict: pass.

### Item 2

- Item text: Run `shellcheck .aitask-scripts/aitask_verified_update.sh` - clean output.
- Approach: CLI lint.
- Action run: `shellcheck .aitask-scripts/aitask_verified_update.sh`
- Output: no diagnostics.
- Verdict: pass.

### Item 3

- Item text: Run verified-update smoke for `2026-05-01` and confirm one-month rollover.
- Approach: isolated temp git repo with copied scripts/model metadata and fake `./ait git` wrapper.
- Action run: `aitask_verified_update.sh --agent-string claudecode/opus4_6 --skill pick --score 5 --date 2026-05-01 --silent`
- Output: `prev_month` became `{period:"2026-04", runs:5, score_sum:480}` and `month` became `{period:"2026-05", runs:1, score_sum:100}`.
- Verdict: pass.

### Item 4

- Item text: Reset and run verified-update smoke for `2026-08-01` to confirm multi-month skip.
- Approach: same isolated temp git repo pattern.
- Action run: `aitask_verified_update.sh --agent-string claudecode/opus4_6 --skill pick --score 4 --date 2026-08-01 --silent`
- Output: `prev_month` became `{period:"", runs:0, score_sum:0}` and `month` became `{period:"2026-08", runs:1, score_sum:80}`.
- Verdict: pass.

### Item 5

- Item text: Run verified and usage update test suites.
- Approach: CLI tests.
- Action run: `bash tests/test_verified_update.sh` and `bash tests/test_usage_update.sh`
- Output: verified suite 86/86 passed; usage suite 36/36 passed.
- Verdict: pass.

### Item 6

- Item text: Run ShellCheck on verified, usage, and shared lib scripts.
- Approach: CLI lint.
- Action run: `shellcheck .aitask-scripts/aitask_verified_update.sh .aitask-scripts/aitask_usage_update.sh .aitask-scripts/lib/verified_update_lib.sh`
- Output: no diagnostics.
- Verdict: pass.

### Item 7

- Item text: Confirm codex usage bump happens while verified stats remain unchanged.
- Approach: isolated temp git repo smoke plus satisfaction-feedback instruction inspection.
- Action run: `aitask_usage_update.sh --agent-string codex/gpt5_5 --skill pick --date 2026-06-27 --silent`
- Output: `usagestats.pick.month.runs` changed 24 -> 25; `verifiedstats.pick` was unchanged. `satisfaction-feedback.md` contains Step 0 invoking `aitask_usage_update.sh` before the score prompt.
- Verdict: pass.

### Item 8

- Item text: In a fresh shell, run `./.aitask-scripts/aitask_usage_update.sh --help`.
- Approach: CLI invocation.
- Action run: `./.aitask-scripts/aitask_usage_update.sh --help`
- Output: help text printed, exit 0, no permission prompt.
- Verdict: pass.

### Item 9

- Item text: Verify all five whitelist touchpoints contain `aitask_usage_update.sh`.
- Approach: file inspection.
- Action run: Python path scan over `.claude/settings.local.json`, `.gemini/policies/aitasks-whitelist.toml`, `seed/claude_settings.local.json`, `seed/geminicli_policies/aitasks-whitelist.toml`, `seed/opencode_config.seed.json`.
- Output: old checklist expectation includes Gemini/geminicli policy files, but geminicli is no longer supported.
- Verdict: skip; obsolete follow-up t1081 removed.

### Item 10

- Item text: Compile `agent_model_picker.py`.
- Approach: Python compile check.
- Action run: `python3 -m py_compile .aitask-scripts/lib/agent_model_picker.py`
- Output: exit 0.
- Verdict: pass.

### Item 11

- Item text: Cycle agent picker modes and observe seven modes including `geminicli`.
- Approach: Python inspection of `AgentModelPickerScreen._MODES` and `MODEL_FILES`.
- Action run: import `agent_model_picker`, print modes/providers.
- Output: six modes/providers only: top verified, top usage, all, codex, opencode, claudecode; providers are `claudecode|codex|opencode`. `geminicli` is absent.
- Verdict: skip; the old seven-mode expectation is obsolete because geminicli is no longer supported. Obsolete follow-up t1080 removed.

### Item 12

- Item text: Confirm top-verified rankings are recent-window based and do not let no-recent all-time scores dominate.
- Approach: controlled Python fixture with `old_high` no recent data and `recent_lower` recent data.
- Action run: `AgentModelPickerScreen("pick")._build_options_top()` against the fixture.
- Output: `old_high` appeared first via flat verified fallback (`score: 100 (no recent data)`) ahead of `recent_lower`.
- Verdict: fail; follow-up t1082.

### Item 13

- Item text: Confirm top-by-usage recent mode includes a codex model.
- Approach: Python inspection against live model metadata.
- Action run: `AgentModelPickerScreen("pick", all_models=load_all_models())._build_options_top_usage()`
- Output: includes `codex/gpt5_5`.
- Verdict: pass.

### Item 14

- Item text: Confirm per-agent detail strings include prev-month data.
- Approach: direct helper invocation.
- Action run: `_format_op_stats(...)` with month and prev_month buckets.
- Output: `96 (9 runs, 5 this mo, 3 prev mo)`.
- Verdict: pass.

### Item 15

- Item text: Confirm picker selection returns the correct agent/model string.
- Approach: monkeypatched `dismiss` callback on `AgentModelPickerScreen`.
- Action run: invoke `on_fuzzy_select_selected` for top-usage value `codex/gpt5_5` and provider-mode value `gpt5_5`.
- Output: both paths dismissed with `{"key": "pick", "value": "codex/gpt5_5"}`.
- Verdict: pass.

### Item 16

- Item text: Compile stats modules.
- Approach: Python compile check.
- Action run: `python3 -m py_compile .aitask-scripts/stats/stats_data.py .aitask-scripts/stats/stats_app.py .aitask-scripts/aitask_stats.py`
- Output: exit 0.
- Verdict: pass.

### Item 17

- Item text: Open `./ait stats tui`, navigate to verified pane, and cycle windows.
- Approach: command-surface check plus TUI launch check.
- Action run: `./ait stats tui`
- Output: dispatcher runs `aitask_stats.sh` and reports `unrecognized arguments: tui`; `ait` exposes `stats-tui` as the TUI route instead.
- Verdict: fail; follow-up t1083.

### Item 18

- Item text: Switch to usage rankings pane and cycle windows independently.
- Approach: live `stats-tui` launch plus data/code inspection.
- Action run: `.aitask-scripts/aitask_stats_tui.sh`; inspect `WINDOWS`, `load_usage_rankings()`, and `UsageRankingsPane`.
- Output: agents layout includes `Usage rankings`; usage loader exposes `recent|all_time|month|prev_month|week` with nonzero `pick` data.
- Verdict: pass.

### Item 19

- Item text: In usage pane, cycle operations with left/right.
- Approach: data/code inspection.
- Action run: inspect `_usage_ops_sorted_by_runs(load_usage_rankings())` and `UsageRankingsPane.cycle_op`.
- Output: multiple usage ops available (`pick`, `explore`, `changelog`, `wrap`, `add-model`); pane implements `cycle_op`.
- Verdict: pass.

### Item 20

- Item text: Footer hints reflect window and op keys.
- Approach: live TUI capture plus code inspection.
- Action run: `.aitask-scripts/aitask_stats_tui.sh` in tmux; inspect `stats_app.py` bindings and pane hint strings.
- Output: live footer shows `[ prev win/grp ] next win/grp`; pane code includes left/right op hints and bracket window hints.
- Verdict: pass.

### Item 21

- Item text: CLI `./ait stats` text default does not crash and produces sensible output.
- Approach: CLI invocation.
- Action run: `./ait stats`
- Output: exit 0; rendered task statistics and verified model rankings.
- Verdict: pass.

### Item 22

- Item text: Temporarily hide `models_codex.json`, rerun TUI, and confirm no crash.
- Approach: temporary rename with trap restore.
- Action run: move `aitasks/metadata/models_codex.json` aside, run `timeout 4s ./.aitask-scripts/aitask_stats_tui.sh`, restore file.
- Output: TUI stayed running until timeout (`NO_CRASH_TIMEOUT`); no traceback or non-timeout exit.
- Verdict: pass.

## Cleanup

- Removed temp smoke repositories under `/tmp`.
- Restored `aitasks/metadata/models_codex.json` after the no-codex TUI check.
- Killed any stats TUI process launched during verification.
