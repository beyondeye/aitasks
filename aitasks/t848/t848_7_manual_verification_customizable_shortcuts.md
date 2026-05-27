---
priority: medium
effort: medium
depends: [t848_6]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [848_1, 848_2, 848_3, 848_4, 848_5, 848_6]
created_at: 2026-05-27 17:47
updated_at: 2026-05-27 17:47
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

## Verification Checklist

- [ ] [t848_2] ait board shows (P)ick-style labels driven by current bindings.
- [ ] [t848_2] Editing userconfig.yaml shortcuts.board.pick_task updates board's button labels on relaunch.
- [ ] [t848_2] All other board behavior unchanged (no regression in detail screen).
- [ ] [t848_3] Every TUI (board, monitor, minimonitor, codebrowser, brainstorm, settings, stats, syncer, applink, diffviewer) launches without exceptions.
- [ ] [t848_3] Brainstorm's `H` opens op-help; `?` does NOT open op-help.
- [ ] [t848_3] Settings tab-switcher footer correctly lists current tab keys (registry-derived, not hardcoded).
- [ ] [t848_4] `?` opens the editor in every TUI; table only shows that TUI's actions.
- [ ] [t848_4] Rebind a visible action (e.g. board -> Pick) via the modal; confirm (P)ick label updates (immediately if refresh_bindings is supported, else after restart per fallback notice).
- [ ] [t848_4] Reset (r) and Clear-override (d) flows work and persist.
- [ ] [t848_4] Save under a collision triggers the confirm prompt and saves only on accept.
- [ ] [t848_5] Settings -> Shortcuts tab opens via `k`, shows all scopes.
- [ ] [t848_5] Editing a row updates the yaml AND in-TUI button labels in the source TUI on relaunch.
- [ ] [t848_5] Export-shortcuts -> edit exported bundle -> Import round-trip preserves the change and redraws table without restart.
- [ ] [t848_5] Standard Settings -> Export also carries the `shortcuts:` section verbatim, and re-imports cleanly.
- [ ] [t848_5] Lint coherence surfaces a deliberate quit-key drift between two scopes and clears once aligned.
- [ ] [t848_6] /docs/tuis/ renders the "Customizing keyboard shortcuts" section with working anchor links.
- [ ] [t848_6] /docs/tuis/settings/ renders the Shortcuts tab section with working internal links.
- [ ] [t848_6] Every per-TUI page (board, monitor, minimonitor, codebrowser, stats, syncer, applink) shows the callout linking to Settings -> Shortcuts.
- [ ] [t848_6] Hugo build (cd website && hugo --gc --minify) completes without warnings.
