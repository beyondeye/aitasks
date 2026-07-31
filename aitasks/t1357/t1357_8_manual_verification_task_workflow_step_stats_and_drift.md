---
priority: medium
effort: medium
depends: [t1357_7]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [1357_1, 1357_2, 1357_3, 1357_4, 1357_5, 1357_6, 1357_7]
anchor: 1357
created_at: 2026-07-31 11:03
updated_at: 2026-07-31 11:03
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

## Verification Checklist

- [ ] [t1357_1] bash tests/test_stats_step.sh passes; shellcheck clean on aitask_stats_step.sh + lib/stats_step_lib.sh
- [ ] [t1357_1] Manual round-trip: ait stats-step begin-run/stamp/capture on a scratch task id produces exactly one committed events file under aitasks/metadata/stats/events/<month>/ (then revert the test commit)
- [ ] [t1357_1] Negative control: unwritable spool dir -> every verb still exits 0 and prints STATS_ERROR:
- [ ] [t1357_2] Existing tests for pick_own / gate record / archive / update still pass after instrumentation
- [ ] [t1357_2] Each instrumented helper writes the expected spool line (step/ev/src) in a scratch repo
- [ ] [t1357_2] Negative control: aitask_stats_step.sh absent/broken -> instrumented helpers still succeed
- [ ] [t1357_2] Gate ledger marker now carries duration=<N>s from both run_command_gate and the orchestrator path, and lib/gate_ledger.py parses it
- [ ] [t1357_3] aitask_skill_verify.sh green; goldens regenerated in the same commit; all three rendered profile trees contain every stamp call
- [ ] [t1357_3] Live smoke: one real /aitask-pick cycle on a scratch task -> spool fills during the run and Step 9b capture commits exactly one per-run events file
- [ ] [t1357_3] Aborted run captures outcome=aborted; killed session leaves a spool the next run sweeps as outcome=orphaned
- [ ] [t1357_4] Python suite (--test-dir) last line reads PYTHON SUITE: PASSED
- [ ] [t1357_4] Drift fixture: one step's median doubles -> exactly that step flagged (WoW and MoM); identical periods / below min_samples -> zero flags
- [ ] [t1357_4] ait stats renders Step timings + Drift sections cleanly on real data and on an empty store
- [ ] [t1357_5] Launch record line written before exec; wrappers still work with launches dir unwritable
- [ ] [t1357_5] Session join: pid-anchored match wins over window; no overlap -> join=none and no enrichment sidecar
- [ ] [t1357_5] Enrichment sidecar committed next to the per-run file; token columns appear in ait stats only when enrichment exists; raw transcripts never committed
- [ ] [t1357_6] Dry-run shows sane per-month row counts on the real repo before the real backfill run
- [ ] [t1357_6] Backfill output validates through the t1357_4 loader with zero malformed rows; ledger run= timestamps preferred over commit dates
- [ ] [t1357_6] Second run without --force refuses; --force regenerates with unchanged row count (no duplication)
- [ ] [t1357_7] Retrospective report cites reproducible commands; any config tuning is reflected in a subsequent ait stats run shown in the report
