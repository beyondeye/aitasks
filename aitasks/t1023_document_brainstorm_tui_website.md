---
priority: low
effort: medium
depends: []
issue_type: documentation
status: Ready
labels: [brainstorming, tui]
created_at: 2026-06-17 12:08
updated_at: 2026-06-17 12:08
boardidx: 230
---

## Context
The brainstorm TUI (`ait brainstorm`) has **no dedicated website documentation** —
`website/content/docs/tuis/_index.md` still reads "Dedicated documentation is
pending." Other TUIs (board, monitor, codebrowser, …) each have a
`tuis/<name>/` directory (`_index.md`, `how-to.md`, `reference.md`). This task
fills that gap, now that the IA is finalized by t983 (Browse/Session/Running +
always-on runtime strip).

Spun off from **t983_9** (the IA-finalization child), whose scope was limited to
keeping brainstorm in the user-facing TUI list + a 3-tab note in
`aidocs/framework/tui_conventions.md`.

## Key Files to Modify
- `website/content/docs/tuis/brainstorm/_index.md` (NEW) — overview of the 3-tab IA.
- `website/content/docs/tuis/brainstorm/how-to.md` (NEW) — workflows (explore,
  mark+compare, run operations, manage running agents).
- `website/content/docs/tuis/brainstorm/reference.md` (NEW) — full keymap
  (`b`/`s`/`r` tabs, `v`/`space`/`A`/`Enter`/`c`, Running-tab row actions
  `p`/`k`/`K`/`w`/`R`/`x`/`e`/`L`).
- `website/content/docs/tuis/_index.md` — replace the "documentation is pending"
  line with a link to the new section.

## Coordination — t1018 (brainstorm op-restart / double-click / footer hygiene)
t1018 changes the brainstorm keymap that this task's `reference.md` documents:
it adds Running-tab operation-row restart keys (t1018_2), double-click → open
detail (t1018_3), and replaces the undeliverable `ctrl+shift+b`/`ctrl+shift+l`
preview chords with deliverable `alt+<letter>` keys while gating the retry-apply
actions (t1018_1). Since the source of truth below is the live `BINDINGS`, this
task self-corrects if picked **after** t1018 lands — prefer that ordering, or
re-read `brainstorm_app.py` at implementation time to capture the final keymap.

## Reference
- Source of truth: `.aitask-scripts/brainstorm/brainstorm_app.py` (read the
  current BINDINGS + tab compose, do not rely on archived design plans).
- IA convention note: `aidocs/framework/tui_conventions.md` ("brainstorm TUI
  information architecture").
- Follow `aidocs/framework/documentation_conventions.md` (current-state-only;
  generic example project names).

## Verification
- `cd website && hugo build --gc --minify` succeeds.
- The new pages render and the `tuis/_index.md` link resolves.
