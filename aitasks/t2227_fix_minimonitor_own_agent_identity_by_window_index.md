---
priority: high
risk_code_health: medium
risk_goal_achievement: low
effort: medium
depends: []
issue_type: bug
status: Implementing
labels: [minimonitor, tui, tmux]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
folded_tasks: [1693]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus5_5
created_at: 2026-11-07 19:34
updated_at: 2026-11-07 22:16
---

## Symptom (observed live, 2026-11-07)

The minimonitor in tmux window `aitasks:12 agent-pick-1981_3` (window `@223`,
minimonitor pane `%502`, started 18:24:49) shows in its docked
`── this agent · aitasks ──` panel:

```
 ☆ agent-pick-1893_6
   6 image folder input mode
   ◔ PLAN ⏸
```

The followed agent is really `%501` (`/aitask-pick 1981_3`). Window
`agent-pick-1893_6` (`@222`) sits at index 11, right below it.

The same pane disagrees with itself:
- The **identity text** (window name and title) belongs to 1893_6.
- The **phase line** `PLAN ⏸` belongs to 1981_3. 1981_3's shadow phase is PLAN,
  and the list row for pick-1893_6 shows `◌ unknown`.
- The **general list** leaves out pick-1981_3, because the own pane is excluded,
  and still lists pick-1893_6.

So the current tick resolves "own" correctly. Only the one-shot identity is wrong:
the panel was built from the wrong snapshot once and never rechecked.

## Root cause

Line numbers below are as of commit f2094dd46.

1. **Own identity is keyed on `window_index`, which changes.**
   `_find_own_agent_snapshot` / `_find_own_window_snapshot`
   (`.aitask-scripts/monitor/minimonitor_app.py:2376-2424`) match
   `snap.pane.window_index == self._own_window_index` within the own session.
   `renumber-windows` is `on`, so the index shifts whenever an earlier window
   closes. `TmuxPaneInfo` (`monitor_core.py:1216`) carries no `window_id`, and
   the status protocol only carries `window_index` (`status_protocol.py:347`,
   `:738`, `:807`).
2. **The index and the snapshots are read at different moments.** In the refresh
   tick (`minimonitor_app.py` ~2087-2113), `_update_own_window_info` (a
   `display-message` call) runs first, and `capture_all_async` (list-panes)
   produces `_snapshots` after it. The mount-time seed (`~2294`) is a third
   writer. Under the shared status server (t2037_3) the snapshots can come from
   an even earlier scan. A renumber in that gap pairs a fresh index with old
   indexes, and the index lands on the neighbouring window's agent.
   *Hypothesis, not reproduced:* the window-close event that caused it was not
   identified. The direct evidence is the identity/phase split above.
3. **The panel name and title are built once and never rechecked.**
   `_maybe_build_own_agent_panel` (`~3315`) stores the name and title from the
   first snapshot it resolves and does not re-read them by design.
   `_refresh_own_live_state` (`~3218`) repaints only the mark glyph and phase,
   from the *current* lookup. One bad tick therefore freezes the wrong name
   permanently.

## Blast radius (more than cosmetic)

`_find_own_agent_snapshot()` is called by about 14 action and decision sites in
`minimonitor_app.py`: 2416, 3239, 3924, 3956, 4077, 4260, 4633, 4678, 4783,
5391, 6034, 6191, 6414, 6428, 6449. These include kill / next / shadow
`e`/`E` / `I` and the followed-agent capture pin. During a mismatched tick, any
of them can act on the **neighbouring** agent. Auto-close and the
`_capture_pins` name pin also depend on the same identity fields.

## Suggested fix

- Resolve the followed pane by **stable identity**: this pane's `TMUX_PANE` and
  `_own_window_id` (the `@N` from `display-message`), plus the pane ids
  currently in that window (`list-panes -t <own_window_id>`, as the fallback at
  `~3863` already does with `classify_window_panes`). Match snapshots by
  `pane_id`, never by `window_index`. Another option is adding `window_id` to
  `TmuxPaneInfo`, the list-panes formats (`monitor_core.py:2802`, `:3098`) and
  the status protocol. If you take that route, record why in the plan,
  including the protocol-versioning cost.
