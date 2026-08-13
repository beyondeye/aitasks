---
priority: medium
effort: medium
depends: [t1159_2]
issue_type: refactor
status: Ready
labels: [shadow, aitask_monitormini]
anchor: 1159
followup_kind: review_finding
created_at: 2026-08-13 09:33
updated_at: 2026-08-13 09:34
---

Review the code quality of the t1159_2 auto-recheck loop implementation and refactor where warranted. Spawned at the user's request after t1159_2's archival: the implementation went through **seven adversarial review rounds** (2 at plan time, 5 post-implementation — see `aiplans/archived/p1159/p1159_2_auto_recheck_loop.md`, "Plan-review hardening" rounds 1-4 and Change Requests 1-6), each of which patched a real edge case *in place*. The result is significantly more robust than the approved design but also significantly different from it, and the accretion shows: many small interacting guards were bolted on where the defect surfaced rather than where the concept belongs.

## What accreted (read the archived plan's CR1-CR6 for each mechanism's rationale)

- `.aitask-scripts/monitor/minimonitor_app.py` `_service_review_loop` now interleaves, in one long method: the armed check; a monotonic min-interval evidence serializer; discovery-based tri-state agent presence; baseline maintenance (a 5-tuple of content/kind/pane_id/history/geometry) with identity-replacement and preservation rules; mid-loop shadow-agent capability re-resolution; a raw-tail hash ring; a lifecycle-generation snapshot/abandon around the readiness await; the sticky `_loop_stale_false_pending` accumulator with consumption gating AND an ordered replay tick; the modal probe; the main controller tick; and three action-handling branches with banner maintenance. Each piece is individually contract-pinned but the composition is hard to follow.
- `.aitask-scripts/monitor/review_loop.py` `ReviewLoopController.tick` carries ordering-sensitive stages (presence → observations → currency-edge consume → DELIVERING/FIRED → modal → debounce/fire) whose ordering constraints live only in comments; `_prev_stale` seeding rules differ between `arm()` and `disarm()` for documented but subtle reasons.

## Refactor directions to evaluate (not prescriptions)

- Promote the app-side evidence plumbing (pending-False accumulator + ordered replay + consumption gating + lifecycle generation) into the pure module — e.g. an `EvidenceChannel`/`ObservationLog` object the service feeds raw observations into and the controller drains — so the ordering contract is a tested pure abstraction instead of service-body choreography. The deferred-observation replay contract (ordered own-step replay; consumption-gated clearing; generation across awaits) is the shape to encode.
- Split `_service_review_loop` into named stages (gather-evidence / decide / act) with the tick-input assembly in one dataclass, so overlapping-invocation reasoning attaches to one seam.
- Re-check every docstring and the `shadow_agent.md` safety-contract items against the final code — several were written mid-accretion.
- Consider whether the baseline 5-tuple should be a small NamedTuple with named fields (indexed access `base[2]`/`base[4]` is fragile).

## Hard constraints

- **Behavior is the spec and it is test-pinned**: 53 pure tests (`tests/test_review_loop.py`), ~35 loop tests in `tests/test_minimonitor_concern_action.py`, the live injection smoke, and the hints/bindings parity audit. Every reproduction from the review rounds is among them. The refactor must keep all of them green *unmodified* (fixture-shape edits only where an internal seam moves — never weaken an assertion; each guard exists because its violation was reproduced).
- The safety contract in `aidocs/framework/shadow_agent.md` → "Review-loop automation" (10 items + two documented residuals) is the external spec; update it only if the refactor genuinely relocates a mechanism.
- Advisory-only contract: phase must never gate firing (the negative control must keep passing).

## Coordination

- **t1159_3** (spin-off triage arm) and **t1159_6** (concern status line) both edit `minimonitor_app.py`; whichever lands second rebases trivially if this refactor keeps `_service_review_loop`'s entry signature stable — otherwise coordinate.
- **t1159_5** (aggregate manual verification) should ideally run AFTER this refactor so the human-verified build is the final shape.
- **t1503** (surface review-loop non-convergence, `depends: [t1159_6, t1159_7]`)
  will feed per-round outcome telemetry (new vs repeat findings) through
  whatever evidence seam this refactor settles on — the `EvidenceChannel` /
  `ObservationLog` direction above is the intended attachment point. It is
  sequenced after this task so it does not add fresh accretion to
  `_service_review_loop`. This task is also the reference case for t1503's
  outcome (c) "accept the expanded scope and price it": it was spawned by hand
  after seven review rounds, which is the behaviour t1503 automates.
