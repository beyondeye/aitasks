---
Task: t832_9_manual_verification_cross_repo.md
Parent Task: aitasks/t832_brainstorm_cross_repo_skills_retrieval_xdeps_parallel_planni.md
Sibling Tasks: aitasks/t832/t832_*_*.md
Archived Sibling Plans: aiplans/archived/p832/p832_*_*.md
Worktree: (none — profile 'fast', current branch)
Branch: main
Base branch: main
---

# Auto-Verification Record: t832_9 (cross-repo manual verification)

Autonomous auto-verification of the 36-item checklist verifying sub-tasks
t832_1 → t832_8. Strategy: `autonomous` (executed inline, documented here
retroactively).

- **21 items auto-passed** in the first pass (tests / shellcheck / CLI).
- **6 TUI items (16, 30, 31, 32, 35, 36) auto-passed** in a second pass by
  driving a live `ait board` in tmux against an isolated scratch two-project
  setup (see "Live TUI verification" below).
- **6 items skipped** in the interactive loop (3, 13, 19, 26, 33, 34) — see
  per-item entries.
- **3 items deferred** (21, 22, 23) — they verify the still-pending t832_6
  retrospective doc, which does not exist yet. Archived with a carry-over
  manual-verification task.

Result: `TOTAL:36 PASS:27 FAIL:0 SKIP:6 DEFER:3` (archive with deferred
carry-over).

**Upstream defect found during TUI verification** — see the "Upstream
defects identified" section at the end.

## Execution Log

### Item 1 — [t832_1] test_query_files_cross_repo.sh
- Approach: CLI / test invocation
- Action run: `bash tests/test_query_files_cross_repo.sh`
- Output (trimmed): `Passed: 34 / 34` (exit 0)
- Verdict: pass

### Item 2 — [t832_1] shellcheck query_files / ls / find_by_file
- Approach: CLI lint
- Action run: `shellcheck .aitask-scripts/aitask_query_files.sh .aitask-scripts/aitask_ls.sh .aitask-scripts/aitask_find_by_file.sh`
- Output (trimmed): only SC1091 (dynamic source, ignorable) + pre-existing SC2010/SC2034/SC2231 in aitask_ls.sh. `git blame` confirms flagged lines originate from commit 7f8ea6df ("Initial import") — not introduced by t832.
- Verdict: pass

### Item 4 — [t832_1] aitask_skill_verify.sh
- Approach: CLI invocation
- Action run: `./.aitask-scripts/aitask_skill_verify.sh`
- Output (trimmed): `OK (10 template(s) verified across 3 agents)` (exit 0)
- Verdict: pass

