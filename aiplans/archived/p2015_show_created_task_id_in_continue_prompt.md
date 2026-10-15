---
Task: t2015_show_created_task_id_in_continue_prompt.md
Base branch: main
Output branch: main
---

# t2015 — Name the created task in the post-creation "Continue / Save for later" prompt

## Context

After aitask-explore (and its siblings pr-import, revert, review) creates a
task, the decision prompt reads `"Task created successfully. How would you like
to proceed?"` — it does not say *which* task. The user has to scroll back to see
the id they are deciding about, or the one to pass to `/aitask-pick` later. The
id is already known at that point (every skill reads it back with
`./ait git log -1 --name-only … | grep '^aitasks/t'` just before the prompt).
aitask-fold already names it (`"Tasks folded successfully into t\<primary_id\>. …"`);
this task brings the other four in line.

Codex / OpenCode variants of these four skills are rendered on demand from the
same `.claude/skills/<skill>/SKILL.md.j2` and are gitignored (only
pickrem/pickweb/task-workflow remote variants are force-tracked, and none
contains these strings), so one template edit covers every agent — no porting
task needed.

## Escaping (verified)

- Inside a Jinja **string literal** (macro argument), write `t\\<N\\>`; it
  renders as `t\<N\>` — confirmed by
  `tests/golden/skills/aitask-fold/SKILL-*-claude.md:80`
  (`t\<primary_id\>`).
- In **raw template text** (aitask-review is inline, not the macro), write
  `t\<N\>` with a single backslash — Jinja does not process backslashes in raw
  text, so all four renders read byte-identically `Task t\<N\> created successfully.`
- `assert_contains` (`tests/lib/asserts.sh:179`) matches with `grep -qF`, so a
  single-quoted needle containing `t\<N\>` is a literal match (not a GNU
  word-boundary regex).

## Implementation steps

1. **`.claude/skills/aitask-explore/SKILL.md.j2:323`** — macro call:
   `question="Task created successfully. How would you like to proceed?"`
   → `question="Task t\\<N\\> created successfully. How would you like to proceed?"`

2. **`.claude/skills/aitask-pr-import/SKILL.md.j2:259`** — same change as step 1.

3. **`.claude/skills/aitask-revert/SKILL.md.j2:626`** — macro call:
   `question="Revert task created successfully. …"`
   → `question="Revert task t\\<N\\> created successfully. How would you like to proceed?"`

4. **`.claude/skills/aitask-review/SKILL.md.j2`** (inline, Step 5 else-arm):
   - line 243: `Use \`AskUserQuestion\`: "Task created successfully. How would you like to proceed?"`
     → `"Task t\<N\> created successfully. How would you like to proceed?"`
   - line 249: `"Tasks created. How would you like to proceed?"`
     → `"Tasks created under parent t\<parent_N\>. How would you like to proceed?"`
     — `<parent_N>` (not `<N>`) to match the placeholder the same block's
     "Save all for later" option already uses (`/aitask-pick <parent_N>`), so the
     agent substitutes the parent id, not a child's.

5. **`.aitask-scripts/skill_templates/_auto_continue_block.j2`** header comment —
   the `question` parameter doc has no example wording to update, but add one
   line of guidance so future callers stay consistent: name the task the prompt
   is about, e.g. `"Task t\\<N\\> created successfully. …"` (doubled backslashes
   render as `t\<N\>`). Jinja comment → render-neutral (no golden diff from
   this step).

   Not doing the optional "auto-continue display line carries the id" change:
   no committed profile sets `explore_auto_continue`, and the four tests pin the
   `': continuing to implementation` substring as a negative — low value for a
   wider diff.

6. **Tests** — update the pinned needle in each Test 2 `assert_contains`:
   - `tests/test_skill_render_aitask_explore.sh:96` → `'Task t\<N\> created successfully. How would you like to proceed?'`
   - `tests/test_skill_render_aitask_pr_import.sh:92` → same
   - `tests/test_skill_render_aitask_revert.sh:95` → `'Revert task t\<N\> created successfully. How would you like to proceed?'`
   - `tests/test_skill_render_aitask_review.sh:94` → `'Task t\<N\> created successfully. How would you like to proceed?'`
   (The review parent+children string is pinned by the golden, Test 1.)

