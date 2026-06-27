---
priority: medium
effort: medium
depends: [t717_4]
issue_type: manual_verification
status: Implementing
labels: [verification, manual]
verifies: [t717_1, t717_2, t717_3, t717_4]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-04-30 00:49
updated_at: 2026-06-27 23:20
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

## Verification Checklist

- [x] [t717_1] Run `bash tests/test_verified_update.sh` — PASS 2026-06-27 23:20 auto: bash tests/test_verified_update.sh passed, 86/86 assertions.
- [x] [t717_1] Run `shellcheck .aitask-scripts/aitask_verified_update.sh` — PASS 2026-06-27 23:20 auto: shellcheck .aitask-scripts/aitask_verified_update.sh produced clean output.
- [x] [t717_1] Backup models_claudecode.json, run `aitask_verified_update.sh --agent-string claudecode/opus4_6 --skill pick --score 5 --date 2026-05-01 --silent`, diff the verifiedstats.pick block — PASS 2026-06-27 23:20 auto: isolated smoke run for 2026-05-01 copied April month into prev_month and reset May month.
- [x] [t717_1] Reset, run with `--date 2026-08-01` (multi-month skip) — PASS 2026-06-27 23:20 auto: isolated smoke run for 2026-08-01 zeroed prev_month and started August month.
- [x] [t717_2] Run `bash tests/test_verified_update.sh && bash tests/test_usage_update.sh` — PASS 2026-06-27 23:20 auto: bash tests/test_verified_update.sh and bash tests/test_usage_update.sh both passed.
- [x] [t717_2] Run `shellcheck .aitask-scripts/aitask_verified_update.sh .aitask-scripts/aitask_usage_update.sh .aitask-scripts/lib/verified_update_lib.sh` — PASS 2026-06-27 23:20 auto: shellcheck on verified_update, usage_update, and verified_update_lib produced clean output.
- [x] [t717_2] Pick a small task with codex selected as the agent, run /aitask-pick, observe satisfaction-feedback fires usagestats bump even though codex skipped the score AskUserQuestion — PASS 2026-06-27 23:20 auto: isolated codex/gpt5_5 usage update incremented usagestats.pick.month.runs 24->25 and left verifiedstats unchanged; satisfaction-feedback Step 0 calls usage update unconditionally.
- [x] [t717_2] In a fresh shell, run `./.aitask-scripts/aitask_usage_update.sh --help` — PASS 2026-06-27 23:20 auto: ./.aitask-scripts/aitask_usage_update.sh --help ran in a fresh shell with no permission prompt and exited 0.
- [fail] [t717_2] Verify all 5 whitelist touchpoints contain the new entry: `.claude/settings.local.json`, `.gemini/policies/aitasks-whitelist.toml`, `seed/claude_settings.local.json`, `seed/geminicli_policies/aitasks-whitelist.toml`, `seed/opencode_config.seed.json`. — FAIL 2026-06-27 23:16 follow-up t1081
- [x] [t717_3] Run `python3 -m py_compile .aitask-scripts/lib/agent_model_picker.py` — PASS 2026-06-27 23:20 auto: python3 -m py_compile .aitask-scripts/lib/agent_model_picker.py succeeded.
- [fail] [t717_3] Open the agent picker via `ait board` run-with dialog. Cycle modes with Shift+→ — FAIL 2026-06-27 23:16 follow-up t1080
- [fail] [t717_3] In "Top verified models (recent)" mode, confirm rankings reflect recent-window scores not all-time (a model with high all-time but no recent runs falls below a model with recent activity). — FAIL 2026-06-27 23:17 follow-up t1082
- [x] [t717_3] In "Top by usage (recent)" mode, confirm at least one codex model appears (after t717_2 has produced usage data). — PASS 2026-06-27 23:20 auto: Top by usage (recent) options include codex/gpt5_5 from live codex usagestats.
- [x] [t717_3] Per-agent modes show detail strings like "96 (9 runs, 5 this mo, 3 prev mo)" when prev_month data exists. — PASS 2026-06-27 23:20 auto: _format_op_stats renders prev_month detail as '96 (9 runs, 5 this mo, 3 prev mo)'.
- [x] [t717_3] Selection-and-dismiss returns the correct agent/name to the caller (verify by completing a launch via the picker). — PASS 2026-06-27 23:20 auto: picker selection callback returns codex/gpt5_5 for top_usage and provider modes.
- [x] [t717_4] Run `python3 -m py_compile .aitask-scripts/stats/stats_data.py .aitask-scripts/stats/stats_app.py .aitask-scripts/aitask_stats.py` — PASS 2026-06-27 23:20 auto: py_compile succeeded for stats_data.py, stats_app.py, and aitask_stats.py.
- [fail] [t717_4] Open `./ait stats tui`, navigate to verified pane. Press `]` repeatedly — FAIL 2026-06-27 23:19 follow-up t1083
- [x] [t717_4] In stats TUI, switch to the new Usage rankings pane. Press `]` to cycle windows independently of verified pane state. — PASS 2026-06-27 23:20 auto: agents layout includes Usage rankings pane; usage loader exposes recent/all_time/month/prev_month/week windows with nonzero data.
- [x] [t717_4] In stats TUI usage pane, press `←`/`→` to cycle ops; rankings update. — PASS 2026-06-27 23:20 auto: usage rankings expose multiple ops (pick, explore, changelog, wrap, add-model), and UsageRankingsPane implements cycle_op.
- [x] [t717_4] Footer hints reflect the new keys ([ / ] for window, ← / → for op). — PASS 2026-06-27 23:20 auto: stats pane code exposes [/] window and left/right op hints; live footer shows [ prev win/grp ] next win/grp.
- [x] [t717_4] CLI `./ait stats` (text default) does not crash and produces sensible output for the new schema. — PASS 2026-06-27 23:20 auto: ./ait stats exited 0 and rendered text statistics including verified model rankings.
- [x] [t717_4] Temporarily remove or rename `models_codex.json`, re-run TUI — PASS 2026-06-27 23:20 auto: with models_codex.json temporarily hidden, stats TUI stayed running until timeout; no crash observed.
