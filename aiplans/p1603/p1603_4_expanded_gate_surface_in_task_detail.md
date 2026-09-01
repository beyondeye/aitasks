---
Task: t1603_4_expanded_gate_surface_in_task_detail.md
Parent Task: aitasks/t1603_surface_deferred_plan_marker_on_the_board.md
Sibling Tasks: aitasks/t1603/t1603_1_*.md, aitasks/t1603/t1603_2_*.md, aitasks/t1603/t1603_3_*.md, aitasks/t1603/t1603_5_*.md
Archived Sibling Plans: aiplans/archived/p1603/p1603_*_*.md
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5 @ 2026-09-01 15:13
---

# t1603_4 — Expanded gate surface

## Context

The in-flight card carries only a **compact** gate progress summary because a
card is a narrow surface. This child provides the full passed / current /
pending gate list on an expanded surface — a `Gates` collapsible section in the
existing `TaskDetailScreen` — so the detail is reachable without overcrowding
the card. It consumes t1603_2's model and t1603_3's renderer and adds **no new
derivation**.

## Verification findings (2026-09-01)

This plan was written at decomposition time, before t1603_3 landed. Ten things
were checked against the tree; six changed the design. All line numbers below
are current.

1. **Line numbers drifted.** The four section builders are at
   `aitask_board.py:7039-7196` (was 6492-6640) and the `compose` mounts at
   `:7252-7276` (was 6700-6726). `gate_ledger.py`'s `TaskGateState` is still at
   `:156-190` and its stale-signature docstring still at `:167-174` — those
   citations stand.

2. **The classification table was a second implementation of "satisfied".**
   `_gate_progress` (`aitask_board.py:205`) is documented as the ONE authority
   for `(satisfied, enforced)`, derived from `archive_pending`, and its
   docstring enumerates exactly the four cases a hand-rolled count over
   `state.current` gets wrong. The old table's `✓` condition
   (`current[g].status == "pass" and g not in stale_signed`) was that
   hand-rolled count. **Restructured below**: membership in `archive_pending`
   decides satisfied-vs-pending; `current[g].status` only selects the glyph and
   wording *within* each side. Parity with the card then holds by construction
   rather than by coincidence, and the parity test pins the shared authority
   instead of being the only thing holding it.

3. **The shared renderer already exists and names this task.**
   `phase_chip_text` (`aitask_board.py:536`) says in its own docstring: *"Shared
   with t1603_4's expanded gate surface: a second literal for the degraded
   states is what would let the In-Flight card and the task detail screen
   describe the same ledger differently."* Its `compact=False` form already
   emits both literals this plan used to re-specify — `Gate state unavailable:
   <error>` and `No gate ledger — <label> (<provenance>)`. **Call it; author no
   strings.**

4. **The presence rule cannot be the phase.** `derive_workflow_phase` returns
   `None` for any `Ready` / `Editing` / `Postponed` / `Done` task without the
   deferred-plan marker — i.e. most tasks the detail screen opens. The old
   degraded rendering assumed a phase always exists. Presence is now decided on
   the gate state itself; the phase line is an optional first row.

5. **`manager` may be `None`.** Every sibling builder guards on `self.manager`,
   and `gate_state_for` is a `TaskManager` method. Added to the contract.

6. **The plan-existence probe is free.** `derive_workflow_phase` wants a
   `plan_exists_probe`; `TaskDetailScreen.__init__` already resolved
   `self._plan_path` (`:7031`). Pass `lambda: self._plan_path is not None` — no
   new disk access, and t1656's laziness is preserved.

7. **The sibling guards do not need editing — only running.** The old plan said
   arrow-nav and collapsible were "guards to update in the same commit".
   Checked: `test_board_detail_arrow_nav.py` asserts only *relative* focus
   movement (focus lands on a different widget), never absolute order or count;
   `test_board_detail_collapsible.py` asserts `sections[0].id == "sec_risk"`
   and `assertTrue(sections)`, both of which survive inserting `sec_gates`
   *after* Risk. Run them as guards and expect no diff — a needed edit would be
   the signal that the placement moved.

8. **Escaping idiom.** The old plan said `markup=False` / explicit `Text`.
   `ReadOnlyField` (`:5096`) is a bare `Static` subclass with no markup kwarg
   wired, and the established idiom in this very builder family is
   `escape(...)` from `rich.markup` (imported at `:19`, used for the t1603_1
   `Plan approved:` row at `:7157`). Use `escape()`.

