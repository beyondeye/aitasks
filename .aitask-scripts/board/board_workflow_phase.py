"""Workflow-phase derivation and the in-flight row model (t1794_4).

Pure functions over gate-ledger state (t1603_2/t1603_3), moved verbatim out
of `aitask_board.py`: `derive_workflow_phase`, the lane / next-action helpers,
the phase chip, and the `GateStateResult` / `InFlightItem` records they
produce. No module-global reads; the board and `board_task_manager` both
consume it, and `aitask_board.py` re-exports every name.

Contract (t1794, C1/C2): flat imports only, never `aitask_board`; no task-dir
resolution. A stub of a name called inside this module must patch it HERE,
reachable as `ab.board_workflow_phase`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import gate_ledger
from board_widgets import _plan_approved_marker


@dataclass
class GateStateResult:
    state: gate_ledger.TaskGateState | None = None
    error: str = ""
    has_ledger: bool = False


@dataclass
class InFlightItem:
    task: "Task"
    task_id: str
    title: str
    group: str
    next_action: str
    gate_summary: str
    human_gates: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    state_error: str = ""
    has_ledger: bool = False
    # Ledger-pass human gates whose code-bound signature no longer binds (t1416).
    # These ARE in `human_gates` (t1642): `archive_pending` is derived with stale
    # signatures demoted, so the archival guard genuinely owes a person here and
    # `s` / `f` must reach the gate. This list is the separate fact of WHY — a
    # RE-signature of an approval invalidated by a code change, not a first
    # signature — which is what `_inflight_item_for` renders (ahead of the
    # generic pending-human wording) and what `_gate_summary` pairs with the raw
    # ledger `pass`.
    stale_signed: list[str] = field(default_factory=list)
    # t1603_2's workflow phase, flattened (t1603_3). `phase` / `provenance` are
    # `WORKFLOW_PHASES` / `WORKFLOW_PROVENANCES` members; `progress` is
    # `(satisfied, enforced)` or None — never a stand-in for 0/N.
    phase: str = ""
    provenance: str = ""
    progress: tuple[int, int] | None = None
    #: "Plan approved, implementation never started" — `Ready` AND carrying the
    #: t1595 deferred-plan marker. The ONE authority for that state: the lane,
    #: the ops hint and the three routing guards all read THIS. Never test
    #: `group == "planned"` instead — a blocking dependency claims the lane
    #: first, so such a task renders in Blocked and a lane-keyed guard hands
    #: back `g resume` / `s sign-off` / `f fail` on a task that was never
    #: implemented. Defaults False so every construction site that predates
    #: this field keeps the armed-only-where-needed value.
    approved_unstarted: bool = False


def _resolve_plan_path_for_task(task: "Task", manager) -> Path | None:
    """The plan file for ``task``, or ``None`` when it does not exist (t1603_2).

    The ONE implementation of the `aiplans/` naming rule, including the
    `aiplans/p<parent>/` nesting for child tasks. `TaskDetailScreen` and
    `KanbanApp` both delegate here; before t1603_2 each carried its own
    byte-identical copy.

    A presence check, not a path constructor: a task with no plan yet answers
    `None`, which is what lets callers use it as a boolean.
    """
    is_child = task.filepath.parent.name.startswith("t")
    if is_child:
        parent_num = manager.get_parent_num_for_child(task)
        plan_name = "p" + task.filename[1:]
        plan_path = Path("aiplans") / parent_num.replace("t", "p", 1) / plan_name
    else:
        plan_name = "p" + task.filename[1:]
        plan_path = Path("aiplans") / plan_name
    return plan_path if plan_path.exists() else None


#: Where a task sits in the workflow (t1603_2). The LANE axis ("what happens
#: next" — planned/human/agent/blocked) is separate and belongs to the in-flight
#: view; nothing here derives or asserts a lane.
WORKFLOW_PHASES = (
    "plan_approved", "implementing", "awaiting_review",
    "needs_attended_agent", "post_impl",
)


#: How the phase was determined. `unknown` and `error` are POSITIVE states, not
#: absences — see `derive_workflow_phase`.
WORKFLOW_PROVENANCES = ("ledger", "marker", "derived", "unknown", "error")


@dataclass
class WorkflowPhase:
    """A task's workflow phase, how it was determined, and gate progress.

    ``progress`` is ``(satisfied, enforced)`` or ``None``. ``None`` is never a
    stand-in for ``0/N``: it means no fraction is derivable, which is a
    different claim from "nothing has passed".
    """
    phase: str
    provenance: str
    progress: tuple[int, int] | None = None
    current_gate: str | None = None


def _gate_progress(state) -> tuple[tuple[int, int] | None, str | None]:
    """``((satisfied, enforced), current_gate)`` from ONE authority (t1603_2).

    ``archive_pending`` is computed by `gate_ledger._archive_status_from_state`
    over the **active** set and over the ``effective`` view in which stale
    signatures are already demoted. It is the same list the archival guard
    reads, so a fraction derived from it cannot claim progress the workflow will
    reject — and it inherits, with no second implementation, every case a
    hand-rolled count over ``state.current`` gets wrong: a profile-filtered or
    deleted gate is outside `active_gates` entirely, a ``skip`` is
    terminal-satisfied, a stale signature stays pending despite a raw ledger
    ``pass``, and a ``fail`` stays pending.

    An ungated task has no meaningful fraction, so it answers ``None`` rather
    than ``0/0``.
    """
    total = len(state.active_gates)
    if not total:
        return None, None
    pending = list(state.archive_pending)
    return (total - len(pending), total), (pending[0] if pending else None)


def _pending_human_gates(state, registry: dict) -> list[str]:
    """Active HUMAN gates a person still owes, from ONE authority (t1642).

    Derived from ``archive_pending`` — the same list the archival guard reads —
    rather than a raw ``status != "pass"`` comparison, so it inherits
    `gate_ledger._gate_satisfied` for free: a ``skip`` is terminal-satisfied and
    cannot read as pending, while a ledger-``pass`` whose code-bound signature no
    longer binds IS pending (it needs re-signing, and `s`/`f` must reach it).
    ``archive_pending`` is a subset of ``active_gates`` by construction
    (`gate_ledger._archive_status_from_state` is passed the active set), so the
    result is active-set-scoped with no second filter — a profile-filtered or
    deleted human gate can never appear.

    An unreadable ledger (``state is None``) yields ``[]``: "could not tell" is
    not "a human owes something".
    """
    if state is None:
        return []
    return [g for g in state.archive_pending
            if registry.get(g, {}).get("type") == "human"]


def _pending_procedure_gates(state, registry: dict) -> list[str]:
    """Active PROCEDURE gates still owed, from ONE authority (t1603_4).

    Sibling of `_pending_human_gates`, and derived the same way — from
    ``archive_pending``, the list the archival guard itself reads — so it
    inherits `gate_ledger._gate_satisfied` and the active-set scoping for free.

    A `kind: procedure` gate (``docs_updated``) is deferred by the headless
    engine and can only be run by an attended agent, so a task whose review has
    already passed can still be blocked from archival by one. Both consumers
    need that fact: `derive_workflow_phase` ranks it as its own phase, and
    `TaskDetailScreen._build_gate_fields` renders it as its own row. It was
    inline in the former until this task made it a second consumer — two copies
    of "which gates need an attended agent" is exactly the drift t1642
    collapsed for the other two predicates, and the expanded gate surface exists
    to make these axes agree, not to add a place they can differ.

    An unreadable ledger (``state is None``) yields ``[]``.
    """
    if state is None:
        return []
    return [g for g in state.archive_pending
            if registry.get(g, {}).get("kind") == "procedure"]


def _failed_active_gates(state) -> list[str]:
    """ACTIVE gates whose current run failed, from ONE authority (t1642).

    Iterates ``active_gates`` rather than all of ``state.current`` minus
    ``filtered_gates``: a gate deleted outright from the task's ``gates:`` field
    is in NEITHER list (`gate_ledger.read_active_tuple_from_text` fills
    ``filtered`` only from ``active_gates_filtered``), so subtracting only the
    filtered list still classifies on its stale historical ``fail``. Keying off
    the active set is `TaskGateState`'s own documented rule for decision
    surfaces.
    """
    if state is None:
        return []
    return [g for g in state.active_gates
            if g in state.current and state.current[g].status in ("fail", "error")]


def derive_workflow_phase(task: "Task", result: GateStateResult, registry: dict,
                          *, plan_exists_probe: Callable[[], bool],
                          ) -> WorkflowPhase | None:
    """Which workflow phase ``task`` occupies, or ``None`` if it occupies none.

    Pure and app-free: a `Task`, a `GateStateResult`, the gate registry, and a
    plan-existence probe. No widgets, no manager, no filesystem access of its
    own — the closure the caller supplies (from `_resolve_plan_path_for_task`)
    is what touches the disk, and only if this function asks it to.

    **``plan_exists_probe`` is a CALLABLE, resolved at most once and only on the
    B1 no-ledger branch below** (t1656). Every other state — the deferred-plan
    marker, the `error` branch, the whole ledger ladder — returns without ever
    invoking it, so an in-flight item in any of them costs no `Path.exists()`
    at all. Same shape `TaskManager.gate_state_for` uses when it hands
    `read_task_gate_state` the bound `code_digest_for_refresh` rather than its
    value. The laziness lives HERE rather than in the caller on purpose: a
    caller that resolved it conditionally would have to restate this ladder's
    branch conditions, and would drift the moment their order changes.

    The name says `probe`, not `plan_exists`, because a callable bound to a
    boolean-sounding name makes the B1 ternary silently always-truthy; the
    parameter is keyword-only so an un-updated call site is a `TypeError`
    rather than a wrong phase.

    Total by contract, exactly as `gate_ledger._resolve_digest` states for the
    digest channel: a raising probe **propagates**. Making it total is the
    caller's job; swallowing here would reinterpret a caller bug as a phase.

    ``None`` means **"not in a workflow phase"** (a `Ready` task with neither a
    deferred-plan marker nor a ledger; `Editing` / `Postponed` / `Done`). It
    keeps the vocabulary to exactly `WORKFLOW_PHASES` instead of inventing a
    sixth value for "not applicable", mirroring `_inflight_item_for`'s own
    `InFlightItem | None` contract.

    **Status routes before the ledger.** A `Ready` task carrying the t1595
    deferred-plan marker is one whose plan was approved and whose implementation
    was deliberately deferred — `plan-approved-stop.md` records `plan_approved`
    in the ledger AND stamps the marker, so under a recording profile such a
    task is `Ready` *with* a ledger. Running the in-flight ladder on it would
    let an active-but-unrecorded `review_approved` classify it
    `awaiting_review`, claiming a review is pending on code that does not exist.

    **An unreadable gate state is not an absent ledger.** `has_ledger` can be
    `True` alongside `state is None` and an error (`TaskManager.gate_state_for`
    resolves `has_ledger` before the call that can raise), so "could not derive
    the ledger" gets its own provenance, `error`, rather than being folded into
    the no-ledger degradation below. The shipped consumers already make this
    distinction — both `_inflight_item_for` and `_gate_summary` test
    ``result.error`` before ``not result.has_ledger``.

    **Accepted limitation.** The ledger records nothing between `plan_approved`
    and `review_approved`, so a task halfway through implementation is
    indistinguishable from one whose plan was just approved: both are
    ``resume_point == "IMPLEMENT"`` and both report `plan_approved`. That is the
    honest reading — "the last thing we know is that the plan was approved" —
    and consumers must NOT render it as "implementation has not started".
    """
    status = task.metadata.get("status", "Ready")
    state = result.state
    readable = state is not None and not result.error

    # --- A. Deferred-plan marker on a Ready task: status routes first. -------
    if status == "Ready" and _plan_approved_marker(task.metadata):
        if readable and state.resume_point == "IMPLEMENT":
            progress, current = _gate_progress(state)
            return WorkflowPhase("plan_approved", "ledger", progress, current)
        # The marker is frontmatter, wholly independent of the ledger: an
        # unreadable or absent one costs this branch only its corroboration.
        # Claiming `error` here would over-report a failure that did not change
        # the answer.
        return WorkflowPhase("plan_approved", "marker")

    if status != "Implementing":
        return None

    # --- B0. The ledger exists but could not be derived. ---------------------
    # Ordered above B1 because `has_ledger` is True in this case, so a "no
    # ledger" test would misroute it; and B2 must not run at all, since `state`
    # is None. The phase comes from the task's own status and nothing else.
    if result.error:
        return WorkflowPhase("implementing", "error")

    # --- B1. No ledger recorded: degrade honestly. ---------------------------
    if not result.has_ledger or state is None:
        # `status: Implementing` is the task's own assertion that implementation
        # began. Never re-describe it as "still planning". With no ledger AND no
        # plan file we cannot tell how far it got — a different claim from "it
        # has not started" — so provenance is `unknown` and there is NO fraction,
        # rather than a fabricated 0/N.
        return WorkflowPhase("implementing",
                             "derived" if plan_exists_probe() else "unknown")

    # --- B2. The ledger ladder. ----------------------------------------------
    # Both pending sets are derived from `archive_pending`, never from a raw
    # status comparison, so they inherit `_gate_satisfied`: a `skip` is
    # terminal-satisfied and cannot read as pending, and a stale signature is
    # demoted and does. `archive_pending` is a subset of `active_gates` by
    # construction, so both are active-set-scoped for free.
    #
    # `_pending_human_gates` / `_failed_active_gates` are the SHARED predicates
    # (t1642): `TaskManager._human_pending_gates` / `_has_failed_gate` delegate
    # to these same two functions, so the phase axis and the In-Flight actor axis
    # cannot disagree about who owes what. t1603_2 deliberately did NOT reuse the
    # TaskManager helpers because each carried a defect — a `status != "pass"`
    # test that reported a SKIPPED gate as pending, and a scan of all of
    # `state.current` minus `filtered_gates` that classified on a historical
    # failure of a gate deleted from `gates:` outright (such a gate is in neither
    # list). t1642 fixed both by collapsing them onto these predicates, so the
    # residual is gone rather than merely accepted. The delegation is frozen by
    # `SharedGatePredicateContractTest` in tests/test_board_gate_digest_budget.py;
    # re-inlining either predicate here or there is what that test catches.
    #
    # `pending_procedure` was inline here while it had no second consumer;
    # t1603_4's expanded gate surface is that consumer, so it moved out to
    # `_pending_procedure_gates` under the same delegation rule and is frozen
    # by the same test.
    pending_human = _pending_human_gates(state, registry)
    pending_procedure = _pending_procedure_gates(state, registry)
    failed = _failed_active_gates(state)

    progress, current = _gate_progress(state)

    if pending_human or failed or state.stale_signed:
        phase = "awaiting_review"
    elif pending_procedure:
        # Ahead of post_impl on purpose. `docs_updated` is `type: machine` with
        # `kind: procedure`: the headless engine defers it and only an attended
        # agent can run it, so a task whose review already passed can still be
        # blocked from archival by it. Reporting `post_impl` there would say
        # "ready to archive" about a task the archival guard will refuse. Same
        # reasoning as the `stale_signed` branch in `_inflight_item_for`, which
        # sits ahead of ALL_PASS for exactly this reason (t1416). Keyed on the
        # registry's `kind`, so any future procedure gate inherits it.
        phase = "needs_attended_agent"
    elif state.resume_point == "POSTIMPL":
        # `resume_point` POSTIMPL means `review_approved` is recorded `pass` —
        # the only evidence that the task is PAST review.
        #
        # Deliberately NOT `archive_decision == "ALL_PASS"` as well (t1603_2):
        # ALL_PASS says "the archival guard would allow archiving", which is a
        # different claim. A task whose active set does not include
        # `review_approved` — say `gates: [tests_pass]`, recorded during
        # implementation — reaches ALL_PASS while `resume_point` is still
        # IMPLEMENT, and calling that `post_impl` would report a task that is
        # mid-implementation as past review. The same holds for a SKIPPED
        # `review_approved`: `_resume_point_from_state` applies a strict
        # `== "pass"` because a skip is "not applicable", not an approval.
        #
        # Nothing is lost: ALL_PASS is exactly `progress[0] == progress[1]`, so
        # a consumer that wants to say "ready to archive" reads it off the
        # fraction — an archivability fact, kept out of the phase axis.
        phase = "post_impl"
    elif state.resume_point == "IMPLEMENT":
        phase = "plan_approved"
    else:
        phase = "implementing"
    return WorkflowPhase(phase, "ledger", progress, current)


#: The In-Flight LANE axis ("what happens next"), in render order (t1603_3).
#: `planned` is the fourth VALUE of this one axis — not an actor lane and not a
#: second axis. The refresh path builds its grouping dict and its iteration
#: order from here, so a lane cannot be rendered in one place and missing in
#: the other.
INFLIGHT_LANES = ("planned", "human", "agent", "blocked")


#: The ONE mapping from t1603_2's phase axis onto the lane axis (t1603_3).
#: Total over `WORKFLOW_PHASES` by test, so a sixth phase cannot land without a
#: lane. Two shipped classifications moved when this replaced the old ladder,
#: both deliberately and both pinned by a named test:
#:   Δ1 `needs_attended_agent` + `resume_point == IMPLEMENT` was `agent`. A
#:      pending `procedure` gate is owed by a person launching an attended
#:      agent; the old ladder filed it under the agent only because it never
#:      looked past `resume_point`.
#:   Δ2 `resume_point == POSTIMPL` with another human gate still pending now
#:      says "pending human gate" instead of "reviewed — post-implementation"
#:      (the lane is `human` either way).
LANE_FOR_PHASE = {
    "plan_approved": "agent",
    "implementing": "agent",
    "awaiting_review": "human",
    "needs_attended_agent": "human",
    "post_impl": "human",
}


#: Human-readable phase labels — the chip's only vocabulary (t1603_3).
PHASE_LABELS = {
    "plan_approved": "plan approved",
    "implementing": "implementing",
    "awaiting_review": "awaiting review",
    "needs_attended_agent": "needs attended agent",
    "post_impl": "post-implementation",
}


def _inflight_lane(phase: str, progress, *, approved_unstarted: bool,
                   blocked: bool) -> str:
    """The lane for one in-flight item — PRIMITIVES ONLY (t1603_3).

    Takes the phase NAME and its fraction, never a `TaskGateState`: the
    signature is what makes a second derivation impossible rather than merely
    discouraged, and `PhaseIsTheOnlyLaneAuthorityTest` scans this body for any
    gate-state read. Before t1603_3 the lane was a parallel ladder over
    `resume_point` / `archive_decision` / `stale_signed`, which is exactly the
    drift that lets a card's lane and its chip contradict each other.

    The archivable rung reads the phase model's OWN fraction: `ALL_PASS` is
    exactly ``progress[0] == progress[1]`` (`derive_workflow_phase` says so in
    as many words), so "ready to archive" comes off the phase rather than from
    a second read of `archive_decision`.

    `blocked` outranks `approved_unstarted` — a dependency-blocked task is one
    where nothing can happen next, which is what this axis reports. That is
    precisely why the routing guards read `approved_unstarted` DIRECTLY and
    never `group == "planned"`: the lane is a display fact, and the two sets
    differ on exactly this case.
    """
    if blocked:
        return "blocked"
    if approved_unstarted:
        return "planned"
    if progress and progress[0] == progress[1]:
        return "human"
    return LANE_FOR_PHASE[phase]


def _inflight_next_action(phase: WorkflowPhase, *, blockers: list,
                          approved_unstarted: bool, stale_signed: list,
                          failed: bool, human_gates: list) -> str:
    """The card's one-line "what happens next" copy (t1603_3).

    Keyed on the phase rather than on a second walk of the gate state, in the
    same order the lane rungs run, so the sentence and the lane cannot describe
    different tasks. Every string a pre-t1603_3 board could produce is still
    reachable here, at the same rung — see the Δ2 note on `LANE_FOR_PHASE` for
    the single deliberate re-wording.
    """
    if blockers:
        return "blocked by dependencies"
    if phase.provenance == "error":
        return "gate state unavailable"
    if phase.provenance in ("unknown", "derived"):
        return "No gate information yet — pick/resume"
    if approved_unstarted:
        return "approved plan — pick to implement"
    if stale_signed:
        # Ahead of the archivable rung on purpose (t1416): the demotion has
        # already flipped the fraction off complete, but "blocked" alone would
        # send the user looking for a gate that never ran. The action is to
        # RE-SIGN an approval a code change invalidated, so say that.
        return "awaiting re-sign: " + ", ".join(stale_signed)
    if phase.progress and phase.progress[0] == phase.progress[1]:
        return "all gates pass — archive/re-enter"
    if phase.phase == "post_impl":
        return "reviewed — post-implementation"
    if phase.phase == "needs_attended_agent":
        # `current_gate` is the first entry of `archive_pending`, so it names
        # the gate actually owed. The chip stays a label + fraction and lets
        # this line carry the gate name, which is what keeps both inside a
        # 44-column card.
        return f"needs an attended agent: {phase.current_gate or 'a procedure gate'}"
    if failed:
        return "failed gate — inspect/sign off or fail"
    if human_gates:
        return "pending human gate"
    if phase.phase == "plan_approved":
        return "plan approved — resume implementation"
    return "resume or continue planning"


def phase_chip_text(phase: str, provenance: str, progress, *,
                    error: str = "", compact: bool = False) -> str:
    """The ONE rendering of a workflow phase as text (t1603_3).

    Shared with t1603_4's expanded gate surface: a second literal for the
    degraded states is what would let the In-Flight card and the task detail
    screen describe the same ledger differently.

    `compact=True` is the **card** form — the phase label plus its fraction and
    nothing else. The qualifiers (the provenance, the error text) belong to the
    expanded surface. Measured on a real 100-column terminal: on a card they
    land directly under `next_action` and restate it almost word for word —
    "No gate information yet — pick/resume" over "No gate ledger —
    implementing (unknown)" — while reintroducing exactly the ledger jargon
    that line is deliberately written to keep off this surface (t635_9). The
    card's own action line already carries the degraded state in friendly copy;
    the chip's job here is the phase AXIS, which is what row B of the model
    needs and what a fraction adds.

    `marker` never says "No gate ledger" — a `Ready`-plus-marker task IS
    reachable with a ledger present (the marker just outranks it), so the
    phrase would be false. `None` progress prints no fraction at all rather
    than a fabricated `0/0`, which is `derive_workflow_phase`'s own rule.
    """
    label = PHASE_LABELS[phase]
    if compact:
        return f"{label} · {progress[0]}/{progress[1]}" if progress else label
    if provenance == "error":
        return f"Gate state unavailable: {error}" if error else "Gate state unavailable"
    if provenance == "marker":
        return f"{label} (from marker)"
    if provenance in ("unknown", "derived"):
        return f"No gate ledger — {label} ({provenance})"
    if progress:
        return f"{label} · {progress[0]}/{progress[1]}"
    return label
