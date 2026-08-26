---
priority: medium
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [worktree, git]
gates: [risk_evaluated]
assigned_to: dario-e@beyond-eye.com
anchor: 1159
followup_kind: upstream_defect
created_at: 2026-08-26 17:34
updated_at: 2026-08-26 17:42
---

## Origin

Spawned from t1624 during Step 8b review.

## Upstream defect

- `.aitask-scripts/aitask_setup.sh:1522 — the same impossible remedy text
  ("Failed to create worktree. You may need to run: git worktree add
  .aitask-data aitask-data") on ait setup's own worktree-creation failure path;
  it warns and returns rather than dying, and operates on an explicit
  $project_dir instead of $PWD, so it is a separate flow with its own contract.`

## Diagnostic context

t1624 fixed the identical text in `aitask_init_data.sh`'s bare invocation path,
where it was reached from inside a linked task worktree. The advice cannot work
there: the primary already has the `aitask-data` branch checked out, so a second
worktree of it is exactly what git refuses.

`aitask_setup.sh:1519-1523` is the sibling instance:

```bash
info "Creating .aitask-data/ worktree..."
(cd "$project_dir" && git worktree add .aitask-data aitask-data 2>/dev/null) || {
    warn "Failed to create worktree. You may need to run: git worktree add .aitask-data aitask-data"
    return
}
```

Two differences from the t1624 site, both of which is why it was deliberately
left out of scope rather than fixed in passing:

1. It operates on an explicit `$project_dir` rather than `$PWD`, so the
   linked-worktree confusion t1624 addressed does not arise the same way —
   `ait setup` is told which checkout to act on.
2. It `warn`s and `return`s rather than `die`ing, so setup continues past it
   into Step 3 (populate data) with no `.aitask-data` present. Whether that
   continuation is safe is itself worth checking as part of this task.

What is shared is the defect t1624 actually names: the message advises running
the command that just failed, and `2>/dev/null` discards git's own error, so the
user is left with no information about *why* it failed.

## Suggested fix

Mirror the t1624 change at this site: capture git's stderr
(`err="$(... 2>&1 >/dev/null)"`) and report it instead of naming the failed
command, e.g. "Failed to create the .aitask-data worktree in '$project_dir'.
git said: $err". Then decide, and document, whether `return` is the right
behavior — if Step 3 would go on to write task data into a directory that is not
a worktree, this should probably `die` or skip the populate step.

Check the neighbouring `warn`/`return` paths in the same function for the same
discard-stderr pattern while there.
