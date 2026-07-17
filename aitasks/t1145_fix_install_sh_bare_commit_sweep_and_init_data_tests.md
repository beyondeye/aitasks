---
priority: medium
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [python]
assigned_to: dario-e@beyond-eye.com
anchor: 1074
implemented_with: claudecode/opus4_8
created_at: 2026-07-10 19:03
updated_at: 2026-07-17 10:50
boardidx: 60
---

## Origin

Spawned from t1128 during Step 8b review.

## Upstream defect

- `install.sh:921,1015 — commit_installed_files / commit_installed_data_files finalize with a bare git commit (no pathspec), sweeping a foreign pre-staged index on a dirty curl|bash upgrade; path-scope both commits and their --cached --quiet guards (user deferred this out of t1128)`
- `tests/test_init_data.sh — 23 of 30 checks fail on the unmodified baseline (pre-existing breakage, unrelated to t1128; reproduced on a clean stash of t1128's changes)`

## Diagnostic context

t1128 fixed the same sweep class in `aitask_setup.sh`: `commit_framework_files` / `commit_framework_data_files` now snapshot pre-setup dirty framework paths (`snapshot_pre_setup_dirty`, baseline diff incl. `git diff --cached`) and path-scope the `git commit` / `--cached --quiet` guard. `install.sh` duplicates the framework-path whitelist (sync comment at `aitask_setup.sh` `_ait_framework_paths`) and still finalizes both its commit functions with a bare `git commit` — it is sentinel-gated (`.aitask-scripts/VERSION` tracked) so it never fires on a true bootstrap, but on a dirty upgrade via curl|bash a foreign pre-staged index is swept. The user explicitly deferred this out of t1128 as a follow-up (fresh-install path makes the risk mostly theoretical).

The `test_init_data.sh` failure was found while running setup-adjacent suites for t1128 verification: 7 passed / 23 failed identically with and without t1128's changes, so it is pre-existing breakage — diagnose separately (may be environment drift or a stale scaffold assumption).

## Suggested fix

For install.sh: path-scope both finalize commits (`git commit -m ".." -- "${changed_files[@]}"`) and switch their `git diff --cached --quiet` guards to the path-scoped form — the minimal fix that stops the foreign-index sweep without porting the full snapshot mechanism (install.sh runs stand-alone and cannot source shared helpers). For test_init_data.sh: run the suite, bisect the first failing assertion, and fix the test scaffold or the regression it exposes.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-07-17T07:50:35Z status=pass attempt=1 type=human
