---
Task: t1573_minimonitor_shadow_stale_banner_truthfulness.md
Branch: main
Base branch: main
Output branch: main
---

# t1573 — Make the minimonitor shadow-staleness banner truthful

## Context

Minimonitor's continuous `#mini-shadow-stale` banner asserts "shadow feedback is
stale" in two situations where the claim is untrue:

1. **No feedback exists.** `compute_block_age_staleness` is gated on
   `contains_block_evidence` (no block ⇒ `applicable=False`), and
   `combine_staleness` then returns **read recency unchanged**. Read recency
   ("has the shadow re-read since the agent last changed?") is well-defined even
   for an explain-only shadow that never emitted a concern block — so it goes
   `True` and the banner warns about feedback that was never produced. The
   existence gate protects one input; the banner consumes the *join*.
   Live evidence: window `agent-pick-1566`, shadow pane `%287`, zero concern
   markers in its whole scrollback, banner rendering "⚠ shadow feedback is stale
   — agent moved on (analyzed 15m25s ago)" across 2 of ~38 usable columns.
2. **The warning is never retired.** For a one-shot shadow, read recency is
   permanently `True` once the followed agent types anything after the shadow's
   last read, and `_record_combined_staleness` correctly preserves a standing
   `True`. The only full clears today are an explicit `False` verdict and the
   shadow pane disappearing. Nothing invalidates the warning when the followed
   agent leaves the phase the concerns were about — minimonitor already computes
   a `PhaseSignal` every tick (`_phase_for_snap` / `_restamp_shadow_phase`) and
   the banner never reads it.

The banner is wanted; this task makes it truthful. The staleness *signal* as
consumed by the concern picker / dialog is correct and must not change.

## Design decisions

**1. The existence gate is `age.applicable`, not a second parse.**
`compute_block_age_staleness`'s docstring states that it "and only it" decides
applicability, and its table pins `applicable=False` ⇔
`contains_block_evidence(capture_text)` is false. Both banner write sites already
hold the `BlockAge`, so the gate costs nothing and reuses the canonical
predicate rather than duplicating it.

**2. The gated verdict is `False`, recorded through the existing rule.**
`False` is what a no-block pane already records today when read recency is
`False`, it means "no standing warning", and it keeps the t1493 escalation
contract intact (`False` → a pre-header block appears → `None` is an escalation
and must be recorded — `tests/test_minimonitor_concern_action.py::
test_a_pre_header_block_arriving_on_a_clean_pane_escalates`). Recording `None`
instead would make that transition `None → None` and silently void the test.
The write still goes through `_record_combined_staleness`, so the preserve rule
stays in exactly one place and is **not** weakened: this is a new *explicit*
clear, the same shape as the existing no-shadow clear.

**3. Phase retirement is DERIVED state, not a latch.** This is the decision the
whole retirement path turns on, and the reason is a failure mode a latch cannot
avoid:

> A latch keyed on "a known→known transition happened" has no way back. `PLAN →
> IMPLEMENT` retires the block; `IMPLEMENT → PLAN` is *also* a known→known
> transition, so it re-retires the same unchanged block. A single
> misclassification therefore hides a still-relevant warning **permanently**,
> which violates the advisory anti-gating rule
> (`aidocs/framework/shadow_agent.md`, "Phase detection (advisory)"): a wrong
> phase must cost the user almost nothing.

So the banner does not remember transitions. It binds each piece of feedback to
**the phase it was first observed in**, and suppresses the warning only while the
agent is *positively observed* in a different known phase:

```
suppress  ⇔  the block is identifiable
        AND its origin phase is bound and KNOWN
        AND the current phase is KNOWN
        AND current ≠ origin
```

Every property the task asks for falls out of that one predicate instead of
needing its own rule:

| situation | outcome | why |
|---|---|---|
| `PLAN` block, agent now `IMPLEMENT` | retired | current ≠ origin, both known |
| `IMPLEMENT` block, agent now `POSTIMPL` | retired | same |
| agent flaps back to `PLAN` (misclassification) | **warning returns** | current == origin ⇒ predicate false. Self-recovering; no recovery rule to get wrong |
| phase degrades to `UNKNOWN` either side | warning shows | a known current phase is required to suppress |
| block first seen while phase is `UNKNOWN` | warning shows | origin stays unbound until a known phase binds it |
| a new round arrives | warning re-arms | new block ⇒ new binding ⇒ current == origin |
| the shadow pane is replaced | warning re-arms | the binding is **pane-scoped** (below) |

