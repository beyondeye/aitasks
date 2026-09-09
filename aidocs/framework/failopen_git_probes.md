# Fail-open git probes at authorization sites

A `|| true`-suppressed git probe collapses **"the probe failed"** into **"the
answer is empty"** — and empty is almost always the *permissive* answer: "no
conflicts", "nothing foreign", "nothing staged", "nothing dirty". When that
answer gates a destructive or history-rewriting action, an unreadable repository
silently **authorizes** the action.

Read this when you write or review any `git` / `task_git` / `_ait_data_git` probe
whose result decides whether something is deleted, discarded, rewritten,
released, published, or committed.

> **Citations in this document are anchored on `file::function` first.** Line
> numbers are a secondary hint, accurate as of **`ec9641e79`**. They drift fast —
> the audit that produced this page had eight of its own references go stale
> within a day — so if a line does not match, search for the function name.

## The rule

`lib/task_utils.sh::task_git_commit_scoped` (`:588-594`) states it:

> **Capture the probe's exit status separately — empty output only means
> "nothing" when `rc == 0`.**

```bash
local st st_rc=0
st="$(task_git status --porcelain -- "$@" 2>/dev/null)" || st_rc=$?
if [[ $st_rc -eq 0 && -z "$st" ]]; then
    return 2                      # VERIFIED nothing to commit
fi
[[ $st_rc -ne 0 ]] && warn "git status failed for $* — committing anyway"
```

The failure mode this prevents is not "the probe errored and we noticed". It is
"the probe errored, produced no output, and the empty output was read as a clean
bill of health".

## The canonical fix shape

Four sites in the tree already follow it. Copy whichever is closest in shape:

| site | probe | on failure |
|---|---|---|
| `lib/task_utils.sh::task_git_commit_scoped:588` | `status --porcelain` | warn, commit anyway |
| `aitask_metadata_commit.sh::run_preflight:175` | `status --porcelain` | `FAILED:cannot inspect status of <p>` |
| `aitask_issue_import.sh::_import_amend_guard:657` | `show --name-only` | refuse the amend |
| `aitask_fold_mark.sh::_fold_amend_guard:916` | `show --name-only` | refuse the amend |

## Disposition is site-specific — the rule is *not* "always refuse"

Separating rc from empty tells you the answer is **unverified**. What to *do*
with that is a per-site decision, and the fail-safe direction is **whichever
branch is not destructive**. The three dispositions in the tree:

| disposition | site | why it is the safe direction there |
|---|---|---|
| **refuse** | `aitask_fold_mark.sh::_fold_amend_guard:918`, `aitask_issue_import.sh::_import_amend_guard:659` | the action is a history rewrite; not amending costs one extra commit, amending wrongly is permanent |
| **proceed, with a warning** | `lib/task_utils.sh::task_git_commit_scoped:594` | the probe only asks "is there anything to commit?" — committing an already-clean path is a no-op, while *skipping* a real change loses it |
| **report failure** | `aitask_gate.sh::cmd_materialize_active:1040-1042` | persistence could not be verified, so the caller must not be told the tuple is durable |

Choosing the disposition is the design work. Getting the rc capture right and
then resolving the unknown toward the destructive branch fixes nothing.

## The unverified state travels on the exit status, never on stdout

Wherever the value is consumed arithmetically or as a path, a magic stdout
sentinel is unsafe in **both** spellings. Measured during t1747_6 against
`aitask_merge_task.sh::_tree_dirty_tracked`, whose value is read by
`[[ "$(…)" -gt 0 ]]` — an arithmetic context:

| sentinel | what `[[ "$s" -gt 0 ]]` actually does |
|---|---|
| `"unverified"` | bash resolves it as a **variable name**; under `set -u` it **aborts the script** — mid-operation, possibly after a lock dir was already removed |
| `-1` or `""` | evaluates false ⇒ silently reads as **clean** — a brand-new fail-open |

So:

```bash
# 0 = verified (count on stdout); 2 = unverified (stdout empty).
_tree_dirty_tracked() {
    local out rc=0
    out="$(git status --porcelain -uno 2>/dev/null)" || rc=$?
    (( rc == 0 )) || return 2
    printf '%s' "$(printf '%s' "$out" | grep -c '.' || true)"
}
```

And every consumer must be rewritten with it: a bare `if _probe; then` treats
rc 2 as false, which re-creates the exact fail-open the tri-state was introduced
to close. Hardening a helper while one caller still reads it bare leaves the site
looking fixed and behaving unchanged — so a helper change is only complete when
its **whole** call-site set has been enumerated and given a disposition.

## Group A — authorizing / destructive, fail-open

