---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [ait_setup, install, bash_scripts]
gates: [risk_evaluated]
anchor: 1852
followup_kind: upstream_defect
created_at: 2026-10-06 23:07
updated_at: 2026-10-06 23:07
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
