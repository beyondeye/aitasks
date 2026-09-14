---
priority: high
effort: high
depends: [t1688_1]
issue_type: enhancement
status: Ready
labels: [scheduling, skills, task_workflow, aitask_pick]
gates: [risk_evaluated]
anchor: 1569
created_at: 2026-09-14 17:42
updated_at: 2026-09-14 17:42
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
