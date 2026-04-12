---
Task: t519_5_create_minimonitor_tui_docs.md
Parent Task: aitasks/t519_rewrite_of_website_for_tmux_integration.md
Sibling Tasks: aitasks/t519/t519_1_*.md, aitasks/t519/t519_2_*.md, aitasks/t519/t519_3_*.md, aitasks/t519/t519_4_*.md, aitasks/t519/t519_6_*.md
Archived Sibling Plans: aiplans/archived/p519/p519_1_*.md, aiplans/archived/p519/p519_2_*.md, aiplans/archived/p519/p519_3_*.md, aiplans/archived/p519/p519_4_*.md
Worktree: (current branch)
Branch: main
Base branch: main
---

# Plan — t519_5: Create `tuis/minimonitor/` docs

## Goal

Create `website/content/docs/tuis/minimonitor/` with two pages (`_index.md`, `how-to.md`) that document the `ait minimonitor` TUI — a narrow (~40 col) sidebar variant of monitor showing only code agents.

## Step-by-step implementation

### Step 1 — Inspect siblings + sources

```bash
cat website/content/docs/tuis/monitor/_index.md
cat website/content/docs/tuis/monitor/how-to.md
```

The monitor docs from t519_4 are the primary pattern. Keep terminology consistent.

Read source of truth:
- `.aitask-scripts/monitor/minimonitor_app.py` — app class, BINDINGS, behavior.
- `.aitask-scripts/aitask_minimonitor.sh` — launcher, single-instance guard (lines 43–50).
- `.aitask-scripts/lib/agent_launch_utils.py` `maybe_spawn_minimonitor` — auto-spawn logic from the board.

### Step 2 — Create directory

```bash
mkdir -p website/content/docs/tuis/minimonitor
```

### Step 3 — Write `_index.md`

Front-matter (pick `weight:` right after monitor's):

```yaml
---
title: "Minimonitor"
linkTitle: "Minimonitor"
description: "Compact sidebar variant of the ait monitor TUI"
weight: <monitor_weight + 1 or similar>
---
```

No `aliases:` unless verified unique.

Body outline:

- **H2 Purpose** — narrow sidebar view of running code agents. Meant to sit alongside a code pane while you work.
- **H2 Relationship to monitor** — minimonitor is a subset of monitor: agents-only, no preview panel, ~40 col wide. They can coexist (main window has monitor; a side pane runs minimonitor).
- **H2 Auto-spawn from the board** — when you pick a task and launch an agent from the board, the `maybe_spawn_minimonitor` helper creates a minimonitor automatically if one isn't already running in the session. The single-instance guard prevents duplicates.
- **H2 When to use** — you want a persistent sidebar view of active agents without the full monitor dashboard taking over a window.
- HTML comment placeholder: `<!-- TODO screenshot: aitasks_minimonitor_main_view.svg -->`
- **H2 Next steps** — link to how-to and to the main monitor docs.

### Step 4 — Write `how-to.md`

Body outline:

1. **H2 Starting minimonitor**
   - **Auto-spawn (default):** launch an agent from the board; minimonitor appears automatically in a side pane.
   - **Manual:** `ait minimonitor` from inside tmux.
   - **Single-instance guard:** repeated `ait minimonitor` calls attach to the existing instance instead of spawning a new one.

2. **H2 What you see**
   - Narrow sidebar with a list of code agents.
   - Each agent shows a status/idle indicator.
   - No preview panel (that's in the full monitor).

3. **H2 Navigating**
   - `Tab` — cycle agents.
   - `s` — switch focus to the selected agent's pane (make it the active tmux pane).
   - `i` — show task info for the selected agent.
   - `j` — open the TUI switcher (same as all main TUIs).
   - `r` — refresh the agent list.
   - `q` — quit minimonitor.

   Verify bindings against `minimonitor_app.py` BINDINGS list at implementation time.

4. **H2 Pairing minimonitor with monitor**
   A typical layout while working:
   - Main tmux window: monitor dashboard.
   - Sidebar pane in the same window: minimonitor.
   - Other windows: board, codebrowser, settings, brainstorm — all reachable via `j`.

5. **H2 Key bindings quick reference**
   Small table summarizing the bindings. No separate reference.md file for minimonitor — it's simple enough that `_index.md` + `how-to.md` are sufficient.

### Step 5 — Verification

```bash
cd website && hugo --gc --minify
cd website && ./serve.sh
```

- Both pages render.
- Sidebar weight places minimonitor right after monitor.
- Links to monitor docs, board docs, and `ait ide` resolve.
- No broken links, no missing-image warnings.

### Step 6 — Final plan notes

Add Final Implementation Notes before archival:
- Final `weight:` value.
- Any BINDINGS discovered in `minimonitor_app.py` that weren't in the outline.
- Single-instance guard details that were relevant to the how-to.
- Notes for t519_6: any `/docs/tuis/minimonitor/` URLs that must be linked exactly from `tuis/_index.md`.

## Files to create

- `website/content/docs/tuis/minimonitor/_index.md`
- `website/content/docs/tuis/minimonitor/how-to.md`

## Out of scope

- A separate `reference.md` file — minimonitor is simple enough to document in two pages.
- Screenshots (follow-up task).
- Updating `tuis/_index.md` to link to minimonitor (that's t519_6).
