---
Task: t2370_fix_web_merge_recovery_and_cross_repo_cli_defects.md
Base branch: main
Output branch: main
---

# t2370 — Fix web-merge recovery, pickweb profile order, and cross-repo CLI defects

## Context

The t2258_10 docs audit found 16 places where skills or CLI help say something
the code does not do. The worst three are in `/aitask-web-merge`. After an
archival stop, the run still pushes and deletes the remote branch that the
recommended re-run needs. A re-run then fails at the Step 3d commit, because the
merge is already done ("Already up to date", exit 1). The manual repair text also
leaves out two steps. Because of this, the docs currently say the dependable
finish is a manual one. This task fixes the skills and scripts, then brings the
two web-merge docs pages back in line. One task, implemented directly on `main`
(current-branch profile). The changes are many but each one is small.

User decisions (2026-11-27):
- `ait update --project`: **enforce** the documented allow-list. Today only the
  refusals are enforced.
- Re-rendering `task-workflow-remote-` (3 agents) is approved, **including** the
  uncommitted hunks already in the working tree. They look like the never-committed
  re-render of t1912_3's `task-data-push.md`. Verify they match a fresh render of
  the HEAD templates first (pre-phase below), and stop if they do not.

## Implementation

### Pre-phase (risk mitigations)

1. [verify_render_baseline] **Read-only. Nothing is rendered into the shared
   checkout until this passes.**
   a. Confirm the render *inputs* equal HEAD:
      `git diff --quiet HEAD -- .claude/skills/task-workflow/ .claude/skills/aitask-pickweb/ .claude/skills/aitask-pickrem/`,
      no untracked files under those template dirs
      (`git ls-files --others --exclude-standard <dirs>` empty), and
      `./ait git diff --quiet HEAD -- aitasks/metadata/profiles/remote.yaml`.
      Any input change stops here: the baseline would not be the HEAD render.
   b. For every committed remote prerender entry (`aitask-pickweb`,
      `aitask-pickrem`, and any other `prerender_for_headless: true` template
      whose closure reaches `task-workflow-remote-`) × agent
      (claude/codex/opencode), run
      `python .aitask-scripts/lib/skill_template.py walk-verify <entry SKILL.md.j2> aitasks/metadata/profiles/remote.yaml <agent> <repo_root>`.
      This renders in memory and compares each target in the closure with the
      working-tree file, without writing anything.
   c. Exit 0 for every pair means the uncommitted hunks (including the
      untracked `task-data-push.md`) are exactly what a fresh render writes, so
      re-rendering destroys nothing and the edits can proceed. Any drift or
      missing target means **stop and ask the user**; leave those files alone.
   d. Record each command and its exit status in Final Implementation Notes.

### A. web-merge skill — stop paths and re-run (`.claude/skills/aitask-web-merge/`)

0a. **`SKILL.md` Step 3 (very first) — refuse an open merge.** Run
   `git rev-parse -q --verify MERGE_HEAD >/dev/null`. If it succeeds, a merge
   is already in progress in this checkout, perhaps from an earlier branch or a
   session left at "Resolve manually". Stop this branch **before pulling**:
   "a merge is already in progress (MERGE_HEAD=<sha>) — conclude or
   `git merge --abort` it, then re-run". Never commit it under this task's
   message.
0. **`SKILL.md` Step 3 (first) — refuse a task that is no longer active.**
   Before pulling or merging, resolve the marker's task:
   `aitask_query_files.sh task-file <N>` (parent) or `child-file <p> <c>` (child).
   If that finds nothing, check `aitask_query_files.sh archived-task <id>` and
   `aiplans/archived/`. If any copy is archived, the task is archived or
   mid-archival. Stop this branch **before Step 4**, because Step 4 would write
   the live plan back next to an archived task. Report it, keep the remote
   branch, and point to `./ait git status --short -- aitasks aiplans` (see
   item 4, exit-1 post-move case). Not found anywhere means stop with "task not
   found".
1. **`SKILL.md` Step 3 — skip an already-merged branch.** Add a sub-step between 3a and 3b:
   ```bash
   git merge-base --is-ancestor origin/<branch> HEAD
   ```
   Exit 0 means this branch's code is already on `main` (a re-run after a stop).
   Display "`<branch>` is already merged into main by an earlier run — skipping
   the merge", skip 3b–3d and go to Step 4. Exit 1 means proceed to 3b. Any
   other exit means stop this branch and report the error.
