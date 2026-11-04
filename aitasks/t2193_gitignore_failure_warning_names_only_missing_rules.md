---
priority: low
effort: low
depends: []
issue_type: bug
status: Ready
labels: [ait_setup, git]
gates: [risk_evaluated]
anchor: 2179
followup_kind: upstream_defect
created_at: 2026-11-04 10:03
updated_at: 2026-11-04 10:03
---

## Origin

Spawned from t2188 during Step 8b review.

## Upstream defect

- `.aitask-scripts/aitask_setup.sh:_ait_warn_gitignore_rules_failed` — every caller passes the group's full rule list (`${_ait_gi_rules[@]}`), not the missing subset. So for a multi-rule group (`worktrees`, and now `data`), the rc-2 warning and its "Fix by hand: add the lines …" tell the user to add rules the file already has.

## Diagnostic context

`_ait_add_gitignore_rules` checks each rule on its own and writes only the missing ones. On success it records exactly those in `_ait_gitignore_added`, and the "Added …" line names only them. Its rc-2 failure report, `_ait_warn_gitignore_rules_failed <what> <rule>...`, is different: every caller passes the whole group, `"${_ait_gi_rules[@]}"` (`_ait_setup_gitignore_group`, `upgrade_cache_gitignore`, `upgrade_store_gitignore_rules` via `_ait_upgrade_gitignore_rules`), and since t2188 also Step 7's task-data rules and the re-run repair `setup_data_gitignore_symlink_safe`.

t2188 found this while writing its H4b case: a branch-mode, read-only `.gitignore` holding `/.aitask-data` and `/aiplans` but lacking `/aitasks`. The warning read "Could not add /.aitask-data /aitasks /aiplans to .gitignore — left unchanged", and the hand-fix line listed all three. Following it literally duplicates two lines. That is harmless to git, but the message is wrong about what is missing. `tests/test_setup_git.sh` 27f documents the current behaviour ("<reported> is what the failure line names (every rule of the group)"). t2188's H4b and Test 40 pin the full-group wording for the data rules, so a fix must update those assertions too.

## Suggested fix

Have `_ait_add_gitignore_rules` expose the rules it tried to write on rc 2, for example in a `_ait_gitignore_missing` array set before the write. Make the failure report name those, not the caller's full list. When the failure is "cannot inspect" (not a regular file, unreadable), the missing set is unknown, so keep naming the whole group there. Update the 27f, H4b and Test 40 assertions to match.
