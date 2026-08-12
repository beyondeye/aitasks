---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [tui, ui]
gates: [risk_evaluated]
anchor: 1449
followup_kind: upstream_defect
created_at: 2026-08-12 08:31
updated_at: 2026-08-12 08:31
---

## Origin

Spawned from t1486 during Step 8b review. t1486 fixed the *markup* defects in
`logview_app.py`'s header (literal brackets eaten as tags) and, as a
post-review change, the startup-focus defect that made the header's own keys
unreachable. Writing the behavioural pins for those surfaced a **third**,
independent defect in the same file: a state change that does not redraw.
It is out of scope for t1486 (refresh coupling, not markup) and is not fixed
there.

## Upstream defect

- `.aitask-scripts/logview/logview_app.py:130-134 — action_toggle_raw mutates raw_mode and delegates its header redraw to _read_and_append, which returns early when the file yields no new bytes (and when the path is missing). On an empty or quiet log the [raw]/[live] indicator therefore stays stale until some unrelated action happens to redraw the header. Its sibling action_toggle_pause updates #header-info directly, so the two actions disagree about who owns the redraw.`

## Diagnostic context

Reproduced against the real app (textual 8.2.7), empty log file, `tail=True`:

```
press r ->  raw_mode = True
            header   = 'File: …/empty.log  \[size: 0]  \[live]'      <-- no [raw]
press p ->  paused   = True
            header   = 'File: …/empty.log  \[size: 0]  \[paused] \[raw]'
```

`[raw]` appears only on the *second* keypress, because `action_toggle_pause`
refreshes the header itself. So the indicator is not merely late — it is wrong
for as long as the user does nothing else, which on a quiet log is exactly the
situation where they are staring at it.

The relevant shape in `_read_and_append` is that the `#header-info` update is
the **last** statement, after two early returns (`not self.log_path.exists()`
and `not data`). Any caller relying on it for a redraw inherits those returns.

t1486's own tests seed a non-empty temp log precisely to avoid this path — see
the `LogViewHeaderTests` docstring in `tests/test_textual_markup_structure.py`,
which records why the fixture must hold bytes. That workaround is what should
become unnecessary once this is fixed.

## Suggested fix

Make each action own its redraw rather than inheriting `_read_and_append`'s
early returns: have `action_toggle_raw` update `#header-info` directly (as
`action_toggle_pause` already does) after delegating the log re-read. Consider
extracting a single `_refresh_header()` so the three call sites cannot drift
again, and covering the empty-log case in
`tests/test_textual_markup_structure.py`.
