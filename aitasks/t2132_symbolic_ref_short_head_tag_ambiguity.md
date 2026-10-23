---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [git, bash_scripts]
gates: [risk_evaluated]
anchor: 2123
followup_kind: upstream_defect
created_at: 2026-10-23 11:13
updated_at: 2026-10-23 11:13
---

## Origin

Spawned from t2123 during Step 8b review.

## Upstream defect

`git symbolic-ref --short HEAD` abbreviates by ambiguity: with a tag named like
the checked-out branch (tag `dev` beside branch `dev`) it answers `heads/dev`,
which nothing downstream can resolve as a branch name. Reproduced on git 2.56:

```bash
git init -q -b dev && git commit -q --allow-empty -m i && git tag dev
git symbolic-ref --short HEAD    # heads/dev
```

Sites still using the abbreviated form:

- `.aitask-scripts/aitask_merge_task.sh:84` — `_head_branch()`
- `.aitask-scripts/aitask_task_worktree.sh:392` — `head_ref`
- `.aitask-scripts/aitask_sync.sh:1954` — data-worktree branch `db`
- `.aitask-scripts/lib/task_utils.sh:820` — data-worktree `branch`
- `.aitask-scripts/lib/shadow_scope.py:244` — checkout `branch`

Not in scope: `.aitask-scripts/aitask_plan_externalize.sh:669` is already
being fixed by t2124 (same full-ref approach) — check its landed state first
and reuse its idiom.

## Diagnostic context

t2123 fixed the sibling `--short` class in `detect_primary_branch()`
(`lib/git_utils.sh` + `lib/desync_state.py`) for `refs/remotes/origin/HEAD`:
read the full ref, accept it only under the expected prefix, and pin the fix
with a fixture-precondition assert (`--short` output really is ambiguous) so
the regression test cannot pass vacuously. The upstream report came from a
downstream project (thinking_backend#t65, another repository) that hit the HEAD
variant in plan headers.

Per site, check what the value feeds before choosing behaviour: comparisons
against a configured branch name (merge target, data branch) silently
mismatch on `heads/<b>`; display-only uses are cosmetic.

## Suggested fix

Read `git symbolic-ref --quiet HEAD` and strip `refs/heads/`, accepting the
value only when that prefix matched (detached / unexpected → existing
fallback). Add a tag-beside-branch regression per touched site, with a red
proof against the unfixed code.
