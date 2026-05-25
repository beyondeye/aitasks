---
priority: medium
effort: medium
depends: [t826_1]
issue_type: feature
status: Ready
labels: [tui, tui_switcher, cross_repo]
created_at: 2026-05-25 17:17
updated_at: 2026-05-25 17:17
---

## Context

Second implementation step of t826. Today the `ait` IDE TUI switcher and
`ait monitor` can only display projects whose tmux sessions are already
running — to make project X visible I have to `cd` into project X first and
run `ait ide` to spin up its session. This child surfaces every project
recorded in the per-user registry (`~/.config/aitasks/projects.yaml`, populated
by t826_1) inside the TUI switcher, even when no live tmux session exists for
it. Selecting an inactive project from the switcher auto-spawns its tmux
session and teleports the user there.

**Scope note: `ait monitor` is intentionally out of scope.** Per explicit
user direction during the parent brainstorm, `ait monitor`'s multi-project
view stays scoped to live tmux sessions only. Only the TUI switcher gains
inactive-project visibility in this round.

Depends on t826_1 (needs `~/.config/aitasks/projects.yaml` populated by
`ait projects add` and the registry-aware `aitask_project_resolve.sh`).

## Key Files to Modify

- `.aitask-scripts/lib/agent_launch_utils.py:255-316` (`discover_aitasks_sessions`) — add `include_registered=False` keyword arg (default false to preserve existing callers — `ait monitor` and any other current callers MUST behave identically). When true, append entries from `~/.config/aitasks/projects.yaml` whose `name` is not already covered by a live session, returning them as `AitasksSession(session=None, project_root, project_name)`.
- `.aitask-scripts/lib/agent_launch_utils.py:74-85` (`AitasksSession` dataclass) — add an `is_live` property: `session is not None`.
- `.aitask-scripts/lib/tui_switcher.py:8-13` (multi-session enumeration block) — call `discover_aitasks_sessions(include_registered=True)`. Render inactive entries identically to live ones (per user preference: no extra visual indicator; activity is implied by switch-vs-spawn behavior on selection).
- `.aitask-scripts/lib/tui_switcher.py` selection handler — when `selected.is_live` is False: spawn the tmux session before `tmux switch-client -t <name>`.
- `.aitask-scripts/aitask_ide.sh` — extract the session-bootstrap block (currently inline around line 145+) into a shared helper, e.g. `.aitask-scripts/lib/tmux_bootstrap.sh`, so the switcher's spawn-on-select path reuses the same code as `ait ide` (single source of truth for window layout, env-var setup, etc.).
- **Do not modify** `.aitask-scripts/aitask_monitor.sh` or the monitor's Python TUI.

## Key Files to Create

- `.aitask-scripts/lib/tmux_bootstrap.sh` — extracted session-bootstrap function. If added to `./ait`'s source-on-startup chain, also add it to `tests/lib/test_scaffold.sh::setup_fake_aitask_repo()` in the same PR (per CLAUDE.md). If only sourced on-demand by `aitask_ide.sh` and `tui_switcher.py`'s subprocess call, no scaffold update needed — document the decision.
- `tests/test_discover_include_registered.py` (or `.sh` wrapping `python3 -c`) — round-trip: write a fake `~/.config/aitasks/projects.yaml`, scan with `include_registered=True`, assert entries appear with `is_live=False` and correct fields.
- Regression test: assert `discover_aitasks_sessions()` (default, no flag) returns only live-session entries — no inactive leakage into existing callers like `ait monitor`.

## Reference Files for Patterns

- `.aitask-scripts/lib/agent_launch_utils.py:255-316` itself — the existing live-tmux enumeration is the pattern to extend (additive, default-off flag).
- `.aitask-scripts/aitask_ide.sh:145+` — current `tmux new-session -d -s <name>` flow that needs extracting.
- `t826_1` (sibling, will be archived to `aiplans/archived/p826/p826_1_*.md` by the time this task starts) — defines the `~/.config/aitasks/projects.yaml` schema and the resolver semantics this task consumes.

## Implementation Plan

1. **Read t826_1's archived plan** for the exact registry schema and `aitask_project_resolve.sh` interface — do not redesign.
2. **Extend `AitasksSession`** with `is_live` property.
3. **Extend `discover_aitasks_sessions`** with `include_registered` kwarg. Read the YAML index, merge with live results, dedupe by `name`.
4. **Extract tmux-bootstrap** from `aitask_ide.sh` into shared helper. Update `aitask_ide.sh` to call the helper.
5. **Update `tui_switcher.py`** to pass `include_registered=True` and dispatch spawn-vs-switch on `is_live`.
6. **Tests** — round-trip + regression (default-off behavior).
7. **Manual verification** — see Verification.

## Verification Steps

- Unit: `python3 tests/test_discover_include_registered.py` (or equivalent shell wrapper) — passes.
- Regression: `discover_aitasks_sessions()` (no flag) yields the same entries as before t826_2's changes (no inactive leak into `ait monitor`).
- `shellcheck` modified `.sh` files; run framework test suite.
- Manual:
  1. Have one inactive project in `~/.config/aitasks/projects.yaml` (e.g., `aitasks_mobile` registered but its tmux session not running).
  2. Open `ait ide` switcher — confirm the inactive project appears in the list.
  3. Select the inactive project — confirm a tmux session is spawned for it (matching the existing `ait ide` bootstrap behavior) and the switcher teleports there.
  4. Open `ait monitor` with the same registry state — confirm monitor still shows only live sessions (no inactive leakage).

## Out of Scope

- `ait monitor` multi-project view (explicitly excluded by user during parent brainstorm).
- Visual indicators for inactive entries in the switcher (user said "probably not needed"; behavior on selection is the indicator).
- Bootstrapping logic differences between `ait ide` startup and switcher-triggered spawn (use the same path).

## References

- Parent plan: `aiplans/p826_brainstorm_cross_repo_project_references.md`
- Sibling t826_1 (will be archived once complete): provides the registry + resolver this task consumes.
