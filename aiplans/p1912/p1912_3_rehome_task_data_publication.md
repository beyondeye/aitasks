---
Task: t1912_3_rehome_task_data_publication.md
Parent Task: aitasks/t1912_move_codeagent_stats_to_plumbing_branch.md
Sibling Tasks: aitasks/t1912/t1912_*_*.md
Archived Sibling Plans: aiplans/archived/p1912/p1912_*_*.md
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5_5 @ 2026-11-15 19:37
---

# t1912_3 — Re-home task-data publication (plan, verified 2026-11-15)

## Context

`lib/verified_update_lib.sh` converges `.aitask-data` with origin before and
after every stats write (`converge_current_repo_with_remote`, L140/L247/L306).
That converge also **pushes** any unpushed local task-data commits. Satisfaction
Feedback Step 0 (the usage bump) runs at the end of most sessions, so several
session-ending steps publish their task-data commits only through that side
effect. t1912_4 removes the converge. This child adds an explicit best-effort
`./ait git push` at each step that relies on it **before** that removal lands.

Scope is the steps that (a) commit task data, (b) have no push of their own
before they close, and (c) call Satisfaction Feedback. Steps that never called
the stats writer never relied on the converge and are out of scope (listed
under "Not in scope" for t2288 to classify).

## Verified inventory (re-derived by grep, 2026-11-15)

Swept every non-rendered source under `.claude/skills/**` and
`.aitask-scripts/skill_templates/` for `satisfaction` / `aitask_usage_update` /
`feedback_skill_name=`, then read each caller's commit and push sites. The only
stats writers are `aitask_usage_update.sh` and `aitask_verified_update.sh`, both
reached only through `satisfaction-feedback.md`.

| # | Site (source file) | Unpushed task-data commits it carries | Change |
|---|---|---|---|
| A | `task-workflow/SKILL.md` Step 9 gate guard "Defer — keep in-flight" (skips the L1211 push, goes to 9b) | Step 8 plan commit; manual-verification state commit | push |
| B | `task-workflow/planning.md` child checkpoint "Stop here" | child task files, child plans, manual-verification sibling | push |
| C | `task-workflow/cross-repo-child-assignment.md` Step 7 "Stop here" | local children/plans (repo B pushes itself) | push |
| D | `.aitask-scripts/skill_templates/_auto_continue_block.j2` "Save for later" (explore, **revert** pass `feedback_skill_name`) | the created task; revert's annotation/deletion commits | push |
| E | `aitask-qa/SKILL.md.j2` Step 7 | Step 6 follow-up task | push |
| F | `aitask-docs-gap/SKILL.md` Step 6 → 7 | doc task (`aitask_create.sh --commit`) | push |
| G | `aitask-add-model/SKILL.md` Step 6 → 7 | `models_<agent>.json` (+ `codeagent_config.json`) | push |
| H | `aitask-refresh-code-models/SKILL.md` Step 8 → 9 | `models_*.json` | push |

Changes against the task's table: **added aitask-revert** (it reaches the
Satisfaction Feedback call through the shared macro's `feedback_skill_name`, so
a grep for `satisfaction` in its own file misses it). The macro's push is
unconditional, so aitask-fold and aitask-pr-import "Save for later" also get it.
They never called feedback, but they commit a task and stop the same way, so
one macro shape is simpler and covers them too.

Checked, no change needed: aitask-wrap and aitask-web-merge (push before
feedback); aitask-changelog, aitask-explain, aitask-reviewguide-* (main-branch
commits only; the converge never pushed `main`); aitask-work-report (no
commits); aitask-pickrem and aitask-pickweb (no feedback call); normal Step 9
archival (L1211 push). Codex and OpenCode: `.agents/skills/<skill>/` and
`.opencode/skills/<skill>/` are wrappers pointing at the Claude sources, and the
profile variants are rendered from the same sources. **No port tasks are
needed**, only a rerender.

## Decision: a failed L1211 push (the second-attempt case)

No change. The `## Complete` banner already reports `pushed: no`. The next
`./ait git push` from any step (the claim in `aitask_pick_own.sh`, a gate record,
a note) publishes the commit. A second automatic attempt would only repeat the
same retry loop `task_push` already ran three times.

## Implementation steps

