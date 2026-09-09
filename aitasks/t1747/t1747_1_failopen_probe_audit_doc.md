---
priority: medium
effort: medium
depends: []
issue_type: documentation
status: Implementing
labels: [documentation, git, bash_scripts]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1733
created_at: 2026-09-09 11:12
updated_at: 2026-09-09 12:22
---

## Context

First child of t1747. Lands the durable audit record for the fail-open git-probe
class **before** any code child, so the code children (t1747_2 … t1747_6) can
point at it instead of restating the rule in six places.

The parent plan (`aiplans/p1747_sweep_failopen_git_probes.md`) holds the full
audit; this task moves it to a permanent home.

## Goal

Create `aidocs/framework/failopen_git_probes.md` containing:

1. **The rule**, quoted from `lib/task_utils.sh::task_git_commit_scoped:473`:
   capture the probe's exit status separately — empty output only means
   "nothing" when `rc == 0`.
2. **The canonical fix shape**, with its four existing in-tree call sites:
   `lib/task_utils.sh:473`, `aitask_metadata_commit.sh:174`,
   `aitask_issue_import.sh:650`, `aitask_fold_mark.sh:915`.
3. **The disposition rule**: what a failed probe should *do* is site-specific —
   the fail-safe direction is whichever branch is not destructive. Contrast the
   amend guards (refuse) with `task_git_commit_scoped` (commit anyway with a
   warning). Include `aitask_gate.sh:1035` as a third disposition.
4. **The exit-status-not-stdout rule**: the unverified state must travel on the
   exit status wherever the value is consumed arithmetically or as a path. Cite
   the measured trap from t1747_6: under `set -u`, `[[ "unverified" -gt 0 ]]`
   aborts the script (bash resolves the string as a variable name), while `-1`
   or `""` silently read as clean.
5. **The Group A table** — all 13 authorizing sites from the parent plan, with
   the child that owns each (the Coverage map).
6. **The negative-space table** — sites deliberately left alone and why
   (`rebase --abort … || true` recovery calls, display-only probes,
   `aitask_remote_drift_check.sh` / `aitask_change_surface.sh` /
   `aitask_revert_analyze.sh`, the documented always-return-0 reporting probes,
   and `_head_branch`, which is already fail-closed).
7. **Exemplars to copy**: `lib/data_symlinks.sh:104` (round-trip verification)
   and `lib/txn_snapshot.sh:112` (explicit `die` naming the unverifiable path).
8. **Group C — swallowed *mutation* failures** as named future work, NOT part of
   this sweep: `aitask_setup.sh:1871`, `aitask_archive.sh:413,419`,
   `aitask_zip_old.sh:537-539`, and the `add … || true` immediately before both
   `commit --amend` sites.
9. **The detection boundary, stated explicitly.** The audit is a grep-and-read
   over `.aitask-scripts/**/*.sh`. It catches the common single-command shape; a
   probe assembled through a variable or across statements is not seen. Say this
   rather than claiming exhaustiveness.

## Explicitly NOT in scope

**Do not add a regex tripwire** over `|| true` on git probes. The legitimate
uses vastly outnumber the defects — the informational set is an order of
magnitude larger than the authorizing set — so a scanner would fail on correct
code, and its false positives would break unrelated work. The doc is the
mechanism; see `feedback_docs_over_narrow_source_scan_guard` and
`feedback_enforce_the_convention_dont_parse_for_intent`.

## Cross-referencing

`aidocs/framework/shell_conventions.md` should eventually point here — the
natural anchor is the commit-scoped bullet at its line ~63.

**Do NOT edit `shell_conventions.md` in this task's commit.** At the time t1747
was planned that file carried ~24 uncommitted lines from another live session
(`shell_startup_closure.py` work), and committing it would sweep their work in.
Re-check `git status` for that file when this task runs:

- clean → add the cross-reference here, in its own commit;
- still dirty → leave it, and note in the Final Implementation Notes that the
  back-reference is outstanding.

Check whether `CLAUDE.md` already routes agents through a pointer that reaches
this doc; prefer extending the existing `shell_conventions.md` pointer over
adding a new top-level one.

## Verification

- `python3 -c "..."` or a grep confirming every Group A row in the doc names a
  child, and that the child set matches the parent plan's Coverage map.
- Every file:line cited in the doc resolves — check each one rather than
  trusting the parent plan, since the tree moves (the parent plan itself had to
  correct three stale line references from the task body).
- No new `website/content/` page is needed: this is an `aidocs/` framework doc,
  not user-facing product documentation.
