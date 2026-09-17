---
priority: high
effort: high
depends: [t1688_1]
issue_type: enhancement
status: Implementing
labels: [scheduling, skills, task_workflow, aitask_pick]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1569
created_at: 2026-09-14 17:42
updated_at: 2026-09-17 12:06
---

## Context

Parts B and C of t1688 (parent: `aitasks/t1688_parallel_admission_prepick_assessment_and_task_body_surface.md`;
approved parent plan `aiplans/p1688_*.md`; this child's detailed plan
`aiplans/p1688/p1688_2_*.md`). Depends on t1688_1, which makes the checker
resolve a no-plan task from its description (`task_declared`).

**B — an OPT-IN pre-claim parallel-safety assessment in `aitask-pick`.** Before
Step 4 claims a task, an agent reads the in-flight task descriptions/plans and
grades each `overlaps` / `adjacent` / `unrelated` / `not assessed`, using the
checker's output as structured input. **Opt-in by user decision:**
`parallel_assessment` is `"off"` in every shipped profile and seed mirror and a
missing key is off; when disabled the templates render nothing (no checker
invocation, no extra reading, no prompt). `show` and `ask` stay for users who
enable it.

**C — the shipped `parallel_admission` default, docs, coordination.**

## Key files to modify

- NEW `.claude/skills/task-workflow/parallel-admission-checker.md` (B0) — the
  ungated checker contract extracted from `parallel-admission.md` steps 2-3
  (capture form, require-fresh / self-exclusion / live-state rules, the
  "checker unusable" classification table); `--plan` optional. Needed because
  `parallel-admission.md` renders those steps away under `off` (`:29-33`).
- NEW `.claude/skills/task-workflow/parallel-assessment.md` (B1) — the
  procedure; enabled only for `show`/`ask`; skip on `Implementing` or
  `manual_verification`; read budget (>12 live rows → skimmed rows are `not
  assessed`); "incomplete" recommendation for reading gaps, well-formed
  `VERDICT:UNCHECKABLE` causes, `INFLIGHT_SOURCE:` not `ok`, and (separately)
  checker unavailable; prompt rules (`ask` always; attended `show` on
  `overlaps` or checker unusable; headless never); options "Pick anyway" /
  "Pick a different task" / "Stop".
- `.claude/skills/task-workflow/parallel-admission.md` — steps 2-3 → reference
  B0; Notes (two call sites, two evidence qualities, one checker; description
  prose); step-5 `no_plan` remedy wording.
- `.claude/skills/aitask-pick/SKILL.md.j2` — first action of Step 3, guarded by
  `profile.parallel_assessment is defined and ... in ["show", "ask"]`; full-path
  reference; a Notes bullet.
- Profiles: `aitasks/metadata/profiles/{default,fast,remote}.yaml` +
  `seed/profiles/` mirrors — `parallel_assessment: "off"`; `parallel_admission`
  per C1's decision.
- `.claude/skills/task-workflow/profiles.md` — new key row + section;
  `parallel_admission` row/rationale per C1.
- Docs: `website/content/docs/skills/aitask-pick/parallel-admission.md`,
  `execution-profiles.md`, `_index.md`, `workflows/parallel-development.md`,
  `skills/aitask-backlog-roadmap.md`; `aidocs/framework/background_work_roadmap.md`.
- Tests / goldens: `tests/test_skill_render_aitask_pick.sh` (new Test 7:
  disabled + enabled renderings, line-order, closure-level independent-toggle
  test), `tests/test_skill_render_task_workflow.sh` (Test 0 lists, pins, goldens),
  `tests/test_parallel_admission_preflight.sh`; regenerate goldens;
  `./.aitask-scripts/aitask_skill_rerender.sh remote` and commit.

## C1 — decide the shipped `parallel_admission` default on measured numbers