1. **New shared procedure `.claude/skills/task-workflow/task-data-push.md`**
   (plain markdown, no Jinja, so it is profile-invariant and needs no golden;
   modelled on `workflow-end.md`). Contents:
   - Purpose: one best-effort push of this run's committed task data, run by a
     session-closing step after its last task-data commit, because no later
     step pushes for it. List the referencing sites (A–H).
   - Command: `./ait git push --batch` (`task_git_push` → `task_push_report`,
     `lib/task_utils.sh` ~L665 / ~L1621).
   - Parse the last stdout line:
     - `PUSHED`, `NOTHING`, `NO_REMOTE` → `task_data_pushed = yes` (nothing is
       left unpublished). Display nothing for `NOTHING` and `NO_REMOTE`.
     - `FAILED:<reason>:<n>` → `task_data_pushed = no`. Warn: "Task data not
       pushed (`<reason>`, `<n>` unpushed commit(s)) — run `./ait git push` to
       publish it."
     - Non-zero exit, or no recognised line (for example a refused push while
       the data worktree is mid-rebase) → `no`. Warn the same way, using
       stderr's first line as the reason.
   - Never retry and never stop the calling step. A failed push changes only
     the warning and the caller's banner text.
   - Caller contract: run it after the last task-data commit and **before**
     Satisfaction Feedback. At a `## Stopped` banner exit, when
     `task_data_pushed = no`, start the banner's `next` with
     "`./ait git push` (task data not pushed), then ". The banner grammar is
     unchanged, so the sitrep harvest (`lib/sitrep_harvest.py`, free-text
     `next`) is unaffected.
   - Word it so it contains no exit phrase (`end(s) the workflow/session`,
     `then stop`, `Abort.`). `tests/test_workflow_end_banner_contract.sh`
     Guard 1 scans every `task-workflow/*.md` with that regex.
2. **Site A — `task-workflow/SKILL.md`:**
   - Step 9 Defer branch: replace "Skip the push-after-archival step and
     proceed directly to **Step 9b**" with: skip the archival push, execute
     the **Task-Data Push Procedure** (`task-data-push.md`), because the
     Step 8 / verification commits are otherwise still local, then Step 9b,
     then Step 10.
   - Step 10 Defer bullet: add the `next` prefix rule when
     `task_data_pushed = no`.
   - Step 6 summary (~L484, child "Stop here"): "execute the Task-Data Push
     Procedure, then the Satisfaction Feedback Procedure, then the Stopped
     banner".
   - Procedures list: add an entry for `task-data-push.md`.
3. **Site B — `task-workflow/planning.md` child checkpoint "Stop here"**
   (~L378): insert the push before the Satisfaction Feedback call. Add the
   `next` prefix rule to the Stopped banner sentence. Keep the reference to
   `workflow-end.md` and `outcome=split` in the same list item (Guard 1).
4. **Site C — `cross-repo-child-assignment.md` Step 7 "Stop here":** same
   edit as Site B. Note that repo B's commits are pushed by its own
   `--commit` and this push covers only the local repository.
5. **Site D — `_auto_continue_block.j2`:** in the "Save for later" branch,
   insert "Execute the **Task-Data Push Procedure** (see
   `.claude/skills/task-workflow/task-data-push.md`)" after the Inform-user
   line, unconditionally and before the optional feedback line. Update the
   header comment: the Save-for-later branch always pushes.
6. **Site E — `aitask-qa/SKILL.md.j2` Step 7:** push first, then feedback.
   Add the procedure to the Procedures list.
7. **Sites F, G, H** (`aitask-docs-gap` Step 7, `aitask-add-model` Step 7,
   `aitask-refresh-code-models` Step 9): one line before the feedback call:
   "First execute the **Task-Data Push Procedure** (see
   `.claude/skills/task-workflow/task-data-push.md`). The commit above is
   otherwise still local."
8. **Rerender and goldens (same commit as the edits):**
   - `./.aitask-scripts/aitask_skill_rerender.sh` (all agents and profiles).
   - Regenerate the procedure goldens `tests/golden/procs/task-workflow/`
     `SKILL-{default,fast,remote}.md`, `planning-{default,fast,remote}.md` and
     `cross-repo-child-assignment-default.md`. Use the render loop in
     `tests/test_skill_render_task_workflow.sh`.
   - Regenerate the skill goldens `tests/golden/skills/{aitask-explore,aitask-fold,aitask-pr-import,aitask-revert,aitask-qa}/SKILL-{default,fast,remote}-claude.md`.
     Use the loop in `aidocs/framework/skill_authoring_conventions.md`
     "Regenerate goldens…".
   - Review each golden diff. It must contain only the inserted lines.
9. Commit the code (skill sources, the new procedure, goldens) on `main`:
   `enhancement: Re-home task-data publication to explicit pushes (t1912_3)`.

## Not in scope (for t2288's classification)

These steps commit task data and stop without a push, but never called the
stats writer, so they never relied on the converge:
- the manual-verification "Stop without archiving" and pause exits (verify
  whether their item-state writes are committed);
- the Task Abort Procedure;
- plan-approved-stop (already pushes).

t2288's discovery tripwire must classify them (pinned or exempt).

## Verification

- `./.aitask-scripts/aitask_skill_verify.sh` is clean.
- `bash tests/test_skill_render_task_workflow.sh` passes, and so do
  `test_skill_render_aitask_{explore,fold,pr_import,revert,qa}.sh`,
  `test_skill_render_uniform.sh` and `test_workflow_end_banner_contract.sh`.
- `bash tests/test_ait_git_gateway_pull.sh` passes. It pins the `push --batch`
  line grammar the procedure parses.
- Grep the rendered fast, default and remote variants under
  `.claude/skills/*-{fast,default,remote}-/` (and one `-codex-` variant) for
  `task-data-push.md` at each site A–H. Confirm `task-data-push.md` is present
  in each `task-workflow-*-/` render.
