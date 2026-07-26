---
Task: t1232_fix_models_verified_parity_baseline.md
Base branch: main
plan_verified: []
---

# Plan: Fix models verified-parity baseline (t1232)

## Context

`tests/test_codeagent_work_report.sh` Test 7 exits 1 at HEAD. The failure is on the
**live** task-data file `aitasks/metadata/models_claudecode.json`: model `opus4_8`
carries a real, stats-accumulated `verified["work-report"]: 100` but has **no**
`explain` key. The t1162_2 parity rule the test enforces — *"work-report mirrors
explain, absent where explain absent"* — is asserted with strict equality
(`.["work-report"] == .explain`) across **both** seed and live models files.

Root cause is a **layering mismatch**, not corrupt data:

- `verified["work-report"]: 100` is legitimate — it is a genuine satisfaction score
  recorded by the generic accumulator `aitask_verified_update.sh`, which updates
  `.verified[$skill] = round(avg)` for **whichever** skill actually ran
  (`opus4_8.verifiedstats["work-report"]` = 1 run, score_sum 100 is the evidence).
- The parity invariant is a **seed-authoring** design fact: work-report has no
  independent codeagent config and resolves identically to explain (proven at
  runtime by Test 4/5), so the *seeded baseline* scores are authored to mirror
  explain.
- These two facts are structurally incompatible on live files. Live satisfaction
  feedback accumulates **independent per-skill** scores, so strict equality
  `work-report == explain` cannot hold once a work-report run lands — even when
  `explain` **is** present, an independently measured work-report average will
  diverge from explain's. `trail` passes today only by luck (no live trail run has
  diverged yet); it inherits the identical fragility.

The task asks us to *decide which side owns the invariant*. It is owned by the
**seed files**.

## Chosen approach: scope Test 7 parity to seed files only

Restrict the Test 7 parity loop to `seed/models_*.json` and drop the live
`aitasks/metadata/models_*.json` glob, in **both** parity tests.

### Why this side (rejected alternative)

The task's other option — make the accumulator "refrain from creating `verified`
entries for operations whose parity partner is absent" — is rejected:

- It **only** handles the *absent* case. The equality assertion also breaks when
  `explain` is **present but diverged** (a future live work-report run on
  `opus4_6`, which has `explain: 80`, would produce `work-report != 80` and fail).
  So it does not actually make the live invariant hold — it only papers over
  today's single failure.
- It would **drop real measured data** (a genuine satisfaction score silently
  discarded) purely to satisfy a test.
- It **special-cases** a generic, skill-agnostic accumulator with a hardcoded
  `work-report → explain` dependency, and would need a *second* special case for
  `trail`, and another for every future explain-shadow operation. High blast
  radius, fragile, scope-dishonest.

Seed-only scoping is the minimal, semantically honest fix: parity is exactly a
seed-baseline authoring rule; runtime resolution equivalence is already covered by
Test 4/5; live per-skill scores are legitimately independent.

## Changes

### 1. `tests/test_codeagent_work_report.sh` (Test 7, ~lines 133–147)

- Change the `for f in` loop to iterate **only** `"$PROJECT_DIR"/seed/models_*.json`
  (remove the `"$PROJECT_DIR"/aitasks/metadata/models_*.json` line).
- Rewrite the Test 7 header comment to be **scope-honest** (no overclaim):
  - State the invariant is a **seed-authoring fixture convention** — the seeded
    baseline authors work-report to mirror explain because work-report has no
    independent codeagent config.
  - Explain *why* live files are excluded: live satisfaction feedback
    (`aitask_verified_update.sh`) accumulates **independent per-skill** scores, so
    strict `work-report == explain` equality cannot hold on live files by design.
  - Say precisely what still covers the runtime side, without overstating it:
    resolution equivalence is **spot-checked for claudecode** by Test 4 (seeded
    config) and Test 5 (no-config fallback) — it is **not** asserted generically
    across all agents/configs — and the accumulator-side ownership boundary is
    pinned by the new read-back guard in `tests/test_verified_update.sh` (below).

### 2. `tests/test_codeagent_trail.sh` (Test 7, ~lines 132–146)

- Identical change (drop the live glob, same scope-honest comment) — the `trail`
  parity test is structurally identical and equally fragile; fix both in one task
  so the pattern stays consistent.

