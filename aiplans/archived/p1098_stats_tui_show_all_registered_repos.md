---
Task: t1098_stats_tui_show_all_registered_repos.md
Worktree: (none — profile 'fast' works on current branch)
Branch: main
Base branch: main
---

# t1098 — `ait stats` TUI: show all registered repos

## Context

The `ait stats` TUI is a multi-session viewer: in multi-session mode it lists a
row per aitasks repo and shows each repo's archived-task statistics. Today it
only lists repos that have a **live tmux session** — a registered repo with no
running session (e.g. `aitasks_go`) never appears, so its stats are
unreachable. The user's "only repos with recent completions show up"
observation is a side effect: you only tend to have an `ait` session open for
repos you worked on recently.

**Root cause:** `.aitask-scripts/stats/stats_app.py:177` calls
`discover_aitasks_sessions()` with no arguments, so `include_registered`
defaults to `False`. In that mode `discover_aitasks_sessions()`
(`.aitask-scripts/lib/agent_launch_utils.py:598`) returns only repos detected
via a live tmux session (pane-cwd walk-up or the `AITASKS_PROJECT_<sess>` env
var). Registered projects in `~/.config/aitasks/projects.yaml` without a live
session are excluded.

The fix pattern already exists: `.aitask-scripts/lib/tui_switcher.py:500,557`
calls `discover_aitasks_sessions(include_registered=True)`, which appends
synthesized `is_live=False` entries for every registered project not already
covered by a live session (`agent_launch_utils.py:677-689`). The stats TUI
simply never opted in. Its per-session scan already reads an arbitrary
`project_root` via `collect_stats(project_root=...)`
(`stats_app.py:309-314`, `stats_data.py:_paths_for`), so registered-only repos
render correctly once they appear in the list.

## Approach (agreed scope: core fix + record follow-up)

Opt the stats TUI into `include_registered=True` and filter out `is_stale`
registry rows (the stats TUI is a read-only archive viewer — unlike
`tui_switcher` it has no stale-entry repair modal, and a stale row's archive
may be missing). Extract the discover+filter into a small importable
module-level helper so it is unit-testable without mounting the Textual app.

**Out of scope (recorded as an upstream-defect follow-up, per user decision):**
Repos with no `tmux.default_session` configured all fall back to the literal
session name `"aitasks"` (`agent_launch_utils.py:_read_default_session`, line
555). The stats TUI *and* the shared ring/group helpers
(`cross_group_ring`/`cross_group_step`/`advance_group_selection`, used by
`tui_switcher` too) key session identity on `sess.session`, so multiple
such repos would collide on one key. This is a **pre-existing** latent issue in
the shared discovery/selection layer (it already applies to `tui_switcher`),
and it does not affect this user's repos (each sets a distinct
`default_session`). It will be recorded in the plan's "Upstream defects
identified" bullet so Step 8b offers a standalone follow-up task; it is **not**
fixed here to keep this a small, low-risk change.

## Changes

### 1. `.aitask-scripts/stats/stats_app.py`

Add a module-level helper near the top (after the imports / `ALL_SESSIONS_KEY`):

```python
def discover_stats_sessions() -> list[AitasksSession]:
    """Sessions for the stats TUI: live sessions plus every registered repo.

    Opts into ``include_registered=True`` so registered projects with no live
    tmux session (e.g. a repo you haven't opened this session) still appear and
    have their archived stats scanned. STALE registry rows are dropped — the
    stats TUI is a read-only viewer with no repair UI, and a stale row's archive
    may be absent.
    """
    return [
        s for s in discover_aitasks_sessions(include_registered=True)
        if not s.is_stale
    ]
```

Change `StatsApp.__init__` (line 177) from:

```python
self.sessions: list[AitasksSession] = discover_aitasks_sessions()
```

to:

```python
self.sessions: list[AitasksSession] = discover_stats_sessions()
```

No other changes are needed: the session-selection machinery, group nav
(`default_selected_group`, `cross_group_ring`, …), `_build_session_items`,
and `_stats_for`/`collect_stats(project_root=…)` all already operate on
`AitasksSession` lists and never inspect `is_live`; the only live-vs-registered
distinguisher they'd trip on (`is_stale`) is filtered out here.