9. **The test harness already exists.** `tests/test_board_workflow_phase.py`
   ships `_manager`, `_task`, `_write`, `_run`, `_ledger` and
   `bf.active_tuple_fm`, over a fixture tree that stages the real `gates.yaml`.
   Real registry gates ground every row: `risk_evaluated` / `tests_pass`
   (machine), `plan_approved` / `review_approved` (human → `stale_signed`),
   `docs_updated` (`kind: procedure`).

10. **Docs stay out of scope, confirmed.** t1603_5 already names "an expanded
    gate section" and corrects the parent's non-existent
    `.aitask-scripts/tuis/board/reference.md` path to
    `website/content/docs/tuis/board/reference.md`. No doc edits here.

### Review round 2 — three further findings, all confirmed

11. **`current[g]` raises `KeyError` on the ordinary never-run gate.**
    `state.current` is built solely from parsed ledger runs
    (`gate_ledger.py:2087-2089`), while `archive_pending` includes every active
    gate that is not `_gate_satisfied` — and `_gate_satisfied` counts an absent
    run as unsatisfied (`:1369-1374`). So a declared-but-never-run gate is in
    `active_gates` and in `archive_pending` but **not** in `current`. That is not
    an edge case: it is the state of this very task (`active_gates:
    [risk_evaluated]`, no run recorded). The round-1 pseudocode indexed
    `current[g]` in the pending branch and would have crashed the detail screen
    on it. **Fixed below**: missing-run-safe `.get()` throughout, and the failed
    set delegated to the shared `_failed_active_gates`, which already guards
    with `if g in state.current` (`:263-264`).

12. **The error row was emitted twice.** Round 1 ordered the phase row before
    the `result.error` short-circuit. For an `Implementing` task,
    `derive_workflow_phase` branch B0 returns
    `WorkflowPhase("implementing", "error")` and `phase_chip_text` renders
    `Gate state unavailable: <error>` — so the short-circuit then emitted the
    identical string a second time, breaking the stated "one row, no list, no
    counts" contract. **Fixed**: the error is processed *first* and returns
    immediately; the phase row is unreachable with `error` provenance
    thereafter.

13. **`escape()` was required but never exercised.** Gate names reach
    `active_gates` / `filtered_gates` from task frontmatter, and neither
    `read_active_tuple_from_text` nor `read_declared_gates_from_text` applies
    any charset validation — only ledger *marker* names are constrained
    (`MARKER_RE`, `[A-Za-z0-9_]+`). `ReadOnlyField` is a bare `Static`, which
    parses Rich markup. Every real-registry gate is plain snake_case, so no
    proposed fixture could have caught a dropped `escape()` — a task-controlled
    name would silently alter or hide text while the suite stayed green.
    **Fixed**: a bracketed-name fixture asserted on both an active row and a
    filtered row (the likelier miss). Folded in here rather than deferred: it is
    one fixture in a file this task already creates.

### Review round 3

14. **The title recomputed a fraction the card deliberately suppresses.** Round
    2's title called `_gate_progress(state)` independently. For an
    `Implementing` task with declared active gates and **no** `## Gate Runs`,
    `has_ledger` is `False`, so `derive_workflow_phase` takes branch B1 and
    returns `WorkflowPhase("implementing", "unknown")` with `progress=None` —
    while `_gate_progress` on that same state returns `(0, 3)`, because
    `active_gates` is non-empty and every gate sits in `archive_pending`. The
    detail would therefore have printed `Gates (0/3)` directly beside
    `No gate ledger — implementing (unknown)`, contradicting the card *and*
    `WorkflowPhase`'s own docstring: *"`None` is never a stand-in for `0/N`: it
    means no fraction is derivable, which is a different claim from 'nothing has
    passed'."* Recomputing a fraction beside a renderer that suppressed it is
    exactly the card/detail disagreement this task exists to remove. **Fixed**:
    the title fraction is taken from `phase.progress` whenever a phase exists,
    falling back to `_gate_progress` only when there is no phase *and* a ledger
    is present.

    The gate **rows** still list those gates as `· pending` on the no-ledger
    branch, and that is not the same fabrication: each row states a per-gate
    enforcement fact that `aitask_gate.sh archive-ready` would independently
    report as `BLOCKED`, whereas `0/3` asserts *how far the work got*. The phase
    row sits above the list and says the ledger is absent, which is what keeps
    the two readings consistent.

## Design: reuse the detail screen, invent nothing

A new `Gates` collapsible section in `TaskDetailScreen`, built by
`_build_gate_fields(meta)` alongside the four existing builders and mounted in
`compose` beside them — **after Risk, before Dependencies & hierarchy**,
collapsed by default, `classes="meta-section"`, `id="sec_gates"`.

This settles four otherwise-open questions at zero cost:

- **Invocation / binding:** none added. `enter` on a focused card already routes
  through `KanbanApp.open_task_detail` (`:11294`), and an `InFlightTaskCard` is
  a `TaskCard` with no `trail_entry`, so it takes that path today.
- **Focus return:** already handled — `open_task_detail` passes
  `source_card=focused` and `_queue_refocus` restores focus on close.
- **Section omission:** the `if fields:` guard every existing section uses.
- **Arrow-nav order:** relative-movement assertions only (finding 7).

**Title.** `Gates (<satisfied>/<enforced>)`, else plain `Gates`. The fraction is
a progress claim, not a row count — so it must come from the **same value the
card chip prints**, never from an independent recomputation (finding 14):

```
if phase is not None:      fraction = phase.progress      # card parity, by construction
elif result.has_ledger:    fraction = _gate_progress(state)[0]
else:                      fraction = None
```

One rule underlies both branches: **a fraction requires a ledger.** Deferring to
`phase.progress` inherits `derive_workflow_phase`'s honesty rules for free — no
fraction on the no-ledger branch, and none on the marker branch either, matching
the card in both. The `elif` covers the phase-less-but-readable states (a
`Ready` / `Editing` / `Done` task carrying a ledger), where the count is
genuinely derived from recorded runs. Never `0/0` and never a fabricated `0/N`.

## Section presence (new — finding 4)

Build nothing (return `[]`, so no section is mounted) unless `self.manager` is
set AND the task has something to say about gates:

```
result = self.manager.gate_state_for(self.task_data)
state  = result.state
show   = bool(result.error or result.has_ledger
              or (state and (state.active_gates or state.filtered_gates)))
```

An ungated, never-run task therefore grows no section at all — asserted by
widget absence, not by a blank widget.

## Rows

**Order matters: the error is handled before anything else** (finding 12).

**1. Error short-circuit — FIRST.** If `result.error`, emit exactly one row —
`phase_chip_text("implementing", "error", None, error=result.error)` →
`Gate state unavailable: <error>` — and **return immediately**. No phase row, no
list, no counts, no title fraction. Because this returns first,
`derive_workflow_phase` can never contribute a second `error`-provenance row
(its B0 branch fires only under `result.error`), so the one-row contract holds
for both the `Implementing` case and the phase-less case.

**2. Phase row** — only when `derive_workflow_phase(task, result, registry,
plan_exists_probe=lambda: self._plan_path is not None)` returns non-`None`.
Rendered by `phase_chip_text(p.phase, p.provenance, p.progress,
compact=False)`. That one call covers the marker, ledger and
`derived`/`unknown` provenances — no literals here. No `error=` argument is
passed: by step 1 there is none.

**3. Gate rows** — one per gate in `state.active_gates`, classified **off
`archive_pending`**, which is the same list the archival guard reads. Every
lookup into `state.current` is `.get()`, because an active gate that has never
run has no entry there (finding 11):

```
pending   = set(state.archive_pending)
failed    = set(_failed_active_gates(state))          # shared, missing-run-safe
procedure = set(_pending_procedure_gates(state, registry))   # new shared predicate

for g in state.active_gates:
    run    = state.current.get(g)                     # may be None — never index
    status = run.status if run else None
    name   = escape(g)
    if g in pending:                                  # not satisfied
        if g in state.stale_signed:  ⚠  f"{name} — pass, signature stale; needs re-sign"
        elif g in failed:            ✗  f"{name} — failed"
        elif g in procedure:         ◈  f"{name} — pending; needs attended agent"
        else:                        ·  f"{name} — pending"      # incl. never-run
    else:                                             # satisfied
        if status == "skip":         ⊘  f"{name} — skipped (not applicable)"
        else:                        ✓  f"{name} — passed"
```

The `else` of the pending branch is the **ordinary** never-run case, not a
fallback — a freshly claimed task lands there for every gate it declares.

On the satisfied side a run always exists (`_gate_satisfied` requires
`status ∈ {pass, skip}`), so `status` cannot be `None` there; `.get()` is used
anyway so the row set never depends on that invariant holding.

`stale_signed` is tested **first** inside the pending branch: the raw ledger run
really does say `pass`, so neither the fail test nor the procedure test would
catch it, and the row must show **both facts, never one without the other**
(`gate_ledger.py:167-174`) — that disagreement is the whole reason this surface
exists. `skip` stays terminal-satisfied but **visually distinct from pass**, as
it is in the ledger.

**4. Filtered block** — gates in `state.filtered_gates`, last, under an explicit
`filtered by profile (audit only)` label row, and **excluded from the title
fraction** (they are outside `active_gates`, so `_gate_progress` excludes them
for free). `TaskGateState`'s contract is that a historical run of a filtered
gate must never drive a classification.