### 3. `tests/test_verified_update.sh` — NEW regression guard (Concern 1)

Add focused **update-and-read-back** tests that pin the chosen ownership boundary:
the generic accumulator legitimately persists an independent `verified` score for
an explain-shadow operation **even when `explain` is absent** on that model. This
is exactly what the rejected Option-2 accumulator special-case would break, so
these tests fail loudly if a future change tries to silently discard that real
data (or reinstate the invalid live-parity rule).

Model on the existing Test-1..18 pattern (`setup_repo` → run accumulator →
`json_get` read-back → `rm -rf`). The fixture model `opus4_6` in `populate_repo`
has `explain: 60`; for these tests first **remove** the `explain` key so the model
lacks a parity partner:

- **Test 19 — work-report persists without an explain partner:**
  1. `setup_repo`, then `jq 'del(.models[0].verified.explain)'` the fixture and
     commit (so the model has `pick`/`batch-review` but **no** `explain`).
  2. Run `aitask_verified_update.sh --agent-string claudecode/opus4_6 --skill work-report --score 4 --date <fixed>`.
  3. Assert: `.verified["work-report"] == 80` (independent score persisted);
     `verifiedstats["work-report"].all_time.runs == 1`; and
     `(.verified | has("explain")) == false` (the accumulator did **not** fabricate
     an explain key — parity is not forced at write time).
- **Test 20 — trail persists without an explain partner:** identical, `--skill trail`.

### Non-goal (deliberate, scope-honest)

Not strengthening Test 4/5 into a generic cross-agent resolution-equivalence
matrix. Test 4/5 already compare resolved agent strings for work-report-vs-explain
directly (limited to claudecode + two configs); broadening to codex/opencode is
out of scope for this bug fix and is instead **accurately disclosed** in the Test 7
comment rather than silently implied.

No production code, no models-file data, and no accumulator logic changes. The live
`opus4_8.verified["work-report"]: 100` is left untouched — it is correct measured
data, and Test 19/20 encode that keeping it is the intended behavior.

## Risk

### Code-health risk: low
- Test-only change scoping a parity assertion to the files where it is meaningful;
  no production/runtime code touched, blast radius = 3 test files. · severity: low · → mitigation: none needed
- Reduction in live-file coverage (parity no longer checked on live models files).
  Accepted: the live parity assertion was *incorrect* (unsatisfiable by design).
  The removed check is **replaced** by a stronger, correctly-scoped guard — the new
  Test 19/20 read-back in `test_verified_update.sh` pins the actual runtime
  contract (independent scores persist without an explain partner). · severity: low · → mitigation: Test 19/20 + scope-honest inline comment

### Goal-achievement risk: low
- The task explicitly frames this as an owner decision between two options; the
  chosen option fully resolves the HEAD failure and de-fragilizes the trail test,
  which is exactly the stated goal. · severity: low · → mitigation: none needed

None of these warrant before/after mitigation tasks.

## Verification

1. Run the failing test — must now pass:
   ```bash
   bash tests/test_codeagent_work_report.sh   # expect exit 0, "All tests passed."
   ```
2. Run the sibling test — must still pass:
   ```bash
   bash tests/test_codeagent_trail.sh         # expect exit 0
   ```
3. Run the accumulator test with the new guard — must pass, Test 19/20 included:
   ```bash
   bash tests/test_verified_update.sh         # expect exit 0, "ALL TESTS PASSED"
   ```
4. **Prove the new guard can fail** (harness-can-fail check): temporarily hack
   `aitask_verified_update.sh` to skip creating a `verified` entry when the
   model lacks `explain` (simulating the rejected Option-2), re-run
   `test_verified_update.sh`, and confirm Test 19/20 now **fail** (exit 1). Revert
   the hack. This proves the boundary guard actually bites.
5. Confirm Test 7 still exercises seed parity (guards against accidentally
   emptying the loop): both runs print `PASS: parity holds in models_claudecode.json`
   (and codex/opencode) for the **seed** files.
6. Lint the touched tests are shell-clean (no new shellcheck regressions):
   ```bash
   shellcheck tests/test_codeagent_work_report.sh tests/test_codeagent_trail.sh tests/test_verified_update.sh || true
   ```

## Final Implementation Notes

