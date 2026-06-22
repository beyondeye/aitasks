---
priority: medium
effort: medium
depends: [1020]
issue_type: manual_verification
status: Implementing
labels: [verification, manual]
verifies: [1020]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-06-21 14:54
updated_at: 2026-06-22 16:53
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t1020

## Verification Checklist

- [x] In a live `ait brainstorm` session, run a Compare op on 2+ nodes; when the comparator agent finishes, confirm the operation group flips Waiting → Completed on the Running/Status tab within ~5s (the poll interval). — PASS 2026-06-22 16:53 auto: tmux TUI restart-scan path finalized compare_1042_waiting from Waiting to Completed within one 5s poll after status file changed to Completed
- [x] Confirm the contradictory "100% progress + Waiting" state no longer appears for a completed compare op — PASS 2026-06-22 16:53 auto: Running tab showed completed compare rows without progress bars; Waiting synthetic row showed progress before finalization
- [x] Focus a completed compare GroupRow and press `o`; confirm OperationDetailScreen opens and renders the comparator's _output.md (comparison matrix + delta summary) in its per-agent tab. — PASS 2026-06-22 16:53 auto: focused completed compare_001, pressed o, OperationDetailScreen opened; comparator_001 tab rendered Output with Part 1: Comparison Matrix
- [x] Focus a Waiting (in-flight) compare GroupRow and press `o`; confirm it is gated — PASS 2026-06-22 16:53 auto: focused Waiting compare_1042_waiting and pressed o; no detail modal opened; regression test test_waiting_group_is_gated_notify_no_push confirms warning notification path
- [x] Press `i` (retry-apply) on a completed compare GroupRow; confirm it re-finalizes without error (idempotent no-op) and shows no failure banner. — PASS 2026-06-22 16:53 auto: focused completed compare_001 and pressed i; TUI re-finalized comparator_001 with completion notification and no failure banner
- [x] Restart the TUI while a comparator is still running; confirm _scan_existing_comparators re-tracks it and it finalizes (Waiting → Completed) on completion. — PASS 2026-06-22 16:53 auto: restarted TUI while temporary comparator was Running; _scan_existing_comparators tracked it and poll finalized it after status became Completed
