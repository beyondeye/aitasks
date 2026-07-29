---
Task: t1221_harden_codex_skill_launch_composer.md
Worktree: (none — profile 'fast' works on the current branch)
Branch: main
Base branch: main
Output branch: main
---

# t1221 — Harden Codex skill-launch composer

## Context

`build_invoke_command` converts argv into a single text prompt for skill-launch
operations. That representation cannot preserve an argument containing
whitespace or an empty argument: Claude Code and OpenCode use `${args[*]}`,
while Codex reaches the same result through `build_skill_prompt` and `"$*"`.
Whitespace changes token boundaries, while an empty element collapses into a
separator that the receiving text parser cannot distinguish from formatting.
The existing guard covers only whitespace under `work-report` and `trail`,
leaving `pick`, `explain`, `qa`, `shadow`, and `learn` vulnerable to silent
argument-boundary changes and every composer vulnerable to empty elements. The
Codex dispatch has a second fail-open path: an operation accepted by
`SUPPORTED_OPERATIONS` but omitted from the nested composer case produces an
empty prompt.

Repository call-site and test scans found no caller relying on embedded
whitespace or intentionally empty elements for these skill-launch operations.
Passthrough operations (`batch-review`, `raw`) preserve argv and must remain
outside the guard; `explore` has no composed arguments.

## Implementation

1. Update `.aitask-scripts/aitask_codeagent.sh` in
   `build_invoke_command`:
   - Replace the `work-report|trail` condition with an explicit case covering
     every argument-bearing text-composed skill operation:
     `pick|explain|qa|shadow|learn|work-report|trail`.
   - Reject both zero-length elements and elements containing whitespace. Keep
     validation before per-agent dispatch and model command construction, and
     use a neutral local variable name because the guard is no longer
     work-report-specific.
   - Preserve the existing whitespace diagnostic contract, and add a distinct
     empty-argument diagnostic. Both name the operation and explain that
     slash-command text cannot preserve argv boundaries.
   - Add a wildcard arm to the nested Codex skill-composer case that calls
     `die "operation not wired into the codex composer: $operation"`. This
     makes additions to `SUPPORTED_OPERATIONS` fail at composition time until
     their Codex prompt mapping is wired.

