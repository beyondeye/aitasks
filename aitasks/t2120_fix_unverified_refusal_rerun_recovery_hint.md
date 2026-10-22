---
priority: medium
risk_code_health: low
risk_goal_achievement: low
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [git, bash_scripts, robustness]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 4a36c12bb96d.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1733
followup_kind: upstream_defect
implemented_with: claudecode/opus5_5
created_at: 2026-10-22 10:07
updated_at: 2026-10-22 11:03
---

## Origin

Spawned from t2116 during Step 8b review.

## Upstream defect

- `.aitask-scripts/aitask_setup.sh:4358 — _ait_refuse_unverified_commit tells the user to "Re-run 'ait setup' once git works again", but a re-run's snapshot treats the files the refused run left dirty as pre-existing and never commits them (verified for the install twin by experiment); the recovery that works is a manual commit`
- `install.sh:commit_installed_files (git add failure branch) — "Framework files NOT committed. Run 'ait setup' to retry." has the same flaw: setup's pre-setup baseline will contain those dirty files and leave them alone`

Line numbers are as of t2116's commit (0b18f4cd7) — grep the function names.

## Diagnostic context

t2116 ported the t1747_4 "unverified baseline ⇒ refuse" fix into install.sh. While
writing the install-side refusal message it was checked by experiment what a re-run
does after a refused commit: the re-run's `snapshot_pre_install_dirty` lists the
upgrade's own uncommitted files as dirty, so `commit_installed_files` reports them
under "Pre-existing uncommitted changes … left alone" and commits nothing. The same
baseline logic in `aitask_setup.sh` (`snapshot_pre_setup_dirty` →
`commit_framework_files` subtract) means "Re-run 'ait setup'" cannot recover the
files either. install.sh's new `_install_refuse_unverified_commit` therefore points
to a manual commit ("review 'git status' and commit the framework files yourself
with 'git add' / 'git commit'").

Repro (install twin, sourced in-process):

```bash
source install.sh --source-only; set +euo pipefail
# repo with .aitask-scripts/VERSION committed; INSTALL_DIR=<repo>
AIT_INSTALL_BASELINE_UNVERIFIED=1; echo new > .aitask-scripts/new.sh; commit_installed_files  # refused
snapshot_pre_install_dirty; commit_installed_files   # re-run: new.sh "left alone", stays ??
```

## Suggested fix

Reword `_ait_refuse_unverified_commit`'s recovery line in aitask_setup.sh (and the
install.sh `git add` failure message) to name the manual commit as the recovery,
matching `_install_refuse_unverified_commit`. Check whether any test pins the old
wording (grep "Re-run 'ait setup'" / "to retry") and whether the setup-side
`git add`/`git commit` failure messages carry the same hint.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-10-22T08:03:03Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-10-22T09:53:59Z status=pass attempt=1 type=human
