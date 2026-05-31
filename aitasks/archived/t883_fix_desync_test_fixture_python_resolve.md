---
priority: medium
effort: low
depends: []
issue_type: bug
status: Done
labels: [testing, python, upstream_defect_followup]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-05-31 17:42
updated_at: 2026-05-31 21:57
completed_at: 2026-05-31 21:57
---

## Origin

Spawned from t881 during Step 8b review. While running the full Python suite to
verify t881 (a TUI metadata-dir fix), `tests/test_desync_state.py` failed —
confirmed pre-existing and unrelated to t881 (reproduces with t881 changes
stashed).

## Upstream defect

- `tests/test_desync_state.py:49 — fixture lib-copy loop omits python_resolve.sh (copies only desync_state.py, task_utils.sh, terminal_compat.sh, archive_utils.sh, yaml_utils.sh), but task_utils.sh:18 sources python_resolve.sh unconditionally, so aitask_changelog.sh --gather fails inside the fixture with "python_resolve.sh: No such file or directory". Same test-scaffold-sync class CLAUDE.md flags for test_scaffold.sh::setup_fake_aitask_repo, but in this test's own fixture builder.`

## Diagnostic context

`test_changelog_warns_for_data_desync_and_ignores_bad_helper_output` shells out
to `bash .aitask-scripts/aitask_changelog.sh --gather` inside a temp fixture
project built by the test's own helper. That helper copies a hardcoded list of
lib files into the fixture's `.aitask-scripts/lib/` but the list is stale:
`task_utils.sh` (which `aitask_changelog.sh` sources transitively) was updated to
`source python_resolve.sh`, and the fixture list was never updated to match.
Error: `task_utils.sh: line 18: .../python_resolve.sh: No such file or directory`.

## Suggested fix

Add `python_resolve.sh` to the lib-copy list in `tests/test_desync_state.py:49`.
Check whether any other test in `tests/` builds its own fake `.aitask-scripts/lib/`
with a similar hardcoded list and needs the same entry (the canonical scaffold
`tests/lib/test_scaffold.sh::setup_fake_aitask_repo` already includes it, per
CLAUDE.md baseline). Consider routing such fixtures through the shared scaffold
helper so the list cannot drift again.
