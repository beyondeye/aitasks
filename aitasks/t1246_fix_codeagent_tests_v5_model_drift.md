---
priority: medium
effort: medium
depends: []
issue_type: bug
status: Ready
labels: [codeagent, test]
followup_kind: upstream_defect
created_at: 2026-07-26 00:19
updated_at: 2026-08-13 23:06
boardidx: 37888
---

## Origin

Surfaced during t1232 (Test-7 verified-parity fix). Pre-existing, unrelated to
t1232's Test-7 change — recorded as a concrete follow-up so the regression is
traceable.

## Upstream defect

`seed/codeagent_config.json` and `seed/models_*.json` were migrated to the
Claude 5 model family (`claudecode/opus5`, `claudecode/sonnet5`,
`claude-opus-5`, `claude-sonnet-5`), but two codeagent test suites still assert
the v4 model names, so they now fail at HEAD:

- `tests/test_codeagent_work_report.sh` — Test 1 (dry-run seeded default),
  Test 4 (`resolve work-report == resolve explain` → `sonnet4_6`), Test 5
  (no-config fallback → `opus4_8`). 5 assertions fail.
- `tests/test_codeagent_trail.sh` — Test 1 (dry-run seeded default), Test 4
  (`resolve trail == resolve pick` → `opus4_8`), Test 5 (no-config fallback →
  `opus4_8`). 4 assertions fail.

`tests/test_codeagent.sh` currently passes. Other tests that hardcode v4 names
(`test_add_model.sh`, `test_usage_update.sh`, `test_shadow_spawn_*`,
`test_risk_mitigation_landed.sh`, `test_crew_init.sh`) should be swept for the
same drift while here — check each rather than assuming.

## Suggested fix

Update the affected assertions to the current seed model names:
- `claudecode/sonnet4_6` → `claudecode/sonnet5`, `claudecode/opus4_8` →
  `claudecode/opus5`, `claude-sonnet-4-6` → `claude-sonnet-5`,
  `claude-opus-4-8` → `claude-opus-5` — matching whatever `seed/codeagent_config.json`
  and `seed/models_*.json` actually declare at fix time.

Consider whether these assertions should derive the expected model from the seed
config instead of hardcoding, to avoid re-breaking on the next model bump.

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t1865** id=2026-09-22T21:30:14Z.b8f57186a71b212445e8cd5f from=t1865 from_verified=yes at=2026-09-22T21:30:14Z base=915cb836c4d8e2a054838bd5c312563c62a5fe27 base_branch=main dirty=yes host=omg16
>
> | Advisory: this task's premise appears to be stale, and it may be a duplicate.
> | 
> | **The three suites you cite as failing at HEAD all pass.** Run on 2026-09-22
> | while implementing t1865:
> | 
> | - `tests/test_codeagent_work_report.sh` — PASS
> | - `tests/test_codeagent_trail.sh` — PASS
> | - `tests/test_shadow_spawn_learner.sh` — PASS
> | 
> | t1318 converted all three to source `tests/lib/codeagent_defaults.sh` and derive
> | the expected default from the config the resolver actually reads, which is the
> | "consider whether these assertions should derive the expected model from the
> | seed config instead of hardcoding" your Suggested fix proposes. Your line
> | references (`:80`, `:81`, `:67`) and the `sonnet4_6` / `opus4_8` expectations are
> | correspondingly stale.
> | 
> | Empirical confirmation, not just a green run: t1865 promoted the shipped
> | defaults again (to `claudecode/opus5_5`) and all three stayed green through it —
> | which is the property the derive conversion was for.
> | 
> | **Probable duplicate.** t1316 described the same three files with the same three
> | line numbers and was folded into t1865, whose body records the same "already
> | fixed by t1318" finding. If that reading is right, this task is likewise
> | complete-by-other-means and is a fold/close candidate rather than work.
> | 
> | **Your sweep suggestion is still live, though.** "Other tests that hardcode v4
> | names should be swept for the same drift — check each rather than assuming" was
> | never done as a standing sweep. A full-repo sweep during t1865's planning found
> | ~20 suites carrying hardcoded model names; all are stable fixtures that block
> | nothing, so none is a bug, but the inventory in
> | `aidocs/framework/model_reference_locations.md` badly understates them. t1341
> | owns that doc and has the findings. One genuine production defect did come out
> | of the sweep (`.aitask-scripts/lib/roadmap_run.py` held a second hardcoded
> | default the promote helper never patched) — fixed in t1865.
> | 
> | So: if you close this, the part worth preserving is the sweep, not the three
> | files.
> | 
> | **Hedge:** test results are from a single local run on 2026-09-22 against a
> | worktree that also contained another session's uncommitted changes to unrelated
> | files; re-run before acting. The duplicate judgement is my reading of t1316 and
> | t1865, not a verified fold decision.