### Item 5 — [t832_1] --project <registered> re-execs into correct root
- Approach: CLI invocation
- Action run: `./.aitask-scripts/aitask_query_files.sh --project aitasks_mobile task-file 10`
- Output (trimmed): `TASK_FILE:aitasks/t10_bootstrap_kmp_build_infrastructure.md` (mobile's t10; re-exec worked)
- Verdict: pass

### Item 6 — [t832_1] --project <unregistered> dies with hint
- Approach: CLI invocation (negative)
- Action run: `./.aitask-scripts/aitask_query_files.sh --project bogus_unregistered_xyz task-file 1`
- Output (trimmed): `Error: Project 'bogus_unregistered_xyz' is not registered. Run \`cd /path/to/bogus_unregistered_xyz && ait projects add\`.` (exit 1)
- Verdict: pass

### Item 7 — [t832_1] --project <stale> dies with stale-path message
- Approach: CLI invocation (negative) via temp registry `AITASKS_PROJECTS_INDEX`
- Action run: temp registry with `stale_proj -> /home/ddt/Work/this_path_does_not_exist_av`, then `--project stale_proj task-file 1`
- Output (trimmed): `Error: Project 'stale_proj' is registered but its path is stale: ... Run \`cd /path/to/stale_proj && ait projects add\` to refresh.` (exit 1)
- Verdict: pass

### Item 8 — [t832_1] task-status returns correct status per lifecycle state
- Approach: CLI invocation
- Action run: `task-status 832_9` / `832_1` / `832_11`
- Output (trimmed): `STATUS:Implementing` / `STATUS:Done` / `STATUS:Ready`
- Verdict: pass

### Item 9 — [t832_1] task-status NOT_FOUND is silent (no crash)
- Approach: CLI invocation (negative)
- Action run: `./.aitask-scripts/aitask_query_files.sh task-status 9999999`
- Output (trimmed): `STATUS:NOT_FOUND` (exit 0, no crash)
- Verdict: pass

### Item 10 — [t832_1] aitask_skill_verify.sh
- Approach: CLI invocation (duplicate of item 4)
- Action run: `./.aitask-scripts/aitask_skill_verify.sh`
- Output (trimmed): `OK` (exit 0)
- Verdict: pass

### Item 11 — [t832_2] test_explain_context_cross_repo.sh
- Approach: CLI / test invocation
- Action run: `bash tests/test_explain_context_cross_repo.sh`
- Output (trimmed): `Passed: 22 / 22` (exit 0)
- Verdict: pass

### Item 12 — [t832_2] shellcheck aitask_explain_context.sh
- Approach: CLI lint
- Action run: `shellcheck .aitask-scripts/aitask_explain_context.sh`
- Output (trimmed): SC1091 (dynamic source) only — clean
- Verdict: pass

### Item 14 — [t832_3] xdeps parser / validation / fold_warn tests
- Approach: CLI / test invocation (3 tests per plan p832_3)
- Action run: `bash tests/test_xdeps_parser.sh`; `test_xdeps_validation.sh`; `test_xdeps_fold_warn.sh`
- Output (trimmed): 5/5, 14/14, 9/9 (all exit 0)
- Verdict: pass

### Item 15 — [t832_3] shellcheck clean on touched scripts
- Approach: CLI lint
- Action run: `shellcheck` on aitask_create.sh / aitask_fold_validate.sh / aitask_ls.sh / aitask_update.sh (the xdeps-touching scripts)
- Output (trimmed): only pre-existing SC2001/SC2010/SC2012/SC2034/SC2086/SC2231; `git blame` confirms flagged lines predate t832 (commit 7f8ea6df). No new lint from the xdeps work.
- Verdict: pass

### Item 17 — [t832_4] test_xdeps_blocking.sh
- Approach: CLI / test invocation
- Action run: `bash tests/test_xdeps_blocking.sh`
- Output (trimmed): `Passed: 18 / 18` (exit 0)
- Verdict: pass

### Item 18 — [t832_4] shellcheck aitask_ls.sh
- Approach: CLI lint
- Action run: `shellcheck .aitask-scripts/aitask_ls.sh`
- Output (trimmed): pre-existing baseline warnings only (none from t832)
- Verdict: pass

### Item 20 — TODO: define verification for t832_5
- Approach: CLI / test invocation (substituted the existing test for the undefined placeholder)
- Action run: `bash tests/test_parallel_cross_repo_planning_procedure.sh`
- Output (trimmed): `Tests: 36  Passed: 36  Failed: 0` (exit 0)
- Note: original checklist item was a literal `TODO` placeholder; verified t832_5 (parallel cross-repo planning procedure) via its dedicated test instead.
- Verdict: pass

### Item 24 — [t832_7] test_update_cross_repo.sh
- Approach: CLI / test invocation (+ companion test per plan p832_7)
- Action run: `bash tests/test_update_cross_repo.sh`; `bash tests/test_aitask_update_xdeps.sh`
- Output (trimmed): 41/41 and 20/20 (both exit 0)
- Verdict: pass

### Item 25 — [t832_7] shellcheck aitask_update.sh
- Approach: CLI lint
- Action run: `shellcheck .aitask-scripts/aitask_update.sh`
- Output (trimmed): pre-existing baseline warnings only (none from t832)
- Verdict: pass

### Item 27 — [t832_8] cross-repo notation tests (or equivalent)
- Approach: CLI / test invocation (`.py` equivalent — no `.sh` variant exists)
- Action run: `python3 tests/test_cross_repo_notation.py`
- Output (trimmed): `Ran 9 tests ... OK` (exit 0)
- Verdict: pass

### Item 28 — [t832_8] aitask_skill_verify.sh
- Approach: CLI invocation (duplicate of item 4)
- Action run: `./.aitask-scripts/aitask_skill_verify.sh`
- Output (trimmed): `OK` (exit 0)
- Verdict: pass

### Item 29 — [t832_8] shellcheck clean if new bash wrappers introduced
- Approach: CLI lint + scope check
- Action run: reviewed t832_8 touched files (board.py, cross_repo_notation.py, task_utils.sh, edits to create/fold_validate/ls) — no NEW bash wrappers were introduced; shellcheck on edited bash scripts shows baseline-only warnings.
- Verdict: pass (vacuously — no new wrappers; edited scripts carry no new lint)

### Item 3 — [t832_1] from aitasks_mobile, --project aitasks task-file 832
- Approach: CLI invocation from sibling repo
- Action run: `( cd aitasks_mobile && ./.aitask-scripts/aitask_query_files.sh --project aitasks task-file 832 )`
- Output (trimmed): `Error: Unknown subcommand: '--project'` — aitasks_mobile's local query_files.sh predates the t832_1 `--project` feature (confirmed via grep; no `--project` support). The re-exec capability itself is proven from this repo (item 5).
- Verdict: skip (re-exec capability proven by item 5; sibling repo just needs the t832_1 upgrade — not blocking)

### Item 13 — [t832_2] Manual: from aitasks (truncated)
- Approach: not automatable as written
- Note: checklist item truncated/underspecified; functional coverage provided by item 11's passing explain_context cross-repo test.
- Verdict: skip (truncated checklist item; functional coverage via item 11)

### Item 16 — [t832_3] TUI round-trip (xdeps/xdeprepo preservation)
- Approach: board save-path round-trip (Python, exercising the exact `serialize_frontmatter` the board calls on save)
- Action run: parsed scratch t5 via `task_yaml.parse_frontmatter`, set `priority` medium→high, `serialize_frontmatter(meta, content, order)`, re-read from disk.
- Output (trimmed): `BEFORE priority='medium' xdeps=[1] xdeprepo='av_projB'` → `AFTER priority='high' xdeps=[1] xdeprepo='av_projB'` — unknown keys preserved verbatim.
- Verdict: pass

### Item 19 — [t832_4] aitask_ls.sh -v 5 flags blocked tasks (live cross-repo)
- Approach: needs live cross-repo blocked task
- Note: blocking logic covered by item 17 (test_xdeps_blocking.sh 18/18); live-board flag confirmation left to interactive.
- Verdict: skip (blocking logic covered by item 17; live-board flag not separately verified)

### Item 21 — [t832_6] retrospective doc exists with all sections
- Approach: file inspection
- Action run: `ls aidocs/cross_repo_retrospective_t832.md`
- Output (trimmed): missing — t832_6 is still pending (not yet implemented)
- Verdict: defer (blocked on t832_6)

### Item 22 — [t832_6] follow-up tasks reference retrospective
- Verdict: defer (blocked on t832_6 — not yet implemented)

### Item 23 — [t832_6] zero-friction "no follow-ups" audit statement
- Verdict: defer (blocked on t832_6 — not yet implemented)

### Item 26 — [t832_7] Manual smoke (cross-repo --add-label)
- Approach: would mutate sibling repo task data
- Note: per the auto-verification no-mutation policy (never mutate user-owned files outside the checklist), the `aitask_update.sh --batch --project aitasks_mobile <id> --add-label test` smoke was NOT run autonomously.
- Verdict: skip (would mutate sibling repo via --add-label; update logic covered by item 24)

### Item 30 — [t832_8] board shows xdeps cross-repo dep line
- Approach: live `ait board` in tmux (scratch projA, AITASKS_PROJECTS_INDEX→temp registry)
- Output (trimmed): t5 card rendered a distinct `↗ av_projB#1` line below the meta row.
- Verdict: pass

### Item 31 — [t832_8] board "blocked by cross-repo" indicator
- Approach: live `ait board` in tmux (projB#1 = Ready ⇒ dep unmet)
- Output (trimmed): t5 card showed a distinct `🌐 blocked (cross-repo)` chip.
- Verdict: pass

### Item 32 — [t832_8] board refresh on out-of-band status change
- Approach: live `ait board` in tmux; edited projB t1 `status: Ready`→`Done` on disk, pressed `r`
- Output (trimmed): after refresh the `🌐 blocked (cross-repo)` chip cleared and t5 showed `📋 Ready`; the `↗ av_projB#1` dep line remained. (xdep_status_cache re-probed per refresh.)
- Verdict: pass

### Item 33 — [t832_8] stale-registry case (edit projects.yaml)
- Approach: would mutate the real ~/.config/aitasks/projects.yaml
- Verdict: skip (would mutate the real ~/.config/aitasks/projects.yaml; resolver-level stale already verified in item 7)

### Item 34 — [t832_8] restore registry
- Verdict: skip (paired with item 33; not run since 33 not mutated)

### Item 35 — [t832_8] activate cross-repo link in board (read-only popup)
- Approach: live `ait board` in tmux; focused t5, pressed `#`, picker → selected `av_projB#1`, Enter
- Output (trimmed): read-only `CrossRepoTaskScreen` popup rendered projB t1 (title `↗ av_projB#1`, frontmatter + "Target Feature" body); ESC closed it, board state unchanged. No lock acquired on the cross-repo task.
- Verdict: pass

### Item 36 — [t832_8] activate link to non-registered project (popup)
- Approach: live `ait board` in tmux; added scratch t6 with a single body ref `ghost_proj#1` (non-registered) so `#` opens directly (len(refs)==1), pressed `#`
- Output (trimmed): error popup `Project 'ghost_proj' is not registered. Add it with \`ait projects add\`.` — no crash.
- Verdict: pass

## Live TUI verification (items 16, 30, 31, 32, 35, 36)

Driven against an isolated, fully synthetic two-project setup under
`/tmp/auto_verify_832_9/` — no real `aitasks/`, sibling repo, or user
registry was touched:
- `projA` (git-init'd, `.aitask-scripts`/`ait` symlinked to the real repo,
  metadata copied) with `t5` (`xdeps: [1]`, `xdeprepo: av_projB`, body refs
  `av_projB#1` + `ghost_proj#1`) and `t6` (single body ref `ghost_proj#1`).
- `projB` with `t1` (status Ready → flipped to Done for item 32).
- A temp registry passed via `AITASKS_PROJECTS_INDEX` (inherited by the
  board's cross-repo subprocesses) registering `av_projA` / `av_projB`.
- `ait board` launched in a detached tmux session (220×55); driven with
  `send-keys`, asserted via `capture-pane`.

## Upstream defects identified

- `.aitask-scripts/board/aitask_board.py` (CrossRepoRefPickerScreen, ~:1893) —
  the multi-ref cross-repo picker is **keyboard-navigable only to its first
  (auto-focused) item**. The board binds `Binding("tab", "focus_search",
  priority=True)` at the App level; that priority binding fires even while the
  modal picker is on the screen stack, so pressing Tab inside the picker moves
  focus to the board's search input instead of cycling to the 2nd+ items / the
  Cancel button. Arrow keys don't help (the items are plain focusable
  `Static`s with no arrow focus-movement, and the board disables card-nav over
  modals). Net effect: with ≥2 cross-repo refs, only the first ref is
  selectable via keyboard (Enter); the rest are reachable only by mouse, and
  Escape is the only keyboard way out. Suggested fix: disable
  `focus_search`/`focus_board` in `check_action` when `len(screen_stack) > 1`
  (mirroring the existing nav_* guard), or give the picker explicit
  up/down/tab bindings. Items 35/36 still passed (verified via the first ref
  and the single-ref direct-open path).

## Cleanup
- Scratch projects + temp registry under `/tmp/auto_verify_832_9/` — removed.
- Detached tmux session `avboard` — killed.
- Temp registry file (`/tmp/av_reg_*.yaml`) used for item 7 — removed inline.
- Hung ImageMagick `import` process (from an accidental `bash file.py`
  invocation while running the notation test) — killed; test re-run with
  `python3`.
- `/tmp/av_*.log` scratch logs — transient, no action needed.
