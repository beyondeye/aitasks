---
priority: low
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [git, bash_scripts, robustness]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1599
followup_kind: risk_mitigation
created_at: 2026-10-19 15:28
updated_at: 2026-10-19 16:24
---

## Origin

Risk-mitigation ("after") follow-up for t1739, created at Step 8d after implementation landed.

## Risk addressed

addresses: option-prefixed push left as a bound

From t1739's `## Risk`:
> Merge-mode conflicts and option-prefixed `push` are left as explicit bounds, not closed. The task allows a bound, but the "any framework-driven pull" wording is still only met for rebase mode · severity: low

## Goal

`ait` still routes `git push` on `$1`, so `./ait git push` reaches `task_push`
(the best-effort contract: retries, a pull-rebase between attempts, the reason
classification and `--batch` reporting), while `./ait git -c x push` reaches
`task_git_gateway` → `task_git` and runs a raw `git push` through the guard. That
cannot wedge the worktree, but it skips the best-effort contract and its
reporting, and the retry pull never happens.

Decide and implement what an option-prefixed push does. Either:
- route it through `task_push` using `ait_git_subcmd_index` (t1739's parser);
  this needs a decision on how the user's `-c` / `--config-env` reach the push
  (and its retry pull — `task_git_pull` shows how config is carried through the
  owned pull);
- or refuse it at the gateway with a message pointing at `./ait git push` /
  plain git.

Cover both the bare and the option-prefixed forms through the real dispatcher
(the pattern in `tests/test_ait_git_gateway_pull.sh`).
