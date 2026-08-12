---
priority: medium
effort: medium
depends: [1486]
issue_type: manual_verification
status: Implementing
labels: [verification, manual]
verifies: [1486]
assigned_to: dario-e@beyond-eye.com
anchor: 1449
followup_kind: manual_verification
created_at: 2026-08-12 08:34
updated_at: 2026-08-12 08:45
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t1486

## Verification Checklist

- [ ] ait logview <a log file with content>: header shows [live] at launch; press r with NO prior mouse click -> [raw] appears alongside [live]; press p -> [paused]. Pins both the markup fix and the startup-focus fix.
- [ ] ait logview <an EMPTY log file>: press r -> the header is EXPECTED to stay [live] until another key is pressed. This is the known defect tracked as t1489, not a regression of t1486 — do not fail the task for it.
- [ ] ait crew logview --path <file> --no-tail: header shows [static].
- [ ] ait monitor: toggle auto-switch -> the session bar shows a bold-yellow [AUTO] and the CODE AGENTS header shows the separate "⟳ AUTO" indicator; toggle back -> both disappear.
- [ ] ait board with a task whose issue: frontmatter is a GitLab issue URL: the row renders a GL badge in GitLab orange (#e24329) and the board does NOT crash. Repeat with a GitLab merge-request URL -> MR:GL. This is the crash case — only a real terminal proves the compositor survives it.
- [ ] ait board sibling branches still render after the closing-tag change: GitHub -> GH / PR:GH, Bitbucket -> BB / PR:BB, a non-platform URL -> Issue / PR.
- [ ] TODO: verify .aitask-scripts/board/aitask_board.py end-to-end in tmux
