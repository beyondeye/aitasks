---
priority: high
effort: medium
depends: [t519_2]
issue_type: documentation
status: Ready
labels: [website, tmux, documentation]
created_at: 2026-04-12 15:15
updated_at: 2026-04-12 15:15
---

## Context

Part of t519 (website docs rewrite for tmux integration). The current `website/content/docs/getting-started.md` is a 6-step workflow (install, settings, create task, view board, pick, iterate) that never mentions tmux, `ait monitor`, or the new `ait ide` subcommand. It needs to be updated to recommend the tmux-based IDE workflow as the primary path.

Additionally, the docs lack an end-to-end narrative page showing what a daily workflow actually looks like — "open ait ide → see monitor → pick a task → watch agent → switch to codebrowser → review → commit". A new page `workflows/tmux-ide.md` provides that narrative.

## Key Files to Modify

- `website/content/docs/getting-started.md` — update to recommend `ait ide` in step 2 (startup).
- `website/content/docs/workflows/tmux-ide.md` (new) — end-to-end daily workflow walkthrough.

## Reference Files for Patterns

- `website/content/docs/getting-started.md` (current) — the 6-step structure to update.
- `website/content/docs/workflows/_index.md` and any existing workflow pages — for tone, structure, and `weight:` values.
- t519_1 child plan — for `ait ide` command semantics.
- `.aitask-scripts/monitor/monitor_app.py` — to double-check the monitor UI elements described in the workflow narrative.

## Implementation Plan

### Step 1 — Update `getting-started.md`

Revise step 2 (currently "Review settings via TUI") to be: "Start the ait IDE". Show:

```bash
cd /path/to/your/project
ait ide
```

Explain in 1–2 sentences that this starts (or attaches to) the configured tmux session and opens the monitor TUI. Mention the TUI switcher (`j`) as the way to move between board, monitor, codebrowser, settings, and brainstorm.

Then adjust the later steps so they reference the TUI switcher as the way to get to the board, settings, etc. (instead of invoking each command from the shell).

Keep the existing content's spirit but make the tmux/`ait ide` flow the primary path. For users who can't use tmux, add a one-line note pointing to `/docs/installation/terminal-setup/#minimal--non-tmux-workflow`.

Link the new workflow page: "For a full end-to-end walkthrough, see [the tmux IDE workflow](/docs/workflows/tmux-ide/)."

### Step 2 — Create `workflows/tmux-ide.md`

**Front-matter:**

```yaml
---
title: "The tmux IDE workflow"
description: "Daily end-to-end workflow using ait ide, monitor, the TUI switcher, and the code agents."
weight: <pick based on existing workflows siblings>
---
```

Check existing `workflows/` pages before choosing `weight:`. Do NOT add `aliases:` unless verified unique.

**Content outline:**

1. **Intro paragraph** — what this page covers: the daily flow for developers using ait.
2. **Before you start** — prerequisites: tmux installed, `ait setup` run in the project, code agents configured in `ait settings` → Code Agents tab.
3. **Step 1 — Start the IDE**
   - `cd /path/to/project && ait ide`
   - What you see: the `monitor` window with agent list, preview pane, etc.
   - HTML comment placeholder: `<!-- TODO screenshot: aitasks_monitor_main_view.svg -->`
4. **Step 2 — Jump to the board with `j`**
   - Press `j` in monitor — the TUI switcher dialog appears.
   - Select `board` — switches to the board TUI in a new (or existing) tmux window.
   - HTML comment placeholder: `<!-- TODO screenshot: aitasks_tui_switcher_dialog.svg -->`
5. **Step 3 — Pick a task**
   - Press `p` (or whatever the board's pick binding is — verify in `board/aitask_board.py`) to pick a task.
   - The task launches an agent in a new tmux window.
6. **Step 4 — Watch the agent**
   - Press `j` → select `monitor` to return to the monitor. The new agent appears in the agent list.
   - Optionally press `j` → select `minimonitor` for a sidebar view.
7. **Step 5 — Review changes**
   - When the agent finishes, press `j` → select `codebrowser` to browse the diff.
   - Approve or request more changes using the usual review loop.
8. **Step 6 — Commit and iterate**
   - The aitask-pick skill handles commit and archival; walk through briefly.
9. **Navigation reference** — a small table of the key bindings used throughout (`j` = TUI switcher, etc.).

**Screenshots:** all placeholders are HTML comments (not `{{< static-img >}}` shortcodes).

### Step 3 — Cross-link

- Ensure `getting-started.md` links to `/docs/workflows/tmux-ide/`.
- Ensure the new `workflows/tmux-ide.md` links to `/docs/tuis/monitor/`, `/docs/tuis/board/`, `/docs/tuis/codebrowser/`, and `/docs/installation/terminal-setup/`.
- Mention `ait ide` in `getting-started.md` is linked to the terminal-setup page's recommended-workflow section.

## Verification

- `cd website && hugo --gc --minify` builds cleanly with no broken links.
- `./serve.sh` — navigate `/docs/getting-started/` and verify the `ait ide` startup is step 2.
- Navigate `/docs/workflows/tmux-ide/` and verify the new page renders with the correct sidebar weight.
- All cross-links resolve (monitor, minimonitor, codebrowser, settings, terminal-setup).

## Notes for sibling tasks

This child depends on t519_1 (`ait ide` must exist). It creates forward links to `/docs/tuis/monitor/` (t519_4), `/docs/tuis/minimonitor/` (t519_5), and the updated `/docs/tuis/_index.md` (t519_6). Auto-sibling deps serialize correctly since this child runs after t519_2 but before t519_4/5/6.

## Step 9 — Post-Implementation

Part of t519 — follow the shared task-workflow post-implementation flow.