- An unresolvable or unconfirmed identity must **refuse** the action. It must
  not fall back to an index match.
- The docked panel must check its stored name and title against the pane id the
  current lookup resolves to, and rebuild when that id changes. Keep the "a
  rename after build keeps the old header" behaviour only for a real rename of
  the *same* pane.
- Check whether the full monitor (`monitor_app.py`) or companion / shadow
  pairing keys anything on `window_index` the same way. Fix those consumers in
  the same task, or hand them off explicitly.

## Tests

- Renumber-race regression: snapshots carry pre-renumber indexes while the own
  index is post-renumber, with a neighbouring agent at the stale index. Assert:
  (a) the panel name and title are the real followed agent's; (b) a
  followed-agent action resolves the real pane id, or refuses, and never the
  neighbour's. Each assertion needs a pre-fix control that fails against the
  current index-keyed lookup.
- Panel rebuild: after the identity is corrected, the panel text follows it.
- Drive the real `MiniMonitorApp` methods. Do not re-implement the predicate in
  the test (see the merged t1693 below).

## Fold note (from the user)

> Merge t1693, including its audit of the remaining test sections. Replace or
> remove the stale copied-predicate test and ensure coverage exercises real
> behavior.

## Merged from t1693: retire stale auto select predicate mirror


## Origin

Spawned from t1683 during Step 8b review.

## Upstream defect

- `tests/test_multi_session_minimonitor.sh:147-165` — Tier 1d asserts a locally
  redefined copy of an `_auto_select_own_window` predicate
  (`snap_window_index == own_window_index and snap_session in ("", own_session)`)
  that no longer exists in the source, so it stays green regardless of the real
  method's behaviour. Misleading regression coverage; the file's other tiers
  should be audited for the same self-mirroring pattern.

## Diagnostic context

t1683 fixed `MiniMonitorApp.on_app_focus` / `_auto_select_own_window` in
`.aitask-scripts/monitor/minimonitor_app.py`: the focus-in handler was stealing
the click that produced it, and the auto-select was scrolling the list to the
top. Both methods changed behaviour materially.

While sweeping for coverage that might break, Tier 1d of
`tests/test_multi_session_minimonitor.sh` was found to be **structurally unable
to break**. It does not import or call `_auto_select_own_window`. It defines its
own Python function inside a heredoc:

```python
def would_match(own_window_index, own_session, snap_window_index, snap_session):
    # Mirror of the guard in MiniMonitorApp._auto_select_own_window.
    return (
        snap_window_index == own_window_index
        and snap_session in ("", own_session)
    )
```

...and then asserts against that local copy. The comment claims it mirrors the
production guard, but `_auto_select_own_window` has had no such predicate since
the t511 behaviour degraded to "focus the first card"; today it is simply
`list_cards[0].focus(scroll_visible=False)`. The tier passed unchanged both
before and after t1683's fix, which is the proof that it measures nothing about
the source.

This is the "mirror the production rule in the test" anti-pattern: a test that
re-implements the behaviour it claims to guard can only ever assert that the
copy matches itself.

## Suggested fix

Rewrite Tier 1d to exercise the real `MiniMonitorApp` selection behaviour, or
delete it as superseded by `tests/test_minimonitor_focus_in_click.py` (which
drives the real app headlessly and carries two executable negative controls).
Then audit the file's remaining tiers for the same self-mirroring shape — Tier
1c's `_start_monitoring` assertions look source-derived, but the rest should be
checked rather than assumed.

## Dependency

Depends on t1683 (the behaviour change that exposed this).

## Folded Tasks

The following existing tasks have been folded into this task. Their requirements are incorporated in the description above. These references exist only for post-implementation cleanup.

- **t1693** (`t1693_retire_stale_auto_select_predicate_mirror.md`)

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-11-07T20:16:55Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-11-07T21:04:29Z status=pass attempt=1 type=human
