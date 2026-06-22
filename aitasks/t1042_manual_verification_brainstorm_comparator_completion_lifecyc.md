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
updated_at: 2026-06-22 16:49
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t1020

## Verification Checklist

- [ ] In a live `ait brainstorm` session, run a Compare op on 2+ nodes; when the comparator agent finishes, confirm the operation group flips Waiting → Completed on the Running/Status tab within ~5s (the poll interval).
- [ ] Confirm the contradictory "100% progress + Waiting" state no longer appears for a completed compare op — the progress bar is hidden once status is Completed.
- [ ] Focus a completed compare GroupRow and press `o`; confirm OperationDetailScreen opens and renders the comparator's _output.md (comparison matrix + delta summary) in its per-agent tab.
- [ ] Focus a Waiting (in-flight) compare GroupRow and press `o`; confirm it is gated — a "No completed output to open yet" warning, no modal.
- [ ] Press `i` (retry-apply) on a completed compare GroupRow; confirm it re-finalizes without error (idempotent no-op) and shows no failure banner.
- [ ] Restart the TUI while a comparator is still running; confirm _scan_existing_comparators re-tracks it and it finalizes (Waiting → Completed) on completion.
