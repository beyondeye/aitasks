---
priority: low
effort: medium
depends: []
issue_type: bug
status: Implementing
labels: [git, bash_scripts, robustness]
gates: [risk_evaluated]
assigned_to: dario-e@beyond-eye.com
anchor: 1599
followup_kind: risk_mitigation
created_at: 2026-10-19 15:28
updated_at: 2026-10-19 16:24
---

## Origin

Risk-mitigation ("after") follow-up for t1739, created at Step 8d after implementation landed.

## Risk addressed

addresses: merge-mode gateway pull left as a bound

From t1739's `## Risk`:
> Merge-mode conflicts and option-prefixed `push` are left as explicit bounds, not closed. The task allows a bound, but the "any framework-driven pull" wording is still only met for rebase mode · severity: low

## Goal

t1739 routed `./ait git pull` through `_ait_owned_pull`, which auto-merges or
aborts a conflicted **rebase** it can prove it started (orig-head evidence). A
**merge-mode** pull (`-c pull.rebase=false`, `--no-rebase`) that stops —
on a conflict, or because a hook such as `pre-merge-commit` refuses the merge
commit — leaves `MERGE_HEAD`. It is reported truthfully as `data_midop`, but it
is never cleaned up, so later `./ait git` writes are refused until the user
runs `./ait git merge --abort`.

Add ownership evidence for a merge this pull started, so the gateway can abort
(or auto-merge) its own merge instead of leaving `MERGE_HEAD`. The evidence must
be as strict as the rebase rule: a merge started elsewhere — or one the user
deliberately paused — must never be touched. Candidate evidence: `ORIG_HEAD` ==
the HEAD read just before the pull, plus `MERGE_HEAD` == the fetched upstream
tip, all read under the pull mutex.

Keep `ait_rebase_is_ours` / `ait_rebase_abort_if_ours` as the single evidence
rule per operation (one implementation, several consumers). Update Tests C and L
in `tests/test_ait_git_gateway_pull.sh`, which currently pin the bound, plus the
`sync.md` "A stopped merge is left to you" bullet.
