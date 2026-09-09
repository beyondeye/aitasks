---
Task: t1747_1_failopen_probe_audit_doc.md
Parent Task: aitasks/t1747_sweep_failopen_git_probes.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1747_1 — The fail-open git-probe audit doc

## Context

First child of t1747, ordered first so the five code children can **point at**
this doc rather than restate the rule in six places (which would recreate the
N-copies drift the sweep is fixing). The parent plan
`aiplans/p1747_sweep_failopen_git_probes.md` holds the full audit; this task
gives it a permanent home outside an archived plan.

## Implementation

### 1. Create `aidocs/framework/failopen_git_probes.md`

Sections, in order:

1. **The rule** — quote `lib/task_utils.sh::task_git_commit_scoped` (~:473):
   capture the probe's exit status separately; empty output only means "nothing"
   when `rc == 0`.
2. **The canonical fix shape**, with the four existing in-tree call sites:
   `lib/task_utils.sh:473`, `aitask_metadata_commit.sh:174`,
   `aitask_issue_import.sh:650`, `aitask_fold_mark.sh:915`.
3. **Disposition is site-specific.** The fail-safe direction is whichever branch
   is not destructive. Contrast: the amend guards **refuse**;
   `task_git_commit_scoped` **commits anyway with a warning** (committing is the
   safe direction there); `aitask_gate.sh:1035` is a third disposition. This is
   the part a reader most needs — the rule is not "always refuse".
4. **Exit status, not stdout**, wherever the value is consumed arithmetically or
   as a path. Carry the measured trap from t1747_6: under `set -u`,
   `[[ "unverified" -gt 0 ]]` **aborts the script** (bash resolves the string as
   a variable name), while `-1` or `""` silently read as clean.
5. **Group A table** — all 13 authorizing sites, each with the child that owns
   it (the parent plan's Coverage map).
6. **Negative space** — sites deliberately left alone, with the reason each
   stays. This is what stops the next author "finishing the job".
7. **Exemplars to copy** — `lib/data_symlinks.sh:104` (round-trip verification)
   and `lib/txn_snapshot.sh:112` (explicit `die` naming the unverifiable path).
8. **Group C, named future work** — swallowed *mutation* failures
   (`aitask_setup.sh:1871`, `aitask_archive.sh:413,419`,
   `aitask_zip_old.sh:537-539`, and the `add … || true` before both
   `commit --amend` sites). Explicitly **not** this sweep, which is probes.
9. **Detection boundary** — the audit is a grep-and-read over
   `.aitask-scripts/**/*.sh`; a probe assembled through a variable or across
   statements is not seen. State this instead of claiming exhaustiveness.

### 2. Do NOT add a scanner

No regex tripwire over `|| true` on git probes. The informational uses are an
order of magnitude more numerous than the authorizing ones, so a scanner would
fail on correct code and its false positives would break unrelated work. Say so
in the doc, with the reason, so the decision is not silently revisited.

### 3. Cross-reference — conditionally

`aidocs/framework/shell_conventions.md` should point here; the natural anchor is
its commit-scoped bullet (~:63). At t1747 planning time that file carried ~24
uncommitted lines from another live session, so **check `git status` for it
first**:

- clean → add the back-reference in its own commit;
- still dirty → leave it and record the outstanding back-reference in the Final
  Implementation Notes.

Prefer extending the existing `CLAUDE.md` → `shell_conventions.md` pointer over
adding a new top-level pointer; confirm which is true before editing `CLAUDE.md`.

## Verification

- Every `file:line` cited in the doc resolves **in the current tree** — check
  each one rather than trusting the parent plan. The parent plan itself had to
  correct three stale references from the t1747 task body, so this is a real
  failure mode, not a formality.
- The Group A table's child assignments equal the parent plan's Coverage map
  (compare both, do not retype one from memory).
- No `website/content/` page: this is an `aidocs/` framework doc, not
  user-facing product documentation, so `check_links.py` does not apply.

## Risk

### Code-health risk: low
- Documentation only; no executable surface. · severity: low · → mitigation: none needed.

### Goal-achievement risk: low
- The doc could go stale as the code children land and line numbers move. ·
  severity: low · → mitigation: none needed — cite function names alongside line
  numbers so a moved line is still findable, which is what made the parent's own
  stale references recoverable.
