---
priority: medium
risk_code_health: low
risk_goal_achievement: low
effort: low
depends: []
issue_type: bug
status: Done
labels: [ait_setup, git]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 4a36c12bb96d.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 2179
followup_kind: upstream_defect
implemented_with: claudecode/opus5_5
created_at: 2026-11-03 17:32
updated_at: 2026-11-03 19:06
completed_at: 2026-11-03 19:06
---

## Origin

Spawned from t2179_1 during Step 8b review.

## Upstream defect

- `.aitask-scripts/aitask_setup.sh:2029-2030` — the data-branch `.gitignore` block that setup appends
  ("# Task data (lives on aitask-data branch, accessed via symlinks)") writes **unanchored** `aitasks` and
  `aiplans` lines. In gitignore syntax a bare name with no slash matches that name **at any depth**, so every
  nested directory called `aitasks/` or `aiplans/` anywhere in a consumer project is silently ignored, not just
  the two root symlinks the block is meant for.

## Diagnostic context

t2179_1 built a private fixture store inside the aitasks_go repository (`aidocs/shadow_q_store/`), containing
copies of task and plan files at `fixtures/<scenario>/task/aitasks/t60/…` and `…/task/aiplans/p60/…`.
`git add aidocs/shadow_q_store` then silently skipped exactly those five files:
`git check-ignore -v` pointed at aitasks_go `.gitignore:4: aitasks` and `.gitignore:5: aiplans`, which were
written by `ait setup`. The commit looked complete; only a manifest-vs-`git ls-files` comparison exposed the
gap. (t2179_1 worked around it by storing the copies as `_aitasks/` / `_aiplans/`.)

Any consumer project with a nested `aitasks/` or `aiplans/` directory (examples, fixtures, docs, vendored
copies) loses those files the same silent way.

## Suggested fix

Write the entries anchored to the repository root: `/aitasks` and `/aiplans` (still no trailing slash, so
the root **symlinks** keep matching — a trailing slash only matches directories, which is why the bare form
was chosen; see the trailing-slash rewrite just above in the same function). Add a migration that rewrites
existing bare `aitasks` / `aiplans` lines in that block to the anchored form (the same way setup already
rewrites legacy trailing-slash data entries), and a test with a nested `docs/aitasks/` file proving it is no
longer ignored while the root symlinks still are. Check `.aitask-data` too, and the same block in any other
installer path (`install.sh` / `ait upgrade`) that writes it.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-11-03T16:22:17Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-11-03T17:02:19Z status=pass attempt=1 type=human

> **🔄 gate:risk_evaluated** run=2026-11-03T17:06:19Z-risk_evaluated-a1 status=running attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Note: stuckhash:b6de8194dd18f36f

> **✅ gate:risk_evaluated** run=2026-11-03T17:06:19Z-risk_evaluated-a1 status=pass attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Result: risk evaluated (## Risk section + both levels present)
> Log: `.aitask-gates/2184/risk_evaluated_2026-11-03T17:06:19Z-risk_evaluated-a1.log`
