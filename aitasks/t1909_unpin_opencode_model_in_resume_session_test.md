---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [codeagent]
gates: [risk_evaluated]
anchor: 1892
followup_kind: upstream_defect
created_at: 2026-10-06 23:58
updated_at: 2026-10-06 23:58
---

## Origin

Spawned from t1902 during Step 8b review.

## Upstream defect

- `tests/test_codeagent_resume_session.sh:107-112` — pins `opencode/openai_gpt_5_2`, which the model registry (`aitasks/metadata/models_opencode.json`) now marks `unavailable`. The three opencode assertions fail with exit 1 and "Model 'openai_gpt_5_2' is unavailable (not currently marked as available by connected providers)" no matter what the code under test does:
  - "opencode resume: exit 2 (usage), NOT die's 1"
  - "opencode resume: machine-readable refusal token" (`RESUME_UNSUPPORTED:opencode`)
  - "opencode raw without --resume-session: still works"

## Diagnostic context

Observed while running the t1902 launcher tests (`bash tests/test_codeagent_resume_session.sh` → 36/39). Every codex assertion passed. The same three failures reproduce at the parent commit (a796455b9) in an isolated worktree, so they are independent of t1902.

This is the same class of defect t1871 fixed in `tests/test_codeagent.sh`. A registry refresh that marks a pinned entry unavailable makes the launcher refuse the model before it reaches the code path under test.

## Suggested fix

Derive the opencode model from the registry instead of pinning it. Reuse the `codeagent_active_model` helper `tests/test_codeagent.sh` uses since t1871. Also assert that the derived model is non-empty, so a registry with no active entry fails as a recorded FAIL and not as a silent skip.

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t2159** id=2026-10-27T07:03:51Z.c37e0396ee800061e8b13f0d from=t2159 from_verified=yes at=2026-10-27T07:03:51Z base=aff353fe0e81e10eb613a30540418eb91c820e45 base_branch=main dirty=no host=omg16
>
> | Advisory: t1909's described defect appears already resolved.
> | 
> | Commit 4d1a9f93c (t1949, "Derive the opencode model from a fixture registry in
> | the resume-session test") replaced the `opencode/openai_gpt_5_2` pin at
> | tests/test_codeagent_resume_session.sh:107-112 with
> | `codeagent_active_model "$FIXTURE_META/models_opencode.json"` (line 125 at this
> | note's base commit).
> | 
> | Observed 2026-10-27, after t2159's full OpenCode registry refresh:
> | `bash tests/test_codeagent_resume_session.sh` -> PASS 40/40, exit 0.
> | 
> | Worth confirming nothing else in t1909's scope remains before closing it.
