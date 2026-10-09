---
priority: medium
effort: medium
depends: []
issue_type: bug
status: Ready
labels: [monitor, minimonitor, tmux]
gates: [risk_evaluated]
anchor: 1922
followup_kind: risk_mitigation
created_at: 2026-10-09 15:34
updated_at: 2026-10-09 15:34
---

## Origin

Risk-mitigation ("after") follow-up for t1922, created at Step 8d after implementation landed.

## Risk addressed

unregistered-session guesses (review concerns 1, 3, stray marks)

- Unregistered sessions (pre-upgrade, or created by hand) still rely on a pane guess. A tie, or a failed read, can still mis-root one, together with its marks and `p`, until `ait ide` stamps it · severity: medium · → mitigation: unregistered_session_ambiguity

## Goal

Flag unregistered sessions whose pane vote ties or whose reads failed as unverified; acting consumers (monitor actions, switcher launches + dedupe preference, marks/purge, restore, project-resolve candidates) refuse.

Context from t1922 (see `aiplans/archived/p1922_*.md` once archived):

- Discovery (`.aitask-scripts/lib/agent_launch_utils.py`) now resolves a session
  by: (1) the `@aitask_project_root` session stamp — authoritative;
  (2) `_pane_vote` (majority, ties → smallest realpath); (3) the legacy
  `AITASKS_PROJECT_<s>` global only when no pane resolves. Rules 2–3 are still a
  GUESS for unstamped sessions, and the result carries no signal that it is one.
- Add a per-session "unverified" state to `AitasksSession` (trailing defaulted
  field; positional test constructions `AitasksSession("s", Path, "p")` must keep
  working): set it for an unstamped session whose vote ties or disagrees without
  a clear majority, or whose `list-panes` / legacy read FAILED (the default and
  async paths currently fold failures into "no answer" — the checked adapters
  in `_checked_adapters()` already classify them).
- Acting consumers must refuse on an unverified session; display consumers may
  degrade. Inventory (from t1922 planning):
  - monitor/minimonitor: `p` (pick-by-number + column create/move), `n`, `R`,
    `e`/`E` shadow spawns — guard at action entry and in confirm callbacks
    (coordinate with t1934, which binds/revalidates the root across dialog stages);
  - marks: `AgentMarksMixin._root_for_session` should return None for an
    unverified session (cycle refused, purge: its agents set `complete=False`,
    `_parked_agent_pairs` skips it) — this also closes the stray-mark hazard
    (a mark written under a guessed root, later misapplied/purged);
  - `lib/agent_freeze.py` `reconcile`: mark the session's root(s) not fully observed;
  - `lib/agent_restore.py` `_named_session_for_root` / `_session_for_root`:
    refuse (`session_unverified:<name>`) — today `_named_session_for_root`
    accepts a matching candidate before checking scan completeness;
  - `aitask_project_resolve.sh` `cmd_candidates` / `tmux_scan_lookup`: emit all
    candidate roots / skip the session;
  - TUI switcher (`lib/tui_switcher.py`): guard launches in
    `_ensure_session_live` / spawn paths, and make `_dedupe_sessions_by_key`
    never let an unverified live entry displace a verified record (live or
    registered) for the same project; compute `live_names` from verified
    sessions only.
- Thread the flag to the TUIs without a sync tmux call on the render path
  (`tests/test_monitor_refresh_no_sync_tmux.py`): e.g. a no-I/O
  `MonitorCore` accessor over the sessions cache, published with
  `_set_session_root_map` each tick.

Tests: a tied-root session alongside a verified one (switcher never launches
into the guess; dedupe keeps the verified record); a failed pane read with
competing roots → restore and monitor actions do not launch; marks cycle refused
and purge suppressed for an unverified session.
