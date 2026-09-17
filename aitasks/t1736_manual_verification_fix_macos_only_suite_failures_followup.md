---
priority: medium
effort: medium
depends: [1729]
issue_type: manual_verification
status: Implementing
labels: [verification, manual]
verifies: [1729]
assigned_to: dario-e@beyond-eye.com
anchor: 1705
followup_kind: manual_verification
created_at: 2026-09-08 11:30
updated_at: 2026-09-17 11:03
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t1729

## Verification Checklist

- [x] Run `ait brainstorm init --proposal-file <f>` TWICE in a row; both runs must succeed (the spec tmpfile is now unique per run, and a single run always passed even when broken). — PASS 2026-09-17 10:59 auto: brainstorm init --proposal-file succeeded 3 consecutive runs (scratch project, runner auto-start stubbed); spec reached session; no leftover spec/XXXXXX in TMPDIR
- [x] Run `ait update <id>` interactive description edit TWICE; the tmpfile keeps its `.md` suffix, so confirm the editor still opens with markdown syntax highlighting and the edit is saved both times. — PASS 2026-09-17 11:01 auto: interactive update (tmux-driven fzf) opened $EDITOR twice on distinct aitask_*.md tmpfiles; vim filetype=markdown; both edits saved; no leftovers
- [x] Run `ait crew command` TWICE and `ait crew setmode` TWICE; both use `.yaml` tmpfiles and must succeed on the second run. — PASS 2026-09-17 11:01 auto: crew command send x2 appended both entries; crew setmode x2 (headless, interactive) UPDATED rc=0; no ait_cmd_/ait_setmode_ leftovers
- [x] Run `ait add-model` TWICE (it allocates six tmpfiles, `.json` and `.sh`); confirm the metadata and seed writes land correctly both times. — PASS 2026-09-17 11:02 auto: aitask_add_model.sh (no 'ait add-model' verb exists) add-json/promote-config/promote-default-agent-string each run x2 in scratch; metadata+seed models, config defaults, DEFAULT_AGENT_STRING + note all updated; no leftovers
- [x] Exercise the `ait archive` verify-defer path TWICE (`ait_verify_defer_*.txt`). — PASS 2026-09-17 11:02 auto: aitask_archive.sh --with-deferred-carryover run on 2 scratch MV tasks consecutively; both CARRYOVER_CREATED with deferred item seeded; no ait_verify_defer_ leftovers
- [x] Configure a `resource_admission_command` project hook and confirm it runs TWICE consecutively — this is the exact path that was permanently broken after its first use (`DIAG:could not create a temporary log file`), and it is the one item here with a known pre-fix failure to reproduce against. — PASS 2026-09-17 10:58 auto: 3 consecutive runs admitted with unique logs; pre-fix control failed run 2 with DIAG:could not create a temporary log file
- [x] After all of the above, `ls "$TMPDIR"/*XXXXXX*` must return nothing — a literal-XXXXXX file means a call site was missed. — PASS 2026-09-17 11:03 auto: after all runs, ls $TMPDIR/*XXXXXX* and /tmp/*XXXXXX* both empty; repo grep finds no remaining suffixed mktemp call sites (only comments/docs)
