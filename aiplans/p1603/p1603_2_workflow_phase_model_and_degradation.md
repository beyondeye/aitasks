---
Task: t1603_2_workflow_phase_model_and_degradation.md
Parent Task: aitasks/t1603_surface_deferred_plan_marker_on_the_board.md
Sibling Tasks: aitasks/t1603/t1603_1_*.md, aitasks/t1603/t1603_3_*.md, aitasks/t1603/t1603_4_*.md, aitasks/t1603/t1603_5_*.md
Archived Sibling Plans: aiplans/archived/p1603/p1603_*_*.md
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5 @ 2026-08-30 18:21
---

# t1603_2 — Workflow-phase model + honest degradation

## Context

The board's in-flight view groups tasks by *required next actor* and shows gate
progress only as a raw dump of every current run. It cannot answer "what phase is
this task in?", and under a profile that records no gates (`default.yaml`) it
degrades to the useless string "No gate information yet"
(`aitask_board.py:1901`).

This child builds the **pure, app-free derivation seam** — no widgets, no
Textual — that t1603_3 (planned lane + phase chips) and t1603_4 (expanded gate
surface) both consume. Building it first makes the whole vocabulary
unit-testable before any UI depends on it. Depends on t1603_1 for
`_plan_approved_marker` (`aitask_board.py:3445`), which landed.

## The model it serves

Two independent axes; **each task has exactly one lane and exactly one phase**.
This child owns only the phase (plus provenance and progress); the lane is
t1603_3's, and **nothing in this child asserts anything about lanes**.

- Lane: `planned` · `human` · `agent` · `blocked`  *(t1603_3)*
- Phase: `plan_approved` · `implementing` · `awaiting_review` ·
  `needs_attended_agent` · `post_impl`  *(this child)*

## Verification findings that reshaped this plan

Six things were checked against the tree and changed the design. All line
numbers below are current.

1. **`_resolve_plan_path` is already duplicated.**
   `TaskDetailScreen._resolve_plan_path` (`aitask_board.py:6567`) and
   `KanbanApp._resolve_plan_path_for` (`aitask_board.py:12775`, 7 call sites)
   are byte-identical logic on two classes. Extracting only the first would
   leave two implementations, defeating the stated intent. **Both collapse onto
   the extracted function.**

2. **Phase order: the actionable blocker wins.** A task with
   `review_approved: pass` and `docs_updated` pending has `resume_point ==
   "POSTIMPL"` *and* `archive_decision == "BLOCKED"`. Production-reachable:
   `materialize-active` re-derives the enforced set on every re-pick, so a
   re-pick under a heavier profile can add `docs_updated` to a task whose review
   already passed. Under the originally-planned order that task reads
   `post_impl` — "ready to archive" — while archival is in fact held by a gate
   only an attended agent can run. `needs_attended_agent` therefore evaluates
   **before** `post_impl`, following the in-repo precedent at
   `aitask_board.py:1904`, where the `stale_signed` branch was deliberately put
   ahead of `ALL_PASS` for exactly this reason (t1416). It cannot regress the
   true `ALL_PASS` case: `archive_pending` is empty there, so the branch cannot
   fire.

3. **`Ready` + marker + a ledger is a real state neither table covered.**
   `plan-approved-stop.md:41-46` records `plan_approved: pass` **and** stamps
   `plan_approved_at`. So under a gate-recording profile an approved-and-stopped
   task is `Ready` *with* a ledger — precisely the population this feature
   exists to surface. The task file's ledger table implicitly assumes the
   `Implementing` population and its ledger-free table assumes no ledger, so the
   combination fell between them. Running the in-flight ladder on it would
   report `awaiting_review` for a task that was never implemented.
   **Resolution: status routes first** — see §3 below.

