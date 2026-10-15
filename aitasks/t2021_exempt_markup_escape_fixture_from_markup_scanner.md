---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [aitask_monitormini, tui]
gates: [risk_evaluated]
anchor: 2001
followup_kind: upstream_defect
created_at: 2026-10-15 23:57
updated_at: 2026-10-15 23:57
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

Follow the scanner's own failure message, which explains how fixtures are expected to opt out: either construct the hostile strings so the scanner does not see a literal (e.g. by concatenation), or add the file or its fixture lists to the scanner's exemption mechanism. Then confirm that the scanner's negative controls still fail when they should.
