---
Task: t1166_shared_worktree_for_child_task_families.md
Base branch: main
plan_verified: []
---

# t1166 — Shared git worktree for child-task families

## Context

Today every task gets its own ephemeral code worktree `aiwork/<task_name>` on branch `aitask/<task_name>`: created in task-workflow Step 5, merged to main and torn down in Step 9, all within one workflow run. Children of the same parent get no continuity — each child re-derives its environment from main, and there is no way to accumulate family work on a shared branch with a controlled, incremental hand-off to main.

t1166 adds an opt-in **family worktree**: a parent's children share one long-lived worktree/branch, with (a) a **required per-child selective sync-back stage** — at each child's completion the accumulated family diff is evaluated and the eligible subset synced to main with user approval, (b) sync-forward from main to control drift, and (c) a deferred final family merge + teardown when the last child completes. The targeted-sync logic ships as a reusable sub-procedure, not inlined in workflow steps (acceptance criteria).

**User-pinned decisions:** activation via durable frontmatter on the parent (set at child-creation checkpoint); path-level sync granularity in v1 (hunk-level = follow-up); archival semantics unchanged ("done = committed on family branch"; gates confirmed branch-agnostic); parent+children families only (anchor-group extension = follow-up). Task split into **6 children** as below.

## Design

### Naming + state model

- **Worktree dir:** `aiwork/t<parent>` (bare id — collision-free: per-task dirs are always `t<id>_<slug>`).
- **Branch:** `aifamily/t<parent>` — a separate ref namespace, deviating from the task file's illustrative `aitask/t<root>_family`. Rationale: the Re-entry reuse guard and crash-recovery survey pattern-match `refs/heads/aitask/<task_name>`; a distinct namespace keeps family branches invisible to per-task guards *by construction* (no fragile exclusion rules) and avoids collision with a parent slugged `family`. Base branch is always `main` in v1 (profile `base_branch` does not apply; documented).
- **Frontmatter:** `family_worktree: true` (boolean scalar, parent task only, absent = false). Editable via `aitask_update.sh --family-worktree`. Merge rule: newer-`updated_at`-wins scalar (the `anchor` precedent); fold: scalar no-op. Child discovery is structural: child id `<parent>_<n>` → parent file → field read, encapsulated in the helper's `status` verb.
- **No new lifecycle state:** worktree/branch existence on disk is the session state; the parent's `children_to_implement` is the membership counter; `aitask_archive.sh`'s existing `PARENT_ARCHIVED:` output line is the "family complete" trigger.

### New helper: `.aitask-scripts/aitask_family_worktree.sh`

Framework-style: `set -euo pipefail`, `KEY:value` stdout, exit 0 = success / 1 = usage-infra / 2 = guarded refusal with `BLOCKED:<reason>`. Verbs:

