---
Task: t771_document_tui_full_mouse_support_on_website.md
Base branch: main
plan_verified: []
---

# Plan: Document TUI full mouse support on the website (t771)

## Context

All aitasks Textual TUIs support full mouse interaction (click, drag, scroll), but the website only mentions this implicitly. The user wants:

1. The home page to explicitly state TUIs have full mouse support, in every place TUIs are mentioned.
2. The "take the tour" heading to expand the acronym: "seven TUIs" → "seven TUIs (Terminal User Interface)".
3. A pass across the TUI docs so every documented keyboard action also notes its mouse-equivalent where applicable.

Board and Code Browser docs already cover mouse interactions. The remaining TUIs (Monitor, Minimonitor, Settings, Stats, Syncer) have **no** mouse mentions today. Brainstorm has no docs yet ("documentation is pending") and is skipped.

## Files to edit

### 1. `website/content/_index.md` (home page)

- **Line 10** (hero `lead`/`description`): Add "with full mouse support" to the description. Final:
  > "Kanban board, code browser, agent monitoring, and AI-enhanced git workflows — all in one tmux session, with full mouse support. Press `j` to hop between TUIs without leaving the terminal."
- **Line 23** (Agentic IDE feature card):
  > "Kanban Board, Code Browser, Monitor, Brainstorm, and Settings — all in one tmux session via `ait ide`, with full mouse support. Press `j` to hop between TUIs without ever leaving the terminal."
- **Line 55** (take-the-tour `<p>` line): expand the acronym and mention mouse support:
  > "Seven TUIs (Terminal User Interface) share a single tmux session, with full mouse support. Click any of them to dive in."

### 2. `website/content/docs/tuis/_index.md` (TUI index)

Add a single sentence to the existing first paragraph (line 12) stating that all TUIs support full mouse interaction. Final paragraph:

> The aitasks framework includes several terminal-based user interfaces (TUIs) built with [Textual](https://textual.textualize.io/), all with **full mouse support** (click, drag, scroll). Together they form the core of the ait tmux-based development environment: you launch them inside a single tmux session (typically via [`ait ide`]({{< relref "/docs/installation/terminal-setup" >}})) and hop between them with a single keystroke.

### 3. `website/content/docs/tuis/monitor/how-to.md`

Insert a new short section right after "How to Read the Pane List" titled **"Mouse support"** with the following per-action mouse equivalents (covers actions documented later in the same file):

- **Click a pane card** — focus that card in the pane list (replaces Up/Down navigation).
- **Click inside the preview pane** — move focus into the preview zone (replaces Tab to switch zones); subsequent keystrokes are forwarded to the underlying tmux pane.
- **Scroll wheel inside any zone** — scroll the pane list or preview content.
- Buttons in confirmation dialogs (`k` kill, `n` next-sibling) are clickable.

Single short note — no per-key table; the existing keyboard sections stay authoritative. End with: "All keyboard actions documented below remain available."

### 4. `website/content/docs/tuis/monitor/reference.md`

After the existing **Keyboard Shortcuts** subsections, append a new subsection **#### Mouse Interactions** with a short table:

| Action | Effect |
|--------|--------|
| Click a card in the pane list | Focus that card |
| Click inside the preview pane | Move focus into the preview zone |
| Scroll wheel | Scroll the focused zone |
| Click dialog buttons | Activate the action (Confirm/Cancel on kill, next-sibling, task-info dialogs) |

### 5. `website/content/docs/tuis/minimonitor/how-to.md`

Insert a short **### Mouse support** section near the top (after "How to Read the Agent List"):

- **Click an agent card** — focus that card (replaces Up/Down).
- **Scroll wheel** — scroll the agent list.
- Dialog buttons (task info, switcher) are clickable.

Also add a "Mouse" row to the **Key Bindings Quick Reference** table at the bottom referencing the new section, e.g. an introductory line above the table: "All actions below are also available via mouse — see [Mouse support](#mouse-support)."

### 6. `website/content/docs/tuis/settings/how-to.md`

Add a short **## Mouse support** section near the top (after the title/frontmatter, before "Change the Default Model for an Operation"):

- **Click a tab name** in the tab bar — switch to that tab (replaces the `a` / `b` / `c` / `t` / `m` / `p` shortcuts).
- **Click a field row** — focus it; press Enter/Space to edit/cycle (or use the on-screen Save/Commit buttons, which are clickable).
- **Click "Save Profile" / "Commit" / "Save Board Settings" / "Save Project Config"** — visible buttons are clickable, no keyboard equivalent required.
- **Scroll wheel** — scroll long tab content (Profiles, Models tabs).

### 7. `website/content/docs/tuis/settings/reference.md`

Insert a **### Mouse Interactions** subsection inside the **## Keyboard Shortcuts** section (right after **### Within Tabs**) with a brief table:

| Action | Effect |
|--------|--------|
| Click a tab name | Switch to that tab |
| Click a field row | Focus the row (Enter/Space then edits) |
| Click action buttons (Save, Commit, New Profile, etc.) | Activate the button |
| Scroll wheel | Scroll the focused tab content |

### 8. `website/content/docs/tuis/stats/_index.md`

Insert a short **## Mouse support** section right before the existing **## Navigating** section (line 81):

- **Click a pane name** in the sidebar — show that pane on the right (mirrors Up/Down highlighting).
- **Click a layout name** in the layout picker — highlight; double-click (or press Enter) to activate.
- **Scroll wheel** — scroll the sidebar, layout picker, or chart content.
- Buttons in the new-/edit-/delete-layout dialogs are clickable.

### 9. `website/content/docs/tuis/syncer/_index.md`

Insert a short **## Mouse support** section between "Polling and refresh" and "Actions" (around line 46-47):

- **Click a row in the Branches table** — select that ref (mirrors Up/Down).
- **Scroll wheel** — scroll the detail panel.
- **Click buttons in the failure modal** — Launch agent / Dismiss are both clickable.

## Out of scope

- Board and Code Browser docs already cover mouse usage; no edits there.
- Brainstorm TUI has no website docs yet.
- No screenshots or asset changes — text edits only.

## Verification

After editing:

1. Run `grep -n "with full mouse support" website/content/_index.md` — expect three matches (lines 10, 23, 55 area).
2. Run `grep -n "Terminal User Interface" website/content/_index.md` — expect one match at the take-the-tour line.
3. Run `grep -n "full mouse support" website/content/docs/tuis/_index.md` — expect one match.
4. Run `grep -rln -i "mouse support\|Mouse Interactions\|## Mouse" website/content/docs/tuis/` — expect monitor (how-to + reference), minimonitor/how-to, settings (how-to + reference), stats/_index, syncer/_index in the output (plus the existing codebrowser/reference Mouse Interactions section).
5. Optional: `cd website && ./serve.sh` and visually scan the home page + each TUI page in a browser. Mark this as a manual check — not required if greps pass and the build succeeds.
6. Run `cd website && hugo --gc --minify 2>&1 | tail -20` to confirm the site still builds with no broken-link warnings.

## Notes

- All edits are pure markdown content; no shortcodes added or removed.
- All wording uses positive present-tense statements per the CLAUDE.md doc convention ("describe current state only").
- No frontmatter/metadata fields touched.
- Step 9: post-implementation merge / archive per task-workflow.
