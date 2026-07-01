---
priority: high
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [statistics, tui]
gates: [risk_evaluated]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-07-01 08:36
updated_at: 2026-07-01 08:38
---

## Problem

The `ait stats` TUI only lists repos that currently have a **live tmux
session** — it silently drops registered projects with no running session.
Observed: registered repos whose tasks were completed recently show up, but a
registered repo with no live session (e.g. `aitasks_go`) is never listed, so
its stats are unreachable. The "recently active" appearance is a side effect —
only repos you happen to have an `ait` session open for are shown; recency just
correlates.

## Root Cause

`.aitask-scripts/stats/stats_app.py:177` calls `discover_aitasks_sessions()`
with **no arguments**, so `include_registered` defaults to `False`. With that
default, `discover_aitasks_sessions()`
(`.aitask-scripts/lib/agent_launch_utils.py:598`) only returns repos detected
via a live tmux session (pane-cwd walk-up or the `AITASKS_PROJECT_<sess>` env
var, `agent_launch_utils.py:648-675`). Registered repos in
`~/.config/aitasks/projects.yaml` without a live session are excluded.

The fix pattern already exists: `.aitask-scripts/lib/tui_switcher.py:500,557`
calls `discover_aitasks_sessions(include_registered=True)`, which appends
synthesized `is_live=False` entries for every registered project not already
covered by a live session (`agent_launch_utils.py:677-689`). The stats TUI
simply never opted in.

## Proposed Fix

Change `stats_app.py:177` to call
`discover_aitasks_sessions(include_registered=True)` so registered-only repos
appear in the session list and their archived stats are collected via the
existing `collect_stats(project_root=...)` path (`stats_app.py:309-314`).

## Blast Radius / Considerations (verify during implementation)

- **Stale entries:** `include_registered=True` also emits `is_stale=True` rows
  (registry path missing the marker file). `tui_switcher` handles these via a
  stale-entry modal (`.aitask-scripts/lib/stale_entry_modal.py`), but
  `stats_app` has **no stale handling** — a stale repo would attempt
  `collect_stats` on a missing path. Skip or gracefully handle `is_stale`
  entries.
- **Session-key collisions:** `_session_cache` and session selection are keyed
  on `sess.session` (resolved from each repo's `tmux.default_session`). Two
  registered repos could resolve to the same session name; `tui_switcher` dedups
  on `project_name`, not session. Add a guard/dedup so cache entries don't
  collide.
- **multi_session flip:** Adding registered repos can turn a single-live-session
  setup into `multi_session=True`. That is the desired outcome (all repos
  shown), but confirm the session panel / default-selection logic behaves when
  the attached tmux session doesn't match any registered-only entry
  (`_default_session_selection`, `stats_app.py:198`).

## Acceptance Criteria

- `ait stats` TUI lists **all** registered (RESOLVED) repos from the project
  registry, including those with no live tmux session (e.g. `aitasks_go`).
- Selecting a registered-only repo shows its archived stats correctly.
- Stale registry entries do not crash the TUI.
- Existing single-repo and live-session behavior is unchanged.