1b. **`SKILL.md` 3b — classify a failed merge before the Conflict prompt.**
   Exit 1 does not always mean the branch is new. After a first run, `main` has
   deleted `.aitask-data-updated/`, so a later repair commit that changes the
   marker or plan on the web branch makes 3b stop with a **modify/delete
   conflict** before the 3c strip. Before running 3b, record
   `branch_tip=$(git rev-parse origin/<branch>)`. When `git merge` exits non-zero:
   ```bash
   merge_head=$(git rev-parse -q --verify MERGE_HEAD || true)
   unmerged=$(git diff --name-only --diff-filter=U)
   ```
   - `merge_head` empty: git refused to start, for example because local
     changes would be overwritten. Show its output and stop this branch.
   - `merge_head` ≠ `branch_tip`: this is not the selected branch's merge (a
     backstop: 0a should have caught it). Stop this branch and commit nothing.
   - `merge_head` = `branch_tip`, `unmerged` **non-empty**, and **every** line
     under `.aitask-data-updated/`: a metadata-only conflict. Display "conflict
     confined to `.aitask-data-updated/` — resolved by the strip step", then
     continue to 3c. Its `git rm -rf .aitask-data-updated/` removes every stage
     for those paths. Then re-check that `git diff --name-only --diff-filter=U`
     is empty before 3d, and stop if it is not.
   - `merge_head` = `branch_tip` with `unmerged` empty: unexpected. Stop and
     show `git status`. This is never the metadata route.
   - `merge_head` = `branch_tip` with any unmerged path outside the metadata
     directory: the existing Conflict prompt (Resolve manually / Abort merge),
     unchanged. After a manual resolution, 3c still strips and resolves any
     metadata conflicts.
   3d's `MERGE_HEAD` backstop also requires `MERGE_HEAD` = `branch_tip`.
2. **`SKILL.md` 3d — backstop.** Before the commit block, add prose saying to
   commit only while a merge is in progress
   (`git rev-parse -q --verify MERGE_HEAD >/dev/null`). With no `MERGE_HEAD`,
   nothing was merged, so skip the commit. Keep the
   `<!-- unscoped-commit-ok: … -->` marker line directly above the `git commit`
   block, as it is now (`tests/test_no_unscoped_task_commit.sh` reads it per line).
3. **`SKILL.md` 4d.** Treat `NOCHANGE` (exit 2) from `aitask_task_commit.sh` as
   "plan already committed by an earlier run — continue".
