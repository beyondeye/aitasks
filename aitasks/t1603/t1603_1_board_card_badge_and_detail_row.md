---
priority: medium
effort: low
depends: []
issue_type: feature
status: Ready
labels: [board, ui, task_metadata]
gates: [risk_evaluated]
anchor: 1595
created_at: 2026-08-30 13:27
updated_at: 2026-08-30 13:27
---

## Context

t1595 introduced the `plan_approved_at` frontmatter marker ("plan approved,
implementation deliberately deferred") and shipped two read surfaces (`ait ls -v`
/ `--plan-approved`, and the planning step's existing-plan prompt), explicitly
deferring the board — `aidocs/framework/aitasks_extension_points.md:283-284`
records "(Board layer 3 ships separately)".

This child ships the parent task t1603's own `## Verification` section in full,
on its own, with no dependencies: a kanban card indicator and a read-only detail
row. The remaining children (t1603_2..t1603_5) build the in-flight workflow-phase
view on top.

**Hard constraint carried from t1595 (`aidocs/gates/ledger-driven-reentry.md`):
visibility, not routing.** This surface is read-only. The marker is written and
cleared exclusively by the task-workflow; the board must offer no edit
affordance for it, and nothing here may create a path that starts implementation
from a `Ready` task.

## Design decisions (settled during t1603 planning — do not re-litigate)

- The card shows a **word, not a glyph**: `📋 Ready · Planned`. This is workflow
  state, so it must be explicit rather than a symbol the user has to learn.
- **No timestamp on the card.** A card is a narrow surface (~36 usable columns
  inside a 40-column kanban column). The approval time goes in the detail view.
- **An unmarked task must render byte-identically to today.** This is the
  parity requirement, and it is asserted, not assumed.

## Key Files to Modify

- `.aitask-scripts/board/aitask_board.py`
  - add `_plan_approved_marker()` near `_followup_marker` (~line 3312)
  - add `_status_badge_text()` beside it
  - `TaskCard.compose` status-badge composition (~lines 3186-3189)
  - `TrailTaskCard.compose` status badge (~line 3550)
  - `TaskDetailScreen._build_tracking_fields` (~line 6579)
- `aidocs/framework/aitasks_extension_points.md` — resolve the
  "(Board layer 3 ships separately)" deferral at lines 283-284 of the
  `plan_approved_at` worked example.
- `tests/test_board_plan_approved_marker.py` — new.

## Reference Files for Patterns

- `.aitask-scripts/board/aitask_board.py:3312` `_followup_marker` — the file's
  established "totality boundary over a frontmatter field" pattern, including
  the rule that a present-but-unrecognised value still renders.
- `.aitask-scripts/board/aitask_board.py:6579` `_build_tracking_fields` — the
  `ReadOnlyField(f"[b]Label:[/b] {value}", classes="meta-ro")` row guarded by
  `if meta.get(...)`, which is exactly the omit-when-absent shape needed.
- `tests/test_board_followup_glyph.py` — card-render test module (fixture
  topology, `render().plain`, the app-free `_render_card` helper).
- `tests/test_board_detail_followup_kind.py` — detail-screen field-row tests,
  including the app-free field render harness and `test_fixture_facts`.
- `tests/lib/board_fixture.py` — `bf.FixtureTask(..., extra={...})` is how an
  arbitrary frontmatter key reaches a fixture file.

## Implementation Plan

### Pre-phase (risk mitigation): characterize_status_badge_render

**Runs first, against the unmodified code, and is committed before any
production edit.**

Write a characterization test capturing the exact current rendered card
status-line for a task carrying **no** `plan_approved_at`. This gives the
"unmarked tasks render exactly as before" parity assertion independent ground
truth, rather than an expectation copied out of the new implementation.

It must have a **positive control**: perturb the badge text, confirm the test
fails naming the expected string, then restore. A characterization test that
has never been seen to fail guards nothing.

### 1. `_plan_approved_marker(metadata) -> str | None`

The render boundary. **Total** over what YAML actually produces — verified
empirically against `lib/task_yaml.py` (`yaml.SafeLoader`):

| Input | Result |
|---|---|
| key absent / `None` / `""` / blank string | `None` |
| `str` `"2026-02-01 14:30"` (the canonical form) | returned verbatim |
| `datetime` (a hand-edited `2026-02-01 14:30:05` parses as one) | `%Y-%m-%d %H:%M` |
| `date` (a bare `2026-02-01` parses as one) | `%Y-%m-%d %H:%M` |
| list / dict / int / bool | a fixed literal, e.g. `"set (unreadable)"` |

The last row follows `_followup_marker`'s documented rule: a bad value that
silently vanishes is indistinguishable from a task that never had a marker.

**Do NOT reuse `_normalize_opaque_scalar` from `board/aitask_merge.py:151`.** It
returns `""` for every non-`str`, which is correct for *comparison* and wrong
for *rendering* — it would hide a `datetime`-parsed marker that `ait ls` (a bash
frontmatter parse) still displays. Note this divergence in a comment so the next
reader does not "fix" it.

### 2. `_status_badge_text(status, plan_marker) -> str`

Single-source the badge so the two call sites cannot drift:

```python
def _status_badge_text(status: str, plan_marker: str | None) -> str:
    return f"📋 {status} · Planned" if plan_marker else f"📋 {status}"
```

### 3. Wire the two call sites

`TaskCard.compose` currently reads:

```python
if not is_blocked and status and not implementing_children:
    status_parts.append(f"📋 {status}")
```

The badge is **suppressed** when the card is blocked or has implementing
children. A `Ready` task can legitimately be blocked *and* carry the marker —
the risk-mitigation "before" stop deliberately retains it
(`.claude/skills/task-workflow/SKILL.md:553`) — so the qualifier must survive
that suppression:

```python
plan_marker = _plan_approved_marker(meta)
if not is_blocked and status and not implementing_children:
    status_parts.append(_status_badge_text(status, plan_marker))
elif plan_marker:
    status_parts.append("📋 Planned")
```

`TrailTaskCard.compose` (~line 3550) uses the helper directly; it has no
suppression logic.

### 4. Detail row

One guarded entry in `_build_tracking_fields`, in the "Tracking & provenance"
collapsible:

```python
plan_marker = _plan_approved_marker(meta)
if plan_marker:
    out.append(ReadOnlyField(
        f"[b]Plan approved:[/b] {escape(plan_marker)}", classes="meta-ro"))
```

`ReadOnlyField` parses Rich markup, so the value goes through
`rich.markup.escape` — a hand-edited value containing `[` would otherwise be
swallowed (see `project_textual_static_markup_eats_free_form_prose`). Absent
marker ⇒ no row at all; the collapsible's `(<n>)` count adjusts for free.

Wording is deliberately consistent with the existing surfaces, which say
`Plan: approved <ts>` (`aitask_ls.sh:852-853`) and "awaiting implementation".

### 5. Docs

Resolve the "(Board layer 3 ships separately)" parenthetical in the
`plan_approved_at` worked example at
`aidocs/framework/aitasks_extension_points.md:283-284`. Leave the sibling
deferrals for `anchor` (:173) and `boardgroup` (:206) alone — they are other
fields' business.

The website reference row is **t1603_5's** job, not this child's.

## Verification

New `tests/test_board_plan_approved_marker.py`:

- app-free `_plan_approved_marker` matrix — one case per row of the table above;
- card render via `render().plain`: a marked task reads `📋 Ready · Planned`;
- **exact-parity negative control**: an unmarked task's status line is
  byte-identical to the characterization baseline captured in the pre-phase;
- the suppressed-badge case (blocked + marked) still surfaces `Planned`;
- `TrailTaskCard` carries the qualifier too (the second call site);
- detail screen: the row is present for a marked task and **absent entirely**
  for an unmarked one — assert the widget does not exist, not that it is blank;
- a junk marker (a list) renders the fallback literal and does not vanish;
- a marker containing `[` renders literally rather than being markup-parsed;
- `test_fixture_facts` precondition test (module-wide idiom) so nothing passes
  vacuously if the fixture is reshaped.

Run: `bash tests/run_all_python_tests.sh --test-dir tests` — read only the last
line. No serial-carve-out edit is needed; this module joins the parallel pool.

Live check: this repo has zero tasks carrying the marker, so seed one with
`./.aitask-scripts/aitask_update.sh --batch <n> --plan-approved-at now`, open
`ait board`, confirm the badge and the detail row, then clear it with
`--plan-approved-at ""` and confirm the indicator disappears on refresh.
