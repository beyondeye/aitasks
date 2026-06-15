---
priority: medium
effort: medium
depends: []
issue_type: enhancement
status: Implementing
labels: [aitask_monitormini, tmux, tui]
assigned_to: daelyasy@hotmail.com
created_at: 2026-06-15 10:20
updated_at: 2026-06-15 10:28
---

## Goal

Polish the `ait minimonitor` UI/UX with four related changes: spawn the shadow
companion pane on the **left** with a configurable minimum width, reorganize and
tidy the footer keyboard-shortcut hints, remove the refresh shortcut, and expand
the followed-agent task-description area at the top to two lines.

## 1. Shadow pane: spawn left + configurable minimum width

Currently the shadow companion pane (minimonitor `e`) spawns to the **right** of
the minimonitor. It should spawn to the **left**, and have a configurable minimum
width (default **80** columns).

**Touchpoints:**
- `.aitask-scripts/monitor/minimonitor_app.py:941` `action_launch_shadow` —
  builds `TmuxLaunchConfig(...)` (same-window split branch, ~line 978-986) and
  calls `launch_in_tmux`.
- `.aitask-scripts/lib/agent_launch_utils.py:600-615` `launch_in_tmux` split
  branch — currently `split_flag = "-h"`, which places the new pane to the
  **right**. Left placement needs the tmux `-b` (before) flag; the minimum width
  needs `-l <width>`.
- `.aitask-scripts/lib/agent_launch_utils.py:63` `TmuxLaunchConfig` dataclass —
  add fields to carry the new placement/width intent, e.g.
  `split_before: bool = False` and `split_size: int | None = None`. Thread them
  through only from the shadow call site so other `launch_in_tmux` callers are
  unaffected (e.g. the minimonitor self-spawn at lines 800-816 stays a right
  split). Keep the change cleanly scoped — verify blast radius on every
  `launch_in_tmux` / `TmuxLaunchConfig` caller before touching the shared signature.

**New setting `shadow_pane_width` (default 80):**
- Add to the settings schema in `.aitask-scripts/settings/settings_app.py`
  alongside `shadow_same_window` (~line 258), type integer, default 80.
- Add to the seed `tmux:` block in `seed/aitasks/metadata/project_config.yaml`
  (and document the key) plus the live `aitasks/metadata/project_config.yaml`.
- Read it in `action_launch_shadow` via `_load_project_tmux_config`
  (`minimonitor_app.py:1165`), falling back to 80 when unset.

## 2. Footer keyboard-shortcut reorganization

Reorganize the `#mini-key-hints` Static (`minimonitor_app.py:201-207`) into this
layout:
- Line 1: `i:info   q:quit   tab` (tab = focus agent)
- Line 2: `s/↑↓:switch   enter`
- Line 3: `d:detect`
- Line 4: `j:tui switcher   m:full monitor`
- Line 5: `k:kill   n:next   e:shadow` (kept on an extra line so all hints stay
  visible — they were previously interleaved)

Match the existing glyphs/formatting style (e.g. the `d:detect (≈ strip, = raw)`
annotation may be kept or folded in tastefully). Keep wording consistent with the
actual key bindings.

## 3. Remove the refresh shortcut

Remove `r:refresh` entirely:
- Remove the `Binding("r", "refresh", "Refresh", show=False)` at
  `minimonitor_app.py:152`.
- Remove `r:refresh` from the footer hints text.
- Leave `action_refresh` (line 1052) only if it is still invoked by other code
  paths (e.g. timer); otherwise remove it too. Verify before deleting.

## 4. Two-line task description at the top

The followed-agent panel at the top of minimonitor shows the task title on a
single line, truncated to 30 chars (`_own_agent_identity_text`,
`minimonitor_app.py:551-567`). Expand the displayed task description to **two
lines** (increase the character budget and wrap, e.g. ~2×width). The
`.mini-own-card` CSS already uses `height: auto`, so it can grow; the limiting
factor is the truncation logic. Confirm whether the general-list card
(`minimonitor_app.py:540-548`, also 30-char truncated) should match — the request
specifically targets the top/followed-agent description, so default to changing
only that unless it looks inconsistent.

## Notes / cross-agent

- Source of truth is the Claude Code implementation; these are Python TUI + YAML
  config + settings-schema changes, not skill markdown, so no cross-agent skill
  port is implied.
- Follow `aidocs/framework/tmux_gateway.md` — all raw `tmux` calls go through the
  gateway (`lib/tmux_exec.py`); `tests/test_no_raw_tmux.sh` enforces it. Adding
  `-b`/`-l` flags happens inside the existing gateway-routed `_TMUX.run` call.
- Follow `aidocs/framework/tui_conventions.md` for the Textual edits.
- Add/extend a unit test for the new `TmuxLaunchConfig` flag → tmux argv mapping
  (left placement + width) where feasible without a live tmux server.