4. **`skip` is terminal-satisfied, so a raw `status != "pass"` human test is
   wrong.** `SATISFIED_STATUSES = frozenset({"pass", "skip"})`
   (`gate_ledger.py:79`) and `_gate_satisfied` (`gate_ledger.py:1369-1374`)
   admits both, so a **skipped** gate is absent from `archive_pending` and a
   task can legitimately be `ALL_PASS` with a skipped `review_approved`. The
   board's `_human_pending_gates` (`aitask_board.py:1846-1861`) nevertheless
   tests `current.status != "pass"`, which reports such a gate as pending.
   Copying that predicate would make the seam report `awaiting_review` for a
   task that is in fact ready to archive. **The pending-human set is therefore
   derived from `archive_pending`, not from a raw status comparison** — see §3.

5. **An unreadable gate state is not an absent ledger.** `gate_state_for`
   assigns `has_ledger` **inside** the `try`, before the call that can raise
   (`aitask_board.py:1743-1755`), so `has_ledger=True, state=None, error=…` is a
   reachable result: the task has `## Gate Runs` markers but derivation failed.
   Both shipped consumers already treat that as its own state, checking
   `result.error` **before** `not result.has_ledger` — `_inflight_item_for:1893`
   ("gate state unavailable") and `_gate_summary:1824`. A seam that keyed only on
   `state is None` would fold it into the no-ledger degradation path and report
   an inferred `derived` / `unknown` provenance for a task whose ledger simply
   could not be read. **"Cannot check" is its own state** — see the `error`
   provenance in §3.

6. **`filtered_gates` does not scope to the active set.**
   `read_active_tuple_from_text` (`gate_ledger.py:732-738`) populates `filtered`
   from `active_gates_filtered` when the tuple is valid and falls back to `[]`
   otherwise — so a gate **deleted outright** from `gates:` appears in neither
   `active_gates` nor `filtered_gates`. The board's `_has_failed_gate`
   (`aitask_board.py:1864-1872`) iterates all of `state.current` minus
   `filtered_gates`, so a historical `fail` run for such a gate still classifies
   the task. That contradicts `TaskGateState`'s documented rule that decision
   surfaces key off the active set (`gate_ledger.py:162-165`). **This seam
   iterates `state.active_gates` instead** — see §3.

## Implementation Steps

### Pre-phase (risk mitigations)

**`characterize_plan_path_resolvers`** — before touching either resolver, add
characterization tests to `tests/test_board_workflow_phase.py` pinning the
*current* behavior of both `TaskDetailScreen._resolve_plan_path` and
`KanbanApp._resolve_plan_path_for`: a parent task resolving to
`aiplans/p<N>_<name>.md`, a child resolving through the `aiplans/p<parent>/`
nesting, and a missing file returning `None`. Run them and see them pass
against the unmodified code, then perform the extraction in step 1 and confirm
they still pass. The collapse touches a method with 7 live call sites, so
"behavior-preserving" must be demonstrated rather than assumed.

### 1. Extract plan-file presence — one implementation, two delegates

Add a module-level function beside the existing `GateStateResult` /
`InFlightItem` dataclasses (`aitask_board.py:110-131`, immediately before
`_task_git_cmd` at 134):

```python
def _resolve_plan_path_for_task(task, manager):
    """The plan file for `task`, or None when it does not exist."""
    is_child = task.filepath.parent.name.startswith("t")
    if is_child:
        parent_num = manager.get_parent_num_for_child(task)
        plan_name = "p" + task.filename[1:]
        plan_path = Path("aiplans") / parent_num.replace("t", "p", 1) / plan_name
    else:
        plan_name = "p" + task.filename[1:]
        plan_path = Path("aiplans") / plan_name
    return plan_path if plan_path.exists() else None
```

Both existing methods become one-line delegates, keeping their signatures so all
7 `KanbanApp` call sites are untouched:

```python
# TaskDetailScreen (6567)
def _resolve_plan_path(self):
    return _resolve_plan_path_for_task(self.task_data, self.manager)

# KanbanApp (12775)
def _resolve_plan_path_for(self, task):
    return _resolve_plan_path_for_task(task, self.manager)
```