- `status <task_id>` — `FAMILY_MODE / PARENT / BRANCH / DIR / EXISTS / BRANCH_EXISTS / REMAINING_CHILDREN / REMAINING_LIST / AHEAD / BEHIND / DIRTY`, plus one `ACTIVE_SIBLING:<id>:<hostname>` line per *other* child of the family that currently holds a task lock or is `Implementing` (read via `aitask_lock.sh --check` + sibling frontmatter). Always exit 0; the single resolver skills call.
- `ensure <task_id> [--force]` — create-or-reuse: `REUSED:` / `REATTACHED:` (branch survived a lost worktree) / `CREATED:` (`git worktree add -b aifamily/t<N> aiwork/t<N> main`). Refuses without the frontmatter flag. **Hard concurrency guard (v1):** refuses with `BLOCKED:active_sibling:<id>:<hostname>` when another sibling holds a lock or is `Implementing` — a shared family worktree serializes child implementation by construction; the guard covers same-host *and* cross-host siblings (locks carry hostname). `--force` overrides after explicit user confirmation (e.g. a dead sibling session already handled by crash recovery).
- `sync-from-main <task_id> [--keep-conflicts]` — merge main into the family branch. `UP_TO_DATE` / `SYNCED:<hash>`; on conflict, default **aborts fail-closed** (`CONFLICTS:<n>` + `CONFLICT_FILE:` lines, exit 2); `--keep-conflicts` leaves the merge in progress for agent-assisted resolution.
- `diff-summary <task_id>` — `git diff --name-status --no-renames main...aifamily/t<N>` → `DIFF:<A|M|D>:<path>` lines + `TOTAL:`. The eligibility input.
- `sync-paths <task_id> -- <path>...` — the partial sync. **Mechanics: per-path checkout onto main + one plain commit** (`A`/`M` → `git checkout aifamily/t<N> -- <path>`; `D` → `git rm -r`), NOT `merge --no-commit` + restore. The merge-commit variant is silently lossy: a partial merge advances the merge base past the ineligible changes, so the final merge drops them without a conflict. Checkout-sync leaves the base at the fork/last-sync point; synced paths become content-identical on both sides and auto-resolve at the final merge; repeated partial syncs compose. Guards (exit 2): root on `main` + clean, no wedged merge state, family worktree clean, each path present in the diff (else `SKIPPED:<path>:not_in_diff`). Output `SYNCED_PATH:` lines + `COMMIT:<hash>`. Workflow prose mandates an immediate `sync-from-main` afterwards — the two halves of divergence control.
- `undo-sync <task_id> <commit>` — fail-closed rollback of a just-made partial-sync commit after a failed main-side verification: if `<commit>` is `HEAD` on main and unpushed → `git reset --hard HEAD~1` (`ROLLED_BACK:<hash>`); if HEAD has moved or the commit is on the remote → `git revert --no-edit <commit>` (`REVERTED:<hash>`); refuses on dirty/wedged state.
- `final-merge <task_id> [--force]` — refuses while children remain; `git merge --no-ff aifamily/t<N>` → `MERGED:` / `UP_TO_DATE` (fully-synced happy path); conflicts as in sync-from-main.
- `teardown <task_id> [--force]` — refuses while children remain or commits are unreachable from main (`BLOCKED:unmerged_commits:<n>`); then worktree remove + `branch -d`.
- `list` — audit verb: enumerate all existing `aifamily/*` branches with `FAMILY:<branch>:<ahead>:<worktree_attached>` lines (discoverability of leftover family branches).

Whitelisted at all 5 permission touchpoints (`.claude/settings.local.json`, `.codex/rules/default.rules`, 3 seed mirrors). No `ait` dispatcher entry (skill-facing helper).

### Skill-prose changes (authoring sources under `.claude/skills/task-workflow/`)

