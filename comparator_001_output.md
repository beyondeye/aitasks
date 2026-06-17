# Output from agent: comparator_001

Subgraph: `_umbrella`
Nodes compared: `n001_explorer_001a` (Intent-anchored triage) vs `n002_explorer_001b` (Decision-withholding + spillover)

---

## Part 1: Comparison Matrix

### Requirements

| Dimension | n001 (Intent-anchored triage) | n002 (Decision-withholding + spillover) | Key Tradeoff |
|-----------|-------------------------------|----------------------------------------|--------------|
| requirements_fixed | Advisory-only; static user-invocable skill; reuse helpers; human as sole **disposition** authority | Advisory-only; static user-invocable skill; human as **decision author**; deferred concerns never auto-applied | n001 pins human authority on concern disposition; n002 pins it on decisions and adds an explicit no-auto-apply constraint |
| requirements_mutable | Ledger format/location; re-anchor nudge threshold; drafts vs committed child tasks | Decision-withholding can be relaxed per-request; ledger format/location; scope-drift meter timing (proactive vs on-demand) | n001 leaves the relaxation question open; n002 makes it a named mutable (opt-out "you pick") |

### Assumptions

| Dimension | n001 (Intent-anchored triage) | n002 (Decision-withholding + spillover) | Key Tradeoff |
|-----------|-------------------------------|----------------------------------------|--------------|
| assumption_advisory_contract | Read-only guardrail is correct; steerability problem is human cognitive delegation, not shadow typing | — (absent; treated as invariant in requirements_fixed instead) | n001 surfaces this as an explicit assumption to validate; n002 encodes it as a non-negotiable requirement |
| assumption_intent_capturable | User can state intent in 1–2 sentences at session start; anchor is stable enough to triage against | — (absent; intent sourced from task AC automatically) | n001 requires a live user statement; n002 pulls intent from the task file — no user turn needed |
| assumption_create_batch_available | `--batch` with draft mode (aitasks/new/, no `--commit`), plus `--parent` flag | `--batch` can mint a child/follow-up with `depends:` on current task id | Both need `--batch`; n001 needs draft (no-commit) path; n002 needs `depends:` linking — both flags must co-exist if implementations converge |
| assumption_ephemeral_session | Shadow pane may be killed when followed agent dies; durable artifacts must live outside the pane | — (absent; durability handled by per-task ledger file on disk) | n001 names ephemeral-kill as an explicit risk; n002 mitigates implicitly via the ledger file path |
| assumption_loss_aversion_is_the_driver | Plan bloat = fear of losing concerns; credible capture (drafts) removes that incentive | — (absent; plan bloat not modelled as a loss-aversion problem) | n001's triage UX is psychologically motivated; n002's is architecturally motivated (AC drift detection) |
| assumption_followed_agent_pane | — (absent; inherited from existing shadow infra) | tmux pane id is resolvable (passed by launcher or supplied by user) | n002 makes pane resolution an explicit assumption to verify; n001 treats it as given |
| assumption_context_fetch_has_ac | — (absent) | Task file returned by `aitask_shadow_context.sh` carries original intent / AC the plan can be measured against | n002's scope-drift meter is load-bearing on this assumption; if the task AC is sparse the meter degrades |
| assumption_developer_owns_decisions | — (implicit in requirements) | Developer wants to remain decision author; full delegation is an explicit opt-out, not the default | n002 names delegation-by-default as the failure mode to guard against; n001 assumes advisory purity handles it |
| assumption_no_auto_apply | — (implicit: spinoff.sh shows the draft; user runs it) | Generating an `ait create` stub does not run it; advisory boundary preserved even for task creation | n002 makes the no-auto-run contract explicit; n001 relies on the existing spinoff helper's behavior |

### Components

