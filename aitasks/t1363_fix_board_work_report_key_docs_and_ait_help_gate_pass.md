---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [docs, web_site]
gates: [risk_evaluated]
anchor: 1361
created_at: 2026-07-31 12:57
updated_at: 2026-07-31 12:57
boardidx: 940
---

## Origin

Spawned from t1361 during Step 8b review.

## Upstream defect

- `website/content/docs/tuis/board/how-to.md:225-243 — work-report section documents the key as uppercase W, but the default binding is lowercase w (aitask_board.py:5615); ~6 occurrences in that section, outside t1361's four gaps`
- `ait:51-60 — the --help "Gates:" block omits `gate pass`, which is dispatched at ait:323 and listed in the inline `ait gate --help`; known and deliberately deferred by t635_34`

## Diagnostic context

While documenting the board By-Trail view for t1361, the `w` row in
`website/content/docs/tuis/board/reference.md` had to be edited to add By-Trail
to its "hidden in ..." view list. The reference page documents the work-report
key as lowercase **`w`**, but `website/content/docs/tuis/board/how-to.md` uses
uppercase **`W`** throughout its "How to Generate a Work Report" section —
including the rebinding note, which names `shortcuts.board.work_report`.

The source of truth is `.aitask-scripts/board/aitask_board.py:5615`:

```python
Binding("w", "work_report", "Work Report"),
```

so the default key is lowercase `w` and the how-to page is wrong. It was left
untouched in t1361 because the mismatch predates that task's release window
(v0.29.0..HEAD) and correcting it means editing roughly six occurrences in a
section about work reports, not about any of t1361's four documented gaps.

Separately, while enumerating the user-facing gate verbs for the new
`website/content/docs/commands/gates.md` page, `ait gate pass` turned out to be
dispatched (`ait:323`) and present in the inline `ait gate --help` string
(`ait:326`), but absent from the top-level `ait --help` "Gates:" block
(`ait:51-60`). The t635_34 plan records this as known and worth a one-line
follow-up, which it deliberately did not take.

## Suggested fix

1. Replace **W** with **w** throughout the "How to Generate a Work Report"
   section of `website/content/docs/tuis/board/how-to.md`, verifying each
   occurrence against `aitask_board.py:5615` first (the rebinding note and the
   step list both name the key).
2. Add a `gate pass  Sign off a human gate` line to the "Gates:" block in `ait`'s
   `show_usage`. Note `tests/test_gate_cli_wiring.sh` pins the inline help
   strings — check whether it also pins the `show_usage` block before editing.
