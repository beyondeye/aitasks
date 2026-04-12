---
priority: medium
effort: low
depends: [t519_4]
issue_type: documentation
status: Implementing
labels: [website, tmux, aitask_monitor, documentation]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-04-12 15:16
updated_at: 2026-04-12 17:44
---

## Context

Part of t519 (website docs rewrite for tmux integration). `ait minimonitor` is a narrow (~40 col) sidebar variant of `ait monitor` that shows only running code agents with idle status indicators. It is auto-spawned after launching an agent from the board (via `maybe_spawn_minimonitor` in `agent_launch_utils.py`) and has a single-instance guard. It has **no documentation** currently.

This child creates `tuis/minimonitor/` with two pages (no reference page — minimonitor is simpler than monitor, so `_index.md` + `how-to.md` are sufficient).

## Key Files to Modify

All NEW files under `website/content/docs/tuis/minimonitor/`:

- `_index.md` — overview.
- `how-to.md` — usage guide.

## Reference Files for Patterns

- `website/content/docs/tuis/board/_index.md` + `how-to.md` — structural model.
- `.aitask-scripts/monitor/minimonitor_app.py` — source of truth for key bindings, behavior.
- `.aitask-scripts/aitask_minimonitor.sh` — launcher with single-instance guard (lines 43–50).
- `.aitask-scripts/lib/agent_launch_utils.py` — `maybe_spawn_minimonitor` auto-spawn logic.

## Implementation Plan

### Step 1 — Directory + front-matter

Create `website/content/docs/tuis/minimonitor/`.

Front-matter pattern (check sibling weights before committing to a number):

```yaml
---
title: "Minimonitor"
description: "Narrow sidebar variant of ait monitor, showing only code agents"
weight: <pick after t519_4's monitor weight — minimonitor should appear right after monitor>
---
```

Same Hugo notes as t519_4: do NOT add `aliases:`, pick `weight:` deliberately.

### Step 2 — `_index.md` content

- **Purpose** — compact sidebar variant of monitor. Narrow (~40 col), agents-only, designed to sit alongside a code agent pane.
- **When to use** — you want a constant sidebar view of active agents while the rest of your tmux window is used for other TUIs or code.
- **Relationship to monitor** — minimonitor shows a subset of what monitor shows, in a narrower layout. They can coexist in the same session; the auto-spawn logic ensures only one minimonitor per session (single-instance guard).
- **Auto-spawn behavior** — when you launch an agent from the board via the agent command screen, the board calls `maybe_spawn_minimonitor`, which creates a minimonitor in a side pane if one isn't already running. Link to the monitor docs for the full dashboard variant.
- Screenshot placeholder: `<!-- TODO screenshot: aitasks_minimonitor_main_view.svg -->`

### Step 3 — `how-to.md` content

1. **Starting minimonitor**
   - Auto-spawn from the board (default, via agent launch).
   - Manual: `ait minimonitor` from inside a tmux session.
   - Note the single-instance guard: subsequent `ait minimonitor` calls attach to the existing instance instead of creating a second one.

2. **Navigating**
   - `Tab` — cycle agents.
   - `s` — switch focus to the selected agent's pane.
   - `i` — show task info for the selected agent.
   - `j` — open the TUI switcher (same as monitor and all other TUIs).
   - `r` — refresh the agent list.
   - `q` — quit minimonitor.

3. **Pairing minimonitor with monitor**
   - It's fine to have both running at once. A typical layout:
     - Main window: monitor dashboard.
     - Sidebar pane in the same window: minimonitor.
     - Separate windows: code agents + TUIs (board, codebrowser, etc.).

4. **Key bindings quick reference table** (small, since reference.md is not being created).

## Verification

- `cd website && hugo --gc --minify` builds cleanly.
- `./serve.sh` — navigate `/docs/tuis/minimonitor/` and verify both pages render.
- Sidebar weight places minimonitor right after monitor.
- No broken internal links (e.g., to monitor docs, board docs, `ait ide`).

## Notes for sibling tasks

This child is independent of the others content-wise. Auto-sibling deps serialize it after t519_4 (monitor docs), which is convenient because this page cross-references them.

## Step 9 — Post-Implementation

Part of t519 — follow the shared task-workflow post-implementation flow.
