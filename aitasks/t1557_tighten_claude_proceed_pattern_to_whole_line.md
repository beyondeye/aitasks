---
priority: medium
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [shadow, aitask_monitormini]
gates: [risk_evaluated]
assigned_to: dario-e@beyond-eye.com
anchor: 1159
followup_kind: upstream_defect
created_at: 2026-08-17 21:56
updated_at: 2026-08-17 22:02
---

## Origin

Identified during t1540's post-implementation review.

## Defect

`.aitask-scripts/monitor/prompt_patterns.py:131` — `claude_proceed` matches
`Do you want to proceed?` **anywhere on a line**. Claude's tool-permission dialog
renders option 1 as *editable* (`Tab` amends it), so a user typing that phrase
into the option puts a second copy of it inside the bottom-6-line detection
window. The reported kind then flips mid-dialog, and
`classify_followed_change` returns `WORK` on the `prev_kind != curr_kind`
short-circuit — firing a spurious auto-recheck round while the user is mid-edit.

Measured against the shipped fixtures:

| transition | kinds | verdict |
|---|---|---|
| dialog → user types the phrase into the amend box | `claude_help_bar` → `claude_proceed` | **`work`** |

The kind flip is the sole cause: with the kind held constant the same pair
classifies `selection_only`, because the typed text sits *below* the boundary and
the comparison never sees it.

**Pre-existing** (the substring pattern is t1474's), but it stands out now
because t1540 closed the identical hole one layer down and left the two layers
inconsistent: the *boundary* in `review_loop.py` is a whole-line anchor
(`^\s*Do you want to proceed\?\s*$`) precisely so user-typed text cannot relocate
it, while the *prompt pattern* that selects the kind is still a substring.

## Suggested fix

Tighten `claude_proceed` to the same whole-line form. Verified against every
Claude fixture in `tests/review_loop_fixtures.py`, matching on the last 6 lines
(the window `_prompt_detection_text` actually reads):

| fixture | whole-line matches in window | substring matches in window |
|---|---|---|
| `CLAUDE_PERMISSION_SHORT_SEL1/SEL2/LATER_RAW` (120x6) | **yes** | yes |
| `CLAUDE_AMEND_TYPED_SEL1_RAW` (typed copy) | **no** | yes |
| `CLAUDE_PERMISSION_SEL1/SEL2/LATER_RAW` (120x30) | no | no |
| `CLAUDE_PERMISSION_COMPACT_SEL1_RAW` (120x14) | no | no |

So the tightening keeps every legitimate match and drops only the typed one.

**Do not break the short-pane regime.** At <=9 rows Claude truncates the option
list, which lifts the question into the detection window and makes
`claude_proceed` the *correct* reported kind for the real dialog (t1540's
measurement). The real header is a whole line there (` Do you want to proceed?`
at index -5), which is why the tightening is safe — but any alternative fix must
preserve that, or the short-pane regime loses detection entirely.

## Verification

- Add a fixture-backed test asserting the dialog→typed transition no longer
  classifies `WORK`.
- Re-run `python3 tests/test_review_loop.py` and
  `python3 tests/test_prompt_detection.py` (the latter owns `claude_proceed`'s
  existing coverage).
- Negative control: revert to the substring form; the new test must fail.
