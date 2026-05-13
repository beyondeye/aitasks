---
priority: medium
effort: medium
depends: []
issue_type: documentation
status: Done
labels: []
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_7_1m
created_at: 2026-05-13 10:15
updated_at: 2026-05-13 10:31
completed_at: 2026-05-13 10:31
---

The aitasks TUIs support full mouse interaction (click, drag, scroll), but
this is not surfaced on the website. Update the home page wording and audit
every TUI doc to make mouse support discoverable.

## Home page (`website/content/_index.md`)

1. Hero description (line 10): after the sentence ending "...without leaving
   the terminal." add a mention of full mouse support. Suggested wording:
   "Kanban board, code browser, agent monitoring, and AI-enhanced git
   workflows — all in one tmux session, with full mouse support. Press `j`
   to hop between TUIs without leaving the terminal."

2. Feature card (line 23, "Agentic IDE in your terminal"): change
   "...all in one tmux session via `ait ide`. Press `j` to hop between TUIs..."
   to include "with full mouse support" — e.g., "Kanban Board, Code Browser,
   Monitor, Brainstorm, and Settings — all in one tmux session via `ait ide`,
   with full mouse support."

3. Take-the-tour heading (line 55): change
   "Seven TUIs share a single tmux session. Click any of them to dive in."
   to expand the acronym and mention mouse support, e.g.:
   "Seven TUIs (Terminal User Interface) share a single tmux session, with
   full mouse support. Click any of them to dive in."

## TUI index page (`website/content/docs/tuis/_index.md`)

Add a one-line callout near the top stating that all listed TUIs support
full mouse interaction (click, drag, scroll). The existing first paragraph
("...terminal-based user interfaces (TUIs) built with Textual...") is a
natural place.

## Per-TUI documentation audit

For each TUI doc, ensure documented actions also note their mouse-equivalent
(click target, drag, scroll) where applicable. Already covered:

- `docs/tuis/board/how-to.md` — has Keyboard / Mouse / Command-palette table
- `docs/tuis/codebrowser/how-to.md` and `.../reference.md` — document mouse
  click + drag selection

Needs review (currently no mouse coverage):

- `docs/tuis/monitor/how-to.md` and `.../reference.md`
- `docs/tuis/minimonitor/how-to.md`
- `docs/tuis/settings/how-to.md` and `.../reference.md`
- `docs/tuis/stats/_index.md`
- `docs/tuis/syncer/_index.md`

For each, identify keyboard-documented actions whose mouse equivalent (click
a row, click a tab, drag to select range, scroll a pane) is non-obvious and
add a short note or table column. Where a TUI has no meaningful
mouse-specific interactions beyond click-to-focus, a single sentence under
the actions section is enough.

Skip brainstorm — its dedicated docs are still pending.

## Acceptance

- All three home-page mentions updated.
- "seven TUIs" expanded to "seven TUIs (Terminal User Interface)" exactly once.
- TUI index has a brief full-mouse-support callout.
- Each pending TUI doc above either gains mouse-equivalent notes or
  explicitly justifies (in the doc itself) that the TUI is keyboard-driven
  with click-to-focus only.