### 2. The seam: a pure function returning a phase triple

Beside the extraction, add the result dataclass and the derivation:

```python
@dataclass
class WorkflowPhase:
    phase: str            # plan_approved|implementing|awaiting_review|
                          # needs_attended_agent|post_impl
    provenance: str       # ledger | marker | derived | unknown | error
    progress: tuple[int, int] | None = None   # (satisfied, enforced)
    current_gate: str | None = None           # archive_pending[0]


def derive_workflow_phase(task, result, registry, *, plan_exists) -> "WorkflowPhase | None":
```

App-free by construction: it takes a `Task`, a `GateStateResult`, the registry
dict, and a plan-existence boolean — no `manager`, no widgets, no filesystem
access of its own. Callers thread `plan_exists` from
`_resolve_plan_path_for_task(...) is not None`.

Returning `None` means **"not in a workflow phase"** (a `Ready` task with
neither marker nor ledger; `Editing` / `Postponed` / `Done`). This is
deliberate: it keeps the phase vocabulary exactly the five named values rather
than inventing a sixth for "not applicable", and it mirrors
`_inflight_item_for`'s own `InFlightItem | None` contract.

### 3. Status routes first, then the ledger ladder

Two helpers, both **derived from `archive_pending`** so they inherit
`_gate_satisfied` (findings 4 and 6) rather than re-deriving satisfaction:

```python
# archive_pending ⊆ active_gates by construction (gate_ledger.py:2101 passes
# `active`), so both are active-set-scoped for free, and both automatically
# treat `skip` as satisfied and a stale signature as NOT satisfied.
pending_human = [g for g in state.archive_pending
                 if registry.get(g, {}).get("type") == "human"]
pending_procedure = [g for g in state.archive_pending
                     if registry.get(g, {}).get("kind") == "procedure"]
# Failure is a property of an ACTIVE gate's current run, never of a historical
# run for a gate no longer declared (finding 6).
failed = [g for g in state.active_gates
          if (r := state.current.get(g)) is not None and r.status in ("fail", "error")]
```

The ladder:

```
A. status == "Ready" and _plan_approved_marker(task.metadata)
       -> plan_approved
          provenance "ledger" when a ledger corroborates it
                     (result.state and not result.error and
                      resume_point == "IMPLEMENT"),
                     else "marker"

B. status == "Implementing"
     B0. result.error
           -> implementing, provenance "error", progress None
     B1. no ledger (not result.has_ledger)
           -> implementing, provenance "derived" if plan_exists else "unknown",
              progress None
     B2. with a ledger (result.state is not None), in this order,
         provenance "ledger":
           1. awaiting_review       pending_human, OR failed, OR state.stale_signed
           2. needs_attended_agent  pending_procedure
           3. post_impl             archive_decision == "ALL_PASS" OR
                                    resume_point == "POSTIMPL"
           4. plan_approved         resume_point == "IMPLEMENT"
           5. implementing          otherwise

C. anything else -> None
```

**Why A precedes B.** `Ready` is the task's own assertion that implementation has
not started, and the marker is the workflow's assertion that its plan was
approved and deliberately deferred. No gate ladder applies to such a task — and
running one would let an active-but-unrecorded `review_approved` classify it
`awaiting_review`, claiming a review is pending on code that does not exist
(finding 3).

**Why B0 precedes B1, and why A does not need it.** `result.error` means the
ledger exists but could not be derived — a different claim from "no ledger was
recorded", and the two must not collapse into one degraded phase (finding 5).
Provenance `error` says exactly that: the phase came from the task's own
`status` and nothing else, and no fraction is available. It is ordered above B1
because `has_ledger` can be `True` in the error case, so testing "no ledger"
first would misroute it — and B2 must not be reached at all, since `state` is
`None`. Branch **A** needs no error test: the marker is frontmatter, wholly
independent of the ledger, so an unreadable ledger only costs A its
corroboration and degrades its provenance from `ledger` to `marker` — the phase
is unaffected, and claiming `error` there would over-report a failure that did
not change the answer.