**4. The binding is scoped to `(shadow pane id, block identity)`.** Feedback
identity is `hash(block_region(text))` — the established `hash(raw_tail)` idiom
(`_loop_shadow_hash`). Including the shadow pane id means a *replacement* shadow
starts unretired even in the worst case where its first block is byte-identical
to the previous pane's, and it does so without depending on a reset ever running:
there is no cross-pane state to leak. (The `if not shadow_pane:` clear resets the
binding too, but only as hygiene — correctness does not rest on it.)

**5. Retirement is evaluated on every tick, from the current phase.** There is no
"is a warning standing right now?" precondition: the suppression is a property of
the *feedback*, so it is computed the same way whether the warning has caught up
yet or not. This removes the tick race a transition-triggered design has (the
transition can be observed one tick before the warning arises) and makes the
banner a pure function of (verdict, feedback identity, origin phase, current
phase) plus the preserve rule.

**6. Both suppressions live in one method** (`_record_banner_staleness`), in front
of `_record_combined_staleness`. The fail-safe join keeps exactly one home, and
the tick path and the picker path cannot diverge.

## Files to modify

### `.aitask-scripts/monitor/minimonitor_app.py` (the only source file)

1. **`__init__`** — one new attribute beside `_shadow_stale_combined`:
   ```python
   # Phase binding for the banner's retirement rule (t1573):
   # (shadow_pane_id, block_key, origin_phase) for the feedback currently on
   # the shadow pane — the phase the agent was in when this block was FIRST
   # observed. Derived state, deliberately not a "transition happened" latch:
   # a latch cannot come back from a misclassified phase (PLAN->IMPLEMENT->PLAN
   # would re-retire the same block forever), while this rebinds on a new
   # block or a new pane and stops suppressing the moment the agent is
   # observed back in the origin phase. See _record_banner_staleness.
   self._shadow_feedback_phase: tuple[str, int, str] | None = None
   ```
   No `_shadow_phase_seen` attribute — nothing tracks transitions.

2. **New `_shadow_feedback_key(capture_text)`** (staticmethod) — `hash` of
   `block_region(text)`; `None` when no region can be identified (e.g. a
   head-truncated capture), which fails safe toward *showing* the warning.

3. **New `_feedback_phase_retired(snap, shadow_pane, capture_text) -> bool`** —
   the predicate from decision 3. Resolves the current phase through the existing
   exception-safe `_phase_signal_for_pane(snap)` (`None` ⇒ treat as `UNKNOWN`),
   rebinds `_shadow_feedback_phase` when the `(pane, key)` pair changes or when
   the origin was never bound because the phase was `UNKNOWN`, and returns
   `True` only when all four conjuncts hold. Docstring carries the
   anti-gating reasoning and the latch anti-pattern it rejects.

4. **New `_record_banner_staleness(snap, shadow_pane, capture_text, age,
   combined, banner_text)`**, immediately after `_record_combined_staleness`:
   ```python
   if not age.applicable:            # no block evidence ⇒ no feedback to call stale
       self._record_combined_staleness(False, "")
       return
   if self._feedback_phase_retired(snap, shadow_pane, capture_text):
       self._record_combined_staleness(False, "")
       return
   self._record_combined_staleness(combined, banner_text)
   ```
   Existence is checked first: it is the cheaper conjunct and it is independent
   of the phase. Docstring states why gating the *join* here is the fix and why
   gating `combine_staleness` (shared with other callers) is not: the banner
   asserts something *about feedback*, so its precondition is that feedback
   exists, whereas read recency answers a question that stays well-defined
   without any.

5. **`_refresh_shadow_stale_banner`** — signature becomes
   `(self, snap, shadow_pane, capture_text)`; `followed_pane` is derived inside
   as `snap.pane.pane_id` (still read only inside the existing
   `contains_block_evidence` cost gate on `get_last_change_wall`). The final
   `_record_combined_staleness(...)` becomes `_record_banner_staleness(...)`.
   No test calls this method today, so the signature is free to change.