### 2. Test — `tests/test_stats_include_registered.py` (new)

Follow the `importlib` self-contained style of `tests/test_stats_multistage.py`
(load the module by path, `assert_eq` helpers, PASS/FAIL summary; textual is
importable in the test env — `tests/test_tui_switcher_agent_launch.py` already
imports it).

- Load `stats_app.py` by path.
- Monkeypatch `stats_app.discover_aitasks_sessions` with a fake that (a) records
  the `include_registered` kwarg and (b) returns a mixed list: one live entry,
  one registered `is_live=False` entry, and one `is_stale=True` entry.
- Assert `stats_app.discover_stats_sessions()`:
  - was called with `include_registered=True`;
  - includes the live entry and the registered entry;
  - **excludes** the stale entry.

## Verification

1. **Unit test:** `python3 tests/test_stats_include_registered.py` → all PASS.
2. **Regression (no drift in discovery layer):**
   `python3 tests/test_discover_include_registered.py` and
   `python3 tests/test_discover_default_unchanged.py` → still PASS (this task
   does not touch `agent_launch_utils.py`).
3. **Live acceptance (manual — TUI):** run `ait stats` in this repo's tmux
   session; confirm the session list now includes `aitasks_go` (and the other
   registered repos) alongside the live `aitasks` session, and that selecting
   `aitasks_go` shows its archived stats rather than an empty/duplicated row.
   Offer this as a manual-verification follow-up (Step 8c) since it is a visual
   TUI check.

## Step 9 (Post-Implementation)

Standard: profile 'fast' works on the current branch (no worktree/merge). Run
declared gates via the orchestrator, then archive with
`./.aitask-scripts/aitask_archive.sh 1098`.

## Risk

### Code-health risk: low
- Two-line behavioral change plus a small extracted helper; no shared-layer or
  signature changes, no new coupling. Blast radius = one file
  (`stats_app.py`) + one new test. · severity: low · → mitigation: TBD

### Goal-achievement risk: low
- The `include_registered=True` path is already proven by `tui_switcher`, and
  the stats scan already supports arbitrary `project_root`, so registered repos
  will render. The one honest gap — the `"aitasks"` session-name collision for
  repos lacking `default_session` — is explicitly out of scope, doesn't affect
  this user, and is recorded as a follow-up. · severity: low · → mitigation: TBD

## Final Implementation Notes

- **Actual work done:** Added a module-level `discover_stats_sessions()` helper
  to `.aitask-scripts/stats/stats_app.py` that calls
  `discover_aitasks_sessions(include_registered=True)` and filters out
  `is_stale` rows; pointed `StatsApp.__init__` at it (was the bare
  `discover_aitasks_sessions()`). Added `tests/test_stats_include_registered.py`.
- **Deviations from plan:** None — implemented exactly as designed.
- **Issues encountered:** None. All tests pass (new 5/5; regressions
  test_stats_multistage 22/22, test_stats_data 6/6, test_discover_include_registered
  10/10, test_discover_default_unchanged 4/4).
- **Key decisions:** Filter stale entries rather than surface a repair modal —
  the stats TUI is a read-only viewer with no bootstrap/repair UI (unlike
  `tui_switcher`), and a stale row's archive may be absent. Extracted a pure,
  importable helper so the behavior is unit-testable without mounting Textual.
- **Upstream defects identified:** .aitask-scripts/lib/agent_launch_utils.py:555 — `_read_default_session` falls back to the literal session name `"aitasks"` for any repo without a `tmux.default_session`, so multiple such registered repos collide on one key; the stats TUI and the shared ring/group helpers (`cross_group_ring`/`cross_group_step`/`advance_group_selection`, also used by `tui_switcher`) key session identity on `sess.session`, so the collision would show duplicate rows / bleed stats. Pre-existing latent issue in the shared discovery/selection layer (already applies to `tui_switcher`), not introduced by this task; scoped out per user decision and worth a separate follow-up.
