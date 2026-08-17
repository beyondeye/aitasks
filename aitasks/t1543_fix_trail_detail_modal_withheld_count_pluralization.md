---
priority: low
effort: low
depends: []
issue_type: bug
status: Ready
labels: [aitask_board, tui, trails]
anchor: 1210
followup_kind: review_finding
created_at: 2026-08-17 17:17
updated_at: 2026-08-17 17:17
---

## Problem

`TrailDetailScreen._sections`'s `more(count, noun)` helper
(`.aitask-scripts/board/aitask_board.py:4106-4109`) pluralizes by appending
`"s"` to the **end** of the noun phrase it is handed:

```python
def more(count, noun):
    if count:
        plural = "" if count == 1 else "s"
        text.append(f"… {count} more {noun}{plural}\n")
```

Two of its three call sites pass a multi-word phrase whose head noun is at the
**start**, so for any count other than 1 the rendered line is ungrammatical:

| call site | noun passed | rendered at count > 1 |
|---|---|---|
| `other_drift` | `reason for other entries` | `… 4 more reason for other entriess` |
| `other_obs` | `observation not affecting this entry` | `… 24 more observation not affecting this entrys` |
| `other_evidence` | `evidence record` | `… 54 more evidence records` (correct) |

Only the third reads correctly, and only because its head noun happens to sit
last. The first produces a doubled `s`; the second produces `entrys`. Both also
leave the head noun (`reason`, `observation`) singular against a plural count.

Observed live during t1505_5 manual verification, in the By-Trail detail modal
on both standing artifacts — `art:trail-shadow-review-loop` (entry
`aitasks#1294`: 4 withheld drift reasons, 24 withheld observations) and
`art:trail-gates-framework-landing` (entry `aitasks#635_24`: 14 withheld
observations).

## Fix

Stop deriving the plural by suffixing the whole phrase. Either take both forms
explicitly:

```python
def more(count, singular, plural=None):
    ...
```

called as `more(n, "reason for other entries", "reasons for other entries")`,
or pluralize the head noun and keep the qualifier fixed. Cosmetic only — no
behaviour reads these strings, and the counts themselves are correct.

## Verification

Open the By-Trail detail modal on an entry with more than one withheld
observation and more than one withheld drift reason (either standing artifact
qualifies) and read the `… N more` lines. Worth pinning the three rendered
strings in `tests/test_board_bytrail_view.py`, which already covers this modal
— a count of exactly 1 hides the bug, so any pin must use a count > 1.

## Origin

Surfaced by t1505_5, the manual verification of t1505_1..4. The defect is in
text added by t1505_2 (entry-first detail modal). No t1505_5 checklist item
asserts grammaticality, so all 20 items passed; this is recorded separately
rather than as a verification failure.