6. **`action_pick_concerns`** (picker write site) — the `_record_combined_
   staleness(...)` call becomes `_record_banner_staleness(snap, shadow_pane,
   text, age, stale, format_shadow_stale_banner(...))`, using the picker's own
   (possibly deeper) capture. The `stale=` value handed to `ConcernPickerModal`
   and `format_staleness_detail` is **left untouched** — the picker's warning is
   correct today and is out of scope.

7. **`_maybe_offer_concerns`** —
   - in the `if not shadow_pane:` clear, also reset
     `self._shadow_feedback_phase = None` (hygiene, per decision 4);
   - the banner call becomes
     `self._refresh_shadow_stale_banner(snap, shadow_pane, text)`.
   Nothing is inserted before it: retirement is inside the recorder, so there is
   no second write site and no ordering to get wrong.

### `tests/test_minimonitor_concern_action.py`

- Lift `BlockAgeStalenessTests._app` into a shared `_StalenessAppFixture` base
  (no behavior change; `BlockAgeStalenessTests` keeps every existing test). Give
  the fixture an optional phase hook that installs the established fakes —
  `_task_cache.get_task_info` + `_gate_cache.phase_for` (the idiom from
  `tests/test_minimonitor_gate_phase_row.py`) — so the phase is driven through
  the **real** `_phase_signal_for_pane` / `_phase_for_snap` path, with a mutable
  cell the tests advance between ticks.
- **Flip the characterization test that pins the defect**:
  `test_no_block_pane_still_reports_read_recency_staleness` currently asserts the
  banner says "moved on" for a no-block pane. Rewritten to assert the opposite,
  with a comment naming t1573 and why the old assertion was the bug.
- New `StaleBannerTruthfulnessTests(_StalenessAppFixture)`:
  - **AC1** — explain-only shadow (`"just agent prose\n$ "`), one subTest per
    read-recency state (`True` via `last_change > analyzed + eps`, `False` via
    the reverse, `None` via `option_ok=False`): banner `""` and
    `_shadow_stale_combined is False` in all three.
  - **AC5 / negative control** — the same no-block pane with read recency
    `True`: `app._shadow_feedback_stale is True` while the banner is empty. This
    discriminates the intended fix from a wrong one that gated
    `_shadow_read_recency` itself, which is the value `_service_review_loop`
    reads (`stale_input = self._shadow_feedback_stale`).
  - **AC2** — a block-bearing pane still goes stale with today's wording:
    read-recency-driven "agent moved on" and block-age-driven "predates",
    re-asserted on the banner text so a gating regression is attributable.
  - **AC3** — a standing warning is retired by `PLAN → IMPLEMENT`, and (separate
    fixture, origin `IMPLEMENT`) by `IMPLEMENT → POSTIMPL`: banner `""`,
    verdict `False`.
  - **AC3 negatives** — `PLAN → UNKNOWN`, `UNKNOWN → IMPLEMENT`, `PLAN → PLAN`,
    and a `PLAN → UNKNOWN → PLAN` flap all leave the warning standing.
  - **AC3 recovery (concern 1)** —
    `test_a_misclassified_known_phase_flap_restores_the_warning`: `PLAN →
    IMPLEMENT` (assert suppressed) `→ PLAN` with the block unchanged. The
    warning must come back. This is the case a transition-latched design fails
    permanently, so it is the discriminating test for decision 3 — it must be
    written to fail against a latch implementation, not merely to pass against
    this one.
  - **AC3 pane replacement (concern 2)** —
    `test_a_replacement_shadow_pane_starts_unretired`: tick with shadow `%5`
    holding a block at phase `IMPLEMENT` whose origin was `PLAN` (assert
    suppressed), then mutate the fake monitor's pane list so
    `find_shadow_pane_info_async` returns `%6` — **no intervening no-shadow
    tick** — serving the *byte-identical* block text while the phase stays
    `IMPLEMENT`. The warning must be live on the new pane, proving the binding
    is pane-scoped rather than reset-dependent. Byte-identical text is the
    worst case on purpose: a fixture with a fresh round would pass even with an
    unscoped binding, making the test non-discriminating.
  - **AC3 re-arm** — after retirement, `_ROUND2_BLOCK` (a new round, same
    concerns) re-asserts the warning with no phase change.

