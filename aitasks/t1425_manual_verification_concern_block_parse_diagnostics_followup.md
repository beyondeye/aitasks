---
priority: medium
effort: medium
depends: [1293]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [1293]
created_at: 2026-08-05 11:39
updated_at: 2026-08-05 11:39
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t1293

## Verification Checklist

- [ ] In minimonitor, with a shadow whose block has SOME unparseable marker lines: press `c`, confirm the banner reads "N line(s) ... could not be parsed - [u] inspect" with the bracket visible (not swallowed as markup)
- [ ] Press `u` from that picker: the offending lines and the raw block region appear, brackets intact, and an over-bound split marker is recognisable by its continuation rows
- [ ] Close the inspect view with `q` and again with `Esc`: both return to the picker with any ticks still selected, and the picker has not dismissed
- [ ] In minimonitor, with a shadow whose block has NO parseable marker at all: press `c` and confirm the raw view opens directly (plus the warning toast), rather than only toasting
- [ ] Repeat the all-malformed case in the full monitor (`ait monitor`, `c`): the raw view opens, the concern badge clears, and a SECOND `c` afterwards is still honoured (pick guard released)
- [ ] Resize the minimonitor companion pane to ~30 columns with the picker open: the dialog keeps its full right border, the OK/Cancel buttons are gone, and the compact help line reads through to "esc"
- [ ] Resize further to ~24 columns: region and body are both still visible on the two-line row, nothing is cut mid-word, and the border is intact on every dialog row
- [ ] Resize back above 30 columns with the picker still open: the full help line and the OK/Cancel buttons come back (the tier is re-applied live, not only at mount)
- [ ] Confirm a normal, fully-parseable block is unchanged: no warning banner, `u` reports "Nothing unparsed in this block", and forwarding to the clipboard still pastes the concerns with their Disposition trailers