| Dimension | n001 (Intent-anchored triage) | n002 (Decision-withholding + spillover) | Key Tradeoff |
|-----------|-------------------------------|----------------------------------------|--------------|
| component_intent_anchor | Session-start capture of user-stated intent; fixed reference for all concern triage | — (absent; intent comes from task AC via context_fetch, not a live user statement) | n001 requires an extra session-opening turn; n002 avoids it at the cost of AC quality dependence |
| component_concern_triage | plan-triage.md sub-procedure; classifies each concern against the intent anchor; forces now/defer/drop disposition | — (see component_triage_subprocedure in n002) | Different framing: n001's triage is intent-relative; n002's is AC/IN_SCOPE-relative |
| component_concern_ledger | Session-scoped markdown table: every concern + its disposition recorded; no silent drops | — (see component_spillover_ledger in n002) | n001 names the ledger "concern ledger" scoped to a session; n002 names it "spillover ledger" scoped to a task — persistence model differs |
| component_spinoff_helper | `aitask_shadow_spinoff.sh` — whitelisted wrapper over `aitask_create.sh --batch`; turns a deferred ledger row into a reviewable draft | — (see component_defer_to_task_bridge in n002) | n001 has a named, whitelisted script; n002 refers to a "stub generator" without naming a specific script |
| component_steerability_guardrail | Output-shape contract + delegation nudge: emits a decision sheet (not a rewritten plan); re-anchors user on accept-verbatim detection | — (see component_decision_withholding_guardrail in n002) | n001 is reactive (detects delegation after the fact); n002 is proactive (withholds decision until intent is confirmed) |
| component_skill_flow | — (SKILL.md routing not named as a component) | SKILL.md — routes user's ask; defaults to intent-first decision-withholding; exposes triage/spillover | n002 explicitly models SKILL.md as a component; n001 leaves routing implicit |
| component_capture | — (inherited, not named) | `aitask_shadow_capture.sh` — inherited unchanged; reads followed agent's screen | n002 explicitly names capture as a component for clarity; n001 treats it as invisible infrastructure |
| component_context_fetch | — (not named) | `aitask_shadow_context.sh` — inherited; AC/intent extraction becomes load-bearing for scope-drift meter | n002 elevates context_fetch to a named component because the scope-drift meter depends on it |
| component_spillover_ledger | — (see component_concern_ledger) | `aitask_shadow_spillover.sh` + per-task ledger file — durable home for deferred secondary concerns | n002 names a specific script (`spillover.sh`); n001 names `spinoff.sh` — **these are different scripts and must not be conflated** |
| component_defer_to_task_bridge | — (handled by spinoff_helper) | ledger-to-`ait create --batch` stub generator — converts deferred concerns into trackable follow-up tasks | n001 binds this to a named whitelisted helper; n002 describes the function without naming the implementation script |
| component_decision_withholding_guardrail | — (see component_steerability_guardrail) | Tightened guardrail — shadow lays out decision space and elicits developer's intent before (optionally) recommending | n002 withholds by default; n001 outputs a decision sheet and re-anchors only when delegation is detected |
| component_scope_drift_meter | — (absent) | Lightweight comparison of current plan against original task AC — surfaces concerns that crept beyond stated intent | n001 has no scope-drift meter; its triage step implicitly catches drift but doesn't quantify it |
| component_triage_subprocedure | — (see component_concern_triage) | plan-triage.md — classifies concerns as IN_SCOPE vs DEFER; feeds DEFER items to the ledger | Both reference plan-triage.md; n001 frames disposition as now/defer/drop; n002 as IN_SCOPE/DEFER |

### Tradeoffs

| Dimension | n001 (Intent-anchored triage) | n002 (Decision-withholding + spillover) | Key Tradeoff |
|-----------|-------------------------------|----------------------------------------|--------------|
| tradeoff_scope_creep_reduction | Forces per-concern disposition against intent anchor — active plan stays lean at cost of one extra decision step per concern | — (absent by name; scope creep addressed via scope-drift meter instead) | n001 reduces creep incrementally (per-concern gate); n002 reduces it periodically (drift meter scan) |
| tradeoff_extra_friction | Triage gate adds turns; mitigate with batch disposition and sensible defaults | — (friction named under decision_withholding_friction in n002) | n001 frames friction as triage overhead; n002 frames it as withholding round-trip — both real, but different UX surfaces |
| tradeoff_ledger_persistence | Ephemeral ledger lost on pane kill; mitigate by flushing to stable path on every disposition | — (mitigated implicitly by per-task file path under .aitask-shadow/) | n001 names flush-on-every-write as the mitigation; n002 relies on file storage without specifying write frequency |
| tradeoff_intent_anchor_overhead | Stating intent up front costs a turn; mitigate by pre-filling from task title/description | — (absent; intent sourced from AC, no user turn) | n001 must absorb this overhead or pre-fill; n002 avoids the turn entirely (but pays with AC-quality risk) |
| tradeoff_draft_review_backlog | Spilling concerns into aitasks/new/ trades plan bloat for a draft backlog; mitigate via labels + depends links | — (analogous concern in create_stub_accuracy in n002) | n001 worries about backlog unmanageability; n002 worries about stub accuracy — complementary concerns |
| tradeoff_advisory_purity_preserved | — (handled by spinoff helper semantics) | defer-to-task bridge only drafts commands; developer runs them — advisory contract holds; but requires one explicit action per deferred task | n002 makes the advisory boundary explicit in the tradeoff name; n001 treats it as implicit in helper design |
| tradeoff_decision_withholding_friction | — (see tradeoff_extra_friction) | Default withholding adds a round-trip; mitigated by per-request "you pick" opt-out | n002 offers an explicit opt-out mechanism; n001 has no equivalent for the steerability guardrail |
| tradeoff_ledger_overhead | — (see tradeoff_ledger_persistence) | Per-task ledger file is one more artifact; mitigate by storing under .aitask-shadow/spillover/<task_id>.md (gitignored) and clearing after task creation | n002 specifies gitignored scratch storage and a clear-on-create lifecycle; n001 specifies a different path pattern (.aitask-shadow/ledger_<task>_<ts>.md) |
| tradeoff_scope_meter_false_drift | — (absent) | AC-vs-plan may mis-flag legitimate in-scope work when AC is terse; mitigate by presenting drift as a question, not an auto-defer | n001 has no equivalent risk (triage is human-driven); n002 must guard against false positives from a sparse AC |
| tradeoff_create_stub_accuracy | — (absent) | Auto-drafted stubs may capture concern imperfectly; mitigate by showing full draft for edit-before-run and carrying verbatim concern text in body | n001 relies on the user dictating the concern wording; n002 auto-generates the stub and must handle imprecision |

