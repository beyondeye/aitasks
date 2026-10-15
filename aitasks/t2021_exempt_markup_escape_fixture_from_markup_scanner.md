---
priority: medium
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [aitask_monitormini, tui]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 2001
followup_kind: upstream_defect
implemented_with: claudecode/opus5_5
created_at: 2026-10-15 23:57
updated_at: 2026-10-16 00:18
---

## Origin

Spawned from t2009 during Step 8b review.

## Upstream defect

- tests/test_monitor_markup_escape.py:69 — the t2006 fixture title `'Fix [/] and [dim]x[/dim]'` is an intentionally unescaped markup string, but the repo-wide scanner `tests/test_textual_markup_colours.py::MarkupStructureScanTests::test_every_closing_tag_matches_an_open_tag` parses it as live markup and fails the suite (`MarkupError: auto closing tag ('[/]') has nothing to close`). The fixture needs an escape or an exemption. Observed against main at 7d077e308; another session may already be addressing it.

## Diagnostic context

While verifying t2009, the full Python suite (`bash tests/run_all_python_tests.sh`) ended with `PYTHON SUITE: FAILED (runner=pytest, exit=1)` and exactly one failure:

```
tests/test_textual_markup_colours.py::MarkupStructureScanTests::test_every_closing_tag_matches_an_open_tag
AssertionError: Lists differ: [] != [tests/test_monitor_markup_escape.py:69 'Fix [/] and [dim]x[/dim]' -> MarkupError: auto closing tag ('[/]') has nothing to close]
```

The fixture file was added by commit 337d0f6e0 (t2006, "Render window names and task titles literally in monitor cards, preview header and kill dialog"), which landed on main during the t2009 session. The t2009 change touched none of these files. The `TITLES` list in that file (around lines 68-72) deliberately holds hostile, unescaped titles, because t2006 tests that they render literally. The scanner cannot tell a hostile-input fixture from live markup.

Related in-flight task: t2017 (`render_remaining_user_text_literally_in_monitor_markup`, Implementing) plans to "mirror `tests/test_monitor_markup_escape.py`". New fixtures of that kind will hit the same scanner, so coordinate with it.

## Suggested fix

`tests/test_textual_markup_colours.py` has two opt-out mechanisms (checked at t2009's commit):
- `RICH_RENDERER_WAIVERS`, keyed `(path, qualname, token)`. Its header says it covers Rule B (colour tokens) only, so it does not fit a structural closing-tag finding.
- `SELF_REFERENTIAL_MODULES`, a whole-file exclusion with a stated reason, meant for modules whose "every occurrence ... is *data about* this defect class, not markup that renders". `tests/test_monitor_markup_escape.py` holds hostile-input fixtures, which arguably fits that description. The scanner comments, however, warn that a file-level exclusion is the blanket exemption the waiver key exists to avoid.

Pick one of these:
- (a) add the file to `SELF_REFERENTIAL_MODULES` with a reason; or
- (b) build the hostile strings so they are not a single literal the scanner can see (e.g. by concatenation). This keeps the file scanned.

Whichever is chosen, confirm that the scanner's own waiver-rot and negative-control tests still pass.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-10-15T21:18:50Z status=pass attempt=1 type=human