### `tests/test_minimonitor_top_chrome_render.py`

- **AC4** — new test in `TopChromeGeometryTests`: populate the banner through the
  real setter, then drive the real production gate
  (`_refresh_shadow_stale_banner(snap, "%99", "just agent prose\n$ ")` — the
  t1573 path, safe with `_monitor is None`), and assert on the **composited
  frame** that `#mini-shadow-stale` has `region.height == 0` and that
  `STALE_PROBE` is gone from the flattened frame. Complements the existing
  `test_empty_chrome_costs_no_rows`, which only covers a banner that was never
  set.

### `aidocs/framework/shadow_agent.md`

- Under "Feedback freshness (staleness detection)": extend the **Applicability is
  a third state** bullet — `combine_staleness` still returns read recency
  untouched for every caller, but minimonitor's *banner* refuses to render a
  read-recency warning about feedback that does not exist, and name where the
  gate lives (`_record_banner_staleness`).
- Under **Surface ownership**: document the banner's two suppressions — feedback
  existence, and phase retirement as the derived `(pane, block) → origin phase`
  binding — with the four-conjunct predicate, the self-recovery property, and
  the explicit note that a transition latch was rejected because it cannot
  recover from a misclassified phase. Cross-reference "Phase detection
  (advisory)" for the anti-gating rule this satisfies.

### Post-phase (risk mitigations)

Both steps land in `tests/test_minimonitor_concern_action.py` after the AC tests
above, in the same commit as the implementation.

1. `[pin_capture_window_loss_residual]` Add
   `test_a_block_leaving_the_capture_window_clears_the_banner` to
   `StaleBannerTruthfulnessTests`: drive one app to a **block-age-driven**
   standing warning (`_ROUND1_BLOCK`, `analyzed_at` after the change so read
   recency is `False` and only the block is old — assert
   `_shadow_stale_combined is True` and `"predates"` in the banner), then
   re-stub the capture to block-free prose and tick again. Assert the banner is
   `""` and `_shadow_stale_combined is False`, with a docstring naming this the
   **intended residual** of the `age.applicable` gate: the banner describes the
   feedback the pane is showing, and a warning about a block no longer in a
   `--deep` capture cannot be acted on (the picker's own deeper re-capture is
   the recovery path). Without this test the behavior is an unpinned accident
   rather than a decision.

2. `[assert_applicability_coupling]` Add
   `test_applicability_is_exactly_the_block_evidence_predicate` (a plain
   `unittest.TestCase`, no app): for every block fixture in the module
   (`_CLOSED_BLOCK`, `_UNCLOSED_BLOCK`, `_HEAD_TRUNCATED`,
   `_MALFORMED_ONLY_BLOCK`, `_ROUND1_BLOCK`, `_METADATA_ONLY_BLOCK`, and
   block-free prose), assert
   `compute_block_age_staleness(text, None, 3.0).applicable ==
   contains_block_evidence(text)` via `subTest`. The banner gate consumes
   `age.applicable` **as** the feedback-existence predicate; that equivalence is
   stated in `compute_block_age_staleness`'s docstring table but not enforced
   anywhere, so this is the tripwire that fails if a future edit to the producer
   unhooks the gate silently. The docstring names `_record_banner_staleness` as
   the dependent.

## Out of scope (must not change behavior)

- `compute_shadow_staleness` / `combine_staleness` /
  `compute_block_age_staleness` and `format_shadow_stale_banner` — untouched, so
  every other caller and the pinned wording are unchanged
  (`tests/test_shadow_seam.py::…test_no_block_falls_through_to_read_recency`
  stays green, because it tests the *formatter*, not the banner write site).
- `monitor/review_loop.py` and the `_loop_stale_false_pending` latch — the loop
  reads `_shadow_feedback_stale`, which no edit touches.
- `monitor/monitor_app.py` — no continuous banner; its picker/toast wording and
  `!` badge stay as-is.