7. **Regenerate goldens** (same commit as the template edit) for
   `aitask-explore`, `aitask-pr-import`, `aitask-revert`, `aitask-review`, using
   the command in `aidocs/framework/skill_authoring_conventions.md`
   "Regenerate goldens after any `.md.j2` or closure edit":
   ```bash
   PYTHON="$(source .aitask-scripts/lib/python_resolve.sh && require_ait_python)"
   for skill in aitask-explore aitask-pr-import aitask-revert aitask-review; do
     for profile in default fast remote; do
       "$PYTHON" .aitask-scripts/lib/skill_template.py \
         ".claude/skills/$skill/SKILL.md.j2" "aitasks/metadata/profiles/$profile.yaml" claude \
         > "tests/golden/skills/$skill/SKILL-${profile}-claude.md"
     done
   done
   git diff --stat -- tests/golden/skills/
   git diff -- tests/golden/skills/ | grep '^[-+][^-+]'
   ```
   **Audit the diff:** expected exactly one changed line (one −, one +) in each
   of the 9 explore / pr-import / revert goldens, and two changed lines in each
   of the 3 review goldens. Any other hunk is a regression — stop and investigate
   (e.g. a concurrent session's uncommitted template edit leaking into a
   regenerated golden; check `git status` on these templates first — they are
   not in the session-start dirty list).

## Verification

- `./.aitask-scripts/aitask_skill_verify.sh` passes.
- `bash tests/test_skill_render_aitask_explore.sh`,
  `…_pr_import.sh`, `…_revert.sh`, `…_review.sh` all pass (and
  `…_fold.sh` still passes — the macro comment edit is render-neutral).
- Per-profile render check:
  ```bash
  for p in default fast remote; do
    ./.aitask-scripts/aitask_skill_render.sh aitask-explore --profile $p --agent claude
    grep -n 'Question: "Task t\\<N\\> created successfully' .claude/skills/aitask-explore-$p-/SKILL.md
  done
  ```
- Golden diff audited per step 7.

## Step 9 (Post-Implementation)

Current-branch mode (fast profile): no branch/worktree to merge. After the
Step 8 review and commit (`enhancement: … (t2015)`, code files only, by path;
plan via `aitask_task_commit.sh`), Step 9 runs the gate orchestrator and
archives with `./.aitask-scripts/aitask_archive.sh 2015`.

## Risk

### Code-health risk: low
None identified.

### Goal-achievement risk: low
None identified.

## Final Implementation Notes
- **Actual work done:** Implemented steps 1–7 as planned. The four post-creation
  decision prompts now name the created task: explore / pr-import →
  `Task t\<N\> created successfully. …`, revert → `Revert task t\<N\> created
  successfully. …`, review single → `Task t\<N\> created successfully. …`,
  review parent+children → `Tasks created under parent t\<parent_N\>. …`. Added
  a naming + escaping hint to the `question` param doc in
  `_auto_continue_block.j2` (Jinja comment, render-neutral). Updated the four
  Test 2 needles and regenerated the 12 goldens.
- **Deviations from plan:** None.
- **Issues encountered:** The golden-audit filter in the plan
  (`grep '^[-+][^-+]'`) hides the macro-rendered lines, because they start with
  `- Question:` and so appear as `-- …` / `+- …` in the diff. The audit used
  the unfiltered changed lines instead: exactly 15 −/+ pairs across 12 goldens
  (one per explore / pr-import / revert golden, two per review golden), all
  question strings, nothing else.
- **Key decisions:** The review parent+children prompt uses `<parent_N>`, not
  `<N>`, to match the placeholder its own "Save all for later" option already
  uses. The optional id-in-auto-continue-display-line change was not made (no
  committed profile sets `explore_auto_continue`). Codex / OpenCode variants of
  these skills are gitignored renders of the same template, so this change
  covers them without a porting task.
- **Verification:** `aitask_skill_verify.sh` OK (14 templates, 3 agents).
  `test_skill_render_aitask_{explore,pr_import,revert,review,fold}.sh` all
  pass: 128 / 90 / 93 / 96 / 90 tests, 0 failed. Negative control: each new
  needle has 0 matches in the HEAD goldens and 1 in the regenerated ones. A
  per-profile explore render (default / fast / remote) shows the new question.
- **Upstream defects identified:** None