Every gate name goes through `escape()` (finding 8).

## Extracting `_pending_procedure_gates` (required by finding 11's fix)

`derive_workflow_phase` currently inlines the procedure-pending set, and says so
deliberately: *"`pending_procedure` stays inline: it has no second consumer."*
This task **is** that second consumer, so the rationale expires. Extract it into
a module-level `_pending_procedure_gates(state, registry)` mirroring
`_pending_human_gates` (derived from `archive_pending`, `[]` when
`state is None`) and delegate from `derive_workflow_phase`. Two copies of "which
gates need an attended agent" is precisely the drift t1642 collapsed for the
other two predicates, and this surface exists to make the axes agree.

`tests/test_board_gate_digest_budget.py :: SharedGatePredicateContractTest`
freezes the exact caller set with `assertEqual(callers, expected)`, so this is a
**required, conscious edit** to that test — not an incidental one:

- add `_build_gate_fields` to `EXPECTED_CONSUMERS["_failed_active_gates"]`;
- add `"_pending_procedure_gates": {"derive_workflow_phase", "_build_gate_fields"}`;
- update the `THIN_METHODS` comment (`:343-345`), whose stated reason for
  excluding `derive_workflow_phase` is the now-void "has no second consumer".

The negative control (`test_the_forbidden_shapes_are_present_in_the_shared_predicates`)
iterates `EXPECTED_CONSUMERS` and requires each predicate to read a forbidden
attribute — `_pending_procedure_gates` reads `archive_pending`, so it satisfies
that for free. `FORBIDDEN_ATTRS` / `FORBIDDEN_LITERALS` are scoped to
`THIN_METHODS` (the two `TaskManager` helpers) only, so `_build_gate_fields`
reading `active_gates` / `archive_pending` / `current` and comparing to `"skip"`
is not in scope of that assertion.

## Key files

- `.aitask-scripts/board/aitask_board.py` — `_build_gate_fields` next to
  `_build_risk_fields` (`:7039`); mount in `compose` between the Risk and
  relations blocks (`:7252-7262`); `_pending_procedure_gates` beside
  `_pending_human_gates` (`:228`); delegate at `derive_workflow_phase` (`:386`).
- `tests/test_board_gate_digest_budget.py` — `SharedGatePredicateContractTest`
  consumer map + comment, per above.
- `tests/test_board_detail_gates_section.py` — new.

Reused, not reimplemented: `_gate_progress` (`:205`), `_failed_active_gates`
(`:250`), `phase_chip_text` (`:536`), `derive_workflow_phase` (`:267`),
`TaskManager.gate_state_for` (`:2177`), `TaskManager.gate_registry` (`:2165`),
`escape` (`:19`).

## Verification

New `tests/test_board_detail_gates_section.py`, using the
`tests/test_board_workflow_phase.py` fixture idiom (real task files written into
the fixture tree and parsed by the production parser — a hand-built
`TaskGateState` can encode a combination the parser never emits):

- one test per row of the classification table, on real registry gates;
- **the never-run gate** (finding 11): a task declaring `risk_evaluated` with an
  empty ledger renders `· risk_evaluated — pending` and does **not** raise. This
  is the ordinary claimed-task state, so it is a first-class row of the table,
  not an edge case appended to it;
- `skip` renders `⊘` and is distinct from `✓`, yet counts as satisfied;
- the stale row asserts **both** facts in one string;
- the filtered-gates audit block is present but uncounted (title fraction
  unchanged by adding a filtered gate);
- **markup escaping** (finding 13): a task whose `gates:` carries a
  bracket-bearing name (e.g. `weird[b]name`) displays that name **literally**,
  asserted on an active-gate row *and* on a filtered-block row. Without this
  fixture every other test passes with `escape()` deleted, since real registry
  names are plain snake_case;
- **exactly one field** in the section when `result.error` is set — no phase row
  beside it (finding 12). Driven the way production fails, via
  `test_board_workflow_phase.py`'s `break_ledger_read` idiom (point the `Task`
  at a path not on disk while its in-memory content keeps the `## Gate Runs`
  markers), so the real `except` branch builds the result — no patching, no
  hand-built `GateStateResult`;
- error and no-ledger renderings asserted as text, and asserted **equal to**
  `phase_chip_text`'s output for the same inputs — so a future divergence
  between card and detail fails here;
- section omission on an ungated task asserted by **widget absence**
  (`assertFalse(screen.query("#sec_gates"))`), not a blank widget;
