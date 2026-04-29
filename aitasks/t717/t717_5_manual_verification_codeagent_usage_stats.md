---
priority: medium
effort: medium
depends: [t717_4]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [717_1, 717_2, 717_3, 717_4]
created_at: 2026-04-30 00:49
updated_at: 2026-04-30 00:49
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

## Verification Checklist

- [ ] [t717_1] Run `bash tests/test_verified_update.sh` — all rollover test cases pass.
- [ ] [t717_1] Run `shellcheck .aitask-scripts/aitask_verified_update.sh` — clean output.
- [ ] [t717_1] Backup models_claudecode.json, run `aitask_verified_update.sh --agent-string claudecode/opus4_6 --skill pick --score 5 --date 2026-05-01 --silent`, diff the verifiedstats.pick block — confirm prev_month captures the prior April bucket and month resets to May.
- [ ] [t717_1] Reset, run with `--date 2026-08-01` (multi-month skip) — confirm prev_month is zeroed (period:"", runs:0, score_sum:0) and month is the new period.
- [ ] [t717_2] Run `bash tests/test_verified_update.sh && bash tests/test_usage_update.sh` — all pass after the lib extraction.
- [ ] [t717_2] Run `shellcheck .aitask-scripts/aitask_verified_update.sh .aitask-scripts/aitask_usage_update.sh .aitask-scripts/lib/verified_update_lib.sh` — all clean.
- [ ] [t717_2] Pick a small task with codex selected as the agent, run /aitask-pick, observe satisfaction-feedback fires usagestats bump even though codex skipped the score AskUserQuestion — verifiedstats unchanged but usagestats[skill].month.runs incremented.
- [ ] [t717_2] In a fresh shell, run `./.aitask-scripts/aitask_usage_update.sh --help` — no permission prompt (whitelist coverage works).
- [ ] [t717_2] Verify all 5 whitelist touchpoints contain the new entry: `.claude/settings.local.json`, `.gemini/policies/aitasks-whitelist.toml`, `seed/claude_settings.local.json`, `seed/geminicli_policies/aitasks-whitelist.toml`, `seed/opencode_config.seed.json`.
- [ ] [t717_3] Run `python3 -m py_compile .aitask-scripts/lib/agent_model_picker.py` — succeeds.
- [ ] [t717_3] Open the agent picker via `ait board` run-with dialog. Cycle modes with Shift+→ — observe 7 modes: Top verified models (recent), Top by usage (recent), All models, codex, opencode, claudecode, geminicli.
- [ ] [t717_3] In "Top verified models (recent)" mode, confirm rankings reflect recent-window scores not all-time (a model with high all-time but no recent runs falls below a model with recent activity).
- [ ] [t717_3] In "Top by usage (recent)" mode, confirm at least one codex model appears (after t717_2 has produced usage data).
- [ ] [t717_3] Per-agent modes show detail strings like "96 (9 runs, 5 this mo, 3 prev mo)" when prev_month data exists.
- [ ] [t717_3] Selection-and-dismiss returns the correct agent/name to the caller (verify by completing a launch via the picker).
- [ ] [t717_4] Run `python3 -m py_compile .aitask-scripts/stats/stats_data.py .aitask-scripts/stats/stats_app.py .aitask-scripts/aitask_stats.py` — succeed.
- [ ] [t717_4] Open `./ait stats tui`, navigate to verified pane. Press `]` repeatedly — header cycles recent → all_time → month → prev_month → week. Rankings table updates each time.
- [ ] [t717_4] In stats TUI, switch to the new Usage rankings pane. Press `]` to cycle windows independently of verified pane state.
- [ ] [t717_4] In stats TUI usage pane, press `←`/`→` to cycle ops; rankings update.
- [ ] [t717_4] Footer hints reflect the new keys ([ / ] for window, ← / → for op).
- [ ] [t717_4] CLI `./ait stats` (text default) does not crash and produces sensible output for the new schema.
- [ ] [t717_4] Temporarily remove or rename `models_codex.json`, re-run TUI — no crash; codex absent from rankings.