- **New `family-sync.md`** (Jinja-free, like task-abort.md): the reusable targeted-sync procedure. Per-child mode:
  1. `diff-summary` → propose eligible vs held-back paths. **Default is hold-back**: a path is only proposed when the agent judges the subset self-contained (no imports/references/schema coupling into held-back paths — candidate source: the child's plan file-list + archived sibling plans; anything entangled with pending sibling work stays behind). Plan lists are a heuristic, not proof — the proof is step 3.
  2. **NON-SKIPPABLE** approval AskUserQuestion (same banner framing as Step 9's merge gate; "sync nothing this round" is a valid answer — the *evaluation* is required, syncing is not).
  3. `sync-paths` → **main-side verification of the synced subset**: run the configured `verify_build` commands (or the task's build gate) against main at the sync commit, in the root checkout. The sync is **not complete until this passes**. On failure → `undo-sync` (fail-closed rollback), re-classify the offending paths as held-back, and report; the child's completion is unaffected (its work stays on the family branch).
  4. Only after a verified sync (or a "sync nothing" round): mandatory `sync-from-main`.

  Final mode: NON-SKIPPABLE residual-diff approval → `final-merge` → main-side verification (as above), then **return** — the sub-procedure does NOT tear down. **Ordering is single-sourced in SKILL.md Step 9:** final-merge + verification (this procedure) → `aitask_archive.sh` (child archives, parent auto-archives) → `teardown` (Step 9 calls it last; its unmerged-commits refusal is a no-op safeguard at that point). Plus a Recovery section for deferred/conflicted final merges (web-merge precedent), with `list` as the audit entry point.
- **SKILL.md Step 5** (profile-invariant block before the `create_worktree` Jinja gate at ~248): for child tasks run `status`; if `FAMILY_MODE:true` → `ensure` + `sync-from-main`, work in `DIR`, set `family_mode=true`, skip the per-task worktree logic entirely. The explicit `family_worktree: true` opt-in **overrides** a `create_worktree: false` profile (stated in prose). **On `BLOCKED:active_sibling:<id>:<hostname>`** the pick does not proceed silently: AskUserQuestion — "Sibling t<id> is active (<hostname>). Wait / pick a different task" or, when the sibling's lock is provably stale (dead PID / crash-recovered), "Force and continue" (re-runs `ensure --force`). This is the hard serialization gate; `DIRTY:true` remains only a secondary warning for leftover uncommitted state.
- **SKILL.md Re-entry Routing** (~236): family children reuse via `status`/`ensure` instead of the `refs/heads/aitask/<task_name>` match; no `sync-from-main` when resuming `IMPLEMENT` with uncommitted work.
- **SKILL.md Step 9** (~561–646): split "If a separate branch was created" into family-child vs per-task branches. Family child, in order:
  1. Verify all work committed on the family branch; run the child's own gates / build verification (`./ait gates run` or legacy `verify_build`) **inside the family worktree** — this validates the child's work in its real (family) context, *before* anything touches main.
  2. **Family-sync per-child mode** (replaces the per-task merge approval; `merge_approved` recorded with `scope=partial_sync`) — includes the main-side verification + rollback contract above, so main is never left in an unverified state.
  3. **Last-child detection happens *before* archival**: `status` → if `REMAINING_LIST` is exactly this child, this is the final child → run **family-sync final mode now** (NON-SKIPPABLE approval → `final-merge` → main-side verification; the sub-procedure returns without tearing down). Only after a successful, verified final merge, Step 9 continues — canonical order: **final-merge + verification → `aitask_archive.sh` (child archives, parent auto-archives) → `teardown`** (last; its unmerged-commits refusal is a no-op safeguard here). If the final merge conflicts or the user defers it, do **not** archive — the child stays `Implementing`/in-flight and re-enterable (existing Check 5 / `inflight` resume model), so an archived-Done family with stranded unmerged code is impossible by construction. Non-final children: **skip per-task teardown**, then `aitask_archive.sh` as today.
  This preserves the pinned merge-independent archival for non-final children ("done = on family branch"); the final child is the one whose completion *is* the family completion, so its archival follows the successful family merge — same ordering as today's per-task Step 9.
- **Archive-side durable guard (`aitask_archive.sh`)** — the normal flow above makes "Done but unmerged" impossible, but abnormal archival paths bypass Step 9's family logic (Step 3 Check 1/2/4 backstops, `--ignore-gates`, board-driven archival). Cover them at the shared sink: when archiving a task whose family branch `aifamily/t<N>` exists with commits unreachable from main, `aitask_archive.sh` emits a structured `FAMILY_UNMERGED:<branch>:<ahead>` output line (archival itself proceeds — it must stay merge-independent). Workflow prose parses the line wherever archive output is parsed and routes to family-sync.md's Recovery section: offer "run final merge now" or **create an explicit recovery task** (`aitask_create.sh --batch`, e.g. `merge_family_branch_t<N>`) so the unmerged branch is a visible, pickable task rather than tribal knowledge. The helper's `list` verb plus `teardown`'s unmerged-commits refusal are the audit backstops.
- **task-abort.md** (~41–47): family-aware — never remove the shared worktree/branch; if `DIRTY:true`, ask discard-vs-keep for the aborted child's uncommitted changes; note that committed work stays on the family branch and resurfaces at the next sync evaluation.
- **crash-recovery.md** (~29–35): survey the family worktree (`status` → `DIR`) for family children; read-only as today.
- **planning.md**: child-creation checkpoint gains the family opt-in AskUserQuestion (writes `--family-worktree true` on the parent, folded into the existing parent data commit); plan metadata headers gain the family-child variant (`Worktree: aiwork/t<parent>` / `Branch: aifamily/t<parent>` / `Family worktree: shared`).
- **`aitask_plan_externalize.sh`** (~304): child-pattern + `aiwork/t<p>` dir existence → emit family header lines.

### Docs / schema surface

`profiles.md` `create_worktree` row + example (family override note); `profile_editor.py` help text; frontmatter layer-5 doc surfaces per the extension-points checklist (seed instructions + AGENTS.md regen, `.codex`/`.opencode` mirrors by hand, CLAUDE.md task-format block, website task-format table, `task-creation-batch.md` canonical contract, `aitask-create/SKILL.md` flag list, the checklist itself); website `parallel-development.md`, `aitask-pick/_index.md`, crash-recovery workflow doc. Claude tree first; follow-up port tasks for Codex CLI / OpenCode.

### Tests

- `tests/test_family_worktree.sh` — happy paths: status, ensure create/reuse/reattach, diff-summary A/M/D, sync-paths incl. deletion propagation, final-merge, `UP_TO_DATE` after full partial sync, teardown.
- `tests/test_family_worktree_guards.sh` — negative controls: teardown/final-merge refuse with children remaining; teardown refuses on unmerged commits; sync-paths refuses on dirty/non-main root, wedged state, dirty family tree; `SKIPPED:` paths; ensure refuses without flag; **ensure refuses with an active sibling lock (`BLOCKED:active_sibling`, same-host and cross-host fixtures) and `--force` overrides**; `undo-sync` reset-vs-revert branches and refusal on dirty/wedged state.
- `tests/test_family_worktree_divergence.sh` — conflict abort leaves clean tree; repeated partial syncs then clean final merge; main-side edit of a synced path + family edit → conflict *surfaced* (regression pin against the silent-loss class).
- Frontmatter/merge tests (`--family-worktree` update case, `aitask_merge` newer-wins case); `test_plan_externalize.sh` family-header case.
- Goldens: regenerate `tests/golden/procs/task-workflow/SKILL-{default,fast,remote}.md` + `planning-{default,fast,remote}.md`; `aitask_skill_rerender.sh` per profile incl. committed `task-workflow-remote-` closure; `test_skill_render_task_workflow.sh` must pass.

## Child decomposition (6 children)

1. **t1166_1 — family-worktree helper script + sync mechanics (spike-first).** All verbs of `aitask_family_worktree.sh` (incl. `undo-sync` rollback, `list` audit, and the `status`/`ensure` **active-sibling hard concurrency guard**), checkout+`git rm` partial-sync mechanics, guards, the 3 unit-test files, 5-touchpoint whitelist. Independently testable; if the mechanics falsify the checkout approach, downstream re-plans. No skill edits. **Blocking edge:** sibling auto-dependency makes t1166_3/4 depend on this child — the sync model must be proven before any workflow prose consumes it.
2. **t1166_2 — `family_worktree` frontmatter field.** Full extension-points checklist: create/update flags, fold scalar no-op, merge rule, `task_yaml` normalization, all layer-5 doc surfaces; frontmatter + merge tests. Board widget ships separately (anchor precedent). Parallel with c1.
3. **t1166_3 — task-workflow main path** (deps: 1, 2). `family-sync.md` (incl. main-side verification + `undo-sync` contract), Step 5 block with the `BLOCKED:active_sibling` refusal flow, Step 9 restructure with last-child-detection-before-archival, Re-entry Routing, planning.md checkpoint question + plan headers; golden regeneration + rerender; runs `test_skill_render_task_workflow.sh` + `aitask_skill_verify.sh` in-task.
4. **t1166_4 — failure/recovery surfaces** (deps: 1, 2). task-abort.md, crash-recovery.md, `aitask_plan_externalize.sh` + test; the `aitask_archive.sh` `FAMILY_UNMERGED:` durable guard + its workflow-side routing (recovery-task creation) + archive test; goldens touched by these files.
5. **t1166_5 — docs + profile surface** (deps: 3, 4). profiles.md, profile_editor.py help, website pages, Codex/OpenCode port-task creation.
6. **t1166_6 — manual-verification sibling** (deps: all; created via `aitask_create_manual_verification.sh` seeder). End-to-end on a scratch repo: 2-child family, partial sync each child (incl. a failed main-side verification → rollback round), concurrency refusal when a sibling lock is active, mid-family abort (worktree survives), crash-resume into family worktree, final merge + teardown, `FAMILY_UNMERGED:` recovery path. Doubles as the retrospective that decides whether the hunk-level / anchor-group follow-ups are justified (Deferred follow-ups table).

## Verification

- `bash tests/test_family_worktree*.sh` (all three), extended frontmatter/merge/externalize tests, `bash tests/test_skill_render_task_workflow.sh`, `./.aitask-scripts/aitask_skill_verify.sh`, `shellcheck .aitask-scripts/aitask_family_worktree.sh`.
- End-to-end behavior is covered by the t1166_6 manual-verification checklist.
- Step 9 (Post-Implementation) of the task workflow handles per-child cleanup, archival, and merge per the standard procedure.

## Known limitations (v1, documented)

- Multi-machine families: the family branch/worktree is local. The hard concurrency guard refuses a pick while a sibling is locked on another host, so silent divergence can't happen — but *sequential* cross-host picks still start a fresh family worktree from main (only partially-synced work propagates). Documented limitation.
- Concurrent sibling implementation is **refused** (hard guard, `BLOCKED:active_sibling`), not merely warned; `DIRTY:true` is a secondary leftover-state warning.
- Path-level granularity only; long-held ineligible paths re-surface at every per-child evaluation by design.

## Deferred follow-ups (explicit dispositions)

| Exclusion | Disposition |
|---|---|
| Hunk-level selective sync | Task created **only if t1166_6's retrospective recommends it** (evidence that path-level was too coarse) |
| Anchor-group families (follow-up tasks joining the worktree) | Task created **only if t1166_6 recommends it**; v1 documents parent+children scope |
| Full multi-machine support (pushed/remote family branches) | **Documented only** (Known limitations + website docs); hard guard prevents the dangerous case |
| Concurrent sibling implementation (parallel children in one family) | **Documented only** — explicitly out of scope; the v1 hard guard enforces serialization |
| Non-main base branches for family worktrees | **Documented only** (profiles.md limitation note) |
| Codex CLI / OpenCode ports | **Verified in t1166_5, tasks created only if needed**: the task-workflow closure (incl. family-sync.md) auto-renders to the other agent trees; t1166_5 verifies the renders and hand-syncs the `.codex`/`.opencode` instruction mirrors (c2 doc surfaces); separate port tasks are created only if an agent-specific surface actually diverges |
| Board TUI widget for `family_worktree` field | **Documented in t1166_2's task file** (anchor precedent: board layer ships separately) |

## Risk

### Code-health risk: medium
- Partial-sync commits mutate `main` directly from a helper; a mechanics bug could corrupt main or silently drop deferred family changes at final merge · severity: high · → mitigation: t1166_1 (spike-first: sync mechanics + divergence/guard tests land and are proven before any workflow edit — sibling auto-dependency blocks t1166_3/4 on it) + per-sync main-side verification with `undo-sync` fail-closed rollback (family-sync.md step 3)
- Step 5/9 restructure touches the load-bearing merge/teardown prose consumed by every profile; golden/rerender churn across 6+ files risks a stale committed remote closure · severity: medium · → mitigation: t1166_3 verification runs `test_skill_render_task_workflow.sh` + `aitask_skill_verify.sh` (its prerender-freshness check catches a stale committed remote closure) in-task
- New long-lived local state (family branch/worktree) adds crash/abort surfaces that must never be torn down while siblings remain · severity: medium · → mitigation: t1166_1 guard tests (teardown/final-merge refuse with children remaining; negative controls) + t1166_4 abort/crash prose + t1166_6 manual verification of the mid-family abort path

### Goal-achievement risk: medium
- Path-level granularity may prove too coarse for real families (entangled files can never partially sync), undercutting the divergence-control goal · severity: medium · → mitigation: t1166_6 retrospective (files hunk-level follow-up only if justified)
- Multi-machine family workflows degrade (fresh worktree from main on a second host for *sequential* cross-host picks) — the feature's value is bounded to single-host families in v1 · severity: medium · → mitigation: v1 hard concurrency guard in t1166_1 (`BLOCKED:active_sibling` covers cross-host via lock hostnames) + documented limitation

### Planned mitigations
- (none as separate tasks) — the previously confirmed `family_crosshost_lock_warning` after-mitigation was **promoted into v1 scope**: the t1166_1 hard concurrency guard refuses on active sibling locks, same-host and cross-host, which subsumes the warning. No separate mitigation task is created.