---

## Part 2: Delta Summary

### Most Critical Assumption Differences

- **Intent sourcing is the sharpest architectural split.** n001 requires the user to articulate intent in 1–2 sentences at session start (explicit cost: one extra turn, benefit: intent is fresh and task-specific). n002 reads intent from the task AC already on disk (no cost unless the AC is sparse or stale, in which case the scope-drift meter degrades silently).

- **n002 assumes `context_fetch` returns load-bearing AC.** If `aitask_shadow_context.sh` returns minimal or missing AC (common for quickly-drafted tasks), the scope-drift meter produces noisy false-drift alerts. n001 has no equivalent fragility because the user re-states intent live.

- **n001 treats loss aversion as the root cause of plan bloat.** This psychological model motivates the entire triage UX — credible capture removes the fear. n002 does not share this model; it treats bloat as a scope-boundary problem measurable against AC. These are complementary hypotheses, not contradictory ones.

### Hidden Risks and Infrastructure Complexities

- **Script name collision risk.** n001 depends on `aitask_shadow_spinoff.sh`; n002 depends on `aitask_shadow_spillover.sh`. These are different scripts with different semantics (spinoff = whitelisted wrapper with explicit test coverage; spillover = named in reference files but no test file listed). A merge that conflates the two would silently break one approach's advisory boundary guarantees.

- **n001's ledger flush strategy vs n002's ledger lifecycle.** n001 flushes on every disposition (write-ahead to `.aitask-shadow/ledger_<task>_<ts>.md`); n002 stores under `.aitask-shadow/spillover/<task_id>.md` and clears after deferred tasks are created. These paths don't conflict but do need coordination if both get merged — two overlapping files for the same task is confusing.

- **n2 scope-drift meter has no false-positive escape hatch in the component layer.** The tradeoff names a question-not-auto-defer mitigation, but the component itself has no explicit "approve this drift" affordance described. If the meter runs proactively, the developer may see repeated identical drift warnings for the same legitimately in-scope work.

- **n1's re-anchor nudge threshold is undefined.** n001 lists "how many consecutive accept-verbatim dispositions trigger re-anchoring" as mutable. Without a default, an implementation that sets the threshold too low creates constant interruptions; too high leaves the steerability guardrail dormant. n002 sidesteps this by making decision-withholding the default rather than a triggered response.

### Requirements That Would Need to Change Per Approach

- **If n001 is selected:** `aitask_create.sh --batch` must support draft mode writing to `aitasks/new/` *without* `--commit`. The `--parent` flag is also required for depends-linking. If the current `--batch` implementation always commits, n001 breaks without a code change.

- **If n002 is selected:** `ait create --batch` must support `depends:` linking (child task with explicit parent dependency). The scope-drift meter needs an agreed trigger (proactive vs on-demand) before implementation — leaving it mutable risks the component never being built with a clear UX contract.

- **Both require** `--batch` with `--name`, `--desc`, `--priority`, `--effort`, `--type`, `--labels`, and `--parent`/`--depends` — these flag overlaps must be confirmed against the current `aitask_create.sh` implementation before either approach finalizes its component list.

### Dependency and Integration Risks

- **plan-triage.md is shared but framed differently.** n001 uses it as a concern classifier (now/defer/drop against intent anchor); n002 uses it as a scope classifier (IN_SCOPE/DEFER against AC). A single plan-triage.md cannot serve both semantics simultaneously — the sub-procedure will need either parameterization or two variants if both approaches inform the final design.

- **n002's decision-withholding guardrail interacts with existing plan-challenge/plan-assumptions/plan-socratic modes.** If the shadow is invoked in explain or challenge mode, does decision-withholding apply? n002 is silent on this; n001's steerability guardrail similarly doesn't address mode interactions. A merged implementation must specify guardrail scope per mode.

- **n001 names a test file (`tests/test_aitask_shadow_spinoff.sh`); n002 does not.** If n002's `aitask_shadow_spillover.sh` ships without a corresponding test, it bypasses the existing whitelist-helper test convention.
