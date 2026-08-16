---
priority: medium
effort: medium
depends: [1527]
issue_type: enhancement
status: Ready
labels: [dependencies, aitask-create, child_tasks]
gates: [risk_evaluated]
anchor: 1527
created_at: 2026-08-16 11:27
updated_at: 2026-08-16 11:27
---

Validate the `depends` field where it is written, so a task file can never
acquire a dependency id that no consumer can resolve. Producer side of t1527,
which fixes the consumer side.

## The gap

`depends` is written at four sites and validated at none of them:

- `aitask_create.sh:527`, `:668`, `:1865` — three separate `echo "depends:
  $deps_yaml"` sites, fed from `--deps` through `format_yaml_list`.
- `aitask_update.sh:725` — the same, for edits.

`format_yaml_list` formats; it does not check that anything in the list names a
task that exists, or even that the id is well-formed. So
`--deps 2,3` on a child of t1159 is accepted silently and writes
`depends: [2, 3]`, which every consumer then reads as top-level tasks 2 and 3.
That is exactly how `t1159_4` and `t386_7` came to carry sibling shorthand that
no resolver supports (fixed as data in `6f78a3e05`; the write path that allowed
it is untouched).

## The asymmetry — the cross-repo half already has this

`validate_xdeps_pair` (`lib/task_utils.sh`, shared by `aitask_create.sh` — see
the comments at `:530`, `:653`, `:1166`) enforces the `xdeps`/`xdeprepo`
both-or-neither contract at write time. The local `depends` field has no
equivalent. This task adds one, following that validator's shape rather than
inventing a new pattern.

## Scope

1. **One validator, called from all four write sites.** Not four checks that
   agree — a single helper in `lib/task_utils.sh` beside `validate_xdeps_pair`,
   invoked by both scripts. Adding a fifth write site later must be the only way
   to bypass it, and that should be caught by the guard in item 4.
2. **What to reject.** At minimum: an id that is neither `N`, `tN`, `N_M` nor
   `tN_M`; and an id that resolves to no task file (active or archived).
   Rejection must be an error with a usable message, naming the offending id.
3. **The sibling-shorthand trap specifically.** A bare `N` written into a
   **child** task, where no top-level task `N` exists but sibling `<parent>_N`
   does, is the exact shape of both historical defects. Do not silently rewrite
   it — the writer's intent is inferable but not certain. Reject it with a
   message that names the likely intended id (`did you mean t1159_2?`), and let
   the caller re-issue. A scan of the current tree finds this shape in 0 files
   after `6f78a3e05`, and correctly leaves the two genuine cross-parent
   parent-level deps alone (`t635_30` → 1183, `t1076_4` → 635) — so the
   heuristic is precise enough to reject on, not merely to warn about.
4. **A guard against regression.** A test that enumerates the `depends:` write
   sites in `.aitask-scripts/` and fails when one does not route through the
   validator. Prefer a source-level enumeration over a comment asking future
   authors to remember (the `monitor/` AST guard from t1294 is the local
   precedent for this shape).

## Deliberate non-goals

- Do **not** retro-validate the existing tree as part of this task — the two
  known offenders are already fixed, and a bulk sweep would mix a data
  migration into a validator change.
- Do **not** auto-correct on write. Rejecting with a suggestion keeps the
  authoring decision with the caller; silently rewriting an id is how a wrong
  guess becomes permanent.

## Verification

- Unit tests per rejection case (malformed id, non-existent id, sibling
  shorthand in a child) and per accepted form (`N`, `tN`, `N_M`, `tN_M`,
  archived dep, empty list).
- Drive the **real entry points** — `aitask_create.sh --batch` and
  `aitask_update.sh` — not just the helper, and assert both the non-zero exit
  status and the message content.
- A negative control: remove the validator call from one write site and confirm
  the item-4 guard fails, naming that site.
- Confirm the accepted-form list matches whatever t1527 settles as canonical —
  a validator that accepts a form the resolver cannot handle would reintroduce
  the same class of defect from the other end.
