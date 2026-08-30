---
Task: t1603_1_board_card_badge_and_detail_row.md
Parent Task: aitasks/t1603_surface_deferred_plan_marker_on_the_board.md
Sibling Tasks: aitasks/t1603/t1603_2_*.md, aitasks/t1603/t1603_3_*.md, aitasks/t1603/t1603_4_*.md, aitasks/t1603/t1603_5_*.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1603_1 — Card status qualifier + detail row

## Context

t1595 shipped the `plan_approved_at` marker and two read surfaces, deferring the
board (`aidocs/framework/aitasks_extension_points.md:283-284`: "Board layer 3
ships separately"). This child closes that deferral and delivers the parent
t1603's own `## Verification` section in full, standalone.

**Constraint: visibility, not routing** (`aidocs/gates/ledger-driven-reentry.md`).
Read-only surface. No edit affordance; no path that starts implementation from a
`Ready` task.

## Pre-phase (risk mitigations)

### `characterize_status_badge_render`

Runs **first**, against unmodified code, committed before any production edit.

1. Add `tests/test_board_plan_approved_marker.py` with a single test capturing
   the exact `render().plain` of the card status line for a fixture task with no
   `plan_approved_at`.
2. **Positive control:** temporarily perturb the badge literal in
   `aitask_board.py`, confirm the test fails naming the expected string, restore.
   A characterization test never seen to fail guards nothing.
3. Commit this test on its own.

## Implementation Steps

### 1. `_plan_approved_marker(metadata) -> str | None`

Place beside `_followup_marker` (`aitask_board.py:3312`) and mirror its
docstring conventions. Total over what YAML actually produces — verified against
`lib/task_yaml.py` (`yaml.SafeLoader`):

| Input | Result |
|---|---|
| absent / `None` / `""` / blank | `None` |
| `str` `"2026-02-01 14:30"` | verbatim |
| `datetime` (`2026-02-01 14:30:05` parses as one) | `%Y-%m-%d %H:%M` |
| `date` (`2026-02-01` parses as one) | `%Y-%m-%d %H:%M` |
| list / dict / int / bool | fixed literal `"set (unreadable)"` |

Returning `None` vs a string keeps "no marker" structurally distinct from "a
marker that happens to look odd", so every call site is a single `if marker:`.

**Do not reuse `_normalize_opaque_scalar` (`board/aitask_merge.py:151`)** — it
returns `""` for every non-`str`, correct for *comparison*, wrong for
*rendering*: it would hide a `datetime`-parsed marker that `ait ls` (a bash
frontmatter parse) still shows. Record this divergence in a comment.

### 2. `_status_badge_text(status, plan_marker) -> str`

```python
def _status_badge_text(status: str, plan_marker: str | None) -> str:
    return f"📋 {status} · Planned" if plan_marker else f"📋 {status}"
```

One authority, so the two call sites cannot drift.

### 3. `TaskCard.compose` (`:3186-3189`)

The badge is suppressed when blocked or when children are implementing. A
`Ready` task can be blocked *and* marked — the risk-mitigation "before" stop
deliberately retains the marker (`task-workflow/SKILL.md:553`) — so the
qualifier must survive suppression:

```python
plan_marker = _plan_approved_marker(meta)
if not is_blocked and status and not implementing_children:
    status_parts.append(_status_badge_text(status, plan_marker))
elif plan_marker:
    status_parts.append("📋 Planned")
```

### 4. `TrailTaskCard.compose` (`:3550`)

Use the helper. No suppression logic here.

### 5. Detail row — `_build_tracking_fields` (`:6579`)

```python
plan_marker = _plan_approved_marker(meta)
if plan_marker:
    out.append(ReadOnlyField(
        f"[b]Plan approved:[/b] {escape(plan_marker)}", classes="meta-ro"))
```

`ReadOnlyField` parses Rich markup, so the value goes through
`rich.markup.escape`. Absent marker ⇒ no row; the collapsible's `(<n>)` adjusts
for free. Wording matches the existing surfaces (`aitask_ls.sh:852-853` renders
`Plan: approved <ts>`).

### 6. Docs

Resolve the "(Board layer 3 ships separately)" parenthetical at
`aidocs/framework/aitasks_extension_points.md:283-284`. Leave the `anchor`
(`:173`) and `boardgroup` (`:206`) deferrals alone. The website reference row
belongs to t1603_5.

## Verification

`tests/test_board_plan_approved_marker.py`:

- app-free `_plan_approved_marker` matrix, one case per table row;
- card render: marked task reads `📋 Ready · Planned`;
- **exact-parity control**: unmarked status line byte-identical to the pre-phase
  baseline;
- suppressed-badge case (blocked + marked) still surfaces `Planned`;
- `TrailTaskCard` carries the qualifier (second call site);
- detail row present when marked, **widget absent** when unmarked;
- a list-valued marker renders the fallback and does not vanish;
- a marker containing `[` renders literally, not markup-parsed;
- `test_fixture_facts` precondition test.

`bash tests/run_all_python_tests.sh --test-dir tests` — read only the last line.
No serial-carve-out edit needed.

Live: seed with `./.aitask-scripts/aitask_update.sh --batch <n> --plan-approved-at now`,
open `ait board`, confirm badge + detail row, clear with `--plan-approved-at ""`,
confirm the indicator disappears on refresh.

## Risk

### Code-health risk: low
- Three small edits plus one new pure function, all in `aitask_board.py`; the
  badge refactor is behaviour-preserving and covered by the characterization
  test. · severity: low · → mitigation: inline pre-phase `characterize_status_badge_render`

### Goal-achievement risk: low
- The requirements are fully specified by the parent's settled decisions (word
  not glyph, no timestamp on the card, byte-identical unmarked render), and each
  maps to an assertion. · severity: low · → mitigation: none (accepted residual)

## Step 9 (Post-Implementation)

Standard closure: commit, merge per the plan header (current-branch mode, `main`
for both fields), archive the task and this plan.
