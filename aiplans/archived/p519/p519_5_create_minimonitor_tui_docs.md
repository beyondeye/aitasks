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

## Final Implementation Notes

- **Actual work done:** Created two new files under `website/content/docs/tuis/minimonitor/`:
  - `_index.md` — Purpose, Relationship to monitor (comparison table), Auto-spawn from the board, When to use. Front-matter `weight: 17`, `linkTitle: "Minimonitor"`.
  - `how-to.md` — 12 `### How to ...` sections: Start minimonitor, Read the agent list, Navigate the agent list, Focus the sibling agent pane, Send Enter to the sibling agent, Switch to the selected agent, Show task info, Jump to another TUI, Refresh, Quit, Pair with monitor, Configure auto-spawn, plus a Key Bindings quick reference table.
- **Weight chosen:** `17`. Verified sidebar order via generated HTML: board(10) → monitor(15) → **minimonitor(17)** → codebrowser(20) → settings(30).
- **Deviations from plan:**
  - **Tab binding description corrected.** The original plan said Tab "cycles agents"; the actual behavior in `minimonitor_app.py:93-101` is that Tab focuses the sibling tmux pane (moves tmux focus to the first non-minimonitor pane in the same window). Up/Down are the actual in-list navigation keys. The how-to documents this correctly and also documents the Enter-to-sibling-pane shortcut (not in the original outline).
  - **Single-instance guard corrected.** The plan said repeated `ait minimonitor` invocations "attach to the existing instance". In reality, `aitask_minimonitor.sh:43-51` silently exits if another monitor or minimonitor is running **in the same tmux window** (per-window, not per-session). Documented as such: "prints a short message and exits". The per-window scope is explicitly called out so the user knows they can still have minimonitor split alongside each agent window.
  - **Auto-close behavior added** (not in plan). Minimonitor exits automatically when it is the last pane left in its tmux window, with a 5-second grace period after mount (`_check_auto_close` in `minimonitor_app.py:212-220`). Called out in the "How to Quit" section.
  - **Config keys documented** (not in plan). The auto-spawn helper reads `tmux.minimonitor.auto_spawn` and `tmux.minimonitor.width` from `project_config.yaml` (`agent_launch_utils.py:234-243`). Added a "Configuring Auto-Spawn" how-to section covering both keys.
  - **Relationship-to-monitor comparison table** replaced the plan's prose "H2 Relationship to monitor" — easier to scan and reflects the same information more densely.
- **Issues encountered:** None. Build was clean on first attempt (127 pages, zero errors, zero warnings).
- **Key decisions:**
  - Two-file structure per plan — no `reference.md`. The key bindings quick reference at the bottom of `how-to.md` doubles as the reference.
  - Linked to `/docs/tuis/monitor/reference/#configuration` for shared config keys instead of duplicating the full monitor configuration table in minimonitor docs. Only the minimonitor-specific keys (`tmux.minimonitor.auto_spawn`, `tmux.minimonitor.width`) are documented inline.
  - Per project memory `project_diffviewer_brainstorm.md`, `diffviewer` is not mentioned anywhere in the new pages.
  - Followed sibling t519_4's conventions: title-case section headings, `{{< relref >}}` for internal links, HTML comments for screenshot placeholders.
- **Notes for sibling tasks:**
  - **t519_6 (TUI switcher docs + footer label):** Exact relref paths for the new minimonitor pages:
    - `{{< relref "/docs/tuis/minimonitor" >}}` — overview
    - `{{< relref "/docs/tuis/minimonitor/how-to" >}}` — how-to guides
    - The `how-to.md` page has an H3 anchor `#pairing-minimonitor-with-monitor` that t519_6 can link from the tmux integration sections of other TUIs.
    - `tuis/_index.md` landing page still needs a mention for both monitor (from t519_4) and minimonitor (this task) — that remains part of t519_6's scope.
  - The `maybe_spawn_minimonitor` logic only fires when the window name starts with `agent-`; t519_6 should reflect this if it touches the agent launch flow docs.
- **Build verification:** `hugo --gc --minify` reports 127 pages (up from 124 for monitor-only), zero errors, zero warnings. HTML comment screenshot placeholders are stripped by the minifier (verified: `grep -c SCREENSHOT public/docs/tuis/minimonitor/*.html` returns 0 for both files). All internal `relref` links resolve (board, monitor, monitor/reference, monitor/how-to, settings).

## Post-Review Changes

### Change Request 1 (2026-04-12 19:15)

- **Requested by user:** Reframe the docs so auto-spawn is clearly the primary mode (not just a "from the board" side-note), call out that auto-spawn happens from board AND codebrowser AND monitor's next-sibling (`n`) command, and document that minimonitor auto-despawns when its companion agent pane exits.
- **Verification:** `grep maybe_spawn_minimonitor .aitask-scripts/**/*.py` confirmed the helper is called from `board/aitask_board.py` (two sites), `codebrowser/codebrowser_app.py`, `codebrowser/history_screen.py`, `monitor/monitor_app.py` (the `n`/next-sibling handler at `monitor_app.py:1012`), and `lib/tui_switcher.py` (explore launch). The auto-despawn behavior is implemented in `minimonitor_app.py:212-220` (`_check_auto_close`) and documented accordingly.
- **Changes made:**
  - `_index.md`: added a lead paragraph calling out auto-spawn as the primary mode. Replaced "Auto-spawn from the board" section with "Auto-spawn and auto-despawn" covering all four call sites (board, codebrowser, monitor's `n`, TUI switcher explore launch) and the auto-despawn lifecycle. Added a "When to launch manually" section listing the rare cases where `ait minimonitor` should be invoked directly.
  - `how-to.md`: replaced the single "How to Start Minimonitor" section with two sections: "How Minimonitor Is Auto-Spawned" (primary — lists all launch points and the auto-despawn behavior) and "How to Start Minimonitor Manually" (escape hatch). Updated "How to Quit" to frame manual quit as rare because auto-despawn handles the common case. Updated the "Configuring Auto-Spawn" intro to mention all call sites.
- **Files affected:** `website/content/docs/tuis/minimonitor/_index.md`, `website/content/docs/tuis/minimonitor/how-to.md`