- `shellcheck` is not affected (no shell scripts change).

## Risk

### Code-health risk: low
- The new `task-workflow/*.md` file and the edited exit blocks are scanned by
  the banner-contract test (Guard 1). An exit phrase in the new procedure, or
  a moved banner reference, would fail it · severity: low · → mitigation: none
  (the procedure is worded without exit phrases, and Verification runs that
  test)
- The golden churn spans 5 skills and 3 procedures. An unrelated render shift
  could hide inside it · severity: low · → mitigation: none (step 8 reviews
  every golden diff for insert-only content)

### Goal-achievement risk: medium
- The publication inventory comes from grep. A missed path, or a new stop exit
  added later, would silently stop publishing task data once t1912_4 removes
  the converge · severity: medium · → mitigation: t2288 (an existing 'after'
  task from the parent plan: a pinned-inventory guard with a discovery
  tripwire)

No new mitigations are proposed. The one material risk already has its
mitigation task (t2288, which depends on this child).

## Step 9

Post-Implementation per task-workflow: commit, then archive the child.

## Post-Review Changes

### Change Request 1 (2026-11-15 22:37)
- **Requested by user:** the new add-model / refresh-code-models lines said the
  main-branch commits "are not pushed here". That is false in legacy mode,
  where task data and code share the current branch and `./ait git push`
  publishes the seed commits too (confirmed against a temporary legacy repo
  with a bare remote). Qualify the promise and keep the legacy upload behaviour.
- **Changes made:** both lines now say "In separate-branch mode the main-branch
  … commits are not pushed here. In legacy mode they share the current branch
  with the task data, so this push publishes them too." No behaviour change.
- **Files affected:** `.claude/skills/aitask-add-model/SKILL.md`,
  `.claude/skills/aitask-refresh-code-models/SKILL.md` (no goldens; skill verify
  re-run clean).

## Final Implementation Notes
- **Actual work done:** implemented as planned. New plain-markdown procedure
  `.claude/skills/task-workflow/task-data-push.md`: `./ait git push --batch`,
  last-stdout-line parse (`PUSHED` / `NOTHING` / `NO_REMOTE` → `yes`;
  `FAILED:<reason>:<n>`, a non-zero exit or no recognised line → `no` plus a
  warning), never retried, and never changes the caller's control flow. At a
  `## Stopped` exit, `task_data_pushed = no` prefixes the banner's `next` with
  "`./ait git push` (task data not pushed), then ". It is wired into all 8
  sites: A) `SKILL.md` Step 9 Defer (plus the Step 10 Defer bullet, the Step 6
  child-stop summary and the Procedures list); B) `planning.md` child "Stop
  here"; C) `cross-repo-child-assignment.md` Step 7 "Stop here"; D)
  `_auto_continue_block.j2` "Save for later", unconditional (explore, revert,
  fold, pr-import); E) aitask-qa Step 7 (plus its Procedures list); F)
  docs-gap Step 7; G) add-model Step 7; H) refresh-code-models Step 9.
  Regenerated 22 goldens: procs/task-workflow `SKILL-*`, `planning-*`,
  `cross-repo-child-assignment-default`; skills explore / fold / pr-import /
  revert / qa × 3 profiles. Rerendered every profile and agent tree.
- **Deviations from plan:** the macro line reads "This run's task commits are
  otherwise still local" rather than "the task-creation commit". aitask-fold
  makes a fold commit, not a task creation, so the generic wording is accurate
  for all four callers. Post-review: the add-model / refresh-code-models lines
  were qualified for legacy mode (Change Request 1).
- **Issues encountered:** none. Every golden diff was insert-only, and only the
  22 predicted goldens changed (verified by rendering every golden first and
  diffing).
- **Key decisions:** a shared procedure rather than 8 inline copies, so the
  parse contract lives in one place, as `workflow-end.md` does for banners, and
  t2288 can pin one token (`task-data-push.md`). The Stopped banner grammar is
  unchanged: a push failure goes into the free-text `next`, so
  `lib/sitrep_harvest.py`'s closed outcome vocabulary is untouched. Decision
  recorded for a failed Step 9 L1211 push: no change (the Complete banner
  reports `pushed: no`).
- **Upstream defects identified:** None
- **Notes for sibling tasks:**
  - **t1912_4** (writer cutover) can now remove
    `converge_current_repo_with_remote` from `lib/verified_update_lib.sh`.
    Every step that relied on its push side effect now calls
    `task-data-push.md` **before** Satisfaction Feedback.
  - Until t1912_4 lands, the converge still runs after these pushes. That is
    harmless: there is nothing left to push.
  - **t2288** (pin_rehomed_push_sites): the pinned site list is the A–H
    inventory above. Pin the token `task-data-push.md` at each site in the
    goldens. The "Not in scope" exits above (manual-verification stops, task
    abort) need classifying by its discovery tripwire. The macro covers fold
    and pr-import as well.
  - `.agents/` / `.opencode/` trees are wrappers or renders of these sources,
    so no port tasks are needed.