2. Extend `tests/test_codeagent.sh` with focused regression coverage:
   - Iterate over `pick`, `explain`, `qa`, `shadow`, `learn`, `work-report`, and
     `trail`, asserting that whitespace-bearing and empty argv elements are
     rejected before a `DRY_RUN:` command can be emitted.
   - Assert that a normal whitespace-free skill argument still composes, and
     that a passthrough operation such as `raw` still accepts a
     whitespace-bearing and an empty argv element unchanged.
   - Add an explicit-Codex dry-run matrix for all seven guarded operations,
     asserting that each emits its expected `$aitask-*` composer prompt and a
     representative argument. This pins every existing normal Codex arm rather
     than relying on the default Claude configuration or scattered suites.
   - Create a separately named temporary copy of `aitask_codeagent.sh`. Use a
     validated `awk` transform anchored on the `SUPPORTED_OPERATIONS=(` symbol
     (not the declaration's complete formatting) to add a test-only operation,
     then invoke it under an explicit Codex agent string. Assert a nonzero exit,
     the exact "not wired" diagnostic, and absence of `DRY_RUN:`. Remove the
     copied script immediately after the assertions; the enclosing temporary
     fixture cleanup remains a backstop. This dynamically pins the otherwise
     unreachable wildcard arm without altering the shared fixture or production
     operation metadata.

3. Verify the change:
   - Run `bash -n .aitask-scripts/aitask_codeagent.sh` and
     `bash -n tests/test_codeagent.sh`.
   - Run `bash tests/test_codeagent.sh` for the generalized contract and Codex
     composer regression.
   - Run the existing operation-specific suites
     `tests/test_codeagent_work_report.sh`, `tests/test_codeagent_trail.sh`,
     `tests/test_shadow_spawn_config.sh`, and
     `tests/test_shadow_spawn_learner.sh` to confirm current skill launch shapes
     remain intact.

4. After explicit user review, commit only the script and test as
   `bug: Harden Codex skill launch composition (t1221)`, then update this plan's
   Final Implementation Notes. Run the declared gate orchestration and archive
   t1221 through Step 9; profile `fast` works directly on `main`, so no task
   branch merge is required.

## Risk

### Code-health risk: low
None identified. The behavior change is a centralized fail-closed validation
for whitespace-bearing and empty elements on an already-lossy boundary, with
passthrough argv operations excluded and operation-specific regression suites
retained.

### Goal-achievement risk: low
None identified. An explicit-Codex matrix covers every current argument-bearing
composer arm, while isolated dynamic mutation of a temporary script copy
exercises the future-operation omission path directly.

## Verification

- `bash -n .aitask-scripts/aitask_codeagent.sh`
- `bash -n tests/test_codeagent.sh`
- `bash tests/test_codeagent.sh`
- `bash tests/test_codeagent_work_report.sh`
- `bash tests/test_codeagent_trail.sh`
- `bash tests/test_shadow_spawn_config.sh`
- `bash tests/test_shadow_spawn_learner.sh`

## Implementation Progress

- [x] Generalized fail-closed validation to every argument-bearing text
  composer, covering whitespace-bearing and empty argv elements.
- [x] Added the explicit Codex wildcard refusal for supported-but-unwired
  operations.
- [x] Added generalized validation, passthrough controls, an explicit-Codex
  normal-arm matrix, and an isolated synthetic unwired-operation regression.
- [x] Syntax checks, `git diff --check`, and `tests/test_codeagent.sh` pass
  (`156 / 156`).
- [x] Existing composer assertions pass in the work-report, trail, shadow, and
  learner suites. Three suites retain pre-existing failures solely in stale
  seeded-model expectations (`opus4_8` / `sonnet4_6` versus current
  `opus5` / `sonnet5`); `tests/test_shadow_spawn_config.sh` passes `13 / 13`.

## Post-Review Changes

### Change Request 1 (2026-07-29 09:26)

- **Requested by user:** Confirm that the red work-report, trail, and shadow
  learner auxiliary suites are failing because their expected default models
  predate the current seed configuration, and track that defect separately
  instead of expanding t1221.
- **Changes made:** Verified the stale assertions at
  `tests/test_codeagent_work_report.sh:80,107-108,116-117`,
  `tests/test_codeagent_trail.sh:81,108-109,116`, and
  `tests/test_shadow_spawn_learner.sh:67`. Kept t1221 code unchanged and
  recorded the defect for the Step 8b upstream follow-up workflow.
- **Files affected:** `aiplans/p1221_harden_codex_skill_launch_composer.md`

## Final Implementation Notes

- **Actual work done:** Generalized `build_invoke_command`'s fail-closed argv
  validation across `pick`, `explain`, `qa`, `shadow`, `learn`, `work-report`,
  and `trail`; rejected both empty and whitespace-bearing elements; added a
  wildcard diagnostic to the nested Codex composer; and added regression tests
  for every guarded operation, passthrough controls, every current Codex prompt
  arm, and a supported-but-unwired synthetic operation.
- **Deviations from plan:** The initial plan covered whitespace only. User plan
  review correctly identified that empty argv elements are equally
  unrepresentable and requested explicit normal-path Codex coverage plus
  stronger synthetic-test isolation; all three were incorporated into the
  revised plan before implementation. No deviations from that revised plan.
- **Issues encountered:** The focused `tests/test_codeagent.sh` suite passes
  `156 / 156`. Three auxiliary suites remain red only because they assert old
  default models; their composer-specific assertions pass. This pre-existing
  defect was not mixed into t1221 and is recorded below for a standalone
  follow-up.
- **Key decisions:** Kept passthrough operations (`raw`, `batch-review`) outside
  validation because they preserve argv; kept zero-argument `explore` outside
  because it composes no argv; used an explicit operation allowlist so future
  passthrough operations are not accidentally restricted; and tested the Codex
  wildcard by mutating and cleaning a separate temporary script fixture.
- **Upstream defects identified:**
  - `tests/test_codeagent_work_report.sh:80` — seeded and fallback model
    assertions still expect `sonnet4_6` / `opus4_8` after configuration moved to
    `sonnet5` / `opus5`.
  - `tests/test_codeagent_trail.sh:81` — seeded and fallback model assertions
    still expect `opus4_8` after configuration moved to `opus5`.
  - `tests/test_shadow_spawn_learner.sh:67` — default learn resolution still
    expects `opus4_8` after configuration moved to `opus5`.
