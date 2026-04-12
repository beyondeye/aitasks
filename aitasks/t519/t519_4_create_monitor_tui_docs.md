---
priority: high
effort: medium
depends: [t519_3]
issue_type: documentation
status: Ready
labels: [website, tmux, aitask_monitor, documentation]
created_at: 2026-04-12 15:16
updated_at: 2026-04-12 15:16
---

## Context

Part of t519 (website docs rewrite for tmux integration). `ait monitor` is the orchestrator TUI of the new tmux-based IDE workflow: it classifies tmux panes into agents/TUIs/others, shows a live preview of focused panes, forwards keystrokes interactively, and handles session-name fallback dialogs. Despite being the centerpiece of the workflow, it has **zero documentation** in the website.

This child creates the `tuis/monitor/` documentation directory with three pages, modeled on the existing `tuis/board/` structure.

## Key Files to Modify

All NEW files under `website/content/docs/tuis/monitor/`:

- `_index.md` — overview of ait monitor.
- `how-to.md` — task-oriented usage guide.
- `reference.md` — complete key bindings + configuration reference.

## Reference Files for Patterns

- `website/content/docs/tuis/board/_index.md` — structural model for the monitor `_index.md`.
- `website/content/docs/tuis/board/how-to.md` — structural model for how-to.
- `website/content/docs/tuis/board/reference.md` — structural model for reference.
- `.aitask-scripts/monitor/monitor_app.py` — source of truth. Read for:
  - Pane classification logic (agents / TUIs / others)
  - Key bindings (Tab, Up/Down, Enter, `j`, `q`)
  - Session-name resolution (lines 1019–1074) and `SessionRenameDialog` (lines 118–165, 402–435)
- `.aitask-scripts/monitor/tmux_monitor.py` — core library. `discover_panes()` + related helpers.
- `.aitask-scripts/lib/tui_switcher.py` — the `j` shortcut that opens the TUI switcher from monitor.

## Implementation Plan

### Step 1 — Directory + front-matter

Create `website/content/docs/tuis/monitor/` directory.

Each file gets Docsy front-matter modeled on `tuis/board/`:

```yaml
---
title: "Monitor"
description: "tmux pane monitor and orchestrator TUI for ait"
weight: <pick deliberately — see Hugo notes below>
---
```

**Hugo notes:**
- `weight:` — check `tuis/board/_index.md`, `tuis/codebrowser/_index.md`, `tuis/settings/_index.md` for existing weights and pick a value that places monitor prominently (e.g., if board is 10, monitor could be 15 so it appears second). Do not reuse an existing sibling's weight.
- **Do NOT add `aliases:`** unless you've verified they don't collide with any other page's aliases.

### Step 2 — `_index.md` content

Outline:
- **Purpose** — what monitor is, why you want it, relationship to `ait ide` (the normal launcher) and to minimonitor.
- **When to use** — you're running inside tmux and want a single dashboard for all running agents and TUIs.
- **At a glance** — bulleted list of what monitor shows: agent list, TUI list, other panes, live preview with keystroke forwarding.
- Screenshot placeholder: `<!-- TODO screenshot: aitasks_monitor_main_view.svg — the monitor dashboard showing agents and TUIs -->`
- Links to how-to and reference.

### Step 3 — `how-to.md` content

Task-oriented guide. Outline:

1. **Starting monitor**
   - Recommended: via `ait ide` (from t519_1) which starts tmux and launches monitor in one step.
   - Standalone: from inside an existing tmux session, run `ait monitor`.
   - Explain that the session-name fallback dialog fires if the current tmux session name doesn't match the configured `default_session` — link to the reference page for details.

2. **Understanding the panels**
   - The main window has two zones: the session list (top/left) and the preview panel (right).
   - Session list categorizes panes: **agents** (code agent windows), **TUIs** (board, codebrowser, settings, brainstorm), **others** (shells, logs).
   - Preview panel shows live content of the focused pane and forwards keystrokes directly to tmux.

3. **Navigating**
   - `Tab` — cycle zones (session list ↔ preview).
   - `Up`/`Down` — navigate within the focused pane list.
   - `Enter` — in the preview, sends an Enter keystroke to the focused pane.
   - In the preview panel, all other keystrokes are forwarded to the pane too — so you can interactively control whatever is running inside.

4. **Jumping to another TUI**
   - Press `j` to open the TUI switcher overlay.
   - Select any known TUI (board, codebrowser, settings, brainstorm, monitor itself, or minimonitor).
   - The switcher either selects an existing tmux window or creates a new one running that TUI.
   - Screenshot placeholder: `<!-- TODO screenshot: aitasks_tui_switcher_dialog.svg -->`

5. **Session-name mismatch**
   - Briefly describe what happens if monitor is launched inside a tmux session whose name doesn't match the configured `default_session`: a `SessionRenameDialog` offers to rename.
   - Recommend using `ait ide` instead to avoid this.

6. **Quitting**
   - `q` — quit monitor (the tmux window closes).

### Step 4 — `reference.md` content

Reference-style tables and configuration details:

1. **Key bindings table** — all bindings, with columns: Key | Action | Scope.
   | Key | Action | Scope |
   |-----|--------|-------|
   | `Tab` | Cycle zones | Global |
   | `Up`/`Down` | Navigate pane list | Session list zone |
   | `Enter` | Send Enter to focused pane | Preview zone |
   | `j` | Open TUI switcher | Global |
   | `q` | Quit monitor | Global |
   | (any others discovered in `monitor_app.py`) | ... | ... |

2. **Configuration** — where settings come from:
   - `aitasks/metadata/project_config.yaml` → `tmux.default_session` — the session name monitor uses.
   - `tmux.default_split` — how splits are created.
   - `tmux.prefer_tmux` — whether tmux-based workflows are the default.
   - Cross-link to `ait settings` → Tmux tab for editing via TUI.

3. **Session-name fallback dialog** — describe the `SessionRenameDialog`:
   - Triggered when the current tmux session name differs from the configured `default_session` AND the configured session doesn't already exist.
   - Offers to rename the current session.
   - Avoid entirely by using `ait ide` which always passes an explicit session name.

4. **Pane classification rules** — briefly: which window names count as "agents", "TUIs", or "others". Reference the actual code if the rules are non-obvious. Verify against `tmux_monitor.py` during implementation.

## Verification

- `cd website && hugo --gc --minify` builds cleanly.
- `./serve.sh` — navigate `/docs/tuis/monitor/` and verify:
  - All three pages render (index, how-to, reference).
  - Sidebar weight places monitor where expected relative to board, codebrowser, settings.
  - No broken internal links.
  - HTML comment placeholders are present but invisible in rendered output.
  - No Hugo warnings about missing image files (HTML comments don't trigger this; verify no `{{< static-img >}}` shortcodes were accidentally added).

## Notes for sibling tasks

- This child does NOT depend on t519_1, 2, or 3 at a content level (monitor exists already and can be documented in isolation), but auto-sibling deps will serialize it. That's fine.
- t519_6 will link to these pages from `tuis/_index.md` and from the "tmux integration" sections in other TUI how-tos.

## Step 9 — Post-Implementation

Part of t519 — follow the shared task-workflow post-implementation flow.
