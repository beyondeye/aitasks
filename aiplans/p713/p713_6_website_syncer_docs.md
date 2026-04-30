---
Task: t713_6_website_syncer_docs.md
Parent Task: aitasks/t713_ait_syncer_tui_for_remote_desync_tracking.md
Sibling Tasks: aitasks/t713/t713_7_manual_verification_syncer_tui.md
Archived Sibling Plans: aiplans/archived/p713/p713_1_desync_state_helper.md, aiplans/archived/p713/p713_2_syncer_entrypoint_and_tui.md, aiplans/archived/p713/p713_3_sync_actions_failure_handling.md, aiplans/archived/p713/p713_4_tmux_switcher_monitor_integration.md, aiplans/archived/p713/p713_5_permissions_and_config.md, aiplans/archived/p713/p713_8_extract_sync_action_runner.md
Base branch: main
plan_verified:
  - claudecode/opus4_7_1m @ 2026-04-30 15:50
---

# t713_6 — Website docs for `ait syncer`

## Context

Parent **t713** added the `ait syncer` TUI plus integrations:
- `lib/desync_state.py` — shared snapshot helper (t713_1).
- `aitask_syncer.sh` + `syncer/syncer_app.py` — entrypoint and TUI shell (t713_2).
- `s/u/p/a` actions + agent escape hatch (t713_3).
- `tui_registry`, switcher binding `y`, `ait ide` autostart, monitor/minimonitor desync line (t713_4).
- Permission whitelist + `seed/project_config.yaml` `tmux.syncer.autostart` block (t713_5).
- Shared `lib/sync_action_runner.py` (t713_8).

This child writes the user-facing website documentation: a new dedicated Syncer TUI page plus targeted edits to existing pages that list TUIs, switcher shortcuts, `ait ide` autostart, the monitor/minimonitor classification, and `project_config.yaml` keys.

**CLAUDE.md "Documentation Writing" applies:** describe current behavior only — no "previously" / "earlier" / "this corrects" framing.

## Verified state of code (verify-mode read, 2026-04-30)

- `aitask_syncer.sh` exists and dispatches to `syncer/syncer_app.py`.
- `syncer_app.py`: `BINDINGS` are `r` (refresh), `s` (sync data), `u` (pull main), `p` (push main), `a` (resolve with agent, hidden), `f` (toggle fetch), `q` (quit). Default `--interval 30`, `--no-fetch` available. Refs displayed: `main` and `aitask-data` only.
- `sync_failure_screen.py`: modal offers **Launch agent to resolve** / **Dismiss** when sync/pull/push fails.
- `lib/tui_switcher.py`: binding `y` on `action_shortcut_syncer`; switcher modal renders a desync info line via `_render_desync_line` (30s TTL cache; subprocesses `desync_state.py snapshot --format lines`).
- `aitask_ide.sh`: `read_syncer_autostart()` parses `tmux.syncer.autostart`, `ensure_syncer_window()` creates a singleton `syncer` window when the flag is `true`. Default `false`.
- `seed/project_config.yaml` lines 213–231: documented `tmux.syncer.autostart` block with the `false` default.
- `monitor/desync_summary.py` + bar wiring in `monitor_app.py` and `minimonitor_app.py`.
- `pypy.md:41` lists `Syncer | ait sync` — the command should be `ait syncer`.
- Hugo extended 0.159.1 is installed; `hugo build --quiet` from `website/` returns 0.

## Files to modify and create

### NEW: `website/content/docs/tuis/syncer/_index.md`

Dedicated Syncer TUI page. Frontmatter:

```yaml
---
title: "Syncer"
linkTitle: "Syncer"
weight: 40
description: "TUI for tracking remote desync state of main and aitask-data"
maturity: [stabilizing]
depth: [intermediate]
---
```

Weight `40` places the page after Stats (`35`) in the TUI sidebar.

Sections:

1. **Purpose** — visible remote desync tracking for `main` and `aitask-data`. Shows which refs are ahead/behind origin and exposes pull/push/sync actions plus an agent-resolution escape hatch when an action fails.

2. **Launching** — `ait syncer` (manual) or auto-launched by `ait ide` when `tmux.syncer.autostart: true`.

