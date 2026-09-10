---
priority: medium
effort: high
depends: [t1166_1, t1166_2]
issue_type: feature
status: Ready
labels: [task_workflow, git-integration, child_tasks, skills]
gates: [risk_evaluated]
anchor: 1166
created_at: 2026-07-20 12:06
updated_at: 2026-09-10 11:58
---

## Context

Third child of t1166 (shared family worktree). Wires family-worktree mode into the task-workflow skill's main path: Step 5 environment setup, the new reusable family-sync procedure, the Step 9 restructure, Re-entry Routing, and the planning-time opt-in. Depends on t1166_1 (helper verbs proven) and t1166_2 (frontmatter field exists).

All edits go to the AUTHORING sources under `.claude/skills/task-workflow/` (rendered `task-workflow-<profile>-/` dirs regenerate). SKILL.md is plain-named but passes through Jinja via the closure walk; family blocks are **profile-invariant plain markdown** (outside Jinja gates) so golden churn stays mechanical. Read `aidocs/framework/skill_authoring_conventions.md` before editing.

## Key Files to Modify

- **NEW** `.claude/skills/task-workflow/family-sync.md` — Jinja-free reusable targeted-sync procedure (like task-abort.md; no per-profile goldens, lands in every rendered closure once referenced from SKILL.md).
- `.claude/skills/task-workflow/SKILL.md` — Step 5 (~246-296), Re-entry Routing (~236), Step 9 (~561-646).
- `.claude/skills/task-workflow/planning.md` — child-creation checkpoint (family opt-in question) + plan metadata headers (~375-396).
- Goldens: `tests/golden/procs/task-workflow/SKILL-{default,fast,remote}.md`, `planning-{default,fast,remote}.md`.

## Implementation Plan (contracts PINNED by parent plan `aiplans/p1166_shared_worktree_for_child_task_families.md`)

