---
priority: medium
effort: medium
depends: [1343]
issue_type: enhancement
status: Ready
labels: [task_workflow, git, worktree]
gates: [risk_evaluated]
anchor: 1343
created_at: 2026-07-29 22:02
updated_at: 2026-07-29 22:02
---

## Problem

t1343 introduces an advisory parallel-agent file-conflict signal whose unit of
overlap is the **file path**. That granularity is correct for the common case —
several agents sharing one working tree, where two agents editing the same file
genuinely clobber each other — but it is too coarse for agents working in
**separate git worktrees on separate branches**, where the same file can be
edited concurrently without any interference at edit time.

The framework supports both modes. `create_worktree` is a profile key:
`aitasks/metadata/profiles/fast.yaml:5` sets it to `false`, the `default` and
`remote` profiles omit it and fall through to an interactive question whose
first/default option is "No, work on current branch"
(`.claude/skills/task-workflow/SKILL.md:252-260`). So a real session mixes both:
most agents in the shared checkout, some in `aiwork/<task_name>` on
`aitask/<task_name>`.

t1343 does not model this distinction. Its signal will over-warn for
worktree-isolated agents.

## The two safety models

**Same working tree / same branch.** Any file-path overlap between two live
agents is unsafe: concurrent writes to the same file in one checkout clobber,
and there is no merge step to reconcile them. Path granularity is exactly right.

**Separate worktrees / separate branches.** Edit-time interference is zero. The
risk moves to the *merge*, where git reconciles hunks: non-overlapping hunks in
the same file merge cleanly, overlapping hunks conflict. So the question is no
longer "same file?" but "same lines?", and the honest answer for a same-file,
different-hunks pair is **probably safe, resolve at merge**.

Deciding the second case needs line-range information, and that is where the
open questions are.

## Open questions

1. **Cost and reliability of line ranges.** Plans state paths, not line numbers —
   the existing extractor at `aitask_remote_drift_check.sh:210-219` yields paths
   only. Asking a planning agent to estimate affected line ranges costs agent
   turns and produces numbers that go stale as soon as any edit shifts the file.
   `git diff -U0` hunks are cheap and exact, but purely **observational**: they
   describe edits already made, not edits about to be made. So there may be no
   reliable *predictive* line-range signal at all — quantify this before
   designing around it.
2. **Is an observational signal enough?** Comparing live `git diff -U0` hunks
   across worktrees would give exact, zero-estimate overlap for work already in
   progress. That may cover the real need without any prediction.
3. **What is the right verdict vocabulary?** Path overlap alone can no longer map
   to a single "unsafe". At minimum: unsafe-now (shared tree, path overlap),
   merge-risk (separate trees, hunk overlap), merge-clean (separate trees, no
   hunk overlap), unknown.
4. **Where does branch/worktree identity come from?** The plan header records
   `Worktree:` / `Branch:` / `Base branch:` / `Output branch:`
   (`.claude/skills/task-workflow/planning.md:375-398`), and
   `git worktree list --porcelain` enumerates live worktrees. Decide which is
   authoritative and how a claim records it.
5. **Does the same-branch-different-worktree case exist**, and is it safe? Two
   worktrees cannot check out the same branch in git, but they can share a base
   branch and merge into the same output branch — that is a merge-time risk.
6. **Does the extra precision change any user-visible decision?**, or does it
   only downgrade warnings? If it only ever downgrades, it may be worth shipping
   as a suppression rule rather than a new analysis.

## Acceptance criteria

- [ ] The claim/scan model records enough branch and worktree identity to tell
      "shared working tree" from "isolated worktree" for every live task.
- [ ] The verdict vocabulary distinguishes edit-time clobber risk from merge-time
      conflict risk; a same-file/different-hunk pair in separate worktrees is not
      reported with the same severity as a same-file pair in one checkout.
- [ ] A written evaluation of line-range feasibility: what it costs to obtain
      (agent turns vs. `git diff -U0`), how stale it becomes, and whether a
      predictive range is reliable enough to act on. A documented decision **not**
      to use predictive ranges is an acceptable outcome.
- [ ] Whatever is adopted stays advisory — no blocking, no auto-action.
- [ ] Tests cover a mixed fleet: at least one shared-checkout task and one
      worktree-isolated task live at the same time.

## Relationship to t1343

t1343 ships the path-granular signal and the claim registry. This task refines
the *interpretation* of that signal for worktree-isolated agents. It should be
planned only after t1343's claim schema exists, so the branch/worktree fields can
be added to a real schema rather than a hypothetical one.
