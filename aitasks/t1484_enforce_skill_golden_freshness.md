---
priority: medium
effort: medium
depends: []
issue_type: chore
status: Ready
labels: [testing, framework]
created_at: 2026-08-11 17:14
updated_at: 2026-08-11 17:14
---

## Problem

Nothing in the repo mechanically enforces the same-commit rule for skill-render
goldens — "regenerate the affected goldens in the same commit as the template or
closure edit" (CLAUDE.md; `aidocs/framework/skill_authoring_conventions.md:467`).
The rule is prose only, so it drifts silently and the suite stays red until
somebody happens to run the tests.

## Evidence: it has already drifted once, for two tasks

Commit `4f8d0387e` (t1466, "Gate lock acquisition on holder liveness") edited two
skill sources and regenerated none of their four goldens:

| golden | stale since |
|---|---|
| `tests/golden/procs/task-workflow/SKILL-default.md` | `4ba78d1c7` (t1272) |
| `tests/golden/procs/task-workflow/SKILL-fast.md` | `75ca90438` (t635_23) |
| `tests/golden/procs/task-workflow/SKILL-remote.md` | `4ba78d1c7` (t1272) |
| `tests/golden/skills/aitask-pickrem/SKILL-remote-claude.md` | `b9c44161b` (t1233) |

The cost was not just a red suite. t1468_2 hit the three task-workflow failures,
they looked caused by its own change, it regenerated them to get green — and that
regeneration was then reverted on review because curing a pre-existing regression
fixture inside an unrelated task obscures provenance. So one missed regeneration
consumed diagnosis time in two later tasks. t1482 finally cured all four.

## Design constraints (established while planning t1482)

1. **`aitask_skill_verify.sh` does not look at goldens at all.** It is the
   pre-commit check CLAUDE.md mandates for `.j2` / stub-surface changes, and it
   verifies renders, stub surfaces and wrapper-set parity — but never compares
   anything to `tests/golden/`. It is the natural host for the check, and adding
   one there costs nothing at the call sites that already run it.

2. **No single place knows the golden matrix.** Each `tests/test_skill_render_*.sh`
   hard-codes its own `GOLDEN_DIR`, profile set and agent dimensionality, and they
   genuinely differ: `aitask-pickrem` is `remote` × `claude` only (one file);
   `task-workflow` is 3 profiles with no `-claude` suffix under
   `tests/golden/procs/`; entry-point skills are `{default,fast,remote}` ×
   `claude` under `tests/golden/skills/` — except a skill whose template carries
   an `{% if agent %}` gate, which keeps goldens for all 4 agents. Any freshness
   check must either derive this matrix from a single declaration or drive the
   existing test scripts rather than re-deriving paths.

3. **CLAUDE.md's trigger is too narrow to have caught t1466.** It says to run
   `aitask_skill_verify.sh` before committing "any `.j2` template or stub-surface
   change". t1466 edited `.claude/skills/task-workflow/SKILL.md` — a plain wrapped
   `.md` in a render closure, not a `.j2` — so even a goldens-aware verify script
   would not have fired. Closing the loop means widening the trigger to any `.md`
   in a render closure, alongside the code change.

4. **A timestamp-based check is not viable.** The task note that seeded this
   (t1482) floated "fails when a wrapped source file is newer than its golden",
   but mtime is not tracked by git, and comparing commit timestamps is fragile
   across rebases and cherry-picks. The render tests are already the correct
   content-based comparison; the gap is purely that nothing runs them at the
   right moment.

## Candidate approach

Add a golden-freshness check to `.aitask-scripts/aitask_skill_verify.sh` that,
for every golden under `tests/golden/`, re-renders its source with the recorded
profile/agent and diffs — failing with the exact regeneration command for each
stale file. Source the matrix from one declaration (a manifest, or by having each
`tests/test_skill_render_*.sh` expose its `GOLDEN_DIR`/profile/agent tuple) so
constraint 2 cannot rot. Then widen the CLAUDE.md trigger per constraint 3.

Consider also whether the check belongs in a `--check` / `--regen` pair, so the
fix is one command instead of the hand-copied per-skill loop that
`skill_authoring_conventions.md:484-497` documents today — the loop's per-skill
variation (constraint 2) is itself part of why regeneration gets skipped.

## Verification

- A negative control: revert one golden to its pre-t1466 content and confirm the
  new check fails, naming that file and printing a regeneration command that
  actually cures it.
- Confirm the check passes on a clean tree, and that it covers all 76 goldens
  (compare its file count against `find tests/golden -name '*.md' | wc -l`).
- Confirm a wrapped-`.md`-only edit (no `.j2` touched) trips it — that is the
  t1466 case the current trigger misses.

## Origin

Spawned from t1482 (which regenerated the four stale goldens) with the user's
explicit decision to keep the enforcement mechanism as separate work rather than
widening that low-effort bug fix.