3. **Layout** — header / branches `DataTable` (Branch, Status, Ahead, Behind, Last refresh) / detail panel showing remote commit subjects and changed paths for the selected ref / footer.

4. **Polling and refresh** — 30s default tick, `r` for immediate refresh, `f` to toggle `git fetch` on/off, `--interval SECS` and `--no-fetch` CLI flags. Subtitle bar shows the active interval and fetch state.

5. **Actions** —
   - `s` — Sync `aitask-data` via `ait sync --batch`. Auto-merges frontmatter conflicts; on unresolved conflict opens an interactive sync screen.
   - `u` — Pull `main` with `git pull --ff-only` (refuses on a dirty tree or non-`main` HEAD).
   - `p` — Push `main` to `origin main:main`.
   - `a` — Re-open the most recent failure modal to launch a resolution agent.

6. **Failure handling** — when a sync/pull/push fails, a modal shows Branch / Command / Status / Output (tail) with two buttons: **Launch agent to resolve** opens an `AgentCommandScreen` that dispatches a code agent in a sibling tmux pane (named `agent-syncfix-<ref>`) with a prompt describing the failure; **Dismiss** closes the modal. The most recent failure stays available via `a`.

7. **TUI switcher integration** — press `y` from any switcher-aware TUI (board, monitor, minimonitor, codebrowser, settings, brainstorm, syncer itself) to focus or open the syncer window. The switcher modal also shows a compact desync summary for the selected session.

8. **`ait ide` autostart** —
   ```yaml
   # aitasks/metadata/project_config.yaml
   tmux:
     syncer:
       autostart: true
   ```
   When `true`, `ait ide` opens a singleton `syncer` window alongside the `monitor` window. Default is `false` (key omitted or `false`).

9. **Relationship to `ait sync`** — `ait sync` is the underlying CLI that the syncer's `s` action calls in batch mode. Cross-link to [`ait sync`]({{< relref "/docs/commands/sync" >}}) for the full sync protocol, auto-merge rules, and exit codes.

10. **Desync summary in monitor and TUI switcher** — monitor and minimonitor surface a one-line desync indicator in their session bar (e.g., `· desync: aitask-data 3↓`). The TUI switcher shows the per-session summary for the selected session.

11. **Configuration** — table of relevant `project_config.yaml` keys:

    | Key | Type | Default | Description |
    |-----|------|---------|-------------|
    | `tmux.syncer.autostart` | bool | `false` | When `true`, `ait ide` opens a singleton `syncer` window inside the project session. |

    Cross-link to [Settings]({{< relref "/docs/tuis/settings" >}}) and [Monitor reference]({{< relref "/docs/tuis/monitor/reference" >}}) for the full `tmux.*` schema.

12. **Trailing cross-link** — "Next: Stats" or back to TUIs index, mirroring the convention of other TUI pages.

### MODIFIED: `website/content/docs/tuis/_index.md`

- "Available TUIs" list (lines 14–22): insert a `**[Syncer](syncer/)** (`ait syncer`) — Tracks remote desync state for `main` and `aitask-data`, with pull/push/sync actions and an agent-based escape hatch when an action fails.` row, ordered after Stats.
- TUI switcher description (line 28): include `**`y`** for syncer in the shortcut examples (the line already names `b` for board and `n` for create-task).

### MODIFIED: `website/content/docs/installation/terminal-setup.md`

- Line 39 lists switcher-aware TUIs as "`ait board`, `ait monitor`, `ait minimonitor`, `ait codebrowser`, `ait settings`, `ait brainstorm`". Append `, `ait syncer`` to that list.
- "Without tmux you lose" list (line 83): no change (still TUI switcher, same key).

### MODIFIED: `website/content/docs/tuis/monitor/_index.md`

- Line 49 (TUIs classification examples) currently reads "(board, codebrowser, settings, monitor, minimonitor, brainstorm) or start with `brainstorm-`". Update to also include `syncer` and `stats`. (The existing list is incomplete — `stats` is also classified — adding both keeps the doc in sync with the TUI registry; describe current behavior.)
- Line 69 (switcher overlay TUI list) currently reads "(board, monitor, minimonitor, codebrowser, settings, brainstorm)". Update to also include `syncer` and `stats`, matching what the registry produces.
- Add a single sentence near the layout description (around the session-bar bullet, line 38) noting the optional desync suffix surfaced by syncer integration: e.g., "When `aitask-data` or `main` is behind origin, the session bar appends a compact desync summary (e.g., `· desync: aitask-data 3↓`); see [Syncer]({{< relref "/docs/tuis/syncer" >}})."

### MODIFIED: `website/content/docs/tuis/monitor/reference.md`

- Line 68 (TUI classification): "board, codebrowser, settings, brainstorm, monitor, minimonitor, stats" → add `syncer`.
- Line 110+ Configuration YAML example: add a commented `# syncer: { autostart: true }` example block under `tmux:` to mirror `seed/project_config.yaml`. (Keep example minimal.)
- Line 131+ keys table: add a new row:
  | `tmux.syncer.autostart` | bool | `false` | When `true`, `ait ide` opens a singleton `syncer` window inside the project session. |