**Why the two helpers are not copies of the board's.** `pending_human` is
deliberately **not** `_human_pending_gates`, and `failed` is deliberately **not**
`_has_failed_gate`. Both board helpers predate this seam and each carries one of
the defects in findings 4 and 6. Deriving from `archive_pending` /
`active_gates` makes three properties structural rather than remembered: a
`skip` cannot read as pending, a profile-filtered gate is out of scope, and
`awaiting_review` **cannot fire when `archive_decision == "ALL_PASS"`** (the list
is empty, and `failed` would have kept it out of `ALL_PASS` anyway). The
`stale_signed` disjunct is retained for explicitness even though a demoted stale
gate is already in `archive_pending`.

`needs_attended_agent` exists because `docs_updated` is `type: machine` with
`kind: procedure` (`aitasks/metadata/gates.yaml:186-203`): the headless engine
defers it and only an attended agent can run it, yet `_human_pending_gates`
filters on `type == "human"` and never sees it — so such a task currently falls
through to `group = "agent"` / `"resume or continue planning"`
(`aitask_board.py:1918-1920`), reading as "Agent can continue". Keying on the
registry's `kind` means any future procedure gate inherits the behavior.

`pending_procedure` is the same predicate `gate_ledger.unmet_procedure_gates`
(`gate_ledger.py:1871`) implements — `kind: procedure` over the active set, minus
terminal-satisfied — but evaluated over the in-memory state rather than
re-reading the file. **Assert the two agree in a test** so they cannot drift.

### 4. Progress — exactly ONE authority: `archive_pending`

Do **not** count statuses by hand. `_archive_status_from_state`
(`gate_ledger.py:1863`) is called as `_archive_status_from_state(active,
effective)` (`gate_ledger.py:2101`) — over the **active** set, and over the
`effective` view in which stale signatures have already been demoted
(`gate_ledger.py:2098-2100`):

```
denominator = len(state.active_gates)      # enforced set; filtered excluded
numerator   = denominator - len(state.archive_pending)
current     = state.archive_pending[0]     # the gate being waited on
```

This is the same list the archival guard uses, so the surface **cannot claim
progress the workflow will reject**. It inherits, with no second implementation:

| Case | Handled because |
|---|---|
| profile-filtered gate | not in `active_gates` — out of both terms |
| gate deleted from `gates:` | likewise not in `active_gates` (finding 6) |
| `skip` | `_gate_satisfied` treats it as terminal-satisfied (finding 4) |
| stale signature | demoted in `effective`, so still pending despite a raw ledger `pass` |
| `fail` / `error` | not satisfied — still pending, plus a flag |
| procedure gate | counted normally; drives `needs_attended_agent` when pending |

`TaskGateState`'s docstring states the rule directly: *"TUI decision surfaces
(failed-gate classification, pending-human-gate detection, compact counts) must
key off the active set"* (`gate_ledger.py:162-165`). The same docstring warns
that `current` keeps the raw `pass` for a stale gate — precisely why a
hand-rolled count over `state.current` would over-report.

Progress is populated on every ledger path (including branch A when a ledger
corroborates the marker) and is `None` on every ledger-free path. Budget the
rendered form for a 34-column card (e.g. `3/5 · docs_updated`); t1603_3 owns the
rendering.

### 5. Degradation without a ledger — "unknown" is a state, not an inference

| Status | Plan file | Phase | Provenance |
|---|---|---|---|
| `Ready` + marker | any | `plan_approved` | `marker` |
| `Implementing` | present | `implementing` | `derived` |
| `Implementing` | **absent** | `implementing` | **`unknown`** |