## Verification

```bash
# The three modules that own the changed surfaces (each has a __main__ entry).
python3 tests/test_minimonitor_concern_action.py
python3 tests/test_minimonitor_top_chrome_render.py
python3 tests/test_shadow_seam.py
# AC6 — the full monitor's staleness surfaces must be untouched.
python3 tests/test_monitor_concern_action.py
python3 tests/test_monitor_shadow_status.py
# Whole Python suite (read ONLY the last line for the verdict).
bash tests/run_all_python_tests.sh
```

Negative-control discipline: the new AC1 / AC3 / AC4 tests are run **before** the
source edit and must fail (AC1 on the "moved on" banner, AC3 on the standing
warning, AC4 on the composited rows). A passing negative control means the test
is not reaching the defect. The two concern-driven tests get a second, sharper
control: after the fix, the flap-recovery and pane-replacement tests are re-run
against a **latched** variant of `_feedback_phase_retired` (retire on a
known→known transition, key on the block alone) and must fail there — otherwise
they are not actually discriminating the derived design from the latch it
replaces.

Manual (optional, real terminal): with a live `agent-<task>` window, spawn an
explain-only shadow (`e` in minimonitor, ask it to explain the plan only), let
the followed agent type, and confirm no banner appears and the pane list keeps
its rows; then take a real review round, let the agent move from planning to
implementation, and confirm the standing warning disappears at the transition
and returns for a fresh round.

Step 9 (Post-Implementation) applies as usual: no separate branch was created,
so the merge steps are no-ops; `ait gates run 1573` runs the declared
`risk_evaluated` gate, then archival.

## Risk

### Code-health risk: medium
- The `age.applicable` gate does not only suppress the untrue read-recency warning — it also retires a **genuine** block-age warning when the block leaves the `--deep` capture window entirely, a fail-open direction beyond the reported symptom · severity: medium (residual — addressed by inline post-phase pin_capture_window_loss_residual) · → mitigation: inline post-phase pin_capture_window_loss_residual
- The gate consumes `age.applicable` as the feedback-existence predicate; the equivalence with `contains_block_evidence` is held by `compute_block_age_staleness`'s docstring rather than by construction, so a future edit to the producer could unhook the banner gate silently · severity: low (residual — addressed by inline post-phase assert_applicability_coupling) · → mitigation: inline post-phase assert_applicability_coupling
- Phase retirement adds one cross-tick binding (`_shadow_feedback_phase`) to a path that already carries several fail-safe rules · severity: low · → mitigation: none (bounded by construction: the binding is derived, pane-scoped and re-bound on every new block, so no phase misclassification can outlive the misclassification itself — pinned by the flap-recovery and pane-replacement tests)
- A block first observed only *after* the agent already moved on binds its origin to the later phase and is therefore never retired · severity: low · → mitigation: none (accepted and fail-safe: the outcome is a visible advisory warning, never a hidden one)
- `_record_combined_staleness`'s preserve rule is left untouched and both suppressions are routed through it as explicit `False` clears, so the fail-safe join keeps exactly one home · severity: low · → mitigation: none

### Goal-achievement risk: low
- AC3 says "retired" without stating for how long; this plan reads it as "while the agent is observed in a different known phase", which is what makes recovery automatic. A stricter reading ("retired permanently once the phase moves on") is what the rejected latch implements, and it is the reading that breaks the anti-gating constraint · severity: low · → mitigation: none (stated as decision 3, with the flap-recovery test as the executable statement of the chosen reading)
- All six acceptance criteria map onto named tests, including the frame-level AC4 and the review-loop input AC5, and every seam used already exists and is exercised by current tests · severity: low · → mitigation: none

### Planned mitigations
- timing: post-phase | name: pin_capture_window_loss_residual | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — the applicability gate also retires a genuine block-age warning when the block leaves the capture window | desc: test pinning that a stale block leaving the deep capture window clears the banner, as an intended residual
- timing: post-phase | name: assert_applicability_coupling | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — age.applicable is used as the feedback-existence predicate on a docstring-only contract | desc: tripwire asserting compute_block_age_staleness(...).applicable equals contains_block_evidence(text) across the module's block fixtures