- Line 141 (`tui_window_names` defaults): "(board, codebrowser, settings, brainstorm, monitor, minimonitor, stats)" → add `syncer`.
- "Related Commands and TUIs" table at the bottom: add a row for `ait syncer` linking to the new Syncer page.

### MODIFIED: `website/content/docs/tuis/minimonitor/_index.md`

- Add one short sentence near the relationship table (after line 32) noting the desync suffix in the bar text and cross-linking to [Syncer]({{< relref "/docs/tuis/syncer" >}}).

### MODIFIED: `website/content/docs/tuis/board/how-to.md`

- Line 325 currently reads "jump to another integrated TUI (Monitor, Code Browser, Settings, a running code agent window, or a brainstorm session)". Append `, or the Syncer window`.

### MODIFIED: `website/content/docs/installation/pypy.md`

- Line 41 currently reads `| Syncer         | `ait sync`        |`. Update the command cell to ``ait syncer``.

### MODIFIED: `website/content/docs/commands/sync.md`

- After the "Data Branch Mode" section (around line 102), add a small "See also" block:
  - "For an interactive view of remote desync state and one-keystroke pull/push/sync actions across `main` and `aitask-data`, see the [Syncer TUI]({{< relref "/docs/tuis/syncer" >}})."

### MODIFIED: `website/content/docs/commands/_index.md`

- TUI table (the section starting "### TUI"): add a row `| [\`ait syncer\`](../tuis/syncer/) | Open the remote-desync syncer TUI |`.

## Verification

### Build
- `cd website && hugo build --gc --minify` — must succeed with exit 0 (Hugo 0.159.1 + Docsy already verified working in this repo). Capture the build log; warn on any new "REF_NOT_FOUND" / `relref` errors.

### Static checks
- `grep -rn '`ait sync`' website/content/docs/installation/pypy.md` — must return zero matches in the Syncer table row after the fix.
- `grep -rn 'ait syncer' website/content/docs/` — must include the new page plus the table/list updates.
- `find website/content/docs/tuis/syncer -type f` — must list `_index.md`.
- Open the rendered site (`./serve.sh` from `website/`, then http://localhost:1313) and confirm:
  - The Syncer page appears in the TUIs sidebar between Stats and any later items.
  - All `relref` cross-links resolve (no `404` or `REF_NOT_FOUND` warnings in the build log).
  - Layout reads naturally — short paragraphs, table renders, code fences render.

### Manual inspection
- The new page covers the eight items required by the parent task: command, purpose, branches displayed, polling/refresh, sync relationship, pull/push actions and failure handling, switcher key `y`, `tmux.syncer.autostart`.
- No "previously" / "earlier" / "we used to" wording anywhere in the changes (CLAUDE.md rule).

## Out of scope (handled or deferred elsewhere)

- Manual aggregate verification of the syncer behavior across child tasks → sibling **t713_7**.
- A blog post announcing the syncer in `website/content/blog/` is not part of this task; it is created at release-cut time via `aitask-changelog`.

## Reference: Step 9 (Post-Implementation)

After Step 8 commits land:
- `verify_build` (if configured) runs.
- `./.aitask-scripts/aitask_archive.sh 713_6` archives the task and plan, releases the lock, removes from parent's `children_to_implement`, commits.
- `./ait git push` after archival.
