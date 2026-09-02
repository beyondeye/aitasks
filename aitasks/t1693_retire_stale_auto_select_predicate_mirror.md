---
priority: medium
effort: low
depends: [1683]
issue_type: bug
status: Ready
labels: [tui, minimonitor]
gates: [risk_evaluated]
anchor: 1683
followup_kind: upstream_defect
created_at: 2026-09-02 17:07
updated_at: 2026-09-02 17:07
---

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
