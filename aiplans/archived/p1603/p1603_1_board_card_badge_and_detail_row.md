---
Task: t1603_1_board_card_badge_and_detail_row.md
Parent Task: aitasks/t1603_surface_deferred_plan_marker_on_the_board.md
Sibling Tasks: aitasks/t1603/t1603_2_workflow_phase_model_and_degradation.md, aitasks/t1603/t1603_3_inflight_planned_lane_and_phase_chips.md, aitasks/t1603/t1603_4_expanded_gate_surface_in_task_detail.md, aitasks/t1603/t1603_5_website_docs_board_planned_lane_and_phases.md, aitasks/t1603/t1603_6_manual_verification_surface_deferred_plan_marker_on_the_boar.md
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5 @ 2026-08-30 16:08
---

# t1603_1 — Card status qualifier + detail row

## Context

t1595 shipped the `plan_approved_at` frontmatter marker ("plan approved,
implementation deliberately deferred") and two read surfaces (`ait ls -v` /
`--plan-approved`, and the planning step's existing-plan prompt), explicitly
deferring the board: `aidocs/framework/aitasks_extension_points.md:283-284`
records "(Board layer 3 ships separately.)".

On the board a marked task is today indistinguishable from a never-touched one —
the kanban card renders the same `📋 Ready` badge, and `TaskDetailScreen` has no
widget for the field, so it is invisible even though it is in the file. This
child closes that deferral and delivers the parent t1603's own `## Verification`
section in full, standalone, with no dependencies.

**Constraint: visibility, not routing** (`aidocs/gates/ledger-driven-reentry.md`).
Read-only surface. No edit affordance; no path that starts implementation from a
`Ready` task.

## Settled decisions (from t1603 planning — do not re-litigate)

- The card shows a **word, not a glyph**: `📋 Ready · Planned`. Workflow state
  must be explicit, not a symbol the user has to learn.
- **No timestamp on the card** (~36 usable columns inside a 40-column kanban
  column). The approval time goes in the detail view.
- **An unmarked task renders byte-identically to today** — asserted, not assumed.

## Verification findings (this pass — plan corrected against live code)

Every anchor was re-checked; several had drifted and are corrected throughout.

| Claim | Status |
|---|---|
| `_followup_marker` def | **:3411** (was cited :3312) |
| `TaskCard.compose` badge block | **:3188-3197**, append at **:3194** (was :3186-3189) |
| `TrailTaskCard.compose` badge | **:3552-3554** (was :3550) |
| `_build_tracking_fields` | **:6583**; collapsible count at **:6714** (was :6579) |
| `_normalize_opaque_scalar` | `board/aitask_merge.py:151` ✓ |
| deferral to resolve | `aitasks_extension_points.md:283-284` ✓ |
| `Plan: approved` wording | `aitask_ls.sh:853` ✓ |
| "before" stop keeps the marker | `task-workflow/SKILL.md:553` ✓ (canonical skill; the `-fast-` render carries it at :524) |

Substantive findings:

1. **`date` is NOT imported.** `aitask_board.py:11` is `from datetime import
   datetime` only — probed: the module has no `date` attribute. A bare
   `isinstance(raw, date)` would raise `NameError` on exactly the bare-YAML-date
   row of the matrix. **Step 0 below makes the import an explicit edit.**
2. **The loader is `_TaskSafeLoader`** (`lib/task_yaml.py:19`), a SafeLoader
   subclass with an extra `^\d+_\d+$` → str resolver — not plain
   `yaml.SafeLoader`. The type table was re-verified **empirically** against it.
3. **`datetime` is a subclass of `date`**, and `%Y-%m-%d %H:%M` formats both
   (a bare date yields `00:00`). One `isinstance(raw, date)` branch covers both
   rows — no ordering hazard, no second branch to keep in sync.
4. **The app-free detail harness works**: `_build_tracking_fields` reads only
   `meta`, so `TaskDetailScreen._build_tracking_fields(None, meta)` returns the
   widget list with no app boot. Confirmed by probe. Simpler than the
   pilot-based harness in `test_board_detail_followup_kind.py`, and it makes
   "the row is absent" a *structural* assertion.
5. **`escape()` is empirically necessary**: `ReadOnlyField("… 2026-02-01 [b]14:30")`
   renders as `Plan approved: 2026-02-01 14:30` — the `[b]` is silently eaten.
   Escaped, it renders literally.
6. **The `elif` branch has three triggers, not one** — see Step 3.
7. **`status` is not a `str`.** Both call sites read it raw from type-honest
   frontmatter (`:3113`, `:3552`) and interpolate with an f-string, which is
   total over any type. A `" · ".join()` over the raw value raises `TypeError`
   for `[Ready]`, `42`, `True` or a bare `date` — verified by probe — which
   would crash card composition. Step 2's `str()` and the regression cases in
   `## Verification` exist for exactly this.

**Non-goal, stated explicitly:** `InFlightTaskCard` (`:3271`) is a third card
class but renders **no** status badge — it yields `next_action` / `gate_summary`
instead, and only two `📋` sites exist in the file. The in-flight view also holds
only `Implementing` tasks, which by construction carry no marker. Surfacing
marked `Ready` tasks there is **t1603_3's** job. `TrailGhostCard` carries
`metadata = {}` and is likewise untouched, mirroring the t1468_3 decision at
`:3595`.

## Pre-phase (risk mitigations)

### 1. [characterize_status_badge_render]

**Runs first, against unmodified code, committed on its own before any
production edit.**

Add `tests/test_board_plan_approved_marker.py` capturing the exact
`render().plain` of the card status line for a task with **no**
`plan_approved_at`, in **three** shapes — one per trigger of the `elif` branch
Step 3 introduces:

- a plain `Ready` card (`📋 Ready`);
- a **blocked** card (`🚫 blocked`);
- a **parent with an implementing child** (badge suppressed);
- a card whose `status` is a truthy **non-string** (e.g. `status: [Ready]` →
  today renders `📋 ['Ready']`). This shape is only safe by accident today —
  the f-string is total — so it must be in the baseline before Step 2 replaces
  that f-string with a `join`.

**Positive control (mandatory):** perturb the badge literal at
`aitask_board.py:3194` — *verify the edit actually landed on that line* (re-read
it) before running, not on a docstring — confirm the test fails naming the
expected string, then restore. A characterization test never seen to fail guards
nothing.

Commit this test alone.

## Implementation Steps

### 0. Import `date`

`aitask_board.py:11` — `from datetime import datetime` → `from datetime import
date, datetime`. Required by Step 1; `date` is currently unbound at module scope
and nothing else shadows the name (checked).

### 1. `_plan_approved_marker(metadata) -> str | None`

The render boundary. Place beside `_followup_marker` (`:3411`), mirroring its
docstring conventions. **Total** over what the loader actually produces
(empirically verified this pass):

| Input | Result |
|---|---|
| absent / `None` / `""` / blank string | `None` |
| `str` `"2026-02-01 14:30"` (the canonical form `aitask_update.sh:822` writes) | verbatim |
| `datetime` (a hand-edited `…14:30:05` parses as one) | `%Y-%m-%d %H:%M` |
| `date` (a bare `2026-02-01` parses as one) | `%Y-%m-%d %H:%M` |
| list / dict / int / bool | fixed literal `"set (unreadable)"` |

Use a **single `isinstance(raw, date)` branch** for rows 3–4 (finding 3).
Returning `None` vs a string keeps "no marker" structurally distinct from "a
marker that looks odd", so every call site is one `if marker:`. The fallback
literal follows `_followup_marker`'s documented rule: a bad value that silently
vanishes is indistinguishable from a task that never had a marker.

**Do NOT reuse `_normalize_opaque_scalar`** (`board/aitask_merge.py:151`). It
returns `""` for every non-`str` — correct for *comparison*, wrong for
*rendering*: it would hide a `datetime`-parsed marker that `ait ls` (a bash
frontmatter parse) still displays. **Record this divergence in a comment** so the
next reader does not "fix" it into a shared helper.

### 2. `_status_badge_text(status, plan_marker) -> str` — the single authority

It owns **both** badge forms, so a wording change cannot land on one and miss the
other:

```python
def _status_badge_text(status, plan_marker: str | None) -> str:
    """The one authority for a card's status badge text.

    Both call-site forms come from here: the ordinary badge and the
    qualifier-only badge a *suppressed* card falls back to. A second literal
    at the suppression site would let `· Planned` and `Planned` drift apart on
    the next wording change, so that site calls this with an empty status
    rather than hard-coding its own string.

    `status` is a raw frontmatter value, NOT a `str`: `lib/task_yaml.py` leaves
    values type-honest, so a hand-edited file yields `[Ready]`, `42`, `True` or
    a `date`. The `str()` is load-bearing — `join` raises `TypeError` on any of
    those and would crash card composition, where the f-string it replaces was
    total. Truthiness is tested on the RAW value so falsey shapes (`""`,
    `None`, `0`, `[]`) suppress exactly as the previous `if status:` guard did.
    """
    parts = [str(p) for p in (status, "Planned" if plan_marker else None) if p]
    return f"📋 {' · '.join(parts)}" if parts else ""
```

**Parity note:** `f"{x}"` is `format(x, "")`, which equals `str(x)` for every
type reachable here (`list`, `int`, `bool`, `date`, `datetime`, `str`), so the
rendered bytes are unchanged for non-string statuses too — which is what lets
the characterization baseline cover them.

Total over all four combinations — `("Ready", ts)` → `📋 Ready · Planned`;
`("Ready", None)` → `📋 Ready`; `("", ts)` → `📋 Planned`; `("", None)` → `""`
(the degenerate case; call sites append nothing). All four are pinned in the
unit matrix, alongside the non-string cases below.

### 3. `TaskCard.compose` (`:3188-3197`)

The badge is **suppressed** on three conditions — blocked, empty status, or
implementing children. A `Ready` task can legitimately be blocked *and* marked:
the risk-mitigation "before" stop deliberately keeps the marker
(`task-workflow/SKILL.md:553`). So the qualifier must survive suppression:

```python
plan_marker = _plan_approved_marker(meta)
if not is_blocked and status and not implementing_children:
    status_parts.append(_status_badge_text(status, plan_marker))
elif plan_marker:
    status_parts.append(_status_badge_text("", plan_marker))
```

**The `implementing_children` trigger is production-reachable, and rendering it
is deliberate.** A parent can carry a marker *and* have an implementing child:
the single-repo decomposition cleanup (`planning.md:281`) reverts the parent with
`--status Ready --assigned-to ""` and — unlike its cross-repo twin
(`cross-repo-child-assignment.md:115`, whose comment claims to "mirror the
single-repo decomposition cleanup") — **does not clear `plan_approved_at`**. So a
task that was approved-and-stopped, then re-picked and decomposed, keeps a marker
its single-task plan no longer justifies.

The board is a read-only mirror: it renders what the file says rather than
deciding the field is wrong, and showing `📋 Planned` there is what makes that
stale marker *visible*. **Do not "fix" the workflow gap in this task** — it is a
task-workflow change, out of scope for a read-only board child. Record it at
**Step 8b (Upstream Defect Follow-up)** as a named spawned task against the
`planning.md` / `cross-repo-child-assignment.md` divergence, so it is tracked as
an artifact rather than a note.

### 4. `TrailTaskCard.compose` (`:3552-3554`)

Use the helper **and widen the guard**. The original plan said "there is no
suppression logic here" — that was **wrong**, and it shipped a real divergence
before being caught in review. `if status:` *is* a suppression condition: the
same empty-status trigger `TaskCard`'s `elif plan_marker` branch exists to
cover. Left as-is, a task carrying a marker with no `status:` key rendered
`📋 Planned` on the kanban card and **nothing at all** in By-Trail.

```python
status = self.task_data.metadata.get("status", "")
plan_marker = _plan_approved_marker(self.task_data.metadata)
if status or plan_marker:
    yield Label(_status_badge_text(status, plan_marker), classes="task-info")
```

`_status_badge_text` returns `""` iff both inputs are falsey, so `status or
plan_marker` is precisely "the helper has something to say" — guard and helper
agree by construction rather than as two separately-maintained truth tables.
**Single-sourcing the badge *text* was not enough; the *render condition* was
duplicated too.**

### 5. Detail row — `_build_tracking_fields` (`:6583`)

One guarded entry, placed after the `implemented_with` row and before the
`dates` row (provenance grouping; `created`/`updated` stays last):

```python
plan_marker = _plan_approved_marker(meta)
if plan_marker:
    out.append(ReadOnlyField(
        f"[b]Plan approved:[/b] {escape(plan_marker)}", classes="meta-ro"))
```

`escape` is already imported (`:18`). Absent marker ⇒ no row at all; the
collapsible's `Tracking & provenance (<n>)` count (`:6714`) adjusts for free.
Wording matches the existing surface, which renders `Plan: approved <ts>`
(`aitask_ls.sh:853`).

### 6. Docs

Resolve the "(Board layer 3 ships separately.)" parenthetical at
`aidocs/framework/aitasks_extension_points.md:283-284`. **It wraps across those
two lines** — `grep "ships separately"` alone will not find it. Leave the sibling
deferrals for `anchor` (`:173`) and `boardgroup` (`:206`) alone. The website
reference row is **t1603_5's** job.

## Verification

New `tests/test_board_plan_approved_marker.py` (module idiom follows
`tests/test_board_followup_glyph.py`: synthetic-module board load threaded as
`ab`, `bf.FixtureTask(..., extra={...})` to place the frontmatter key):

- **`_plan_approved_marker` matrix** — one case per table row, app-free;
- **`_status_badge_text` matrix** — all four `(status, marker)` combinations;
- **non-string-status regression** — `[Ready]`, `42`, `True` and a `date`, each
  with and without a marker, must **not raise** and must render exactly what the
  pre-phase baseline captured (`📋 ['Ready']`, `📋 ['Ready'] · Planned`, …).
  This is the case that turns the `join` from a crash into a no-op change;
- **falsey non-string suppression** — `0` and `[]` suppress the badge exactly as
  `""` does, matching the previous `if status:` guard;
- **single-authority drift guard** — assert the `📋` glyph appears in exactly
  one *rendered string literal*, i.e. only inside `_status_badge_text`. Scope it
  via `ast` over non-docstring `Constant` nodes, **not** `source.count()`: the
  raw count fires on explanatory comments about the badge, and a guard that
  fails on its own documentation is a guard people delete. An f-string's static
  pieces are `Constant` nodes and are still caught. Failure message names the
  offending line numbers and the remedy. *Note for t1603_3:* if that sibling
  adds a legitimate new badge surface, this guard is the prompt to route it
  through the helper or to widen the guard deliberately;
- **empty-status qualifier on BOTH card surfaces** — a task with a marker and no
  `status:` key must read `📋 Planned` on `TaskCard` *and* `TrailTaskCard`.
  Two separately-written conditions over one rule, so a single-surface test
  lets them drift — which they did;
- **widened-guard parity** — a trail card with neither status nor marker still
  yields no status label, and emits no blank one;
- **card render**: a marked task reads `📋 Ready · Planned`;
- **exact-parity control**: an unmarked card's status line is byte-identical to
  the pre-phase baseline — for all three shapes (plain, blocked, implementing
  child);
- **suppressed-badge cases**: blocked + marked, **and** implementing-child +
  marked, both surface `📋 Planned`. The second needs a parent fixture plus
  `mgr.child_task_datas["t<parent>_1_child.md"]` holding a Task with
  `status: Implementing` — that dict-key prefix is what
  `get_child_tasks_for_parent` (`:1604`) matches on;
- **`TrailTaskCard`** carries the qualifier (the second call site);
- **detail row** present when marked, and **absent from the returned widget
  list** when unmarked (structural, via the app-free
  `_build_tracking_fields(None, meta)` call — assert no widget, not a blank one);
- **junk marker** (a list) renders the fallback literal and does not vanish;
- **a marker containing `[`** renders literally rather than being markup-parsed;
- **`test_fixture_facts`** precondition test, so nothing passes vacuously if the
  fixture is reshaped.

**Selector caution:** `TrailTaskCard` yields four `.task-info` labels
(`trail-badges`, status, `trail-drift`, `trail-ops`), so `.first(Label)` returns
the *badges* line, not the status line. Select the status label **by content**
(the one starting `📋`) and **assert it was found** before asserting on it —
otherwise a badge that vanished entirely would make the test pass silently.

Run: `bash tests/run_all_python_tests.sh --test-dir tests` — **read only the last
line** (`PYTHON SUITE: PASSED|FAILED`); use `set -o pipefail` if piping. This
module joins the parallel pool; no serial-carve-out edit is needed.

**Live check:** this repo has zero tasks carrying the marker, so seed one with
`./.aitask-scripts/aitask_update.sh --batch <n> --plan-approved-at now`, open
`ait board`, confirm the card badge and the detail row, then clear it with
`--plan-approved-at ""` and confirm the indicator disappears on refresh.

## Risk

### Code-health risk: low
- Four small edits plus two new pure functions, all in `aitask_board.py`; the
  badge refactor is behaviour-preserving and all three suppression triggers are
  pinned by the characterization baseline. · severity: low (residual — addressed
  by inline pre-phase `characterize_status_badge_render`) · → mitigation: inline
  pre-phase `characterize_status_badge_render`
- Replacing a total f-string with a `join` narrows the accepted type of a raw
  frontmatter value, and `status` is type-honest — an unnormalized join would
  crash card composition on a hand-edited file. Contained by `str()` in the
  helper plus a non-string baseline case and an explicit regression matrix. ·
  severity: low (residual — addressed by inline pre-phase
  `characterize_status_badge_render`) · → mitigation: inline pre-phase
  `characterize_status_badge_render`
- The `implementing_children` + marker case renders a **stale** marker the
  workflow failed to clear (`planning.md:281`). Rendering it is the deliberate
  read-only-mirror choice, so the residual is a workflow defect this task does
  not own. · severity: low · → mitigation: none here — routed to a spawned
  upstream-defect follow-up at Step 8b

### Goal-achievement risk: low
- Requirements are fully specified by the parent's settled decisions (word not
  glyph, no timestamp on the card, byte-identical unmarked render), and each maps
  to an assertion. This pass verified the YAML type table, the missing `date`
  import, and the markup-escape requirement empirically rather than by
  inspection. · severity: low · → mitigation: none (accepted residual)

### Planned mitigations
- timing: pre-phase | name: characterize_status_badge_render | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — behaviour-preserving refactor of the two `📋` composition sites | desc: capture the exact rendered card status line for unmarked plain, blocked, and implementing-child cards against unmodified code, with a verified positive control, committed before any production edit

## Step 9 (Post-Implementation)

Standard closure: commit, merge per the plan header (current-branch mode, `main`
for both fields), archive the task and this plan. Step 8b carries the
upstream-defect follow-up for the `planning.md:281` marker-clear gap.

## Implementation notes

All steps landed as planned; no deviations from the approved design.

**Pre-phase (commit 1, `e23e549`).** `characterize_status_badge_render` was
written and run against unmodified code. Every expected string was **read off
the running board**, not predicted — which immediately corrected one assumption:
the implementing-child shape yields **no status label at all** (with no assignee
`status_parts` ends up empty), so the baseline for it is an absence, not a
string. Positive control: perturbing the badge literal at `aitask_board.py:3194`
(verified landed by re-reading the line, and by `git diff` showing that one line)
failed `test_baseline_plain_card` and
`test_baseline_non_string_status_renders_via_f_string` naming the expected
strings, and correctly left the trail-card test passing. Restored byte-identical
before implementing.

**Steps 0–6 (commit 2).** Import widened to `from datetime import date,
datetime`; `_plan_approved_marker` and `_status_badge_text` added beside
`_followup_marker`; both card call sites and the detail row wired; the
`aitasks_extension_points.md:283-284` deferral resolved into a real layer-3
description.

**Negative control.** With the pre-change board swapped back in (via
`git show HEAD:<path>`, never a stash), **20 of 27** tests fail and 7 pass. The 7
are exactly the six characterization baselines plus
`test_the_row_is_absent_entirely_when_unmarked` — i.e. every assertion that
describes *unchanged* behaviour passes, and every assertion that describes new
behaviour fails. The parity claim is therefore load-bearing in both directions.

**Width.** Widest reachable badge is `📋 Implementing · Planned` at 25 cells and
`🚫 blocked | 📋 Planned` at 23, against the ~36 usable columns inside a
40-column kanban column. The "no timestamp on the card" decision holds with room
to spare.

**Live check.** Seeded `--plan-approved-at now` on a real task, loaded it through
the board's own `Task.from_text` + `TaskCard`, and confirmed both surfaces:
card `🚫 blocked | 📋 Planned`, detail row `Plan approved: 2026-08-30 16:25`.
That task is blocked on this one, so the live run exercised the
**suppression-survival branch on a real file** rather than only in a fixture.
Marker cleared afterwards and the file restored byte-identically (the two writes
had bumped `updated_at`).

**Suite.** `bash tests/run_all_python_tests.sh --test-dir tests` →
`PYTHON SUITE: PASSED (runner=pytest, exit=0)` (5771 passed, 2 skipped, plus the
5 serial carve-out tests).

**Deferred to Step 8b.** The `implementing_children` + marker case is reachable
because the single-repo decomposition cleanup (`planning.md:281`) omits the
`--plan-approved-at ""` its cross-repo twin
(`cross-repo-child-assignment.md:115`) performs — a task-workflow defect this
read-only board child deliberately does not fix.

### Review correction: the By-Trail empty-status divergence

Caught in Step 8 review, after the first implementation pass. **Confirmed by
probe**, not argued: a task with `plan_approved_at` and no `status:` key
rendered `📋 Planned` on `TaskCard` and produced *no status label at all* on
`TrailTaskCard`.

Root cause was a plan error, not a coding slip — Step 4 originally asserted
"there is no suppression logic here" about `TrailTaskCard`. Its `if status:` is
exactly the empty-status suppression trigger that `TaskCard`'s `elif
plan_marker` branch was added to survive. Introducing `_status_badge_text`
single-sourced the badge **text** while leaving the **render condition**
duplicated across the two surfaces, so the drift the helper was meant to prevent
reappeared one level up.

Fixed by widening the guard to `if status or plan_marker:` — the helper's own
non-empty condition — plus two regression tests: the qualifier asserted on both
surfaces in one test (so they cannot drift independently again), and a parity
test that the widened guard adds only the qualifier case and never emits a blank
label.

The drift guard itself was rebuilt in the same pass. As first written it counted
raw `📋` occurrences in the source and failed on the explanatory **comment**
added beside the fix — a false positive on prose. It now walks the AST and
counts only non-docstring string constants, so documentation may name the glyph
freely while any second *rendered* literal still trips it.

Three negative controls, all run:

- narrowing the trail guard back to `if status:` fails the both-surfaces test;
- a comment mentioning the glyph does **not** trip the drift guard;
- a second rendered `f"📋 {status}"` does, naming both line numbers.

## Final Implementation Notes

- **Actual work done:** All six planned steps landed as designed. `date` added to
  the `datetime` import; `_plan_approved_marker` (render boundary, total over the
  loader's type-honest values) and `_status_badge_text` (single authority for
  both badge forms) added beside `_followup_marker`; both card call sites and one
  guarded `ReadOnlyField` detail row wired; the
  `aitasks_extension_points.md:283-284` deferral resolved into a real layer-3
  description. New `tests/test_board_plan_approved_marker.py` — 29 tests across
  four classes, committed in two commits (pre-phase characterization first).

- **Deviations from plan:** One, and it was a plan **error** rather than a
  drifting implementation. Step 4 as approved said `TrailTaskCard` has "no
  suppression logic"; its `if status:` is exactly the empty-status suppression
  trigger. Corrected in place, with the wrong claim called out rather than
  quietly overwritten. Two smaller in-flight corrections: the
  implementing-child baseline turned out to be *no status label at all* rather
  than a suppressed-badge string (discovered by reading the running board, which
  is why the pre-phase reads rather than predicts), and the drift guard was
  rebuilt from `source.count()` to an AST walk.

- **Issues encountered:**
  1. *By-Trail empty-status divergence (found in Step 8 review, after the first
     pass).* A task with a marker and no `status:` key rendered `📋 Planned` on
     `TaskCard` and nothing at all in By-Trail. Introducing `_status_badge_text`
     single-sourced the badge **text** while leaving the **render condition**
     duplicated, so the drift the helper was meant to prevent reappeared one
     level up. Fixed by widening the guard to `if status or plan_marker:` — the
     helper's own non-empty condition, so guard and helper now agree by
     construction. Both surfaces are asserted in one test so they cannot drift
     independently again.
  2. *The drift guard failed on its own comment.* Counting raw `📋` occurrences
     fired on explanatory prose beside the fix. Rebuilt to walk the AST and count
     only non-docstring string constants: documentation may name the glyph, a
     second rendered literal still trips it, and f-string static pieces are
     `Constant` nodes so they remain caught.
  3. *A near-miss the review caught before it shipped:* the first draft of
     `_status_badge_text` used a bare `' · '.join(...)` over the raw `status`.
     That raises `TypeError` for `[Ready]`, `42`, `True` or a `date` — all
     reachable from a hand-edited file — where the f-string it replaced was
     total, and a raising `compose` takes the board down. The `str()` and the
     non-string regression matrix exist for exactly this.

- **Key decisions:**
  - *Render the stale marker rather than suppress it.* The
    `implementing_children` + marker case is production-reachable (see upstream
    defects). The board is a read-only mirror: showing `📋 Planned` is what makes
    the staleness visible, rather than the board deciding the field is wrong.
  - *Boundary diverges from `_normalize_opaque_scalar` on purpose.* That helper
    answers `""` for every non-`str` — right for comparison, wrong for rendering,
    since it would hide a datetime-parsed marker `ait ls` still displays. Pinned
    by a test that asserts the divergence, not just the behaviour.
  - *Guard conditions, not just strings, must be single-sourced.* The lesson of
    issue 1, and why the empty-status case is asserted across both surfaces in a
    single test.

- **Upstream defects identified:**
  - `.claude/skills/task-workflow/planning.md:281 — single-repo decomposition
    cleanup reverts the parent with `--status Ready --assigned-to ""` but omits
    the `--plan-approved-at ""` its cross-repo twin
    (`cross-repo-child-assignment.md:115`) performs, so a task that was
    approved-and-stopped and later decomposed keeps a `plan_approved_at` marker
    its single-task plan no longer justifies. The cross-repo site's own comment
    claims to "mirror the single-repo decomposition cleanup", so one of the two
    is wrong by its own description. Out of scope here: this is a task-workflow
    change, and t1603_1 is a read-only board surface.

- **Notes for sibling tasks:**
  - **t1603_3** (in-flight / planned lane) will most likely add a badge surface.
    `_status_badge_text` is the single authority and
    `test_the_badge_glyph_has_exactly_one_home` will fail on any new rendered
    `📋` literal — that failure is the prompt to route the new surface through
    the helper, or to widen the guard deliberately. `InFlightTaskCard`
    (`aitask_board.py:3271`) renders **no** status badge today (it yields
    `next_action` / `gate_summary`), so the lane work starts from zero there.
  - **Card-render test harness.** `_info_texts` + `_status_line` in the new test
    module select the status label **by content**, because `TrailTaskCard` yields
    four `.task-info` labels and `.first(Label)` returns the trail badges. Reuse
    that rather than positional indexing.
  - **App-free detail-screen harness.** `TaskDetailScreen._build_tracking_fields`
    reads only its `meta` argument, so
    `_build_tracking_fields(None, meta)` returns the widget list with no app
    boot — much cheaper than the pilot-based harness in
    `test_board_detail_followup_kind.py`, and it makes "the row is absent" a
    structural assertion. t1603_4 (expanded gate surface in task detail) can use
    the same trick.
  - **Frontmatter values are type-honest.** Any new board render boundary needs
    the same totality table, and any new `join` over a raw value needs `str()`.
