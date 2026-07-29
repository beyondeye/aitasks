---
priority: medium
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [shadow, execution_profiles]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1311
created_at: 2026-07-29 11:36
updated_at: 2026-07-29 12:05
---

## Origin

Spawned from t1317 during Step 8b review.

## Upstream defect

- `tests/test_opencode_setup.sh:22 — derives expected_skill_count from the tree
  under test (git ls-files '.opencode/skills/aitask-*/SKILL.md'), so a missing
  wrapper lowers BOTH sides of the comparison and the assertion stays green.
  Self-referential expectation — it can never detect a missing skill wrapper.`
- `.aitask-scripts/aitask_skill_verify.sh:57-64 — _stub_path_for covers only 3
  surfaces and omits .opencode/skills/<skill>/SKILL.md; its Read-path check
  (lines 150-164) also greps a regex rebuilt from the script's own restatement
  of stub-skill-pattern.md §3g rather than confirming the rendered file exists.`
- `.gitignore:43 — comment points at the stale path
  .claude/skills/task-workflow/stub-skill-pattern.md; the live doc is
  aidocs/framework/stub-skill-pattern.md.`

## Diagnostic context

t1317 added `tests/test_skill_dispatch_contract.sh`, a discovery-based
dispatch-contract smoke over every templated skill × every agent surface.
While enumerating the surfaces it found that `.opencode/skills/aitask-trail/SKILL.md`
did not exist — 11 of the 12 templated skills had that stub, `aitask-trail` had
only the command wrapper, missing since t1210_3 (`3386e1f43`).

The gap had survived because **no existing guard could see it**:

- `test_opencode_setup.sh` derives its expected count from the very tree it is
  checking, so the missing file silently reduced expected and actual together.
- `aitask_skill_verify.sh` never looks at the `.opencode/skills/<skill>/SKILL.md`
  surface at all.

t1317 fixed the `aitask-trail` stub itself and now enforces all four surfaces,
so the specific instance is closed. These three items are the *reasons it went
unnoticed*, which t1317 deliberately left out of scope (production-script and
test changes beyond the mitigation's remit).

## Suggested fix

- `test_opencode_setup.sh`: derive the expected wrapper set from an independent
  ground truth — e.g. the templated-skill discovery (`find .claude/skills -name
  'SKILL.md.j2'`) plus the user-invocable skill list — rather than from
  `.opencode/skills/` itself. A count derived from the artifact under test can
  only detect packaging/staging drift, never a missing source wrapper.
- `aitask_skill_verify.sh`: add `.opencode/skills/<skill>/SKILL.md` to
  `_stub_path_for`. Consider replacing the self-restated Read-path regex with
  `agent_skill_dir` from `.aitask-scripts/lib/agent_skills_paths.sh` (the seam
  `tests/test_skill_dispatch_contract.sh` already reuses), so §3g stays the
  single source of truth.
- `.gitignore:43`: repoint the comment at `aidocs/framework/stub-skill-pattern.md`.

## Related

- t1317 (`templated_skill_dispatch_smoke`) — created the four-surface contract
  test and fixed the `aitask-trail` instance.
