---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [auto-update]
gates: [risk_evaluated]
anchor: 1223
created_at: 2026-07-26 00:15
updated_at: 2026-07-26 00:15
boardidx: 31744
---

## Origin

Spawned from t1223_2 during Step 8b review.

## Upstream defect

- `.aitask-scripts/lib/github_release.sh:94` — `github_latest_tag_version`'s
  `git ls-remote` fallback has no time bound, while both curl paths in the same
  file use `--max-time` (10s REST, 5s rate-limit probe). Attended callers that
  reach the fallback — `ait upgrade` (`aitask_upgrade.sh` via
  `github_resolve_latest_version`) and `ait`'s `check_for_updates` — can hang
  indefinitely on a wedged network (e.g. a connection that blackholes instead
  of refusing).

## Diagnostic context

Found during t1223_2 plan review: the new Python wrapper
`framework_version.resolve_latest_version` had to add
`start_new_session=True` + a process-group SIGKILL on timeout specifically
because a timed-out helper could leave a live `git ls-remote` grandchild
behind (`subprocess.run(timeout=…)` kills only the direct child). The
falsifiability run demonstrated it: with a plain child kill, the orphaned
process held the pipe open for the full sleep duration. The bash-side callers
of the same helper have no equivalent bound at all.

## Suggested fix

Bound the fallback inside `github_latest_tag_version`, e.g.
`GIT_HTTP_LOW_SPEED_LIMIT`/`GIT_HTTP_LOW_SPEED_TIME` env vars plus a portable
watchdog (`timeout(1)` where available, falling back to a background-kill
pattern — mind macOS which lacks GNU coreutils `timeout` by default; see
aidocs/framework/shell_conventions.md). Keep the fix inside the helper so all
callers inherit it.