- **Actual work done:** Scoped the Test 7 verified-score parity loop to
  `seed/models_*.json` only in `tests/test_codeagent_work_report.sh` and
  `tests/test_codeagent_trail.sh` (dropped the live `aitasks/metadata/models_*.json`
  glob), with scope-honest comment rewrites. Added Test 19/20 to
  `tests/test_verified_update.sh` pinning the accumulator-side ownership boundary
  (an independent `verified` score persists for work-report/trail even when the
  model has no `explain` key, and `explain` is not fabricated). No production code,
  no models-file data, no accumulator-logic changes.
- **Deviations from plan:** None in approach. Two review-driven refinements were
  folded in (see Post-Review Changes): (1) the Test 7 comments were corrected —
  the verified-**score** parity is a seed-authoring baseline convention DECOUPLED
  from model **resolution**; the original comment wrongly implied work-report/trail
  "have no independent codeagent config" and that trail resolves like explain. In
  fact each op has its own independently-editable `codeagent_config` key, and
  `trail` currently resolves to the heavy class like `pick` (`opus5`), NOT explain
  (`sonnet5`). (2) A concrete upstream follow-up (t1246) was created for the
  pre-existing v5 model-drift regression instead of only noting it.
- **Issues encountered:** The full `test_codeagent_work_report.sh` /
  `test_codeagent_trail.sh` suites are NOT green — Tests 1/4/5 in each fail because
  `seed/codeagent_config.json` and `seed/models_*.json` were migrated to the Claude
  5 family (`opus5`/`sonnet5`) while those assertions still hardcode v4 names. This
  is pre-existing and unrelated to the Test-7 fix (verified: my diff only touches
  the Test 7 block). The harness-can-fail check passed cleanly: under a simulated
  Option-2 accumulator special-case, exactly Test 19 & 20 failed (2/92), all else
  passed.
- **Key decisions:** The parity invariant is owned by the **seed files**, not the
  accumulator. Rejected the alternative (make the accumulator refrain from creating
  `verified` entries when `explain` is absent): it handles only the *absent* case,
  not *present-but-diverged*; it would drop real measured data; and it special-cases
  a generic skill-agnostic accumulator. Declared a non-goal: broadening Test 4/5
  into a generic cross-agent resolution matrix.
- **Upstream defects identified:** tests/test_codeagent_work_report.sh:76-117 and tests/test_codeagent_trail.sh:76-116 — Tests 1/4/5 in each assert v4 model names (claudecode/sonnet4_6, claudecode/opus4_8, claude-sonnet-4-6, claude-opus-4-8) but seed/codeagent_config.json and seed/models_*.json were migrated to the Claude 5 family (opus5/sonnet5), so 5 (work-report) + 4 (trail) assertions fail at HEAD. Pre-existing, unrelated to t1232's Test-7 change. Tracked as follow-up t1246 (also flags other v4-hardcoding tests to sweep: test_add_model.sh, test_usage_update.sh, test_shadow_spawn_*, test_risk_mitigation_landed.sh, test_crew_init.sh).

## Post-Review Changes

### Change Request 1 (2026-07-26) — plan review
- **Requested by user:** (1) add a regression test proving a live work-report/trail
  score may persist for a model lacking explain (protect the ownership boundary);
  (2) don't overclaim Test 4/5 resolution coverage — clarify scope.
- **Changes made:** Added Test 19/20 to `tests/test_verified_update.sh`; rewrote the
  Test 7 comments to be scope-honest. Both folded into the approved plan.
- **Files affected:** plan only (pre-implementation).

### Change Request 2 (2026-07-26) — implementation review
- **Requested by user:** (1) record a concrete upstream follow-up for the
  pre-existing v5 model-drift test failures; (2) fix the Test 7 comments — they
  wrongly said work-report/trail have "no independent codeagent config"; each has a
  distinct, independently-editable config key.
- **Changes made:** Created follow-up task **t1246**. Rewrote both Test 7 comments to
  state the score parity is a seed-authoring baseline convention decoupled from
  resolution, and corrected the trail comment (trail resolves like `pick`/heavy
  class `opus5`, NOT explain `sonnet5`).
- **Files affected:** `tests/test_codeagent_work_report.sh`,
  `tests/test_codeagent_trail.sh`, new `aitasks/t1246_*.md`.
