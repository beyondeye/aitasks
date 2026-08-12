---
priority: medium
effort: medium
depends: [1486]
issue_type: manual_verification
status: Implementing
labels: [verification, manual]
active_gates: []
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 4a36c12bb96d.681bafac2cb9.08c6f06389cd
verifies: [1486]
assigned_to: dario-e@beyond-eye.com
anchor: 1449
followup_kind: manual_verification
created_at: 2026-08-12 08:34
updated_at: 2026-08-12 09:30
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t1486

## Verification Checklist

- [x] ait logview <a log file with content>: header shows [live] at launch; press r with NO prior mouse click -> [raw] appears alongside [live]; press p -> [paused]. Pins both the markup fix and the startup-focus fix. — PASS 2026-08-12 09:30 auto: ait crew logview --path <full.log> in tmux -- header [live] at launch, r (no prior click) -> [live] [raw], p -> [paused] [raw]
- [x] ait logview <an EMPTY log file>: press r -> the header is EXPECTED to stay [live] until another key is pressed. This is the known defect tracked as t1489, not a regression of t1486 — do not fail the task for it. — PASS 2026-08-12 09:30 auto: empty log -- r left header [live]; [raw] appeared only after p. Matches the documented t1489 stale-header defect, not a t1486 regression
- [x] ait crew logview --path <file> --no-tail: header shows [static]. — PASS 2026-08-12 09:30 auto: ait crew logview --path <full.log> --no-tail -> header shows [static]
- [x] ait monitor: toggle auto-switch -> the session bar shows a bold-yellow [AUTO] and the CODE AGENTS header shows the separate "⟳ AUTO" indicator; toggle back -> both disappear. — PASS 2026-08-12 09:30 auto: ait monitor, A toggles -- session bar [AUTO] and CODE AGENTS header 'ReAUTO' both bold yellow (SGR 1 + 38;2;255;255;0); second A removed both (0 AUTO matches)
- [x] ait board with a task whose issue: frontmatter is a GitLab issue URL: the row renders a GL badge in GitLab orange (#e24329) and the board does NOT crash. Repeat with a GitLab merge-request URL -> MR:GL. This is the crash case — only a real terminal proves the compositor survives it. — PASS 2026-08-12 09:30 auto: isolated fixture board -- GL and MR:GL render in SGR 38;2;226;67;41 (#e24329), board did not crash. Negative control (same fixture, only [/] reverted to [/e24329]) crashed with MarkupError: closing tag '[/e24329]' does not match any open tag
- [x] ait board sibling branches still render after the closing-tag change: GitHub -> GH / PR:GH, Bitbucket -> BB / PR:BB, a non-platform URL -> Issue / PR. — PASS 2026-08-12 09:30 auto: same fixture -- GH/PR:GH, BB/PR:BB, non-platform Issue/PR all render; colours blue/green as coded
- [x] TODO: verify .aitask-scripts/board/aitask_board.py end-to-end in tmux — PASS 2026-08-12 09:30 auto: aitask_board.py driven end-to-end in a live tmux pane (200x50) across 8 tasks covering all four issue/PR indicator branches