- `manager is None` yields no section;
- **the no-ledger title** (finding 14): an `Implementing` task with a valid
  `active_gates` tuple and **no** `## Gate Runs` renders the title as plain
  `Gates` — asserted by the *absence* of any `/` fraction, not merely by "not
  `0/3`" — beside a `No gate ledger — implementing (…)` phase row, with the
  declared gates listed as `· pending`. This is the case where an independent
  `_gate_progress` call and the card disagree, so it gets its own test;
- **cross-surface parity, stated as the user-visible claim**: for the same task,
  the fraction in the section title is exactly the fraction in
  `phase_chip_text(…, compact=True)` — the card chip — including the cases where
  **both** show none (no-ledger, marker-only). Asserting the rendered strings
  agree, rather than comparing two derivations, is what makes this a real parity
  test: it fails both if someone re-inlines a count and if someone reintroduces
  a fraction the card suppresses.
- sibling guards re-run unchanged: `tests/test_board_detail_arrow_nav.py`,
  `tests/test_board_detail_collapsible.py`;
- `tests/test_board_gate_digest_budget.py` and
  `tests/test_board_workflow_phase.py` re-run: the first must pass *with* the
  deliberate consumer-map edit above, the second must pass *without* edits —
  `derive_workflow_phase`'s behavior is unchanged by delegating
  `pending_procedure`, and that suite is the proof.

Run: `bash tests/run_all_python_tests.sh --test-dir tests` — read only the last
line (`PYTHON SUITE: PASSED|FAILED`), and mind that piping discards the status.

## Risk

### Code-health risk: medium

Raised from `low` in round 2: the change is no longer purely additive. Fixing
finding 11 properly requires extracting `_pending_procedure_gates` out of
`derive_workflow_phase` — a shipped, heavily covered seam — and editing a
deliberately **frozen** contract test.

- Touching `derive_workflow_phase` risks a behavior change in the phase axis
  that three other surfaces (in-flight lanes, chips, minimonitor) consume.
  Bounded: the delegation is a one-line substitution of an identical
  comprehension, and `tests/test_board_workflow_phase.py` must pass **unedited**
  — that is the behavior-preservation proof. · severity: medium ·
  → mitigation: none (accepted residual)
- Editing `SharedGatePredicateContractTest`'s consumer map weakens the guard if
  done carelessly (e.g. broadening rather than adding a named consumer). The
  edit is additive and named, and its negative control still requires the new
  predicate to actually read gate state. · severity: low · → mitigation: none
  (accepted residual)
- One new section builder otherwise follows an established four-way pattern; no
  new screen, binding, or focus lifecycle. The verify pass moved the design
  *onto* the documented shared authorities (`_gate_progress`,
  `phase_chip_text`, `_failed_active_gates`) instead of beside them.
  · severity: low · → mitigation: none (accepted residual)
- Residual: a future edit could re-inline a satisfaction count and drift from
  `_gate_progress`. · severity: low · → mitigation: none (accepted residual —
  the cross-surface parity test is the standing guard)

### Goal-achievement risk: low

- Every row of the classification table maps to a real gate in the shipped
  registry and to a named test, and the verify pass closed the four assumptions
  that were open (phase-`None` for non-in-flight tasks, `manager is None`, the
  shared renderer, the sibling-guard edits). Only glyph choice remains a
  judgement call. · severity: low · → mitigation: none (accepted residual)
- The section-presence rule is new to this revision, so a wrong rule would show
  a noisy section on ordinary tasks. · severity: low · → mitigation: none
  (accepted residual — pinned by the widget-absence and `manager is None` tests)
- Two review rounds each found a defect of the same shape — round 2 a crash on
  the ordinary never-run gate, round 3 a fabricated `0/N` beside a renderer that
  suppresses it — both from **recomputing** something a shared authority already
  answers. That is the residual worth naming: this surface's whole value is
  agreeing with the card, and every independent derivation is a chance to
  disagree. Both are fixed and each has its own test; the standing defence is
  that the design now takes its fraction, its failed set, its procedure set and
  its degraded strings from the card's own authorities rather than deriving any
  of them. · severity: low · → mitigation: none (accepted residual)

### Mitigations

No spawned or inline mitigation tasks are proposed. The medium code-health risk
has exactly one useful mitigation — proving the `_pending_procedure_gates`
extraction is behavior-preserving — and that is already an inline requirement of
the Verification section above (`tests/test_board_workflow_phase.py` must pass
**unedited**). Recording it a second time as a mitigation would duplicate a
check the plan already blocks on.

## Step 9 (Post-Implementation)

Standard closure: commit, merge per the plan header (current-branch mode —
nothing to merge), archive the task and plan.
