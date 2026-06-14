---
Task: t915_fix_stale_test5_risk_eval_comment.md
Base branch: main
plan_verified: []
---

# Plan: Fix stale Test 5 risk-eval comment (t915)

## Context

`tests/test_skill_render_task_workflow.sh` Test 5 (lines 210–217) carries a
header comment that is now factually wrong. It claims:

> "No committed profile sets the key, so default renders show neither (proven by
> Test 1 zero-diff goldens)"

But `aitasks/metadata/profiles/fast.yaml:16` now sets `risk_evaluation: true`.
Verified against the goldens:
- `planning-fast.md` / `SKILL-fast.md` **carry** the gated risk steps (grep count 1)
- `planning-default.md` / `planning-remote.md` / `SKILL-default.md` / `SKILL-remote.md` **omit** them (count 0)

So a committed profile (`fast`) *does* activate the gate, and the fast goldens
are not zero-diff w.r.t. the risk steps. The comment misleads a future reader.
This is **comment-only**: Test 5's assertions still pass — they use a synthetic
`risk_evaluation: true` profile to prove the branch fires and the `default`
profile to prove absence; neither depends on the stale sentence.

## Change

Single edit to the comment block at `tests/test_skill_render_task_workflow.sh:211-217`.

Replace the stale sentence ("No committed profile sets the key, so default
renders show neither …") with an accurate statement that:
1. `fast.yaml` sets `risk_evaluation: true`, so the committed fast goldens
   (`planning-fast` / `SKILL-fast`) carry the gated steps;
2. `default`/`remote` omit them (all proven by Test 1's per-profile goldens);
3. the synthetic `risk_evaluation: true` profile below still proves both
   branches fire independently of any committed profile, and the `default`
   profile proves absence.

Proposed new comment (lines 211–217):

```bash
#
# The risk-evaluation gate is a zero-footprint {%- if profile.risk_evaluation
# is defined and profile.risk_evaluation %} wrap at two dispatch sites:
# planning.md §6.1 (the eval step) and SKILL.md Step 7 (the two-field write).
# fast.yaml sets risk_evaluation: true, so the committed fast goldens
# (planning-fast / SKILL-fast) carry the gated steps, while default/remote omit
# them (all proven by Test 1's per-profile goldens). The synthetic
# risk_evaluation: true profile below still proves both branches fire
# independently of any committed profile, and the default profile (key absent)
# proves absence.
```

No assertion changes. No golden regeneration. No `.md.j2` / closure edits.

## Files to modify

- `tests/test_skill_render_task_workflow.sh` — rewrite comment block lines 211–217.

## Verification

```bash
bash tests/test_skill_render_task_workflow.sh   # all tests still PASS (comment-only change)
shellcheck tests/test_skill_render_task_workflow.sh   # no new findings
```

Expected: identical pass/fail summary to before (the comment is not executable),
and the comment now matches reality (`fast.yaml` sets the key).

See **Step 9 (Post-Implementation)** of the shared workflow for commit/archive.

## Risk

### Code-health risk: low
- None identified. Pure comment edit in a single test-file block; no executable
  code, assertions, or goldens are touched, so there is no regression surface.

### Goal-achievement risk: low
- None identified. The task is precisely to correct this comment; the rewrite
  states the verified facts and plainly delivers the goal.

## Final Implementation Notes
- **Actual work done:** Rewrote the stale sentence in the Test 5 header comment
  of `tests/test_skill_render_task_workflow.sh` (lines 215–217 → 215–220). The
  comment now states that `fast.yaml` sets `risk_evaluation: true` (so the
  committed `planning-fast` / `SKILL-fast` goldens carry the gated steps, while
  `default`/`remote` omit them — proven by Test 1's per-profile goldens), and
  that the synthetic `risk_evaluation: true` profile still proves both branches
  fire independently of any committed profile while `default` proves absence.
- **Deviations from plan:** None. Implemented exactly as planned.
- **Issues encountered:** None.
- **Key decisions:** Kept the accurate parts of the original comment (the
  zero-footprint Jinja-wrap description and the two dispatch sites) and replaced
  only the inaccurate "No committed profile sets the key …" sentence, matching
  the task's "pure comment edit" scope.
- **Upstream defects identified:** None.
- **Verification:** `bash tests/test_skill_render_task_workflow.sh` → 85/85 pass
  (comment-only change, no assertion or golden impact). `shellcheck` reports only
  pre-existing info-level findings (SC1091 source-not-followed, SC2016 on the
  unrelated line 179) — none in the edited block.
