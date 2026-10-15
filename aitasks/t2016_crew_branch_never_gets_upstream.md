---
priority: medium
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [git, bash_scripts, robustness, syncer]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1599
followup_kind: upstream_defect
implemented_with: claudecode/opus5_5
created_at: 2026-10-15 23:07
updated_at: 2026-10-16 00:13
---

## Origin

Spawned from t2008 during Step 8b review.

## Upstream defect

- `.aitask-scripts/aitask_crew_init.sh:117-118` — the crew branch is created and checked out with no upstream, and no crew path ever runs `push -u`. So the `git push` in `aitask_crew_addwork.sh:333`, `aitask_crew_setmode.sh:127` and `agentcrew_utils.py git_commit_push_if_changes()` fails with "has no upstream branch" unless the user sets `push.autoSetupRemote`. The crew branch never reaches the remote, and addwork/setmode warn "git push failed (offline?)", which misattributes the cause.

Line numbers are as of commit 185aefca8. Re-derive them before editing.

## Diagnostic context

t2008 pinned `--no-autostash` on the three crew-worktree pulls. Proving reachability showed that no crew path gives the crew branch an upstream: `aitask_crew_init.sh` uses `git update-ref` + `git worktree add`, and nothing anywhere runs `push -u` / `--set-upstream`. Without an upstream, every crew `git pull` dies with "There is no tracking information for the current branch", and every bare `git push` dies with "The current branch crew-<id> has no upstream branch". The callers swallow both (`2>/dev/null || true` for the pull; `|| warn "git push failed (offline?)"` for the push; `check=False` plus a stderr warning in the Python helpers).

Verified by probe on git 2.55 with global/system config isolated: in a repo with a working `origin` remote, `crew init --id pr` then `crew addwork --crew pr --name w1` prints "Warning: git push failed (offline?)". The remote then has only `main`, and `git push` inside `.aitask-crews/crew-pr` reports "fatal: The current branch crew-pr has no upstream branch."

Consumers that assume the crew branch reaches the remote: `ait crew status set`'s terminal push (t653_3, "so they reach remote independently of the runner's iteration loop"); the runner's `enforce_single_instance` cross-host takeover; and `aitask_brainstorm_delete.sh` / `brainstorm_app.py`, which run `git push origin --delete crew-<id>`.

t2008's `tests/test_crew_pull_no_autostash.sh` sets the upstream by hand in its fixture (`push -u`) for exactly this reason.

## Suggested fix

First decide whether crew branches are meant to be published. If they are: when a remote exists, have `aitask_crew_init.sh` publish the branch with an upstream (`git -C <wt> push -u origin crew-<id>`, best-effort), or have the push sites use `push -u origin HEAD`. Also make the push warning report git's actual stderr instead of "offline?". If they are meant to be local-only, drop the pushes and pulls, and the `push origin --delete` cleanup.

Keep t2008's `--no-autostash` on the pulls. Note the runner-pull recovery follow-up from t2008's plan (`crew_runner_pull_refusal_recovery`): once branches really sync, that convergence gap becomes reachable for every user, not only `push.autoSetupRemote` users.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-10-15T21:13:30Z status=pass attempt=1 type=human
