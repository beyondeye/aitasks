---
priority: medium
effort: medium
depends: [t1468_6]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [t1468_3, t1468_4, t1468_5]
anchor: 1468
followup_kind: manual_verification
created_at: 2026-08-10 16:35
updated_at: 2026-08-13 23:07
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

## Verification Checklist

- [ ] [t1468_3] Launch `ait board` in a real terminal. A follow-up task is identifiable at first sight by BOTH colour and shape, without reading the task name.
- [ ] [t1468_3] Scan a kanban column containing a mix of follow-up and non-follow-up cards — the follow-ups stand out as a group, not one at a time.
- [ ] [t1468_3] Two different kinds (e.g. risk_mitigation vs upstream_defect) are distinguishable from each other, not merely distinguishable from "no kind".
- [ ] [t1468_3] Narrow the terminal to ~60 columns. The glyph still renders as a single cell, does not wrap, and does not push the task number or title off-screen.
- [ ] [t1468_3] The glyph does not collide with or shift the ☑/☐ mark on markable kanban cards, and still appears on TopicColumn and child cards, which have no mark.
- [ ] [t1468_3] By-Topic view: follow-ups show the glyph and cluster with their topic root.
- [ ] [t1468_3] In-Flight view: an in-flight follow-up shows the glyph.
- [ ] [t1468_3] By-Trail view: a trail card for a marked task shows the glyph; a trail GHOST card shows no glyph and renders without visual breakage.
- [ ] [t1468_3] Collapse a group containing follow-ups: the GroupHeader roll-up reports them, and the count is correct.
- [ ] [t1468_3] Collapse a group containing NO follow-ups: no roll-up text is shown (negative control).
- [ ] [t1468_3] A task with a hand-edited MALFORMED followup_kind (a list, an int, an empty or whitespace-only string) renders NO glyph at all and does not crash the board.
- [ ] [t1468_3] A task with an UNKNOWN non-empty followup_kind (e.g. a typo like `risk_mitgation`) renders the `·` fallback, UNCOLOURED — it must stay visible, since a value that silently vanishes reads as "not a follow-up". (Decided in t1468_3; this is deliberately different from the malformed case above.)
- [ ] [t1468_3] Collapse a group containing an unknown kind: the roll-up tallies it last, under `·`.
- [ ] [t1468_4] `ait ls -v` shows the kind on a marked task and shows nothing extra on an unmarked one.
- [ ] [t1468_4] `ait ls --followup-kind risk_mitigation` returns a plausible, non-zero set; spot-check two of the returned tasks are genuinely risk mitigations.
- [ ] [t1468_4] `ait ls --type bug` filters correctly and composes with `-l` and `--followup-kind`.
- [ ] [t1468_4] Filters behave in `--tree`, `--children N` and `--all-levels` modes, not only the default listing.
- [ ] [t1468_4] An unknown long flag still fails with the help text (the arg-parse case was not accidentally loosened).
- [ ] [t1468_4] Run `/aitask-pick` far enough to see the Step 2c selection options: the kind is visible in the option descriptions and helps distinguish new work from follow-ups.
- [ ] [t1468_5] Minimonitor sibling chooser shows the kind for ready siblings.
- [ ] [t1468_5] Work report output is not corrupted by the added TASK: field — column/task rows read correctly and the board `w` flow round-trips a reviewed selection with membership and order intact.
- [ ] [t1468_5] After the trail schema bump, `art:trail-gates-framework-landing` and `art:trail-shadow-review-loop` report a clean invalid-trail error (not a confusing STALE), and refresh successfully to 1.1.0.
- [ ] [t1468_5] A refreshed trail visibly contains followup_kind in its stored entry snapshots — inspect the artifact, do not rely on validation passing.