**1. family-sync.md** — inputs `task_id`, `parent_id`, `mode` (per-child | final).
- Per-child mode: (a) `diff-summary` → propose eligible vs held-back paths; **default is hold-back** — propose a path only when the subset is judged self-contained (no imports/references/schema coupling into held-back paths; candidate sources: the child's plan file-list + archived sibling plans; anything entangled with pending sibling work stays behind); plan lists are heuristic, the proof is (c). (b) **NON-SKIPPABLE** approval AskUserQuestion (same banner framing as Step 9's merge gate; "sync nothing this round" is valid — the evaluation is required, syncing is not). (c) `sync-paths` → **main-side verification**: run configured `verify_build` (or the task's build gate) against main at the sync commit in the root checkout; the sync is NOT complete until it passes; on failure → `undo-sync` fail-closed rollback, re-classify offending paths held-back, report (child completion unaffected). (d) Only after a verified sync (or sync-nothing round): mandatory `sync-from-main`.
- Final mode: NON-SKIPPABLE residual-diff approval → `final-merge` → main-side verification, then **return — the sub-procedure does NOT tear down** (ordering single-sourced in Step 9).
- Recovery section: deferred/conflicted final merges — re-run `final-merge`, `list` as audit entry point; consumed by t1166_4's FAMILY_UNMERGED routing.

**2. SKILL.md Step 5** — profile-invariant block BEFORE the `{% if profile.create_worktree %}` gate: for child tasks run `./.aitask-scripts/aitask_family_worktree.sh status <task_id>`; if `FAMILY_MODE:true` → `ensure` + `sync-from-main`, work in `DIR`, set context `family_mode=true`, skip per-task worktree logic entirely. State: the explicit `family_worktree: true` opt-in OVERRIDES a `create_worktree: false` profile. On `BLOCKED:active_sibling:<id>:<hostname>`: AskUserQuestion — wait / pick different task / (when lock provably stale) force via `ensure --force`. `DIRTY:true` = secondary warning only.

**3. SKILL.md Re-entry Routing** — family children reuse via `status`/`ensure` instead of the `refs/heads/aitask/<task_name>` match; do NOT `sync-from-main` when resuming IMPLEMENT with uncommitted work.

**4. SKILL.md Step 9** — split "If a separate branch was created" into family-child vs per-task. Family child order: (1) all work committed on family branch; child's gates/build verification run INSIDE the family worktree; (2) family-sync per-child mode (replaces per-task merge approval; `merge_approved` recorded `scope=partial_sync`); (3) last-child detection BEFORE archival: `status` → `REMAINING_LIST` == exactly this child → family-sync final mode NOW; only after successful verified final merge: `aitask_archive.sh` (parent auto-archives) → `teardown` LAST (its unmerged-commits refusal = no-op safeguard). On final-merge conflict/deferral: do NOT archive — child stays Implementing/in-flight, re-enterable (Check 5 resume model). Non-final children: skip per-task teardown, then `aitask_archive.sh` as today.

**5. planning.md** — child-creation checkpoint: after batch child creation, AskUserQuestion "Should these children share one long-lived family worktree with per-child selective sync to main?" (No, independent per-child worktrees (default) / Yes, shared family worktree); on Yes: `aitask_update.sh --batch <parent> --family-worktree true`, folded into the existing parent data commit. Plan metadata headers: family-child variant `Worktree: aiwork/t<parent>` / `Branch: aifamily/t<parent>` / `Base branch: main` / `Family worktree: shared`.

**6. Goldens + rerender** — regenerate the six golden files via `skill_template.py <file> <profile>.yaml claude > golden`; run `.aitask-scripts/aitask_skill_rerender.sh <profile>` for each profile (incl. committed `task-workflow-remote-` closure).

## Coordination — current-branch gate run (t1776)

t1776 changes the same `If a separate branch was created` block in Step 9 that
this task splits into family-child and per-task paths. It makes the
`ait gates run` call reachable on current-branch picks, where today it is
skipped and `risk_evaluated` goes unrecorded. Whichever of the two lands second
must keep a gate run on the current-branch path, and must not bring back the
branch-only nesting.

## Verification Steps

- `bash tests/test_skill_render_task_workflow.sh` (byte-equality vs goldens; agent-invariance)
- `./.aitask-scripts/aitask_skill_verify.sh` (prerender freshness — catches stale committed remote closure)
- Confirm family-sync.md present in every rendered closure dir after rerender.

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t1166_5** id=2026-09-10T18:37:52Z.04d3ea620560aa33e3d9e32d from=t1166_5 at=2026-09-10T18:37:52Z base=e2f12c49990459143f2e387db431b5222fc66ef7 base_branch=main dirty=no host=omg16
>
> | Docs-coordination sweep, run outside any task: `from=` names the docs task that
> | depends on you, not an agent working on it, so it is unverified. Advisory only —
> | tree-relative claims are dated by this note's base SHA; `~` line numbers are
> | approximate. Verify before acting.
> | 
> | Your item 2 places the family-worktree block in task-workflow SKILL.md
> | "Step 5 — profile-invariant block BEFORE the {% if profile.create_worktree %}
> | gate" (~246-296). That ground moved after t1166 was written (2026-07-20):
> | 
> | - t1536 (bbafbd4f5, "Defer the worktree fork until after plan approval") moved
> |   the worktree fork out of Step 5 to after plan approval; t1558 (7bae59b51,
> |   "Defer the worktree claim in Step 5's create_worktree surfaces") followed up.
> | - Resource admission (68af4d67a) and the parallel-admission preflight
> |   (2384e4a64) now run before the fork.
> | - t1233 (b9c44161b) added output_branch, so "a family worktree always bases on
> |   main" has to say how it interacts with output_branch.
> | 
> | Re-derive where the family block belongs — and the Re-entry Routing / Step 9
> | line refs — against the current task-workflow SKILL.md.j2 before planning.
> | t1166_5 (docs) will document whatever you ship; a note there says the same.
