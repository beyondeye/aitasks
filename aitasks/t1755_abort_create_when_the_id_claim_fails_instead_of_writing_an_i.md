---
priority: high
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [bash_scripts, robustness]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 4a36c12bb96d.681bafac2cb9.d73bba2fc21f
file_references: [.aitask-scripts/aitask_create.sh:1042-1050, .aitask-scripts/aitask_create.sh:2320]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-09-09 09:50
updated_at: 2026-09-09 10:31
---

## Problem

`claim_parent_id_once()` (`.aitask-scripts/aitask_create.sh:1042`) allocates its
stderr capture with an **unchecked** `mktemp`:

    claim_stderr=$(mktemp)
    claimed_id=$("$SCRIPT_DIR/aitask_claim_id.sh" --claim 2>"$claim_stderr") || { ... }

When `TMPDIR` is missing, full, read-only or not a directory, `mktemp` fails and
`claim_stderr` is empty, so `2>"$claim_stderr"` is an ambiguous redirect and the
claim cannot run. The failure is then **swallowed**: the caller invokes it as
`claimed_id=$(claim_unique_parent_id false)`, and a `die` inside a command
substitution exits only the subshell — the outer script continues with an
**empty** `claimed_id`.

Observed end state (reproduced 2026-09-08 while implementing t1725_2):

    mktemp: failed to create file via template '.../nope/tmp.XXXXXXXXXX'
    ./.aitask-scripts/aitask_create.sh: line 1047: : No such file or directory
    cat: '': No such file or directory
    Error: Atomic ID counter failed: unknown error
    Created: aitasks/t_tdf.md          <-- id-less task file, exit 0

So a failed id claim produces `aitasks/t_<name>.md` — a task file carrying **no
id at all** — and `create` reports success. t1721 already had to add downstream
handling to "skip and warn on task files whose filename carries no task id",
which is evidence this shape leaks into the rest of the framework rather than
being caught at the source.

## Goal

A failed id claim **aborts** the create. Nothing is written, nothing is
committed, and the exit status is non-zero, so a caller can distinguish it from
success.

Two defects to fix, and they are separable:

1. `mktemp` is unchecked. Allocation failure must degrade or abort deliberately,
   never leave an empty path in a redirect. (`lib/task_utils.sh`'s
   `task_git_commit_scoped` took the "degrade to /dev/null" route in t1725_2 —
   see the `_ait_cs_sink` comment there for the shape.)
2. A `die` inside `claim_unique_parent_id` is invisible to its caller because of
   the surrounding `$( )`. Even with (1) fixed, any other failure in the claim
   path has the same hole. The status must be propagated — capture with
   `|| rc=$?` on a pre-declared local and check it, rather than relying on
   `set -e` through a command substitution.

Fixing (1) alone would close this reproduction while leaving the class open.

## Verification

- Forced-failure row: run `aitask_create.sh --batch --commit` with `TMPDIR`
  pointing at a non-existent directory. Assert non-zero exit, **no** id-less
  `t_*.md` file, no commit, and that the id counter did not move
  (`aitask_claim_id.sh --peek` identical before and after).
- Negative control: the same create with a usable `TMPDIR` still succeeds.
- A second forced failure that is NOT mktemp (e.g. stub `aitask_claim_id.sh` to
  exit non-zero) must also abort — this is what pins defect (2) rather than only
  (1), and it is the row that stays red if only the mktemp is fixed.

## Context

Found while implementing **t1725_2** (refuse task-data writes on a wedged
worktree; stop `create` burning ids). Out of scope there: t1725_2's AC4/AC5 cover
the pre-write guard and the commit-failure retry path, not the id-claim path.
t1725_2 fixed the same unchecked-`mktemp` class in `lib/task_utils.sh` and
records this one as an upstream defect in `aiplans/p1725/p1725_2_*.md`.
