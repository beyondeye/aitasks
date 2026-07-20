---
Task: t1166_3_task_workflow_family_mode_main_path.md
Parent Task: aitasks/t1166_shared_worktree_for_child_task_families.md
Sibling Tasks: aitasks/t1166/t1166_1_family_worktree_helper_script.md, aitasks/t1166/t1166_2_family_worktree_frontmatter_field.md, aitasks/t1166/t1166_4_family_failure_recovery_surfaces.md, aitasks/t1166/t1166_5_family_worktree_docs_and_profile_surface.md
Base branch: main
---

# Plan: t1166_3 — task-workflow family-mode main path

## Context

Wires the proven helper (t1166_1) and field (t1166_2) into the task-workflow skill. All edits in the **authoring sources** `.claude/skills/task-workflow/` — rendered dirs regenerate. Family blocks are **profile-invariant plain markdown** placed outside Jinja gates. Read `aidocs/framework/skill_authoring_conventions.md` first; before starting, re-read the CURRENT SKILL.md/planning.md (line anchors below are from planning time and main advances — verify each insertion point against live source).

Canonical ordering (single-sourced here, in Step 9): per-child gates in family worktree → family-sync per-child (sync + main-side verification) → [last child only: family-sync final (merge + verification)] → `aitask_archive.sh` → `teardown` last.

## Steps

1. **Create `.claude/skills/task-workflow/family-sync.md`** (Jinja-free). Structure:
   - Inputs table: `task_id`, `parent_id`, `mode` (`per-child` | `final`).
   - **Per-child mode:** (a) run `./.aitask-scripts/aitask_family_worktree.sh diff-summary <task_id>`; build the proposal — **default hold-back**: propose a path only when the synced subset is self-contained on main (no imports/references/schema coupling into held-back paths); candidate sources: the child's plan file-list + archived sibling plans (`aiplans/archived/p<parent>/`); anything entangled with pending sibling work stays behind; plan lists are heuristic — the proof is step (c). (b) NON-SKIPPABLE AskUserQuestion (copy Step 9's merge-gate warning framing: profiles/auto-mode do NOT bypass); present proposed vs held-back path lists; "Sync nothing this round" is a valid option (the evaluation is the required stage, not the sync). (c) on approval: `sync-paths <task_id> -- <paths…>`, parse `COMMIT:<hash>`, then **main-side verification**: run the configured `verify_build` commands (`aitasks/metadata/project_config.yaml`) — or the task's build gate — against main in the root checkout; the sync is complete ONLY when this passes; on failure run `undo-sync <task_id> <hash>`, mark the offending paths held-back, report to the user (child completion unaffected — work remains on the family branch). (d) after a verified sync or a sync-nothing round: mandatory `sync-from-main <task_id>` (on `CONFLICTS` exit-2, rerun `--keep-conflicts` and resolve with the user).
   - **Final mode:** show residual `diff-summary`; NON-SKIPPABLE approval; `final-merge <task_id>`; main-side verification as above (rollback of a bad final merge: `git reset --hard ORIG_HEAD` only when unpushed, else surface to user); then **return — no teardown here** (Step 9 owns the ordering).
   - **Recovery section:** deferred/conflicted final merges — `list` to find leftover `aifamily/*` branches, re-run `final-merge`/`teardown`; entry point for t1166_4's `FAMILY_UNMERGED:` routing.
2. **SKILL.md Step 5**: insert the family block immediately after the Step 5 heading/notes, BEFORE the `{% if profile.create_worktree is defined %}` gate: child task → `status <task_id>`; `FAMILY_MODE:true` → display banner, handle `BLOCKED:active_sibling:<id>:<hostname>` from `ensure` with AskUserQuestion ("Wait / pick a different task / Force and continue" — force only when the sibling lock is provably stale), then `ensure` + `sync-from-main`, work in `DIR`, set `family_mode=true`, and skip the per-task worktree logic (state: the parent's `family_worktree: true` **overrides** `create_worktree: false` profiles). `DIRTY:true` at pick → secondary warning about leftover uncommitted state. Non-family falls through unchanged.
3. **SKILL.md Re-entry Routing** (the "Environment setup (Step 5) with reuse" bullet): family children reuse via `status`/`ensure` instead of the `refs/heads/aitask/<task_name>` porcelain match; do NOT `sync-from-main` when `resume_point=IMPLEMENT` and the family worktree has uncommitted work.
4. **SKILL.md Step 9**: restructure "If a separate branch was created" into two branches. Family child (`family_mode=true`), in the canonical order above; last-child detection: `status` → `REMAINING_LIST` equals exactly this child. Record `merge_approved` (existing record_gates-gated call) at the per-child sync approval with `fields="type=human scope=partial_sync"`, and again at the final-merge approval (plain `type=human`). On final-merge conflict/deferral: do NOT archive; the child stays `Implementing` (Check 5 resume model). Non-final children skip teardown and archive as today. Per-task branch: unchanged.
5. **planning.md**: (a) child-creation checkpoint — after batch child creation, AskUserQuestion "Should these children share one long-lived family worktree with per-child selective sync to main?" (No, independent per-child worktrees (default) / Yes, shared family worktree); on Yes run `./.aitask-scripts/aitask_update.sh --batch <parent> --family-worktree true` before the parent-status-revert commit so it rides the same data commit. (b) plan metadata headers: add the family-child variant (`Worktree: aiwork/t<parent>` / `Branch: aifamily/t<parent>` / `Base branch: main` / `Family worktree: shared`).
6. **Goldens + rerender**: regenerate `tests/golden/procs/task-workflow/SKILL-{default,fast,remote}.md` and `planning-{default,fast,remote}.md` (`.aitask-scripts/lib/skill_template.py <file> aitasks/metadata/profiles/<profile>.yaml claude > <golden>`); run `.aitask-scripts/aitask_skill_rerender.sh <profile>` for default/fast/remote (refreshes rendered dirs incl. codex/opencode + the committed `task-workflow-remote-` closure). Same commit as the source edits.

## Verification

- `bash tests/test_skill_render_task_workflow.sh` (byte-equality, agent-invariance, verbatim fall-through blocks)
- `./.aitask-scripts/aitask_skill_verify.sh` (closure walk + prerender freshness)
- `grep -rl family-sync .claude/skills/task-workflow-*/ .agents/skills/ .opencode/skills/` — family-sync.md present in every rendered closure
- Manual read-through of rendered fast variant: Step 5 family block appears before the profile-resolved worktree text; Step 9 family branch complete.