An explicit `status: Implementing` must **never** be re-described as "still
planning". The status is the task's own assertion that implementation began; a
missing ledger *and* plan file mean we cannot tell how far it got — a different
claim from "it has not started". That case reports `implementing` with
provenance `unknown` and **no progress fraction**, not a fabricated `0/N`. This
is legacy and partially-migrated work; mislabelling it makes the view actively
misleading about the population it exists to serve.

Plan-file presence comes from the step-1 extraction, never a reimplementation of
the `aiplans/p<parent>/` nesting rule.

### 6. Accepted limitation, documented in the docstring

Between `plan_approved` and `review_approved` the ledger records nothing, so a
task actively mid-implementation is indistinguishable from one whose plan was
just approved — both are `resume_point == "IMPLEMENT"` and both report
`plan_approved`. That is the honest answer ("the last thing we know is that the
plan was approved"), not a defect, but it must be stated in the function's
docstring so t1603_3 does not render it as "implementation has not started".

### Post-phase (risk mitigations)

**`pin_phase_ladder_totality_and_precedence`** — a test that pins the ladder as
a whole, entirely within this child's own axis (it makes **no** claim about
lanes, and never calls `_inflight_item_for`; cross-axis expectations belong to
t1603_3, which owns the lane). Three parts, over a fixture matrix spanning
`status` × ledger-presence × gate-state:

- **Totality** — every fixture yields either exactly one `WorkflowPhase` or
  `None`; the function never raises and never returns an unlisted `phase` or
  `provenance` value.
- **Reachability** — each of the five phase values and each of the five
  provenance values (`ledger`, `marker`, `derived`, `unknown`, `error`) is
  produced by at least one fixture, so no branch is dead.
- **Precedence** — one *discriminating* fixture per adjacent ladder pair, each
  satisfying **both** conditions at once, so the order is pinned rather than
  incidental: `pending_human` + `pending_procedure` ⇒ `awaiting_review`;
  `POSTIMPL` + `pending_procedure` ⇒ `needs_attended_agent` (finding 2);
  `ALL_PASS` + a **skipped** `review_approved` ⇒ `post_impl`, not
  `awaiting_review` (finding 4); `Ready` + marker + an active unrecorded
  `review_approved` ⇒ `plan_approved`, not `awaiting_review` (finding 3).

This turns "the phase vocabulary might be the wrong cut" from an unfalsifiable
worry into a check that can fail: a reordering or a mis-cut shows up as a
precedence or reachability failure here, before t1603_3 and t1603_4 build on it.

## Verification

`tests/test_board_workflow_phase.py`, new, pure-unit (no board boot), following
the bare-`TaskManager` idiom of `tests/test_board_inflight_view.py:22-46` and
`FixtureBoardTestBase` (`tests/lib/board_fixture.py:578`), which chdirs into a
fixture tree — required, because plan-path resolution is relative — and copies
the real `gates.yaml` (`board_fixture.py:387-389`), which is what supplies
`docs_updated`'s `kind: procedure`.

Fixtures are **real task files written to disk** and parsed via `Task.from_text`,
never hand-built `TaskGateState` objects: a hand-built state can encode a
combination the parser never produces, and matching production semantics is the
entire point.

- one case per row of both tables in §3 and §5;
- **named regression case** — `status: Implementing` + no ledger + no plan file
  ⇒ phase `implementing`, provenance `unknown`, `progress is None`;
- **`Ready` + marker + ledger** (finding 3) ⇒ `plan_approved`, provenance
  `ledger`, *not* `awaiting_review` — with `review_approved` in `active_gates`
  and unrecorded, to make it discriminating;
- **skipped human gate** (finding 4) ⇒ `review_approved` recorded `skip`, all
  other active gates `pass` ⇒ `post_impl` with `progress == (n, n)`, *not*
  `awaiting_review`;
- **inactive historical failure** (finding 6) ⇒ a `fail` run recorded for a gate
  that is **absent from both `active_gates` and `active_gates_filtered`**
  (deleted from `gates:`), everything active satisfied ⇒ `post_impl`, *not*
  `awaiting_review`. A profile-filtered failed gate gets the same assertion;
