---
priority: medium
effort: medium
depends: [1612]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [1612]
anchor: 1595
followup_kind: manual_verification
created_at: 2026-08-26 00:01
updated_at: 2026-08-26 00:01
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t1612

## Verification Checklist

- [ ] Run `ait setup` end-to-end in this repo (real TTY, tmux) and confirm it completes normally with the moved CLAUDE.md call.
- [ ] Confirm the t1607 guard fires on the now-live path: this repo's CLAUDE.md is byte-identical afterwards, still has 0 `>>>aitasks` markers, and setup printed "leaving it hand-maintained".
- [ ] Legacy mode via the DECLINE branch (the path no automated test can drive — needs a real TTY): on a throwaway git repo, answer `n` to "Use a separate branch for task data?" and confirm setup still writes the CLAUDE.md block. This is the acceptance criterion T43's structural declare -f guard was substituted for (t1612).
- [ ] On a throwaway project whose CLAUDE.md is markerless and has NO `## Git Operations on Task/Plan Files` section: confirm the upgrade append renders correctly in a real terminal — the three info lines contain an em dash and quoted `>>>aitasks` / `<<<aitasks` markers that must not be mangled.
- [ ] Follow the printed opt-out advice by hand on that project (delete the marker pair, keep a `## Git Operations on Task/Plan Files` section) and confirm the next `ait setup` leaves the file alone.
- [ ] Confirm `commit_framework_files`' interactive "READY TO COMMIT" list includes CLAUDE.md, and that declining the prompt leaves it uncommitted and reported.