**Thirteen sites, as audited at `ec9641e79`** (see [Re-deriving this
set](#re-deriving-this-set) — the count is reproducible, not standing). Each row
names the child of t1747 that owns the fix.

| # | site | probe answers | gates | on probe failure | owner |
|---|---|---|---|---|---|
| A1 | `lib/task_automerge.sh::ait_automerge_advance:203` | "any unresolved conflict paths?" | **`git rebase --skip`** | reads "empty patch" ⇒ **discards the replayed commit** | t1747_2 |
| A2 | `lib/task_automerge.sh::_ait_automerge_conflicted_now:212` | same | loop entry ⇒ compounds into A1; post-advance ⇒ `return 2` ⇒ abort | entry use is fail-open *into A1*; post-advance use is already fail-closed | t1747_2 |
| A3 | `aitask_sync.sh::_commit_group:772` | "has another session staged these paths?" | `add` / `commit -o` / `reset` | reads "nobody staged" ⇒ **replaces another session's index entry** — the harm its own comment names | t1747_3 |
| A4 | `aitask_sync.sh::_quarantine_load_and_prune:503` | "is this quarantined path settled?" | **releasing a publication quarantine** | reads "clean/settled" ⇒ **pushes a commit deliberately withheld**. Its comment argues that a clean worktree is not settlement — yet an *unreadable* one currently reads as clean | t1747_3 |
| A5 | `aitask_sync.sh::do_pull_rebase:919` | "did `pull --rebase` stop on a conflict?" | conflict resolution vs. **unconditional `rebase --abort`** | reads "not a conflict" ⇒ aborts a real in-progress resolution (recoverable via `ORIG_HEAD`) | t1747_3 |
| A6 | `aitask_fold_mark.sh::_fold_amend_guard:961` | "is HEAD already published upstream?" | **`commit --amend`** | two holes: `\|\| true` conflates "no upstream" with "rev-parse failed"; and `merge-base --is-ancestor` returns **≥2 on error**, treated as "not published" ⇒ amend authorized | t1747_5 |
| A7 | `aitask_issue_import.sh::_import_amend_guard:686` | identical to A6 | **`commit --amend`** | identical two holes | t1747_5 |
| A8 | `aitask_merge_task.sh::_unmerged_paths:82`, `::_tree_dirty_tracked:83` | "unmerged paths? tree dirty?" | force-release lock deletion; **post-`reset --hard` verification** | `_tree_dirty_tracked` prints `0` both when clean and when `git status` failed ⇒ reports `FORCE_RELEASED` on an unverified tree | t1747_6 |
| A8b | `aitask_merge_task.sh::_merge_head_present:81` | "is a merge in progress?" | the force-release remedy selector (`:406`) and the post-`merge --abort` verification (`:411`) | a failed `rev-parse` yields empty, so the test degrades to `[[ -f "/MERGE_HEAD" ]]` ⇒ **"no merge in progress"** | t1747_6 |
| A9 | `aitask_setup.sh::_ait_list_framework_changes:3591-3594` | "which framework files are dirty?" | the **baseline subtracted** so setup does not sweep foreign work | empty baseline ⇒ **another session's uncommitted work is committed under `ait: Add aitask framework`** | t1747_4 |
| A9b | `aitask_setup.sh::snapshot_pre_setup_dirty:3647`, `::commit_framework_files:3763` | "is `.aitask-scripts/VERSION` tracked?" | bootstrap ⇒ commit-**all** | `&>/dev/null` conflates untracked (rc 1) with git error (rc 128) ⇒ same sweep. The two rcs *are* separable | t1747_4 |
| A10 | `aitask_sync.sh::_sync_gitdir:301` | "which git-dir owns the data worktree?" | `_worktree_wedged` early refusal; quarantine file location | fabricated `.git` ⇒ "not wedged" ⇒ sync proceeds; **and relocates the quarantine file, losing every held entry** | t1747_3 |
| A12 | `aitask_lock.sh::lock_task:195` | "does a lock already exist?" | acquiring a task lock **over another session's** | failed `ls-tree` ⇒ no output ⇒ `grep -q` false ⇒ the whole lock-exists block at `:195-276` is skipped, and with it *every* liveness gate (`LOCK_LIVE_HOLDER`, `LOCK_UNVERIFIABLE_HOLDER`, `LOCK_RECLAIM`) — a silent reprise of the t1466 defect those gates exist to prevent | t1747_6 |

**A11 — `lib/task_utils.sh::task_git_commit_scoped:588-594` — is correct as
written**, not a defect. It already separates rc from empty and deliberately
resolves the unknown toward *committing*, which is that site's safe direction. It
is the reference pattern; it appears here so a future auditor does not "find" it
again.

Every row has an owner. A Group A row with no owning child would make the sweep's
"every authorizing probe" claim false, so that partition is the check — not the
row count.

## Deliberately left alone

These are **not** oversights. Tightening them would add noise without removing
risk, and this table is what stops the next author "finishing the job".

| site | why it stays |
|---|---|
| `aitask_sync.sh::do_pull_rebase:1004,:1009,:1015` — `rebase --abort … \|\| true` | best-effort *recovery* on an already-failing path, not a probe gating anything |
| `aitask_setup.sh::commit_framework_files:3804` — post-commit `still_untracked` | feeds a `warn` only |
| `aitask_remote_drift_check.sh` | pure reporter, exits 0; `:182` / `:191` already fail **closed** to `FETCH_FAILED`. `:219` is a soft spot (a failed diff reads as `NO_OVERLAP`) but advisory only — noted, not fixed |
| `aitask_change_surface.sh` | display-only; written best-effort by `aitask_pick_own.sh::main:681`, read by the docs-updated gate skill |
| `aitask_revert_analyze.sh::_collect_hashes_for_id:172` | read-only analyzer; its failure direction is *under*-destructive ("no commits found" ⇒ nothing reverted) |
| `lib/task_utils.sh::_task_sync_head:854`, `::_task_sync_unpulled_count:860`, `::_task_push_unpushed_count:1378`, `::_task_push_upstream:1383`, `::_task_push_has_remote:1388` | documented always-return-0 reporting probes; empty is a *declared* "undeterminable" value the warning text handles (`TASK_SYNC_UNPUSHED=""` / `TASK_PUSH_UNPUSHED=""`) |
| `lib/data_symlinks.sh::ait_main_worktree_root:105`, `lib/txn_snapshot.sh::txn_require_clean:112` | already exemplary — see below |
| `aitask_merge_task.sh::_head_branch:84` | empty reads as detached ⇒ `RECOVERY_FAILED`. Already fail-closed |

## Exemplars to copy

- **`lib/data_symlinks.sh::ait_main_worktree_root:105-108`** — round-trip
  verification. It re-resolves the canonicalized root through git and requires
  the answer to match, returning 2 on any mismatch rather than trusting a single
  read.
- **`lib/txn_snapshot.sh::txn_require_clean:112`** — an explicit `die` that names
  the unverifiable path: *"could not read the git status of `<p>` — refusing to
  start a transaction whose paths cannot be verified"*. `errexit` is suppressed
  inside its caller, so the check is explicit or it does not happen.

## Group C — swallowed *mutation* failures (named future work)

Not probes, so **not** part of this sweep — but the same blast radius, recorded
here so a later reader does not think the class was missed:

- `aitask_setup.sh::setup_data_branch:1871-1872` — a failed `git rm` is
  swallowed, then an unconditional `rm -rf` runs anyway.
- `aitask_archive.sh::handle_folded_tasks:413,:419` — a failed `rm` drops the
  path from the commit's pathspec via `|| continue`.
- `aitask_zip_old.sh::main:544-546` — three `task_git add … || true` calls, then
  the commit proceeds with whatever staged set survived.
- The `add … || true` immediately before both `commit --amend` sites:
  `aitask_fold_mark.sh:1027` (top-level `amend)` case arm) and
  `aitask_issue_import.sh::_import_commit_frontmatter:706`.

## Why there is no scanner

A regex tripwire over `|| true` on git calls was considered and **rejected**. The
legitimate, informational uses outnumber the authorizing ones by roughly an order
of magnitude, so a scanner would fail on correct code, and its false positives
would break unrelated work. Enforcing a convention people can follow beats
parsing source for intent.

This document is the mechanism. Do not add the tripwire without first re-opening
this decision.

## The detection boundary

The audit behind this page is a grep-and-read over the shell sources under
`.aitask-scripts/`. It catches the common single-command shape. A probe assembled through a variable,
or spread across statements, is **not** seen by it. So "every authorizing probe"
is a claim about what this method reaches — not a proof of absence.

### Re-deriving this set

Before trusting the count, re-run it:

```bash
# (a) candidate population — the tripwire
grep -rnE '(git|task_git|_ait_data_git|_ait_data_gitdir)[^|]*(\|\| *true|\|\| *echo|\|\| *[A-Za-z_]+=)' \
  .aitask-scripts --include='*.sh' | wc -l
grep -rnE 'if +!? *[^;]*\b(git|task_git|_ait_data_git) .*&>/dev/null' \
  .aitask-scripts --include='*.sh' | wc -l

# (b) what changed since this page was last reconciled
git diff ec9641e79..HEAD -- .aitask-scripts | grep -E '^\+' | \
  grep -E '\b(git|task_git|_ait_data_git)\b'
git diff -- .aitask-scripts        # uncommitted work from concurrent sessions
```

Read every hit from (b) and classify it authorizing vs. informational. If (a)'s
counts moved but (b) shows nothing, a probe was removed or reshaped — read that
diff too. Any new authorizing site belongs in the Group A table **with an owner**;
any deliberate exclusion belongs in the negative-space table **with a reason**.
