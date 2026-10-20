---
priority: medium
risk_code_health: low
risk_goal_achievement: low
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [ait_setup, install, bash_scripts]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1852
followup_kind: upstream_defect
implemented_with: claudecode/opus5_5
created_at: 2026-10-06 23:07
updated_at: 2026-10-20 19:08
---

## Origin

Spawned from t1852_5 during Step 8b review.

## Upstream defect

- `.aitask-scripts/aitask_setup.sh:2353-2381 — setup_gate_logs_gitignore() (and the sibling setup_*_gitignore helpers) commit with a bare git commit -m and no pathspec, sweeping whatever else is staged in the index into the "ait: Add … to .gitignore" commit`

## Diagnostic context

t1852_5 added `setup_testmap_gitignore()` by cloning `setup_gate_logs_gitignore()`. The clone of the pattern is:

```bash
(cd "$project_dir" && git add .gitignore && git commit -m "ait: Add .aitask-gates/ to .gitignore (gate sidecar logs)" 2>/dev/null) || true
```

`git commit -m` with no `-- <path>` pathspec commits the ENTIRE index. Any file a
concurrent session (or the user) has staged in that checkout at that moment
rides along under the setup's "ait: Add … to .gitignore" message. The new
helper in t1852_5 commits with `-- .gitignore` instead, and
`tests/test_install_engine_binary.sh` case G1 pins that a pre-staged foreign
file stays staged and uncommitted. The older helpers were left unchanged (not
owned by t1852_5).

Affected helpers to audit (grep `git commit -m "ait: Add` in `aitask_setup.sh`):
`setup_python_cache_gitignore`, `setup_gate_logs_gitignore`,
`setup_shadow_store_gitignore`, `setup_worktree_dirs_gitignore`, and any other
`setup_*` step that commits with a bare `git commit -m`.

## Suggested fix

Add `-- .gitignore` (the one path the helper wrote) to each commit, and add a
regression case modeled on G1 in `tests/test_install_engine_binary.sh`:
pre-stage an unrelated file, run the helper, assert the commit names only
`.gitignore` and the foreign file is still staged.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-10-20T16:08:30Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-10-20T16:08:49Z status=pass attempt=1 type=human
>
> Note: no code change; user approved closing as fixed by t1959
