---
priority: medium
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [ait_setup, git]
assigned_to: dario-e@beyond-eye.com
anchor: 2179
followup_kind: upstream_defect
created_at: 2026-11-03 17:32
updated_at: 2026-11-03 17:43
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