4. **`SKILL.md` Step 5 — "Archival-stop backstop"** (replaces "Gate-guard
   backstop"). If `aitask_archive.sh` exits non-zero, archival did not happen.
   Do not parse success lines, and **do not run Step 6 for this branch**: no
   push and no `git push origin --delete`, because the remote branch and its
   marker are what a re-run needs. Then go to 6e (next branch / done). Branch on
   the stop line:
   - `GATE_PENDING:<csv>`: keep the current guidance (reviewer passes the gates,
     then re-runs `/aitask-web-merge`; never self-signal a human gate).
   - `VERIFICATION_PENDING` / `VERIFICATION_DEFERRED`: this is a
     manual-verification task whose checklist is not terminal. Finish it locally
     with `/aitask-pick <task_id>`, which runs the checklist, offers the
     carry-over for deferred items, and archives. Then push `main` and the task
     data and delete the web branch; re-running web-merge would find an
     already-archived task.
   - any other **exit 2** (`APPROVAL_PENDING`, …): show the output and stop
     this branch. Every exit-2 guard runs before any write
     (`aitask_archive.sh` `main()` L1202-1204, and the child path's parent
     `approval_guard` L708), so the task is untouched and a re-run is safe.
   - **exit 1**: **never recommend a re-run.** Exit 1 cannot be told apart
     from a mid-archival failure. Before `archive_move`, `archive_parent` has
     already run `handle_folded_tasks` (L491: deletes and stages folded tasks
     and plans) and `archive_metadata_update` (L495: rewrites the task file).
     A failure after either leaves the task still "active" with no archived
     copy, yet partly archived. A re-run would skip the already-missing folded
     files, and its scoped commit would leave them in HEAD. Only the exit-2
     guards are confirmed pre-write. So every exit 1 is handled as
     **uncertain**, whether or not anything moved. **The skill does not repair
     it.** The complete change is known only inside the
       archive script. It covers the task and plan, a parent's
       `children_to_implement` edit or a parent archived with its last child,
       folded tasks **and their plans**: folded plans go into
       `FOLDED_DELETED_PATHS` (L659/L665) but are never printed, since
       `FOLDED_DELETED:` names the task only (L668). Depending on where the run
       died, destinations may be untracked (failure before the `task_git add`
       lines, L522-533) or deletions already staged. Any reconstruction by the
       skill could commit a partial move. The skill therefore:
       1. reports the state verbatim: the archive output, the stop line, and
          `./ait git status --short -- aitasks aiplans`;
       2. **keeps the web branch** and skips Step 6 for this branch (no push,
          no delete). It says not to re-run until `./ait git status` shows the
          task data clean for this task, its plan and its folded tasks; item 0
          refuses outright once the task is archived;
       3. points to the manual recovery in the web-merge docs (section B),
          then continues to 6e.
       No commit, push or branch deletion happens on this path.
   Update the Step 6 header and 6e so they say Step 6 runs only after a
   successful archive. Change the Overview flow line to match.
5. **`materialize-gates.md:33` — "Abort this branch".** Shorten the option
   description to: the merge and plan commits stay local, the task stays
   unarchived, and Step 6 is skipped, so the web branch stays. After the
   options, add a "Finishing an aborted branch" paragraph with two routes:
   - a re-run after fixing the profile, or after pushing a fixed marker to the
     branch (the merge step skips or merges only the marker change);
   - a full manual repair: `materialize` until `WEBMAT_OK`/`WEBMAT_SKIP:no-profile`
     → `aitask_update.sh --batch <id> --implemented-with "<v>"` when the marker
     has it → `aitask_archive.sh <id>` → the **Issue Update Procedure** for each
     `ISSUE:`/`PARENT_ISSUE:` line → `git push`, `./ait git push`,
     `git push origin --delete <branch>`.

### B. Docs for A (`website/content/docs/`)

6. `skills/aitask-web-merge.md`: Step-by-Step items 3, 6 and 7 (already-merged
   skip; archive stops = gates **or** pending/deferred manual verification;
   Step 7 never runs after any stop). Rewrite "When archival stops". Abort
   repair: re-run now finishes, and the manual route keeps the issue update.
   Pending-gates: the run keeps the branch, and the finish is pass the gates,
   then re-run. Add a short "manual-verification items are open" case. Rewrite
   "Re-running after a stop": the branch survives every stop, the merge is
   skipped, the plan commit is a `NOCHANGE`, materialize is idempotent, then
   archive. Keep the line saying other branches' pushes carry the stopped
   branch's commits.
7. `workflows/claude-web.md` "If something goes wrong": the gates bullet (the
   run no longer deletes the branch) and the closing paragraph (re-run is the
   finish; manual finish is an alternative).
   Both pages also cover: a marker or plan repair pushed to the web branch
   merges as a metadata-only conflict the skill resolves itself; a re-run
   refuses a task that is already archived or mid-archival; a run refuses to
   start while another merge is open in the checkout; and after any archive
   exit 1, the run stops with the web branch kept, because exit 1 can follow
   partial writes (folded deletions, metadata update) even when nothing moved.
   A re-run is offered only after an exit-2 refusal. The docs
   give the manual recovery:
   - inspect `./ait git status --short -- aitasks aiplans`;
   - finish the moves;
   - `./ait git add` any untracked archived destination;
   - make one `./ait git commit -m … -- <paths>` naming every moved-from and
     archived path, including folded tasks, folded plans and parent changes;
   - confirm with `./ait git show --stat HEAD` that the originals are gone
     and the archived copies are present;
   - then push `main` and the task data and delete the web branch.
   Name `aitask_task_commit.sh` as unsuitable here: it skips staged deletions
   of files that are gone from disk.
   Follow `aidocs/framework/documentation_conventions.md`: describe the current
   state only, with no "previously".

### C. pickweb (`.claude/skills/aitask-pickweb/`)

8. **Stub `SKILL.md`.** Add a new first step before "Resolve active profile":
   run `./.aitask-scripts/aitask_init_data.sh`. Non-zero means show the error
   and stop. The reason: `default_profiles.pickweb` lives in
   `aitasks/metadata/`, which exists only after data-branch init. Renumber the
   steps. The template's Step 0a stays, since init is a no-op when already
   initialized. Keep every Test 5 marker string in
   `tests/test_skill_render_aitask_pickweb.sh`.
9. **`SKILL.md.j2` Profile Schema (L376-385).** `name` → "Recorded in the
   completion marker as `profile`". `description` → move to the ignored list.
   `post_plan_action` → "Accepted, with no effect: web mode always continues to
   implementation". This matches the docs page table.
10. **`SKILL.md.j2` L137/L147 (Done / orphaned parent).** Replace "use
    `aitask-web-merge` locally" (it only handles marker-bearing branches) with
    "archive it locally with `/aitask-pick <N>`, which offers archival for it".
    Apply the same change to the banner `next`.
11. Re-render `aitask-pickweb --profile remote` for claude, codex and opencode
    (`aitask_skill_render.sh … --force`). Regenerate
    `tests/golden/skills/aitask-pickweb/SKILL-remote-claude.md` per
    `aidocs/framework/skill_authoring_conventions.md`, "Regenerate goldens…".
12. Docs `skills/aitask-pickweb.md`: L49, L56 and L133 (profile chosen after task
    data setup, so `default_profiles.pickweb` is honoured; `--profile remote`
    still needed when nothing is configured, since `default` cannot render on
    Web). L60 (Done/orphaned → `/aitask-pick` locally).

### D. task-workflow auto-select text (renders into `task-workflow-remote-`)

13. `task-workflow/execution-profile-selection-auto.md` header: no shipped skill
    runs it. `aitask-pickrem`/`aitask-pickweb` choose their profile in the stub
    (`aitask_skill_resolve_profile.sh`: `--profile`, then `default_profiles`,
    then `default`) and run the variant rendered for it. Keep the
    `workflow-end.md` references (banner-contract test, L226).
14. `task-workflow/SKILL.md:1272` bullet: same correction.
    `task-workflow/profiles.md:277` "4. Interactive selection / auto-select" →
    "4. The profile named `default`". This is the same stale claim as the seed.
15. Re-render `task-workflow` remote for 3 agents. Regenerate the goldens
    `tests/golden/procs/task-workflow/SKILL-{default,fast,remote}.md` and any
    other affected golden. Run `./.aitask-scripts/aitask_skill_verify.sh`.

### E. Cross-repo CLI help and messages

16. **`aitask_update.sh` `main()` allow-list (L2460+).** While walking argv,
    classify each token. Allowed value flags (consume 2 tokens): `--priority|-p`,
    `--effort|-e`, `--status|-s`, `--deps`, `--xdeps`, `--xdeprepo`,
    `--labels|-l`, `--add-label`, `--remove-label`, `--assigned-to|-a`,
    `--boardcol`, `--boardidx`. Allowed bare flags: `--batch`, `--commit`,
    `--silent`, `--help|-h`. Positional tokens are allowed. Record the first
    other `-`-prefixed token as `cross_disallowed`. `forwarded` is built exactly
    as today, so non-project calls are unchanged. In project mode, after the
    `--batch`/`--name` checks, `cross_disallowed` means die: "'<flag>' is not
    supported with --project: only administrative fields can be updated in
    another project (<list>)". Keep the tailored Implementing/Done/Folded
    messages, and add a `*)` for any other non-empty status outside
    Ready|Editing|Postponed. All refusals happen before resolve/re-exec. Update
    `--help` L311-324 to say anything else is refused.
    Docs: rewrite `commands/task-management.md` L287-293, replacing "Only those
    refusals are checked…".
17. **Unresolved-project message.** Add `project_unresolved_msg <name>` to
    `lib/terminal_compat.sh`, which every affected script already sources. It
    returns: "Project '<n>' did not resolve: no running tmux session, registry
    entry or AITASKS_PROJECT_<n> variable names it. Register it with
    `cd /path/to/<n> && ait projects add`." Use it at every resolver-`NOT_FOUND`
    site: `lib/task_utils.sh:3020` (split its `""` case into "resolver produced
    no output"), `aitask_update.sh:2529`, `aitask_create.sh:2719`,
    `lib/cross_repo_reexec.sh:77`, `aitask_explain_context.sh:301`,
    `aitask_projects.sh:759`. Mirror the wording in `board/aitask_board.py:1448`.
    Leave `aitask_projects.sh` 449/510/801 alone if, as expected, they are
    registry-membership checks; confirm while editing. Update the tests that pin
    "is not registered" for resolver NOT_FOUND: `test_aitask_update_xdeps.sh:134`,
    `test_create_project_flag.sh:82`, `test_query_files_cross_repo.sh:118`,
    `test_update_cross_repo.sh` case 6, plus any others a grep finds.
18. `aitask_create.sh:133-135`: `--xdeprepo` alone records the intent to
    coordinate; `--xdeps` requires `--xdeprepo`.
19. `--project` position: `aitask_ls.sh:68-71`, `aitask_find_by_file.sh:56` and
    `aitask_query_files.sh:55` → "May appear anywhere in the argument list". All
    three use `cross_repo_reexec_or_continue`, which strips it anywhere.
20. `aitask_explain_context.sh`: default `MAX_PLANS=""`. After `parse_args`:
    empty → `die "--max-plans is required (0 = no-op)…"`; non-integer → die;
    `0` → exit 0 as today. The only caller (`brainstorm_crew.py:987`) passes it.
    Add a test case in `tests/test_explain_context.sh`.
21. `aitask_projects.sh:222-237` `load_registry_or_die`: when `resolve_python`
    returns empty, die with "No Python interpreter is available to read the
    project registry … — left unchanged. Run `ait setup`." Release the lock
    first when locked. Keep the current message for a real read failure. Add a
    case to `tests/test_projects_unreadable_registry.sh` (force no interpreter:
    `AIT_PYTHON=/nonexistent`, scratch `HOME`, PATH without python). Skip with a
    note if the scaffold cannot isolate it.
22. `aitask_project_resolve.sh:89` help, and `aidocs/framework/cross_repo_references.md:144`:
    NOT_FOUND = "No resolution tier (tmux session, registry, AITASKS_PROJECT_<name>
    env var) matched."
23. `seed/project_config.yaml:444` → "4. The profile named `default` (fallback)".

### F. Tests for E16

24. `tests/test_update_cross_repo.sh`: refusal cases `--desc-file -`,
    `--implemented-with x`, `--gates a`, `--type bug`, `--status Blocked`. Each
    asserts the message and that the sister stub was **not** invoked. Redirect
    cases `--commit` and `--silent` and `-p high` still re-exec.

### Post-phase (risk mitigations)

1. [fixture_webmerge_rerun] Write a scratchpad script that builds a bare
   `origin`, a clone on `main` and a web branch. The branch carries a code
   change plus `.aitask-data-updated/{plan_t1.md,completed_t1.json}`. The script
   then runs the **new** Step 3 commands verbatim (3a ancestor check → 3b
   `git merge origin/<b> --no-ff --no-commit` plus the 1b classification → 3c
   `git rm -rf .aitask-data-updated/` → 3d MERGE_HEAD check + commit) across
   these scenarios. Assert:
   - run 1 (fresh branch): ancestor exit 1, `MERGE_HEAD` present, commit exit 0,
     and `.aitask-data-updated/` absent from HEAD;
   - run 2 (no new commits): ancestor exit 0, so merge is skipped;
   - a forced 3b on the up-to-date branch prints "Already up to date" and leaves
     no `MERGE_HEAD` (the backstop skips 3d);
   - control: the **old** unconditional 3d `git commit` on that state exits 1
     (reproduces the defect);
   - run 3 (**marker-only repair commit** pushed to the web branch after run 1):
     ancestor exit 1, merge exits non-zero, `MERGE_HEAD` present, and every
     `--diff-filter=U` path is under `.aitask-data-updated/` (the modify/delete
     conflict is reproduced). Then 3c resolves it (`--diff-filter=U` empty),
     3d commits with exit 0, and `.aitask-data-updated/` is absent from HEAD;
   - run 4 (repair commit that changes **code plus marker** and conflicts with
     a `main` edit to the same code line): classification yields an unmerged
     path outside `.aitask-data-updated/`, so the Conflict-prompt route is
     taken (assert the classifier's verdict only; then `git merge --abort`).
   - run 5 (**earlier merge still open**), two variants:
     - 5a: leave a conflicting merge of another branch **unresolved**;
     - 5b: same, but resolve and `git add` the earlier conflict **without
       committing**. This is the state where `MERGE_HEAD` belongs to the
       earlier merge and the unmerged-path list is **empty**.
     For each: the new Step 3 stops at 0a before 3a/3b. Then bypass 0a and run
     3b directly. Assert that git refuses and that `MERGE_HEAD` still equals
     the *other* branch's tip (≠ `branch_tip`), so the classifier yields
     "stop" and never the metadata route. In 5b also assert
     `git diff --name-only --diff-filter=U` is empty. Control (5b): the earlier
     classifier (any MERGE_HEAD + vacuous "every path") would have taken the
     metadata route and committed the earlier merge;
   - archive exit-code shape (read-only evidence, no fixture): quote
     `aitask_archive.sh` L1202-1204 (guards before writes), L491/L495/L498
     (folded deletions and metadata update before the move), L222/L559 (`mv`
     before `die "archive commit failed"`) and L648-668 (folded plans tracked
     but not printed) in the notes. Item 4's exit-1 split, and its refusal to
     auto-repair, rest on them.
   Paste the script and its output verbatim into the plan's Final
   Implementation Notes so the closure evidence is durable.

## Verification

- Shell: `shellcheck` on every edited `.aitask-scripts/*.sh`/`lib/*.sh`, then
  `bash tests/<t>.sh` for `test_update_cross_repo`, `test_aitask_update_xdeps`,
  `test_create_project_flag`, `test_query_files_cross_repo`,
  `test_aitask_create_xdeprepo_alone`, `test_xdeps_validation`,
  `test_explain_context`, `test_explain_context_cross_repo`,
  `test_projects_unreadable_registry`, `test_projects_cmd`, `test_project_resolve`,
  `test_web_merge`, `test_web_merge_materialize`, `test_no_unscoped_task_commit`.
- Skills: `test_skill_render_aitask_pickweb`, `test_skill_dispatch_contract`,
  `test_workflow_end_banner_contract`, `./.aitask-scripts/aitask_skill_verify.sh`,
  and the golden tests.
- Board message: any Python test that pins the board's NOT_FOUND text (grep), via
  `bash tests/run_all_python_tests.sh --test-dir` on the matching subset.
- Website: `cd website && hugo build --gc --minify && python3 check_links.py --build`.
- Step 9 (Post-Implementation) handles commit, archival and push (current-branch
  mode, no merge).

## Follow-ups (create after implementation)

- Port the pickweb stub change (init before resolve) to `.agents/skills/aitask-pickweb/SKILL.md`,
  `.opencode/skills/aitask-pickweb/SKILL.md` and `.opencode/commands/aitask-pickweb.md`.
  The web-merge wrappers in other trees point at the Claude skill, so they need
  no port.
- `aitask-pickrem`: its stub has the same resolve-before-init order, and its
  docs (`skills/aitask-pickrem.md:39`) still say "auto-selects a profile".

## Risk

### Code-health risk: medium
- Re-rendering `task-workflow-remote-` / `aitask-pickweb-remote-` commits uncommitted hunks already in the working tree. If they are not a clean render of the HEAD templates, another session's work rides along · severity: medium · → mitigation: inline pre-phase verify_render_baseline
- Enforcing the `--project` allow-list in `aitask_update.sh` refuses a flag some cross-repo caller relies on. Only one in-repo caller exists (`cross-repo-child-assignment.md`: `--xdeps/--xdeprepo/--commit`) and no Python caller · severity: low · → mitigation: none (covered by the step 24 tests)
- The shared unresolved-project message changes strings that 4+ tests pin; a missed site keeps the old wording · severity: low · → mitigation: none (a grep for "is not registered" at each resolver NOT_FOUND site is part of step 17)

### Goal-achievement risk: medium
(Reassessed after the inline phases and the review rounds. The fixture covers the merge mechanics. The partial-archive case is now a report-and-stop with manual recovery in the docs, so the outcome is safe but not automated.)
- The web-merge stop/re-run fixes are skill prose that no test runs. The re-run could still fail at a step not walked, for example if a `--no-ff` merge ancestor check or a `MERGE_HEAD` left on an up-to-date merge behaves differently than assumed · severity: medium · → mitigation: inline post-phase fixture_webmerge_rerun
- Re-run edge cases. A marker or plan repair pushed to the branch conflicts (modify/delete) before the strip step. An earlier open merge could be committed under this task's message. An archive failure leaves files partly or fully moved, and any skill-side reconstruction of the change could commit a partial move · severity: high · → mitigation: inline post-phase fixture_webmerge_rerun (runs 3-5 plus the quoted archive evidence) and items 0a, 0, 1b and 4. Item 4 deliberately does no auto-repair (report state, keep branch)
- pickweb init-before-resolve: `aitask_init_data.sh` already runs in the template's Step 0a, so moving it earlier changes only the order · severity: low · → mitigation: none

### Planned mitigations
- timing: pre-phase | name: verify_render_baseline | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — pre-existing render hunks | desc: confirm render inputs equal HEAD, then read-only walk-verify of every remote prerender (3 agents) against the working tree before any re-render
- timing: post-phase | name: fixture_webmerge_rerun | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: goal-achievement — web-merge re-run untested | desc: scratch git fixture running the new Step 3 commands for a first run, a re-run, a marker-only repair conflict, a code conflict, and an earlier open merge, each with a pre-fix control