- **reordering case** (finding 2) ⇒ `review_approved: pass` + `docs_updated`
  active and unrecorded ⇒ `needs_attended_agent`, not `post_impl`;
- **error is not no-ledger degradation** (finding 5) — a *discriminating pair*,
  because a single error fixture cannot show the conflation. Both are
  `status: Implementing` with `## Gate Runs` markers present, driven through the
  real `TaskManager.gate_state_for` with `gate_ledger.read_task_gate_state`
  patched to raise, so the production `except` branch (`aitask_board.py:1754`)
  builds the `GateStateResult` — not a hand-built one:
    - **plan file present** ⇒ provenance `error`, *not* `derived`;
    - **plan file absent** ⇒ provenance `error`, *not* `unknown`;
  both with `progress is None`. Each half is the value the *unpatched* fixture
  produces, so the assertions fail if B0 is removed. A negative control runs the
  same two fixtures **unpatched** and confirms they do report `derived` /
  `unknown`, proving the pair discriminates on the error and nothing else;
- `progress == (len(active_gates) - len(archive_pending), len(active_gates))`
  for four fixtures: stale-signed, profile-filtered, `skip`, and failed;
- invariant: no gate the seam counts as satisfied appears in `archive_pending`;
- `pending_procedure` agrees with `gate_ledger.unmet_procedure_gates` on the
  same on-disk fixture;
- **negative control**: mutate the ledger and confirm the ledger-free assertions
  change, proving the ledger-free path is not silently taking the ledger path;
- the pre-phase and post-phase mitigation tests above.

Run: `bash tests/run_all_python_tests.sh --test-dir tests` — read **only the last
line** (`PYTHON SUITE: PASSED|FAILED (runner=…, exit=N)`); an earlier
`Results: N passed` line belongs to one script-style module, not the suite.

## Risk

### Code-health risk: low
- A new pure function plus a duplication *collapse* (net one fewer
  implementation of plan-path resolution). No widget or lifecycle changes; the
  single-authority progress rule adds no competing derivation. The collapse
  touches a method with 7 live call sites, but is signature-preserving.
  · severity: low · → mitigation: inline pre-phase characterize_plan_path_resolvers
- The seam deliberately **diverges** from two shipped board helpers
  (`_human_pending_gates`, `_has_failed_gate`) rather than reusing them, because
  each carries a defect (findings 4 and 6). That is two predicates that now
  disagree with their older neighbours until a later task reconciles them.
  · severity: low · → mitigation: none (accepted residual — the divergences are
  documented at the call site with their findings, and the older helpers feed
  only the existing actor-grouping, which this child does not change)

### Goal-achievement risk: medium
- The phase vocabulary is new and its usefulness is only proven once t1603_3
  renders it; a vocabulary that turns out to be the wrong cut would ripple into
  two dependent children. Reduced but not eliminated by resolving four concrete
  mis-signals (findings 2–6) before any consumer lands, including preserving the
  error / no-ledger distinction the shipped consumers already make.
  · severity: medium · → mitigation: inline post-phase pin_phase_ladder_totality_and_precedence

### Planned mitigations
- timing: pre-phase | name: characterize_plan_path_resolvers | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — the resolver collapse touches 7 call sites | desc: Pin both resolvers' current behavior (parent path, child nesting, missing file → None) before extracting, and re-run after.
- timing: post-phase | name: pin_phase_ladder_totality_and_precedence | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: goal-achievement — the phase vocabulary may be the wrong cut | desc: Pin the ladder's totality, per-value reachability, and adjacent-pair precedence with doubly-satisfying fixtures, entirely within the phase axis — no lane or cross-surface claims.

## Step 9 (Post-Implementation)

Standard closure: commit, merge per the plan header (current-branch mode — base
and output are both `main`), archive the task and plan.