Re-run `replay --candidates auto --from plan --lock-freshness require-fresh`
(compare with t1688_1's archived census). Compute the prompt-producing rate
(CONFLICT + UNCHECKABLE) / candidates; sample up to 5 CONFLICTs involving a
`task_declared` surface and classify each as edit collision vs context mention.
Recommend flipping `default`/`fast` to `warn` (remote stays `off`) only when the
rate is ≤ 30% and at most half the sample are context mentions; the **user
decides** at this child's planning with the numbers in the question. Tests and
goldens follow the recorded outcome; synthetic `warn` and `off` renderings stay
covered either way.

## C3 — Step 8e notes (`./ait note`, advisory)

t1569 + t1569_7 (C1 outcome; the CLEAR_CAVEATED item gains the `task_declared`
caveat), t1343 (description heuristic ≠ declaration; hard stops stay t1343's),
t1470 (cross-reference).

## Verification

- `./.aitask-scripts/aitask_skill_verify.sh`; the touched `.sh` tests;
  `bash tests/run_all_python_tests.sh --test-dir tests` (last line only);
  `cd website && python3 check_links.py --build`.
- Live render: `--profile fast` shows no assessment; a scratch profile with
  `parallel_assessment: "show"` shows it before the Step 3 hand-off.

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t1688_1** id=2026-09-16T07:01:25Z.68dcd67e214598818b31f705 from=t1688_1 from_verified=yes at=2026-09-16T07:01:25Z base=8bb86c85cbaa977e6ff52ea11615713a6e3cf8fb base_branch=main dirty=no host=omg16
>
> | Advisory context from t1688_1 (landed as code commit 8bb86c85c) — not an instruction.
> | 
> | t1688_1 shipped the `task_declared` surface. Two pinned contracts change what
> | your plan (`aiplans/p1688/p1688_2_*.md`) assumes:
> | 
> | PINNED 6 — a `task_declared` overlap NEVER grades CONFLICT. It renders
> | `OVERLAP:<ref>|declared|<n>|<path>` (a new class in `vocab.OVERLAP_CLASSES`)
> | plus `CAVEAT:inflight:<ref>|task_declared_overlap:<path>`, so the verdict is
> | CLEAR_CAVEATED. Rationale: descriptions cite files as context as well as edit
> | targets — measured over the 527 active Ready/Implementing tasks, only ~424 of
> | 2669 resolved token occurrences sit under a key-files heading, and only 119/527
> | tasks have such a heading at all.
> | 
> | Consequence for your C1: "sample up to 5 CONFLICT verdicts whose `OVERLAP:`
> | involves a `task_declared` surface" is now empty BY CONSTRUCTION. Sample the
> | `task_declared_overlap` caveats instead.
> | 
> | PINNED 7 — `pa.conflict_refs(lines)` / `pa.conflict_overlaps(lines)` are the
> | only sanctioned way to name a CONFLICT's counterparties from rendered lines:
> | class `specific` AND no `stale_claim` caveat on `inflight:<ref>`.
> | `roadmap_run`'s `CONFLICT_WITH` and `roadmap_policy`'s relations /
> | `in_flight_conflict` observations already use them, and
> | `vocab.ADVISORY_OVERLAP_CAVEATS` names the caveat codes that explain a
> | non-conflicting overlap. Your B1 assessment should read `declared` rows as
> | advisory evidence, not as conflicts. The checker's `INFLIGHT:` row also gained a
> | 6th field, `<provenance>`.
> | 
> | C2 heads-up: the CONFLICT row in
> | `.claude/skills/task-workflow/parallel-admission.md` was ALREADY corrected by
> | t1688_1 — it now names only `specific` rows with no `stale_claim` caveat and
> | lists `declared` / `hub` / stale rows as advisory. Keep it rather than reverting
> | to "from the `OVERLAP:` lines"; the rest of that file's wording (Notes, "plan
> | prose", the `no_plan` remedy row) is still yours.
> | 
> | Numbers you may be tempted to reuse — treat as MOMENT-RELATIVE, re-measure:
> | at the AFTER census (129 candidates, `replay --candidates auto --from plan
> | --lock-freshness require-fresh`) the rates were CLEAR 0 / CLEAR_CAVEATED 103 /
> | CONFLICT 12 / UNCHECKABLE 14, with 6 candidates carrying a
> | `task_declared_overlap` caveat and all 12 CONFLICTs plan-derived. That puts
> | C1's prompt-producing rate at 20.2% (26/129), inside its <=30% rule, but the
> | live corpus moves. Remaining UNCHECKABLE causes: all_phantom (5),
> | no_extractable_paths (9).
> | 
> | File contents and line numbers are as of the base commit recorded with this note.

> **✉ note:t1814** id=2026-09-17T06:17:43Z.324bc13440fe95a636080e18 from=t1814 from_verified=yes at=2026-09-17T06:17:43Z base=bc97800ee96fd5b0349c3bb65edd3395efec4aba base_branch=main dirty=yes host=omg16
>
> | t1814 measured task_declared precision (the numbers are advisory; the contract decision is yours / t1343's).
> | 
> | Method: `aitask_parallel_admission.sh sweep --source task|task-keyfiles|task-vs-plan [--population common]`, on a frozen snapshot at code commit 8ede1e35d. Description sources are graded PROMOTED (as if plan evidence), because as shipped they cannot CONFLICT. Hub threshold 10. Same 400-task cohort for every row (SWEEP_COHORT 7b0461e726532b5c).
> | 
> | - Plan vs plan, pre-implementation (reference): precision 0.4036, recall 0.85, hard-stopped 0.296.
> | - Description vs description (whole body): precision 0.4387, recall 0.49, hard-stopped 0.109.
> | - Described candidate vs planned in-flight task: whole body 0.4333 / recall 0.62; key-files-only candidate 0.4685 / recall 0.54, with +992 missed real collisions.
> | 
> | Q1: the precision bar is met at thresholds 8, 10 and 20. The premise behind PINNED 6 (descriptions are coarser than plans) is not supported, so parity, not a blocking stop, is justified. Both sources are wrong on ~56-60% of hard stops. Caveat: this may be inflated by post-hoc description edits. t1824 bounds that; hold any change until it lands.
> | Q2: do not adopt key-files narrowing (+3.5pp precision, -7.8pp recall; only 180/457 tasks have the section).
> | 
> | Full tables: aiplans/archived/p1814_measure_task_declared_precision.md

> **✉ note:t1824** id=2026-09-17T07:48:21Z.421a5cc5031a6384d7d22649 from=t1824 from_verified=yes at=2026-09-17T07:48:21Z base=4c482cadd11cf161f3fdf3f0fb5e4d2bff80ebc2 base_branch=main dirty=yes host=omg16
>
> | Advisory from t1824 (hindsight bound for t1814's task_declared precision). Full tables: aiplans/p1824_creation_time_description_hindsight.md (archived once t1824 closes).
> | 
> | t1814 recommended lifting PINNED 6 to parity on precision, but only after this follow-up. The result on frozen t1814 inputs:
> | 
> | - Method: each archived task description was recovered as its FIRST data-branch version and re-swept, on the same frozen batch map and corpus with an identical cohort. Cohort 393 = t1814's 400, minus 1 migration-era task and 6 whose creation description does not resolve. Those 7 touch 74/6360 (1.16%) of real collisions.
> | - Threshold 10, pre-implementation plan reference 0.4068:
> |   - promoted description precision: current 0.4461, creation 0.4562
> |   - description-vs-plan: current 0.4393, creation 0.4467
> |   - It holds at thresholds 8 and 20 too (creation 0.4393 / 0.2776 vs plan 0.3814 / 0.2019).
> | - Later edits did NOT inflate description precision; they lowered it slightly (and raised recall about 0.01). The creation-time margin over plans (+0.049) is more than 10x the cohort-selection effect (+0.004).
> | - Sensitivity: excluding the one reparented task (whose first version under its id is not its true creation) leaves the verdict unchanged. That check is a structural heuristic; pre-commit draft edits are invisible.
> | - Scope: the verdict is conditional on tasks whose creation description resolves. Creation time is the strict bound. An admission-time (claim-time) bracket is a separate follow-up (claim_time_bracket, spawned from t1824).
> | 
> | So t1814's Q1 conclusion (description precision >= plan reference) survives the hindsight check. The Q2 answer (no key-files narrowing) is unaffected. This is measurement only; the contract decision stays yours / t1343's.

> **👁 note:read** id=2026-09-17T09:05:32Z.ead4c7a40973fa7c6933e6ca by=t1688_2 at=2026-09-17T09:05:32Z mode=explicit ids=2026-09-16T07:01:25Z.68dcd67e214598818b31f705,2026-09-17T06:17:43Z.324bc13440fe95a636080e18,2026-09-17T07:48:21Z.421a5cc5031a6384d7d22649
