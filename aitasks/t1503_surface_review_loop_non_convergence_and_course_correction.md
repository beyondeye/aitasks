---
priority: high
effort: high
depends: []
issue_type: feature
status: Ready
labels: [shadow, aitask_monitormini, task_workflow, review_loop]
gates: [risk_evaluated]
anchor: 1159
created_at: 2026-08-13 10:00
updated_at: 2026-08-13 10:00
---

Make shadow review-loop **non-convergence visible and actionable**.

A from-scratch adversarial review at every round is **not** the problem and is
**not** in scope to change. The problem is that nothing tells the user the loop
has stopped converging, or why — so no course correction is ever triggered and
rounds accumulate indefinitely.

## Evidence (live sessions, 2026-08-12/13)

- `t1159_2` reached **round 13**; `t1496` reached **round 9** — both under a
  `gpt-5.6-sol high` shadow. The implementer model does not discriminate
  (t1159_2 is `claudecode/fable5`, t1496 is `claudecode/opus5`), so this is
  structural, not a model-capability mismatch.
- **Non-convergence is unmeasured.** `rounds_fired`
  (`.aitask-scripts/monitor/review_loop.py:99`) is a display counter only: never
  compared to anything, reset to 0 on every `arm()` (`:134`), consumed solely by
  the banner string (`minimonitor_app.py:2666`). Nothing anywhere records
  whether a round produced findings that the previous round did not.
- **No cross-round memory, and no vocabulary for "addressed".**
  `DISPOSITIONS = ("blocking", "follow-up", "informational")` and
  `_VERDICTS = ("CONFIRMED", "PLAUSIBLE", "REFUTED")`
  (`concern_parser.py:169-171`). `REFUTED` is the reviewer withdrawing its own
  candidate. The one durable per-task store
  (`.aitask-shadow/<task_id>/rejected.md`, `r` in the picker →
  `monitor_shared.py:2209`) records *"this concern is INVALID"*, not *"this was
  fixed"* — `aidocs/framework/shadow_agent.md:496`: "rejection is a judgement
  about the concern, not about which round raised it". `.aitask-shadow/` was
  **empty** across all 22 observed rounds.
- **The findings-cap drip-feeds a finite pool.** Active tier is `advanced`
  (`aitasks/metadata/profiles/fast.yaml:26` via `userconfig.yaml:4-6`
  `shadow: fast`) — cap ≤8, cutting from the `informational` end, never
  truncating `blocking` (`impl-review-angles.md:269-292`). The cap rule has no
  round-awareness, so items cut in round N resurface as apparently-new concerns
  in round N+1.
- **Many findings are genuinely real, which is the point.** Round 12 on t1159_2
  reported a regression *introduced by round 11's own fix* ("moving the
  DELIVERING branch ahead of the modal pause fixes FIRED re-arming but breaks
  the modal contract"). By round 13 the reviewer had moved to repo hygiene (a
  stray 24 MB `importlib.util` file), plan-conformance (fixture file layout) and
  a pre-existing t1395 flake — all still labelled `blocking`. That trajectory
  — real defects, then fix-induced regressions, then scope expansion — is
  exactly the signal this task must surface.

## Scope

**1. Convergence telemetry — measurement, not suppression.**
Per round, record enough to answer "did this round produce findings the previous
rounds did not?". Keyed on the existing `BlockMeta(round, reviewed_at)` pair
(`concern_parser.py:216-227`). The natural substrate is a sibling of the
rejection store under `.aitask-shadow/<task_id>/` — reuse
`aitask_shadow_rejected.sh`'s proven design (monotonic never-reused ids inside
the file, `lib/registry_lock.sh` mutex, `ait_atomic_render`, git-ignored).
**Nothing here filters what the reviewer emits.**

**2. A visible non-convergence signal.**
When N consecutive rounds (default ~4-5, configurable) each still yield new
findings, say so where the user already looks — the minimonitor loop banner
and/or the concern picker. The signal must state *what* is not converging (e.g.
"round 6: 4 new blocking findings, 3rd consecutive round with new blockers"),
not merely that a threshold tripped. Non-convergence must never silently
disarm the loop.

**3. A shadow "convergence review" sub-procedure.**
A new sub-procedure in `.claude/skills/aitask-shadow/`, invocable by the user
and offered by the signal in (2), that asks the shadow to step back from
defect-hunting and judge the *trajectory*: are we over-engineering this
problem, and why? It should reason over the round history and the plan, and
recommend one of the three outcomes below with justification. It is advisory
only, like every other shadow surface.

**4. Three structured course-correction outcomes, wired to existing machinery.**
   - **(a) Accept a compromise** — deliberately limit edge-case handling now and
     spawn a follow-up task for further adversarial review. Existing seam:
     `followup_kind: review_finding` (`.aitask-scripts/lib/followup_kinds.py:36`),
     and t1159_3's per-concern spin-off triage arm.
   - **(b) Change design direction** — the current design is the defect source.
     (t1159_2 is the live example: 4 states where the plan pinned 3, 8 `tick()`
     inputs where the plan pinned 7, ~370k (input, state) configurations,
     9 return points, 7 writers of `self.streak`, and correctness encoded
     positionally — the modal rule written three times with three different
     answers depending on branch dispatch order.)
   - **(c) Accept the expanded scope, and price it** — re-evaluate
     `risk_code_health` **upward** through the existing producer
     (`.claude/skills/task-workflow/risk-evaluation.md:105`, `### Code-health
     risk: <high|medium|low>`, verified by `aitask_gate_risk.sh`) and create a
     post-implementation refactor task (`followup_kind: risk_mitigation`).
     t1159_2 currently carries `risk_code_health: medium`, which 13 rounds of
     evidence show to be understated — the concrete motivating case.

## Explicit non-goals

- Do **not** suppress, dedup, or filter what the reviewer emits.
- Do **not** stop the from-scratch review or add a baseline/delta-only mode.
- Do **not** add a silent round cap that ends the loop without the user.
- Do **not** change the configured review tier as part of this task.

## Notes

- Recursion worth naming: the task blocked by the non-converging loop
  (`t1159_2`) *is* the loop. Verification must not depend on that task settling.
- Related but **out of scope**, worth its own task: consuming repos cannot
  receive the t1493 recheck routing at all. `thinking_backend` and
  `thinking_app` are byte-identical to tag `v0.31.0`; this repo's main is 49
  commits ahead; `.aitask-scripts/VERSION` tracks the released tag rather than
  tree content, and `aitask_upgrade.sh:126-129` short-circuits on string
  equality. There is no content-level staleness detection anywhere. Their
  shadows answer rechecks in prose with no concern block, so their pickers
  re-offer the first round's concerns indefinitely — the same felt symptom from
  a different cause.
