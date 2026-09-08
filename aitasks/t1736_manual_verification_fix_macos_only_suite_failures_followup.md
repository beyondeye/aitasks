---
priority: medium
effort: medium
depends: [1729]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [1729]
anchor: 1705
followup_kind: manual_verification
created_at: 2026-09-08 11:30
updated_at: 2026-09-08 11:30
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t1729

## Verification Checklist

- [ ] Run `ait brainstorm init --proposal-file <f>` TWICE in a row; both runs must succeed (the spec tmpfile is now unique per run, and a single run always passed even when broken).
- [ ] Run `ait update <id>` interactive description edit TWICE; the tmpfile keeps its `.md` suffix, so confirm the editor still opens with markdown syntax highlighting and the edit is saved both times.
- [ ] Run `ait crew command` TWICE and `ait crew setmode` TWICE; both use `.yaml` tmpfiles and must succeed on the second run.
- [ ] Run `ait add-model` TWICE (it allocates six tmpfiles, `.json` and `.sh`); confirm the metadata and seed writes land correctly both times.
- [ ] Exercise the `ait archive` verify-defer path TWICE (`ait_verify_defer_*.txt`).
- [ ] Configure a `resource_admission_command` project hook and confirm it runs TWICE consecutively — this is the exact path that was permanently broken after its first use (`DIAG:could not create a temporary log file`), and it is the one item here with a known pre-fix failure to reproduce against.
- [ ] After all of the above, `ls "$TMPDIR"/*XXXXXX*` must return nothing — a literal-XXXXXX file means a call site was missed.
