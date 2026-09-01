---
priority: medium
effort: low
depends: [t1599_2]
issue_type: enhancement
status: Implementing
labels: [bash_scripts, robustness, task_metadata]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 4a36c12bb96d.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
created_at: 2026-09-01 10:28
updated_at: 2026-09-01 12:40
---

## Context

Surfaced during t1599_2 review. `aitask_fold_mark.sh` prints its structured
stdout records (`PRIMARY_UPDATED:<id>`, `FOLDED:<id>`, `CHILD_REMOVED:<p>:<c>`,
`TRANSITIVE:<id>`) as Steps 3-5b perform each mutation — i.e. **before** Step 6
commits.

When Step 6 fails or refuses, `_fold_rollback` undoes every one of those
mutations, but the records have already been written to stdout. A stream
consumer therefore observes progress for a transaction that no longer exists.

t1599_2 made this materially more visible: `--commit-mode amend` now *routinely*
refuses (foreign task file in HEAD, unknown metadata, already-published HEAD),
so what used to be a rare failure path is a normal outcome.

## Not currently a live defect

The exit code is authoritative and the refusal message goes to stderr. Every
in-tree caller keys off the terminal records — `AMENDED` / `COMMITTED:<hash>` /
`NO_COMMIT` — which are emitted only on success, so no caller is misled today.
This is a robustness / honesty fix, not a bug fix.

## Suggested fix

Buffer the per-mutation records and flush them only once Step 6 reaches a
terminal success, so stdout describes committed state exclusively.

Alternative if buffering proves awkward (the records are emitted from several
places across ~250 lines): emit an explicit terminal `ROLLED_BACK:<primary_id>`
marker on every rollback path and document in the script header that consumers
must treat it as invalidating every preceding record of that run.

Prefer buffering — a marker requires every consumer to opt in, and the ones that
do not are exactly the ones that get it wrong.

## Scope note

This changes `aitask_fold_mark.sh`'s **stdout output contract**, so it needs a
sweep of the consumers before landing: `aitask_create.sh:1912`
(`run_auto_merge_if_needed`), the `aitask-explore` / `aitask-pr-import` /
`aitask-contribution-review` skills, and the ad-hoc fold procedure in
`task-workflow`'s `planning.md`.

## Verification

- Refused amend: assert stdout carries **no** `PRIMARY_UPDATED:` / `FOLDED:`
  records (or, on the marker design, a terminal `ROLLED_BACK:`), and that the
  frontmatter is genuinely restored.
- Successful fresh + amend: assert the full record set is still emitted, in the
  same order, so the buffering does not drop or reorder anything.
- Extend `tests/test_fold_mark.sh` — its refusal cases already assert restored
  frontmatter and can carry the stdout assertions.
