---
Task: t1603_surface_deferred_plan_marker_on_the_board.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1603 — Surface the deferred-plan marker on the board

## Context

t1595 introduced the `plan_approved_at` frontmatter marker ("plan approved,
implementation deliberately deferred") and shipped two read surfaces: `ait ls -v`
/ `--plan-approved`, and the planning step's existing-plan prompt. It explicitly
deferred the board — `aidocs/framework/aitasks_extension_points.md:283-284`
records "(Board layer 3 ships separately)", and the archived p1595 plan names a
follow-up with `depends: [1595]`. This is that follow-up. t1596 (cross-repo
exploration from a parallel-planning throughput study) was folded in, adding the
in-flight view's inability to express *workflow phase* as a second problem.

Today the board is blind to the whole parallel-planning workflow ("plan several
tasks, defer their implementations, pick them up later"):

- a kanban card renders `📋 Ready` identically whether or not a plan was approved;
- `_inflight_item_for()` hard-filters `status == "Implementing"`
  (`aitask_board.py:1874`), so an approved-and-stopped task — which is `Ready` by
  design — never appears in the in-flight view;
- `TaskDetailScreen` has no widget for the field, so it is invisible there too;
- the three in-flight lanes group by *required next actor*, never by gate reached,
  so no phase distribution is readable from the layout;
- with no ledger (the `default.yaml` profile records no gates) in-flight cards
  degrade to "No gate information yet" instead of deriving what is derivable.

**Intended outcome:** the board becomes a useful operational workflow view —
it answers "which tasks already finished planning?", "what phase is each task
in?" and "what gate is it waiting on?" — without ever becoming a routing signal.

### Hard constraint carried from t1595

**Visibility, not routing** (`aidocs/gates/ledger-driven-reentry.md`, "The state
is visible, and visibility is not routing"). No board affordance may start
implementation from a `Ready` task without going through the planning checkpoint
and its remote drift check. Concretely: a task in the new Planned lane offers
`p pick` and nothing else — never `g resume`.

### Decisions taken during planning

| Question | Decision |
|---|---|
| Card rendering | Modify the status badge — `📋 Ready · Planned`. Explicit word, not a glyph to learn. **No timestamp on the card.** An unmarked task must render *byte-identically* to today. |
| Timestamp | Detail screen only. |
| In-flight lanes | Keep the three existing lanes. **Add a fourth "Planned" lane, placed first.** |
| Phase | Per-task workflow phase shown on every in-flight card, orthogonal to the lane. |
| Gate progress | Compact per-card summary; the full passed/current/pending list lives in an expanded surface, not on the card. |
| No ledger | Degrade honestly — and **never infer a phase that contradicts `status`**; see "Two axes" below. |
| `docs_updated` | `type: machine` but `kind: procedure`, so `_human_pending_gates` never sees it and it currently reads "Agent can continue" although a headless agent cannot run it. The phase model gets a distinct **needs-attended-agent** phase, driven off the registry's `kind` field so any future procedure gate inherits it. |

### The two axes — one coherent model

The in-flight view is often described as "actor-grouped", but that is an
under-description of what it already does, and adding Planned as a fourth lane
only looks exceptional under that wrong description. The dataclass field is
literally `next_action` (`aitask_board.py:120`), and the lane titles read
"Needs your action" / "Agent can continue" / "Blocked" — a **next-action** axis,
not an actor one. This plan names it that way and keeps two axes strictly apart:

- **Lane = what happens next.** Four values, one axis, no exception:
  `planned` (a human picks it) · `human` (a human acts on a gate) ·
  `agent` (an agent resumes) · `blocked` (nothing can happen).
- **Chip = where the task sits in the workflow.** Five values:
  `plan_approved` · `implementing` · `awaiting_review` ·
  `needs_attended_agent` · `post_impl`. Rendered on **every** in-flight card,
  Planned ones included, so the chip's meaning never depends on which lane it
  is in.

**The decision, stated once so code, tests and docs cannot diverge:** Planned is
**intentionally a fourth lane** on the renamed next-action axis. It is not an
actor lane and not a phase lane — the axis is "what happens next", and "a human
picks it" is a fourth value of that axis alongside "a human acts", "an agent
resumes" and "nothing can happen".

**Every task occupies exactly one lane and carries exactly one phase.**
`InFlightItem.group` stays a scalar `str` (`:120`) and the refresh path appends
each item to exactly one lane list (`:9093-9101`). Nothing in this plan makes a
task appear twice, and no multi-lane or multi-group model is proposed.

"Orthogonal" here means precisely one thing: **neither axis determines the
other.** It does **not** mean a task spans lanes. The evidence is that the
phase→lane mapping is not a function in either direction — shown with two
*different* tasks per row:

*Same phase, different lanes* (so the lane is not derivable from the phase):

| # | Task | Status | Phase (chip) | Lane |
|---|---|---|---|---|
| A | approve-and-stop | `Ready` + marker | `plan_approved` | **Planned** |
| B | in-flight, `resume_point == IMPLEMENT` | `Implementing` | `plan_approved` | **Agent can continue** |

A and B are two distinct tasks in two distinct rows of the board. What makes
them share a phase is that an approve-and-stop task reverts to `Ready` but
**keeps its gate ledger** — `plan-approved-stop.md` records `plan_approved: pass`
before reverting the status, and nothing strips the `## Gate Runs` section.

*Same lane, different phases* (so the phase is not derivable from the lane):

| # | Task | Lane | Phase (chip) |
|---|---|---|---|
| C | pending human gate | Needs your action | `awaiting_review` |
| D | `resume_point == POSTIMPL` | Needs your action | `post_impl` |

Both directions hold, so the chip is a real second reading rather than a
restatement of the lane. That is the whole claim.

**Where the chip is redundant, it stays anyway.** A Planned-lane task's chip
reads `plan_approved`, which its lane already implies. The chip is still
rendered, because a chip that disappears on some cards would make its absence
ambiguous — and because row B proves the same chip value is *not* redundant one
lane over.

t1603_5 documents exactly this model, using rows A–D verbatim, and t1603_3's
tests assert it: one lane per item, and the A/B and C/D pairs as fixtures.

### Findings that change the work

1. **The task file's "Key files" names a path that does not exist.**
   `.aitask-scripts/tuis/board/reference.md` is not in the repo; the real
   document is `website/content/docs/tuis/board/reference.md`.
2. **`plan_approved_at` is not always a `str`.** Verified against the real
   parser (`lib/task_yaml.py`, `yaml.SafeLoader`): the canonical
   `2026-02-01 14:30` stays a `str`, but a hand-edited `2026-02-01 14:30:05`
   parses as a `datetime` and a bare `2026-02-01` as a `date`. Any render
   boundary must be total over those, plus list/dict/bool/None.
3. **`_normalize_opaque_scalar` (`board/aitask_merge.py:151`) is not reusable
   here.** It returns `""` for every non-`str`, which is correct for *comparison*
   and wrong for *rendering* — it would silently hide a marker that `ait ls`
   (a bash frontmatter parse) still displays.
4. **The `📋` badge is suppressed** when a card is blocked or has implementing
   children (`aitask_board.py:3186-3189`). A `Ready` task can legitimately carry
   the marker *and* be blocked — the risk-mitigation "before" stop deliberately
   retains it (`task-workflow/SKILL.md:553`) — so the qualifier must survive that
   suppression.
5. **There are exactly two `📋 {status}` call sites**, and they are not the ones
   the task file predicts: `TaskCard.compose` (`:3190`) and `TrailTaskCard.compose`
   (`:3550`). The detail screen renders status through a different idiom
   (`ReadOnlyField` / `CycleField`).
6. **The board applies no frontmatter allowlist.** `Task.metadata` is the whole
   parsed dict, so `plan_approved_at` already arrives intact; `BOARD_KEYS` is a
   *write* vocabulary and the field correctly stays out of it. Its merge rule is
   already wired (`_BASE_AWARE_FIELDS`, deletion-aware).

---

### Pre-phase (risk mitigations)

Confirmed inline mitigations that must land **before** the implementation they
de-risk. Each names the child that owns it; the child's own plan carries the
step verbatim.

- **`characterize_status_badge_render`** *(owned by t1603_1)* — before touching
  the badge composition, commit a characterization test capturing the exact
  current card status-line render for tasks carrying **no** `plan_approved_at`.
  Written and committed against the *unmodified* code, so the "unmarked tasks
  render exactly as before" parity assertion has independent ground truth rather
  than an expectation copied out of the new implementation. Must be seen to fail
  if the badge text is perturbed (a positive control), otherwise it guards
  nothing.
- **`phase_model_is_the_single_authority`** *(owned by t1603_3)* — before adding
  the phase chip, make `_inflight_item_for`'s actor classification **consume**
  t1603_2's phase model rather than deriving a second verdict from the same
  `TaskGateState` in parallel. Ship a test asserting lane and chip cannot
  disagree across every ledger state (including `stale_signed`, failed-gate and
  no-ledger). This is what stops the two groupings drifting into contradiction
  on the same card.

## Approach: decompose into 5 children + 1 verification sibling

The broadened scope spans a card badge, a detail row, a new phase model with
ledger-free degradation, in-flight lane membership for `Ready` tasks, compact
gate progress, an expanded gate surface, and documentation across several files.
That is `effort: high` work in a task filed `effort: low`, against a 13k-line
TUI module. Each child below is independently testable and independently
landable.

```
t1603_1  card status qualifier + detail row      no deps
t1603_2  workflow-phase model + degradation      depends: 1603_1
t1603_3  in-flight Planned lane + phase chips    depends: 1603_2
t1603_4  expanded gate surface                   depends: 1603_3
t1603_5  website documentation                   depends: 1603_4
t1603_6  manual verification (aggregate sibling) depends: 1603_5
```

After creating the children the parent reverts to `Ready` with `assigned_to`
cleared and its lock released; children are picked in fresh contexts.

---

### t1603_1 — Card status qualifier + detail row

Ships t1603's own Verification section on its own. No dependencies.
**Owns inline pre-phase `characterize_status_badge_render`** — it runs first, as
the child's opening step, against the unmodified code.

**New render boundary** in `aitask_board.py`, modelled on `_followup_marker`
(`:3312`) — the file's established "totality boundary over a frontmatter field"
pattern:

```python
def _plan_approved_marker(metadata) -> str | None:
    """Display string for `plan_approved_at`, or None when the task carries no
    deferred approved plan.

    Total over what YAML actually produces: the canonical `YYYY-MM-DD HH:MM`
    arrives as `str`, but a hand-edited value with seconds arrives as
    `datetime` and a bare date as `date`. A present-but-unrecognised value
    still renders — a bad value that silently vanishes is indistinguishable
    from a task that never had a marker (the `_followup_marker` rule).
    """
```

- absent / `None` / empty / blank `str` → `None`
- `datetime` / `date` → formatted `%Y-%m-%d %H:%M`
- non-blank `str` → returned verbatim
- anything else (list, dict, int, bool) → a fixed literal, e.g. `"set (unreadable)"`

**Single-sourced badge composition.** Both `📋` call sites go through one helper
so the two cannot drift:

```python
def _status_badge_text(status: str, plan_marker: str | None) -> str:
    return f"📋 {status} · Planned" if plan_marker else f"📋 {status}"
```

- `TaskCard.compose` (`:3186-3189`) — use the helper, and add an `elif` so a
  suppressed badge (blocked / implementing children) still emits a standalone
  `📋 Planned` part rather than hiding an approved plan.
- `TrailTaskCard.compose` (`:3550`) — use the helper.

**Detail row** — one guarded entry in `_build_tracking_fields` (`:6579`), the
"Tracking & provenance" collapsible, mirroring the `Assigned to:` / `Created:`
rows exactly:

```python
plan_marker = _plan_approved_marker(meta)
if plan_marker:
    out.append(ReadOnlyField(
        f"[b]Plan approved:[/b] {escape(plan_marker)}", classes="meta-ro"))
```

`ReadOnlyField` parses Rich markup, so the value is passed through
`rich.markup.escape` — a hand-edited value containing `[` would otherwise be
swallowed. Absent marker ⇒ no row at all (the section's count in the collapsible
title adjusts for free).

**Docs in this child:** resolve the "(Board layer 3 ships separately)" deferral
at `aidocs/framework/aitasks_extension_points.md:283-284`.

**Tests** — new `tests/test_board_plan_approved_marker.py`, modelled on
`tests/test_board_followup_glyph.py` and `tests/test_board_detail_followup_kind.py`:

- app-free `_plan_approved_marker` matrix over every type above (the cheap
  enumeration the follow-up module uses for `FollowupKindFieldRenderTests`);
- card render via `render().plain`: a marked task reads `📋 Ready · Planned`;
- **exact-parity negative control**: an unmarked task's status line is
  byte-identical to the pre-change render;
- the suppressed-badge case (blocked + marked) still surfaces `Planned`;
- detail screen: row present for a marked task, **absent entirely** for an
  unmarked one (assert the widget does not exist, not that it is blank);
- a `test_fixture_facts` precondition test — the module-wide idiom that stops
  assertions passing vacuously if the fixture is reshaped.

### t1603_2 — Workflow-phase model + honest degradation

A **pure, app-free seam** — no widgets — so the whole vocabulary is unit-testable
before any UI consumes it. Depends on `_plan_approved_marker` from t1603_1.

Derives, from `(task, GateStateResult, plan-file presence, gate registry)`, a
`(phase, provenance, progress)` triple.

**Phase, with a ledger.** Evaluated in this order:

| Phase | Condition |
|---|---|
| `post_impl` | `archive_decision == "ALL_PASS"` or `resume_point == "POSTIMPL"` |
| `awaiting_review` | pending **human** gate, failed/errored gate, or `stale_signed` |
| `needs_attended_agent` | some gate in `archive_pending` whose registry entry has `kind: procedure` |
| `plan_approved` | `plan_approved` recorded `pass`, implementation not yet past it |
| `implementing` | otherwise |

`needs_attended_agent` reuses the predicate `gate_ledger.unmet_procedure_gates`
already implements (`lib/gate_ledger.py:1871`) — same `kind: procedure` +
not-terminal-satisfied rule — evaluated over the in-memory state rather than
re-reading the file, and asserted equal to that function in a test so the two
cannot drift.

**Progress has exactly one authority: `archive_pending`.** Do **not** count
statuses by hand. `_archive_status_from_state` (`gate_ledger.py:1863`) already
computes `archive_pending` as the active gates that are not satisfied, over the
`effective` view in which stale signatures have been demoted
(`gate_ledger.py:2098-2100`). So:

```
denominator = len(state.active_gates)          # enforced set; filtered excluded
numerator   = denominator - len(state.archive_pending)
current     = state.archive_pending[0]          # the gate the task is waiting on
```

This is precisely the list the archival guard uses, so the chip **cannot claim
progress the workflow will reject** — the failure mode the naïve count has. It
also inherits, for free and without a second implementation, every case that
count would get wrong:

| Case | Handled because |
|---|---|
| profile-filtered gate | not in `active_gates`, so out of both terms |
| `skip` | `_gate_satisfied` treats it as terminal-satisfied |
| stale signature | demoted in `effective`, so it stays in `archive_pending` despite a raw ledger `pass` |
| `fail` / `error` | not satisfied, so still pending; the chip additionally flags it |
| procedure gate | counted normally, and drives `needs_attended_agent` when pending |

This is the rule `TaskGateState`'s own docstring states — *"TUI decision surfaces
(failed-gate classification, pending-human-gate detection, compact counts) must
key off the active set"* (`gate_ledger.py:162-165`) — and the same docstring's
warning that `current` deliberately keeps the raw `pass` for a stale gate is
exactly why a hand-rolled count over `state.current` would over-report.

**Degradation without a ledger — "unknown" is a state, not an inference.**
`has_ledger` false (the `default.yaml` case, today's "No gate information yet"):

| Status | Plan file | Phase | Provenance |
|---|---|---|---|
| `Ready` + marker | any | `plan_approved` | `marker` |
| `Implementing` | present | `implementing` | `derived` (from plan presence) |
| `Implementing` | **absent** | `implementing` | **`unknown`** |

The last row is the correction: an explicit `status: Implementing` must **never**
be re-described as "still planning". The status is the task's own assertion that
implementation began; a missing ledger and a missing plan file mean *we cannot
tell how far it got*, which is a different claim from *it has not started*. Such
a task renders `implementing` with an explicit unverified marker on the chip and
**no progress fraction at all** — not a fabricated `0/N`. This is legacy and
partially migrated work, and mislabelling it would make the view actively
misleading about the population it exists to serve.

Plan-file presence reuses `TaskDetailScreen._resolve_plan_path` (`:6480`),
extracted to a module function rather than reimplemented.

**Tests:** pure-unit, one case per row of both tables, plus:

- the exact combination `status: Implementing` + no ledger + no plan file — a
  named regression case asserting phase `implementing`, provenance `unknown`,
  and **no** fraction;
- `progress` equals `len(active_gates) - len(archive_pending)` for a
  stale-signed fixture, a profile-filtered fixture, a `skip` fixture and a
  failed fixture — the four the user's concern names;
- an invariant test that no gate reported "passed" by the surface appears in
  `archive_pending`;
- a negative control proving the ledger-free path is not silently taking the
  ledger path.

### t1603_3 — In-flight view: Planned lane, admission, phase chips

**Owns inline pre-phase `phase_model_is_the_single_authority`** (runs before the
chip is added) **and inline post-phase `narrow_terminal_lane_budget`** (runs
after the lane renders).

- `_inflight_item_for` (`:1873`): admit `Ready` + marker, returning
  `group="planned"` with `next_action` "approved plan — pick to implement".
  Every existing `Implementing` classification is unchanged.
- `InFlightItem` gains `phase`, `provenance` and `progress` fields.
- `InFlightColumn.TITLES` / `.COLORS` gain `planned`; the refresh path's `grouped`
  dict and its iteration order (`:9093-9101`) become
  `("planned", "human", "agent", "blocked")`.
- `InFlightTaskCard.compose` renders the phase chip and the compact progress in
  place of the current raw `gate_summary` dump.

> **⚠ Admitting Planned tasks opens a routing path that must be closed in the
> same change.** `_ops_hint` (`:3296-3305`) appends `g resume` whenever
> `item.has_ledger` is true — and a Planned task **does** have a ledger: the
> approve-and-stop sequence records `plan_approved: pass` *before* reverting the
> status, and nothing strips the `## Gate Runs` section. Its `resume_point` is
> therefore `IMPLEMENT`. So the naïve admission would put a `g resume` affordance
> on a `Ready` task — precisely the "start implementation without the planning
> checkpoint and its remote drift check" path that t1595's
> visibility-not-routing constraint forbids. `_ops_hint` must gate the resume op
> on the lane (`group != "planned"`), not on `has_ledger` alone.

**Regression guards:**
- ops hints unchanged for every `Implementing` task (assert the rendered hint
  text, not the branch);
- a Planned card offers `p pick` and **must not** offer `g resume` — asserted
  against a fixture that genuinely carries a `plan_approved: pass` ledger entry,
  so the test fails if the gate is written as `has_ledger`-only. A fixture with
  no ledger would pass vacuously and is the wrong control;
- the four-lane grouped dict has no lane that silently swallows an item
  (assert the total across lanes equals `len(get_inflight_items())`);
- **one lane per item** — assert each item's `group` is a single value and that
  no task id appears in more than one lane list, pinning the scalar model the
  documentation describes;
- the two-axes model as fixtures: rows **A/B** (two tasks sharing chip
  `plan_approved` in the Planned and "Agent can continue" lanes) and rows
  **C/D** (two tasks sharing the "Needs your action" lane with chips
  `awaiting_review` and `post_impl`). These are the executable form of the
  claim the website makes; if either pair collapses to a single lane or chip,
  the model is wrong and the test says so.

### t1603_4 — Expanded gate surface

The full gate list, reachable from an in-flight card rather than crowded onto it.
Consumes t1603_2's model; adds **no** new derivation.

**Screen and invocation — reuse, do not invent.** A new `Gates (<n>)`
collapsible section in the existing `TaskDetailScreen`, built by a
`_build_gate_fields(meta)` helper alongside the four that already exist
(`_build_risk_fields` / `_build_relations_fields` / `_build_tracking_fields` /
`_build_lockfiles_fields`, `:6492-6640`) and mounted in `compose` next to them
(`:6700-6726`). Placed after Risk, before Dependencies & hierarchy. Collapsed by
default, like every other section.

This settles the four unspecified points at zero cost:

- **Invocation / binding:** none is added. `enter` on a focused card already
  routes through `KanbanApp.open_task_detail` (`:10526`), and an
  `InFlightTaskCard` is a `TaskCard` with no `trail_entry`, so it takes that path
  today.
- **Focus return:** already handled — `open_task_detail` is passed
  `source_card=focused` and the board's existing `_queue_refocus` restores focus
  when the modal closes. No new lifecycle.
- **Section omission:** the `if fields:` guard used by all four existing sections
  means a task with nothing to report grows no empty section.
- **Arrow-nav order:** a new section shifts field navigation, so
  `tests/test_board_detail_arrow_nav.py` and
  `tests/test_board_detail_collapsible.py` are the sibling guards to update in
  the same commit.

**State semantics — "passed" means effective, not historical.** The section
iterates `state.active_gates` and classifies each from the **same** effective
view t1603_2 uses, so the expanded list and the compact chip can never disagree:

| Rendered as | Condition |
|---|---|
| `✓ <gate>` passed | `current[g].status == "pass"` and `g not in stale_signed` |
| `⚠ <gate>` pass, signature stale — needs re-sign | `g in stale_signed` — **both facts shown, never one without the other** (`gate_ledger.py:167-174`) |
| `⊘ <gate>` skipped (not applicable) | `current[g].status == "skip"` — terminal-satisfied but distinct from pass |
| `✗ <gate>` failed | `status in ("fail", "error")` |
| `◈ <gate>` pending — needs attended agent | pending and registry `kind: procedure` |
| `· <gate>` pending | in `archive_pending`, otherwise |

Gates in `state.filtered_gates` are listed **last, under an explicit
"filtered by profile (audit only)" label**, and are excluded from every count —
the `TaskGateState` contract that a historical run of a filtered gate must never
drive a classification.

**Degraded and error rendering** — the two states the card also has to express,
so they are specified once here and shared:

- `result.error` non-empty → a single row `Gate state unavailable: <error>`. No
  list, no counts.
- `has_ledger` false → `No gate ledger — <phase> (<provenance>)`, using
  t1603_2's provenance, rather than an empty list or a fabricated `0/0`.

**Verification:** one test per row of the classification table above, driven from
real task fixtures rather than hand-built `TaskGateState` objects; the
filtered-gates audit block asserted present-but-uncounted; the error and
no-ledger renderings asserted as text; section omission asserted by widget
absence; and a cross-surface parity test asserting the section's satisfied count
equals the card chip's numerator for the same task.

### t1603_5 — Website documentation

`website/content/docs/tuis/board/reference.md` — Task Card Anatomy diagram
(`:94`), the `### Task Metadata Fields` table (`:397`), and the in-flight
material under `### View Filters` (`:196`): the new Planned lane, the phase
vocabulary and the compact progress format.

**The load-bearing part is the two-axes model** (see above): the reference must
state that lanes answer *what happens next* and chips answer *where the task sits
in the workflow*; that **each task sits in exactly one lane with exactly one
chip**; and that "independent" means neither axis determines the other, not that
a task appears twice. It must carry rows A–D verbatim — A/B being two *different*
tasks that share a chip in different lanes, C/D two different tasks that share a
lane with different chips — since without both pairs a reader will assume the
chip merely restates the lane. It must
also document the progress fraction's denominator (the enforced active set, not
the declared `gates:` list) and that a stale signature counts as *not* satisfied,
since both are surprising without explanation.

Plus the frontmatter table in
`website/content/docs/development/task-format.md`, and a cross-reference from
`website/content/docs/commands/task-management.md`, which already documents the
`ait ls -v` `Plan: approved <ts>` segment.

### t1603_6 — Manual verification (aggregate sibling)

Seeded via `aitask_create_manual_verification.sh` over the children above. This
work is TUI-render and layout heavy — a fourth 44-column lane, chip legibility,
badge parity — which is exactly the class of behaviour a human must confirm in a
real terminal (`aidocs/framework/tui_conventions.md`: a headless `run_test` pin
can diverge from a real pty).

---

### Post-phase (risk mitigations)

- **`narrow_terminal_lane_budget`** *(owned by t1603_3)* — after the fourth lane
  renders, measure the view's horizontal budget and decide its narrow-terminal
  behaviour inside the same child: four 44-column lanes plus borders and margins
  need roughly 176 columns. Pick and implement one of horizontal scrolling (the
  status quo the extra lane would silently introduce), lane collapsing, or a
  responsive fold of the Planned lane into "Agent can continue" below a
  threshold. Record the measured threshold in the child's plan; do not leave the
  behaviour to fall out of the layout.

---

## Verification

Per-child tests are listed above. End-to-end, after all children land:

1. `bash tests/run_all_python_tests.sh --test-dir tests` — read only the last
   line (`PYTHON SUITE: PASSED|FAILED`); the new board modules join the parallel
   pool and need no serial-carve-out edit.
2. `shellcheck .aitask-scripts/aitask_*.sh` — unchanged, no shell edits expected.
3. Live board against this repo, which currently has **zero** tasks carrying
   `plan_approved_at`, so seed one: `./.aitask-scripts/aitask_update.sh --batch
   <n> --plan-approved-at now`, then `ait board` and confirm the card badge, the
   detail row, and the Planned lane; clear it with `--plan-approved-at ""` and
   confirm the indicator disappears on the next refresh (t1603's third
   Verification bullet).
4. Confirm an unmarked task's card is unchanged — the parity assertion, not a
   visual impression.

## Step 9 (Post-Implementation)

This parent decomposes, so it does **not** run the normal implement/commit path:
after the children and their plans are created it reverts to `Ready` with
`assigned_to` cleared and its lock released, and this session ends. A decomposed
parent also skips Step 8d spawned-mitigation creation — all three confirmed
mitigations are inline and land with their owning child.

The parent is archived only once every child is archived, via the orphaned-parent
path (Step 3 Check 2). At that point the folded `t1596`
(`aitasks/t1596_board_gate_split_and_planned_ready_visibility.md`, `status:
Folded`, `folded_into: 1603`) is deleted as post-implementation cleanup.

## Risk

Levels below are the **reassessed** ones: Steps 1–2 of the risk evaluation were
re-run once against the plan as augmented by the inline phases above, per the
reassessment note in `risk-evaluation.md`.

**Why code-health stays `medium` despite carrying one `high`-severity item.**
The routing breach is closed *within this plan* by a named guard and a test
whose control genuinely carries a ledger, so the residual exposure is not the
breach itself but the thing no mitigation removes: five edit sites across a
13k-line module. What the mitigation does **not** buy is any reduction in that
blast radius, and it does not protect any *other* `has_ledger`-gated affordance
that a future change might add on the same false assumption — only the ops hint
is guarded and tested here.

### Code-health risk: medium
- `aitask_board.py` is a single 13k-line module and this touches five distinct
  regions of it (two card composes, the detail field builder, the in-flight
  classifier, the refresh path). Blast radius is wide even though each edit is
  small. **This is the item that keeps the level at medium — it is unmitigated,
  and the decomposition bounds it per child without removing it.** · severity:
  medium · → mitigation: none (accepted residual)
- Adding a fourth 44-column in-flight lane changes the view's horizontal budget:
  four lanes need ~176 columns, so narrower terminals gain horizontal scrolling
  they did not have. · severity: medium · → mitigation: inline post-phase
  `narrow_terminal_lane_budget`
- A new phase vocabulary derived from the gate ledger risks becoming a second
  authority alongside `_inflight_item_for`'s existing actor classification, which
  reads the same `TaskGateState`. If the two drift, the lane and the chip on the
  same card can disagree. · severity: medium · → mitigation: inline pre-phase
  `phase_model_is_the_single_authority`
- The status badge is composed in two places today; single-sourcing it is a
  behaviour-preserving refactor of a line every card renders, so a mistake is
  broad but immediately visible. · severity: low · → mitigation: inline pre-phase
  `characterize_status_badge_render`
- **Admitting `Ready` tasks into the in-flight view breaches the
  visibility-not-routing constraint by default.** A Planned task retains its gate
  ledger, so `_ops_hint`'s existing `has_ledger` test would offer `g resume` on a
  `Ready` task, bypassing the planning checkpoint and its remote drift check.
  This is a real defect the naïve implementation ships, not a hypothetical.
  · severity: high · → mitigation: gate the resume op on the lane in t1603_3,
  with a ledger-carrying fixture as the test control (recorded in that child's
  regression guards)

### Goal-achievement risk: medium
- The in-flight view is being asked to serve two orthogonal groupings at once
  (actor lane × workflow phase). If the phase chip does not actually make the
  phase distribution readable, the view gains complexity without gaining the
  operational answer the user asked for. · severity: medium · → mitigation: none
  (accepted residual; t1603_6 is where a human judges whether the view actually
  reads as intended, but no design change is pre-committed)
- Ledger-free degradation can only derive a coarse phase from status + plan
  presence + marker, so under `default.yaml` the view will be less informative
  than under a gate-recording profile. Whether that residual is acceptable is a
  judgement the plan cannot settle in advance. · severity: medium · → mitigation:
  none (accepted residual — bounded by the "unknown is a state, not an inference"
  rule in t1603_2, which makes the reduced information visible rather than
  papered over)
- Compact gate progress must fit ~34 columns; there is no existing truncation
  mechanism on card info lines (the only precedents are hand-rolled in the trail
  helpers), so the format may need iteration against real gate names. · severity:
  low · → mitigation: none (covered by t1603_6 manual verification)

### Planned mitigations
- timing: pre-phase | name: characterize_status_badge_render | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — single-sourcing the status badge is a broad behaviour-preserving refactor | desc: Commit a characterization test of the current unmarked-task card status-line render, with a positive control, before touching the badge composition (t1603_1).
- timing: pre-phase | name: phase_model_is_the_single_authority | type: refactor | priority: high | effort: low | inline_risk: medium | added_complexity: low | addresses: code-health — phase vocabulary becoming a second authority beside the actor classification | desc: Make _inflight_item_for consume the phase model instead of deriving a parallel verdict, with a test that lane and chip cannot disagree for any ledger state (t1603_3).
- timing: post-phase | name: narrow_terminal_lane_budget | type: enhancement | priority: medium | effort: medium | inline_risk: low | added_complexity: medium | addresses: code-health — four lanes need ~176 columns, narrow terminals gain horizontal scrolling | desc: Measure the four-lane horizontal budget and implement a chosen narrow-terminal behaviour (scroll, collapse, or responsive fold), recording the threshold in the child plan (t1603_3).
