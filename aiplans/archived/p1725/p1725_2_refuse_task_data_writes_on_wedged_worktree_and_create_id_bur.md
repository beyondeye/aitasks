---
Task: t1725_2_refuse_task_data_writes_on_wedged_worktree_and_create_id_bur.md
Parent Task: aitasks/t1725_sync_deferrals_actionable_and_safe_to_continue.md
Sibling Tasks: aitasks/t1725/t1725_3_sweep_per_file_deferral_record_tree_state_gate_and_wire.md, aitasks/t1725/t1725_4_resolve_holder_pane_and_prompt_state.md, aitasks/t1725/t1725_5_syncer_and_board_deferral_screen_with_commit_on_behalf.md, aitasks/t1725/t1725_6_document_actionable_sync_deferrals.md, aitasks/t1725/t1725_7_manual_verification_sync_deferrals_actionable_and_safe_to_co.md
Archived Sibling Plans: aiplans/archived/p1725/p1725_1_abort_conflicted_pull_rebase_in_task_utils.md
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5 @ 2026-09-08 23:08
---

# t1725_2 — refuse task-data writes on a wedged worktree; stop `create` burning ids

*(Verify pass over `aiplans/p1725/p1725_2_*.md`, 2026-09-08. Base: `main` @ 92650b0938.)*

## Context

Parent t1725, findings 6 and 7 / AC4 and AC5. Two defects observed live on
2026-09-07 during a 21-behind/39-ahead divergence:

- **F6 — writers edit whatever base is checked out.** Mid-rebase, the checked-out
  task file is origin's version, not the branch tip. The rebase had stopped
  *before* replaying t1717's own three commits, so the checked-out t1717 file was
  the stale `status: Ready` version with no `active_gates` / `assigned_to`. The
  agent wrote its risk-gate result onto **that** file. Had it committed, t1717
  would have flipped back to `Ready` and lost its materialized gates.
- **F7 — `create` retries burn ids.** `ait create --batch --commit` writes the
  file then commits; when the commit fails the script dies under `set -e`, the
  file stays on disk, and the caller retries — each retry claiming a fresh id.
  t1722/t1723/t1724 are byte-identical apart from timestamps.

**Why a pre-write guard, and nothing bigger.** `task_git()`
(`lib/task_utils.sh:412`) *already* calls `assert_data_worktree_clean`, so the
**commit** already refuses on a wedge. The hole is that the in-place write runs
first — the file is corrupted, *then* the commit dies. The general "writer
carries its last-known base SHA" contract is deliberately **not** attempted (it
would be a new field on every writer); the wedge is the one production-reachable
way the checked-out base differs from what the writer last committed, so refusing
there is AC4's "refused, not applied blind".

## What this verify pass changed

The plan was written 2026-09-07. Five of its assumptions have moved:

1. **`_data_wedge_state()` now exists** — `lib/task_utils.sh:289`, with
   `_data_wedge_gitdir()` (:273) and the shared `_ait_inprogress_state_at()`
   (:233) behind it. t1725_1 landed it. The plan's "add it here if t1725_1 has
   not landed" branch is **dead**; delete it and call the helper.
2. **t1599_4 landed and is archived** — it touched `aitask_create.sh` (+135),
   `aitask_update.sh` (+39), `aitask_archive.sh` (+101). Every line number in the
   old plan is stale, and its "t1599_4 (Implementing) … rebase rather than
   hand-merge" coordination note is spent.
3. **The writer list was incomplete — 13 genuine task-data writers, not 6.**
   The old plan missed `aitask_verification_followup.sh`, `aitask_zip_old.sh`,
   `aitask_migrate_archives.sh`, `aitask_pick_own.sh`, `aitask_usage_update.sh`,
   `aitask_verified_update.sh` and `aitask_add_model.sh`. Scope decision below.
4. **`tests/test_create_silent_stdout.sh` is the wrong fixture.** It builds a
   *legacy-mode* repo — no `.aitask-data` worktree at all — so it cannot host a
   wedge. The right base is `tests/lib/sync_fixture.sh`'s `setup_repo()`
   (:32-90): real branch-mode worktree, bare remote, a full `.aitask-scripts`
   copy, plus `run_sync()` (:141), `data_log()` (:161) and `commit_files_for()`
   (:163) — exactly what the F7 sweep assertion needs. It does not init the id
   counter; the test adds `aitask_claim_id.sh --init`.
5. **`tests/test_task_git.sh` Test 16 is lines 774–871** (not "~868") and already
   drives all six in-progress states with per-state negative controls. Reuse its
   `"name:dir"|"name:file"` planting table and its
   `( … ) && echo allowed || echo refused` probe — the guard `die`s, so it must
   run in a subshell.

## Design decisions

**Scope — 9 guarded + 4 audited-but-not-guarded = 13 task-data writers.** Guard
the nine scripts that mutate task `.md` / plan files: `aitask_update.sh`,
`aitask_create.sh`, `aitask_note.sh`, `aitask_gate.sh`, `aitask_archive.sh`,
`aitask_plan_externalize.sh`, `aitask_verification_followup.sh`,
`aitask_zip_old.sh`, `aitask_migrate_archives.sh`. The four metadata-only writers
(`aitask_pick_own.sh` → `emails.txt`; `aitask_usage_update.sh`,
`aitask_verified_update.sh`, `aitask_add_model.sh` → `models_*.json` /
`codeagent_config.json`) are recorded in the table as audited-but-not-guarded
with their reason: the corruption class is a lost list entry, not a lost task
status, and `aitask_pick_own.sh` runs on **every** pick — guarding it would make
a wedged worktree block task selection outright. A recorded bound, not deferred
work; if metadata corruption is ever observed it gets its own task.

**The enumeration command alone does not find all 13.**
`grep -ln 'sed_inplace\|>> *"\$\|write_task_file\|mv ' .aitask-scripts/*.sh`
returns 26 files, of which 12 are genuine task-data writers — it **misses
`aitask_gate.sh`**, whose task-file write happens through `lib/ledger_block.sh`'s
`mv` (`:240`, `:265`) and so matches no pattern in `aitask_gate.sh` itself. The
grep is a starting point; the table, not the grep, is the completeness control.

**Guard placement — earliest irreversible-side-effect point, plus the write choke
point.** The old plan said "entry point" uniformly. That is right for
`aitask_create.sh`, where the guard must precede the id claim (refusing *after*
still burns the id — F7's whole shape). But `aitask_update.sh` has a single write
choke point, `write_task_file()` (`:672`, three callers: `:1231` in
`handle_child_task_completion`, `:1761` interactive, `:2256` batch); guarding
*there* cannot be bypassed by a future fourth caller. So: **create → entry;
update → choke point *and* the two entry points**, the latter as the early, cheap
refusal.

**Message — consistent recovery clause, distinguishable first line.**
`assert_data_worktree_clean` (:345) emits
`Data worktree (.aitask-data) is stuck mid-<state>.` plus
`'--abort' below discards only the partially replayed remote commits; your own
committed work stays on the branch.` — and `tests/test_task_commit_scoped.sh:269`
**pins that exact string**. The new guard reuses that `--abort` clause verbatim
(t1725_1's note asks for consistency) but keeps its own distinctive first
sentence — *"the checked-out task files are not the branch tip, so writing now
would land on stale content"* — so the table rows can assert **this** guard fired
and not the commit guard.

**Legacy mode is covered.** The guard calls `_data_wedge_state`, not
`ait_data_inprogress_state`, so a legacy-mode repo mid-rebase is guarded —
which `assert_data_worktree_clean` deliberately is not (`:255`, `:651`).

**Consequence worth stating:** `aitask_gate.sh materialize-active` delegates its
task-file write to `aitask_update.sh --batch` (`aitask_gate.sh:1065-1071`), so
guarding batch mode makes the task workflow's Step 4 abort a pick on a wedged
worktree. That is the intended fail-safe direction, and a real behaviour change.

## Steps

### Pre-phase (risk mitigations) — lands with step 4

1. **[writer_entry_point_table]** Write `tests/test_task_data_writer_guard.sh` as
   a **table** *before* adding any guard call.

   **A row is one physical script, and every guarded script gets its own
   executable command-level row — no grouping.** All nine appear separately;
   `aitask_zip_old.sh` and `aitask_migrate_archives.sh` are two rows, not one.
   Where a script has more than one guarded entry point (`aitask_update.sh`
   batch + interactive; `aitask_create.sh` `--batch --commit` + `finalize_draft`;
   `aitask_note.sh` append + read-receipt; `aitask_gate.sh` `append` +
   `begin-procedure`) each entry point is its own row too — a script row that
   passes via one entry point must not vouch for the other.

   Row counts, so the table can be checked against them rather than eyeballed:

   | row kind | count | asserts |
   |---|---|---|
   | guarded scripts | **9** (≥13 rows, entry points counted separately) | non-zero exit, the guard's **own** message, file bytes unchanged (md5 before/after) |
   | exempt read-only | 3 — `aitask_ls.sh`, `aitask_query_files.sh resolve <id>`, `aitask_lock.sh --check <id>` | still runs under the wedge |
   | audited-but-not-guarded | **4** — `pick_own`, `usage_update`, `verified_update`, `add_model` | records the deliberate omission and its reason |
   | not-guarded by design | 3 — `aitasks/new/` drafts, recovery paths, `claim_id`/`lock` | as above |

   The table *is* the audit record: a writer missing from it is the hole.
   Rows fail until step 4 lands — commit them together.

   **Two gotchas to honor:**
   - Rows run in `( … )` subshells → `assert_counters_init` after sourcing
     `asserts.sh`, `assert_counters_load` in the footer before the
     `[[ "$FAIL" -eq 0 ]]` guard (CLAUDE.md / t1207).
   - `sync_fixture.sh` installs its **own** `trap _sync_fixture_cleanup EXIT`
     (:30). A second `trap … EXIT` for the counter file would **replace** it and
     leak a full `.aitask-scripts` copy per fixture. Install **one combined**
     EXIT trap after sourcing.

2. **[message_preemption_baseline]** Capture, before the guard lands, the current
   verdicts of the four tests that pin a wedge message —
   `test_task_commit_scoped.sh:269`, `test_task_push.sh:416`, `test_task_git.sh`
   Test 16, `test_sync_deferral_and_quarantine.sh:346-358`
   (`DEFERRED:worktree_wedged`) — and require them unchanged afterwards. An
   earlier `die` can silently replace a message another test owns. (Mirrors
   t1725_1's `characterize_wedge_guard`.)

### Main steps

3. **`lib/task_utils.sh`** — add `assert_task_data_writable()` beside
   `assert_data_worktree_clean` (:345). Returns 0 under
   `AIT_GIT_SKIP_STATE_CHECK=1`; otherwise `die`s when `_data_wedge_state` is
   non-empty, with the message settled above.

4. **Call it at the nine guarded scripts**, at these points (one table row per
   entry point, per the pre-phase's row rule):

   | script | insertion point | note |
   |---|---|---|
   | `aitask_update.sh` | `write_task_file()` `:672`; plus after `:1862` (`run_batch_mode`) and after `:1605` (`run_interactive_mode`) | both post-`resolve_task_file`; sources task_utils `:11` |
   | `aitask_create.sh` | `:2201-2204`, top of the `BATCH_COMMIT` branch (`:2200`) — **before** `add_labels_csv_to_file` `:2205`, `acquire_child_lock` `:2222`, `claim_unique_parent_id` `:2282`; and `finalize_draft` at `:829-830` | `:2205` is the first task-data mutation, earlier than the old plan's anchor. `:829` covers all four `finalize_draft` callers (`:969`, `:2097`, `:2111`, interactive `:2482`/`:2615`) |
   | `aitask_note.sh` | after `:920` (write path) and after `:770` (read receipt) | **outer level only.** `_note_append_inner` (`:440`) / `_note_read_inner` (`:593`) run in subshells whose `die` is reshaped into `NOTE_ERROR:` by the capture at `:519`/`:816` — guarding inside would swallow the message and break that contract |
   | `aitask_gate.sh` | after `:286` in `cmd_append` (`:266`), and the equivalent post-resolve point in `cmd_begin_procedure` (`:1201`) | both **outside** the lock; `_gate_append_locked` (`:312`) would be inside it |
   | `aitask_archive.sh` | `:802`, after `parse_args` `:801`, before `verification_gate_and_carryover` `:803` (which can create+commit a carryover task at `:709`) | **conditioned on `DRY_RUN != true`** — `archive_metadata_update` `:158-161` and `archive_move` `:182-185` short-circuit under `--dry-run`, making it read-only |
   | `aitask_plan_externalize.sh` | `:478`, after the `PLAN_EXISTS` (`:471-474`) / `NOT_FOUND` (`:455-457`) short-circuits | **needs a new `source lib/task_utils.sh` line** |
   | `aitask_verification_followup.sh` | before the `>> "$origin_plan"` appends at `:246`/`:248` | sources task_utils |
   | `aitask_zip_old.sh` | before the archive-bundle `mv` at `:241` | sources task_utils |
   | `aitask_migrate_archives.sh` | before the archive `mv`s at `:156` and `:310` | **needs a new `source lib/task_utils.sh` line** |

   **Deliberately not guarded**, each a table row:
   - Draft creation under `aitasks/new/` — `create_draft_file()` `:615`, rendered
     `:741`, reached from `:2317`. Gitignored (`aitask_setup.sh:2292-2294`), never
     committed, no id claimed: it is the one path that is *supposed* to work while
     the worktree is broken. `finalize_draft` is where it becomes task data.
   - Recovery / diagnostic paths — `aitask_metadata_commit.sh` `run_preflight`
     (`:127-136`, already exports the bypass), `aitask_sync.sh` `_worktree_wedged`
     (`:328-340`, `:1225-1236`) and its quarantine write (`:529`).
   - `aitask_claim_id.sh` / `aitask_lock.sh` — orphan-branch plumbing
     (`aitask-ids` / `aitask-locks`); no data-worktree file to guard.
   - The four metadata-only writers, per the scope decision above.

5. **`lib/task_utils.sh` — make the commit diagnostic reachable.** The old plan
   promised stderr carrying "the first non-blank git line", but
   `task_git_commit_scoped()` (`:448`) cannot supply it: it swallows `add`'s
   stderr outright (`task_git add -- "$@" >/dev/null 2>&1 || true`, `:467`) and
   returns a bare `1` from the commit (`:484`). Under an `index.lock` the
   *informative* message is precisely the swallowed `add` one — the commit then
   fails with a downstream "pathspec did not match any file(s) known to git".

   Add a diagnostic-preserving companion in the helper itself (not in the
   callers): a global `AIT_COMMIT_SCOPED_ERR`, **cleared at function entry** so a
   stale value from a previous call can never be reported, set from the captured
   stderr of `add` (when `add` failed) and of `commit`, and **still re-emitted to
   stderr** so today's visible behaviour is unchanged. Every existing caller
   (`aitask_archive.sh`, `aitask_issue_import.sh`, `aitask_pick_own.sh`) is
   unaffected — they simply do not read the global.

   **Capture through a temp file in the current shell; keep `task_git`.** Two
   designs are wrong here and both are tempting:

   - *Command-substituting `task_git`* — `task_git` calls
     `assert_data_worktree_clean`, which `die`s; a `die` inside `$( … )` exits
     only the *subshell*, downgrading a wedge to an ordinary commit failure.
   - *Swapping in the unguarded `_ait_data_git` after one outer assert* — the
     `task_push` pattern (`:804` → `:895`). It is legitimate **there**, but this
     helper is **shared**: `aitask_archive.sh`, `aitask_issue_import.sh` and
     `aitask_pick_own.sh` call it too. Dropping the per-operation guard would let
     those three run an unguarded git op — or classify its failure — against a
     worktree that wedged after the assert. That weakens a pre-existing safety
     contract for callers this task never touches, to buy a diagnostic only
     `aitask_create.sh` reads. Not acceptable.

   So: keep `task_git` (guarded execution preserved for **every** caller), and
   record stderr by redirecting to a `mktemp` file **in the current shell** —
   no subshell, so `assert_data_worktree_clean`'s `die` still exits the process
   exactly as today. Read the file into `AIT_COMMIT_SCOPED_ERR` and re-emit it to
   stderr after the call returns. Absorb the status with `|| rc=$?` on a
   pre-declared `local`, never a bare command under `set -e`.

   Call `assert_data_worktree_clean <verb> -- "$@"` **unredirected** immediately
   before each redirected `task_git`, so an already-wedged worktree is refused
   with its message on the terminal rather than into the temp file.

   **Stated residual:** if the worktree wedges inside the window between that
   assert and `task_git`'s own, the guard's message lands in the temp file and
   the process exits before the flush — a loud nonzero exit with no explanatory
   line. The refusal itself is intact (that is the safety-critical half); only
   the explanation is lost, and `ait git-health` still reports the state. Closing
   it would need an EXIT trap in a shared helper, which would clobber callers'
   traps (`aitask_create.sh`'s `_child_lock_exit_trap`) and collide with
   `ledger_block.sh`'s trap-must-be-first invariant. Not worth it; recorded, not
   pretended closed.

   This residual is load-bearing for the tests: verification **E2** is the row
   that lands in this window, so it asserts the refusal shape and stays silent
   about the message. Do not write a test that requires the guard's message
   there — and do not write one that requires its *absence* either, or a later
   live-forwarding fix would break it.

   **Second consequence, deliberately left to a follow-up: the temp file leaks on
   that path.** `mktemp` has already created it when the guarded `task_git` dies,
   so `rm -f "$errf"` never runs — likewise on any signal during the commit. The
   residue is a few private bytes in `TMPDIR`, recoverable and harmless, and
   cleaning it up needs an age policy, a `find` predicate this repo has no
   precedent for, and its own negative-control test — all outside AC4/AC5. Use a
   distinctive `mktemp` template (`ait_commit_scoped_err.XXXXXX`) **so the
   follow-up has a prefix to key on**, and stop there. See "Deferred, with
   owners".

6. **`aitask_create.sh` commit failure after the file is written** — do not `die`.
   Both commit sites currently `die "commit failed for ${task_id}"` (child
   `:2271`, parent `:2308`).

   **No re-check here — the helper already guarantees it.** An earlier draft of
   this plan had the failure branch re-call `assert_task_data_writable` before
   treating a failure as recoverable. With step 5 keeping `task_git` guarded that
   is **unreachable**: the helper can only `return 1` from
   `task_git commit … || return 1`, and a wedged worktree makes that `task_git`
   `die` and exit the process, so control never arrives at the failure branch
   with a wedge in effect. A fallback with no reachable trigger is dead code that
   reads as protection; it is deliberately omitted, and the guarantee is pinned
   by section E instead.

   The failure branch therefore means exactly "git refused for a non-wedge
   reason" (index lock, hook, pathspec) — which *is* recoverable. So: keep the
   file, warn on stderr —
   *"task file written but NOT committed (\<first non-blank line of
   `$AIT_COMMIT_SCOPED_ERR`\>) — it will be swept into the next sync's auto-commit
   under its own task id; do not re-run create"* — skip
   `run_auto_merge_if_needed`, and **fall through** to the shared Output block at
   `:2325-2330`.

   **Fall through, do not `exit 0` inside the branch.** The Output block is the
   single site that emits `$filepath` under `--silent` and `Created: $filepath`
   otherwise; reaching it by fall-through makes both modes match their success
   counterparts *by construction* rather than by a duplicated `echo` that can
   drift.

   **Child branch — the lock must be released explicitly.** Today
   `die` at `:2271` fires the `_child_lock_exit_trap` armed at `:2223`, which is
   what releases the lock. Removing the `die` removes that safety net, so the new
   path must do what the parent-not-found branch at `:2229-2233` already does:
   release the lock, then `trap - EXIT`, then continue — in that order, and
   before the Output block. Use `release_child_lock_checked` (as the success path
   at `:2277` does) so a failed release is still loud.

   `run_auto_merge_if_needed` has **four** call sites (`:893`, `:947`, `:2275`,
   `:2312`), not the two the old plan implies; each must be reached only on the
   success branch.

7. `shellcheck` every touched script.

## Verification

`bash tests/test_task_data_writer_guard.sh` — the pre-phase table, plus:

**A. Six-state coverage of the guard itself** (function level, not command level).
`_data_wedge_state` reports all six `AIT_GIT_INPROGRESS_STATES`, and the guard's
message interpolates the state — but the command-level rows below plant only
`rebase-merge`, so a regression in the lookup or message path for merge,
cherry-pick, revert or bisect would pass every one of them. Test 16
(`test_task_git.sh:774-871`) does not close this: it proves the *older*
`assert_data_worktree_clean`, a different function reached by a different
git-dir resolver. So: source `task_utils.sh`, and for each of the six states —
using Test 16's `"name:dir"|"name:file"` planting table and its
`( … ) && echo allowed || echo refused` subshell probe —

  - a **negative control before planting** (guard allows),
  - after planting: refused,
  - the message names **that** state (`mid-MERGE_HEAD`, `mid-CHERRY_PICK_HEAD`,
    … — never a merge announced as a rebase),
  - `AIT_GIT_SKIP_STATE_CHECK=1` bypasses,
  - per-state cleanup `rm -rf "${GITDIR:?}/$state"`.

  Plus the one behaviour Test 16 structurally cannot cover: **legacy mode.**
  `assert_task_data_writable` calls `_data_wedge_state` (legacy-aware, `:289`)
  where `assert_data_worktree_clean` calls `ait_data_inprogress_state`
  (branch-mode only, `:259`). Plant a wedge in a legacy-mode repo's own git-dir
  → the new guard refuses, the old one does not. That assertion *is* the
  difference between the two functions.

**B. Command-level rows** (representative `rebase-merge` case):

- **F6 reproduction.** Commit `status: Implementing` + `active_gates` locally;
  plant the wedge with the checked-out file at the stale `Ready` version →
  `aitask_update.sh --batch <id> --risk-code-health low` exits non-zero, the
  message names retry / abort, file bytes unchanged (md5), nothing committed.
- **Negative control.** The same update on a clean worktree succeeds.
- **F7, wedge.** `aitask_create.sh --batch --commit …` exits non-zero **before**
  claiming — `aitask_claim_id.sh --peek` byte-identical before and after, no file
  written.

**C. F7 commit failure — parent branch.** Plant `index.lock` in the data
worktree's admin git-dir (`git -C .aitask-data rev-parse --absolute-git-dir`, per
`test_task_commit_scoped.sh:261` — never hardcode `.git/worktrees/-aitask-data`).
No test plants a *worktree* index.lock today; `test_gate_active_gates.sh:295-315`
is the only precedent and it is a plain `.git`. **Assert the mutation actually
landed** — that the commit really failed — before trusting the row, or it passes
vacuously. Then:

  - stdout in **`--silent`** mode is byte-identical to the successful `--silent`
    run's shape (the bare path, nothing else);
  - stdout in **normal** mode is byte-identical in shape to a successful normal
    run (`Created: <path>`) — the drift the old plan's silent-only wording would
    have missed;
  - exit 0; stderr carries "NOT committed" **and the actual git diagnostic**
    (assert the exact composed warning, so a `AIT_COMMIT_SCOPED_ERR` that comes
    back empty fails the test rather than yielding a message with an empty
    parenthetical);
  - `--peek` advanced by **exactly one**;
  - remove the lock, `aitask_sync.sh --batch` → committed under
    `ait: Auto-commit t<id> task data before sync` (`aitask_sync.sh:745`),
    asserted via `data_log()` / `commit_files_for()`. A second create is never
    needed — pinned by the peek delta.

**D. F7 commit failure — child branch** (its own row; the parent row does not
cover it). Force the failure on a `--parent <N>` create, then:

  - the same stdout/stderr/exit-0 assertions as C, in **both** modes;
  - **prove the child lock was released** by creating the *next* child
    successfully immediately afterwards — a stale lock would block it. Asserting
    "no lock file" is weaker; the successful next create is the behavioural
    proof, and it also pins that `get_next_child_number` advanced rather than
    re-issuing the failed child's number.

**E. A wedge at commit time is refused, not absorbed.** This is the property
step 6 relies on to be allowed to have no re-check of its own, so it is proven
rather than reasoned about. It splits into two rows because step 5's capture
makes the two cases genuinely different — conflating them would write a test the
intended implementation cannot pass.

**E1 — already wedged when the helper is entered** (the common, user-facing
case). The unredirected preflight assert fires, so the message *is* on the
terminal. Assert: nonzero exit, the guard's own message on stderr, no "NOT
committed" warning, **no path on stdout**, nothing committed, task file retained.

**E2 — wedge opens after the preflight** (the injected race). The seam must sit
**inside `task_git_commit_scoped`, after its preflight assert and before the
guarded `task_git` call** — a seam in `aitask_create.sh` ahead of the helper
would be caught by the preflight and go red for E1's reason, making the mutant
non-discriminating. Follow the `AIT_SYNC_SEAM_<point>` precedent
(`tests/test_sync_deferral_and_quarantine.sh:59-71`): one
`AIT_COMMIT_SCOPED_SEAM_PREGIT` hook, inert when unset, which the test uses to
plant `rebase-merge`.

Assert the **refusal shape only**: nonzero exit, **no path on stdout**, no "NOT
committed" recovery warning, nothing committed, task file retained.

E2 deliberately asserts **nothing either way about the guard's message.** This is
the window step 5 records as a residual — the inner `die`'s stderr is in the temp
file and the process exits before the flush — so requiring the message would
reject the intended implementation. Asserting its *absence* would be worse still:
it would pin the residual as a contract and break the day someone implements live
stderr forwarding. The row is silent on it, with a comment saying why.

The discriminating assertion in both rows is the **absence of the recovery
warning and of a path on stdout** — absorbing the wedge would produce exit 0, a
path, and "NOT committed". So the mutant still bites: swap `task_git` →
`_ait_data_git` inside the helper and E2 goes red while every other row stays
green. That also guards the contract for `aitask_archive.sh`,
`aitask_issue_import.sh` and `aitask_pick_own.sh`, which share the helper and
have no re-check of their own.

**F. Per-part mutants.** Each part of the change must be falsified by rows that
no other part's assertions can carry:

| revert | must fail |
|---|---|
| the guard function / its call sites | the F6 row in B, and all of section A |
| the commit-failure branch (restore `die`) | C and D |
| the `AIT_COMMIT_SCOPED_ERR` plumbing only | the exact-warning assertions in C and D — while their exit-0 / stdout assertions still pass |
| the child-lock release + `trap - EXIT` only | D's next-child-creation proof — while D's stdout assertions still pass |
| `task_git` → `_ait_data_git` in the shared helper | E2 — and nothing else |
| the unredirected preflight assert in step 5 only | E1's message assertion — while E1's exit/stdout assertions still pass |

**Regression sweep (message pre-emption + hot paths):**
`tests/test_task_git.sh`, `tests/test_task_push.sh`,
`tests/test_task_commit_scoped.sh`, `tests/test_sync_deferral_and_quarantine.sh`,
`tests/test_create_silent_stdout.sh`, `tests/test_update_check.sh`,
`tests/test_claim_id.sh`, `tests/test_gate_active_gates.sh`.

## Risk

### Code-health risk: medium
- The guard adds ≥13 call sites across 9 scripts, several on hot paths (every
  update, create, gate append and note). A missed entry leaves the hole; an
  over-broad one blocks legitimate work — the `--dry-run` and `aitasks/new/`
  carve-outs are the two known traps · severity: medium ·
  → mitigation: inline pre-phase `writer_entry_point_table`
- An earlier `die` can pre-empt a wedge message four existing tests pin ·
  severity: medium · → mitigation: inline pre-phase `message_preemption_baseline`
- `aitask_plan_externalize.sh` and `aitask_migrate_archives.sh` gain a
  `source lib/task_utils.sh` line, which now transitively pulls `stale_lock.sh`
  (t1725_1) — a new load-time dependency in two scripts that had none ·
  severity: low · → mitigation: covered by the table rows, which execute both
- Step 5 modifies `task_git_commit_scoped()`, a **shared** helper with three
  other callers (`aitask_archive.sh`, `aitask_issue_import.sh`,
  `aitask_pick_own.sh`). The added global is inert for them, but the stderr
  capture sits on the path where `assert_data_worktree_clean` `die`s: both a
  command substitution and a swap to the unguarded `_ait_data_git` would weaken
  the wedge refusal for callers this task never touches · severity: medium ·
  → mitigation: temp-file capture in the current shell keeps `task_git` guarded
  (step 5); section E's mutant fails precisely on that swap; and
  `tests/test_task_commit_scoped.sh` is in the sweep
- The temp-file capture leaves a documented residual: a wedge opening inside the
  assert→`task_git` window loses the guard's explanatory line (the refusal
  itself survives) · severity: low · → mitigation: none — recorded in step 5
  rather than closed, since the fix needs an EXIT trap in a shared helper
- The same window (and any signal during the commit) leaks the `mktemp`
  diagnostic file, since `die` exits before cleanup · severity: low ·
  → mitigation: **deferred** — see "Deferred, with owners"; the residue is a few
  private bytes in `TMPDIR`, and the distinctive template this plan adopts is
  what makes the follow-up cheap

### Goal-achievement risk: low
- AC4 asks for "refused **or reconciled**"; this delivers *refused*, and only for
  the wedge. A stale base reached any other way stays unguarded — a deliberate,
  recorded bound (the parent plan's scope decision), not a gap · severity: low
- AC5 is satisfied by removing the caller's *reason* to retry (exit 0 + the path),
  not by preventing a retry outright. The `--peek` delta pins the behaviour ·
  severity: low
- The F7 commit-failure row depends on an index.lock technique with no
  worktree-admin-dir precedent; if the lock does not actually fail the commit the
  row passes vacuously · severity: medium ·
  → mitigation: assert-the-mutation-landed, folded into the row itself

### Planned mitigations (both confirmed inline — no spawned tasks)
- timing: pre-phase | name: writer_entry_point_table | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — a missed writer entry leaves the hole, an over-broad one blocks legitimate writes | desc: table one row per guarded writer, per exempt read-only script, and per audited-but-not-guarded writer, written before any guard call
- timing: pre-phase | name: message_preemption_baseline | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — an earlier die can replace a wedge message four tests pin | desc: record the current verdicts of test_task_commit_scoped.sh:269, test_task_push.sh:416, test_task_git.sh Test 16 and test_sync_deferral_and_quarantine.sh:346-358 before the guard lands; require them unchanged after

## Deferred, with owners

Real, found while verifying this plan, recorded so it is not lost. Created as a
follow-up task at Step 8d.

| finding | disposition |
|---|---|
| `task_git_commit_scoped`'s `mktemp` diagnostic file leaks whenever the guarded `task_git` `die`s or the process is signalled — cleanup is never reached. Fixing it needs an age policy, a `find -mmin` predicate the repo has no precedent for (macOS behaviour unconfirmed), and a negative-control test proving the prune cannot delete a concurrent session's *live* diagnostic — all outside AC4/AC5 | **new follow-up task** — `commit_scoped_diagnostic_prune`. Keyed on the `ait_commit_scoped_err.XXXXXX` template this plan adopts. Must carry the macOS `find -mmin` confirmation and a fallback, plus the fresh-file negative control |

## Notes to send at Step 8

- **t1725_6** (user-facing docs) — `website/content/docs/commands/sync.md:235`
  documents `AIT_GIT_SKIP_STATE_CHECK=1`; a second guard now honors it, and the
  new refusal is a user-visible failure mode worth a line.

## Step 9

Standard post-implementation; parent t1725 archives after the last child.

## Final Implementation Notes

**Delivered:** `assert_task_data_writable()` (`lib/task_utils.sh`) called at **16
sites across the 9 guarded scripts**; `AIT_COMMIT_SCOPED_ERR` plumbed through
`task_git_commit_scoped`; all four `create` commit-failure sites converted from
`die` to the recoverable branch. `tests/test_task_data_writer_guard.sh`, 148
assertions, green.

**Deviations from the plan, both deliberate:**

1. **Four commit-failure sites, not two.** The plan named the `--batch --commit`
   pair (`aitask_create.sh:2282`, `:2319`). `finalize_draft` has the *identical*
   defect at `:895` / `:949` — it claims an id, deletes the draft, writes the
   file, then `die`s on a failed commit — and it is the most literal reading of
   AC5's "fails after the draft is written". Fixing two of four would have left a
   known hole in the delivered fix, so all four now route through one shared
   `warn_task_written_not_committed` helper.
2. **`tests/test_migrate_archives.sh` gained a fixture line.** Its scaffold copies
   only `aitask_migrate_archives.sh` + `archive_utils.sh`, so the new
   `source lib/task_utils.sh` killed the script at startup (the source-on-startup
   ↔ test-scaffold rule, `shell_conventions.md`). `test_plan_externalize.sh` was
   unaffected — it already had task_utils in scope. 28/28 after.

**Two defects caught in self-review of the diff, after the tests were green:**

- **`git add`'s stderr was being re-emitted unconditionally.** It had been fully
  suppressed (`2>&1 >/dev/null || true`), so re-emitting would have started
  surfacing previously silent warnings for all four callers of the shared helper.
  Now recorded *and* echoed only when `add` actually fails; dropped on success,
  exactly as before.
- **The test seam was gated on an env var alone.** `aitask_sync.sh`'s
  `_sync_test_seam` (`:275-287`) gates on the variable **and** an on-disk marker,
  and warns loudly — because a stray or inherited variable must never be able to
  `eval` inside a helper that runs in four production scripts. The seam now
  matches that two-gate shape (`.ait_commit_scoped_test_seams`), and the test
  asserts both that it planted the marker and that `TEST SEAM ACTIVE` appeared,
  so an inert seam cannot make E2 pass for the wrong reason.

**Two blocking review concerns, both confirmed and fixed:**

1. **Unchecked `mktemp` in `task_git_commit_scoped`.** The reported mechanism was
   a `set -e` abort after the id was claimed. The *measured* mechanism is
   subtler and still harmful: every caller invokes the helper as
   `… || crc=$?`, and bash suppresses `set -e` inside a function called in an
   AND-OR list, so it does not abort — instead `_ait_cs_errf` is empty, `2>""` is
   an ambiguous redirect, **the commit never runs, and a perfectly healthy commit
   is reported as failed**, leaving the file uncommitted with a spurious "NOT
   committed". Fixed by allocating into `_ait_cs_errf` with `2>/dev/null || …`
   and routing both git calls through `_ait_cs_sink="${_ait_cs_errf:-/dev/null}"`
   — one code path, and the `rm` is guarded on `_ait_cs_errf` so it can never
   target `/dev/null`. Pinned by D3 (function level, both the commit-succeeds and
   commit-fails cases).
2. **The table did not cover every guarded entry point**, despite the plan saying
   it must. Added rows for `run_interactive_mode`, `finalize_draft` (guard), and
   `zip_old unpack`, plus `finalize_draft`'s own parent and child
   commit-failure branches (D2) with its own lock-release assertion. **The
   interactive guard also moved** to the first statement of
   `run_interactive_mode`, ahead of the `fzf` dependency check: it refuses before
   making the user pick a task and fill in a field, and that is what makes the
   entry point reachable headlessly for the table.

**Audited, not guarded** (recorded as table rows, not oversights):
`aitask_pick_own.sh`, `aitask_usage_update.sh`, `aitask_verified_update.sh`,
`aitask_add_model.sh` — metadata-only, and `pick_own` runs on every pick;
`aitasks/new/` drafts (gitignored, no id, never committed); recovery paths
(`aitask_metadata_commit.sh --preflight`, `aitask_sync.sh`'s wedge detection and
quarantine); `aitask_claim_id.sh` / `aitask_lock.sh` (orphan-branch plumbing, no
worktree file). `--dry-run` is exempt in `archive`, `zip_old` and
`migrate_archives`, which are read-only under it.

**Mutation testing — every part independently falsified.** Three mutants passed
on the first attempt and were *test* defects, not proof of correctness:

| mutant | kills | note |
|---|---|---|
| guard neutered | 48 (all of A + F6) | — |
| `die` restored at all 4 sites | 11 | mis-applied first: finalize sites are 12-space indented, batch 16-space, so only the untested pair was patched. **Verify the mutation landed.** |
| `AIT_COMMIT_SCOPED_ERR` removed | 5 | survived first: the helper re-emits git's stderr anyway, so asserting `index.lock` anywhere in the capture was **vacuous**. Now asserts the composed warning *line*. |
| child-lock release removed | 1 | survived first: a lock leaked by an exited process is reclaimed by `stale_lock`'s reaper, so "the next child creates fine" proves nothing. Now asserts the lock **directory** is gone. |
| `task_git` → `_ait_data_git` | 3 (E2 only) | survived first: the seam sat *before* the explicit preflight, so E2 tested that assert rather than `task_git`'s own. Seam moved after it. |
| helper preflights removed | 1 (E1b only) | E1 covers `create`'s guard, which fires long before the helper; E1b was added for the helper itself. |
| unchecked `mktemp` restored | 1 (D3a) | survived first: the mutant kept the `:-/dev/null` fallback, i.e. the part that makes it safe. Rebuilt to the true pre-fix form. |
| interactive-entry guard removed | 1 | — |

**`message_preemption_baseline` satisfied:** `test_task_git` 105, `test_task_push`
346, `test_task_commit_scoped` 63, `test_sync_deferral_and_quarantine` 52 — all
identical before and after. No existing wedge message was pre-empted.

**Upstream defects identified:**

- `aitask_create.sh:1046` — `claim_parent_id_once()` allocates `claim_stderr` with
  an unchecked `mktemp`, and the failure is invisible because the caller runs it
  inside a command substitution (`claimed_id=$(claim_unique_parent_id …)`), where
  a `die` exits only the subshell. With an unusable `TMPDIR` the id claim fails,
  create carries on with an **empty** id, and writes `aitasks/t_<name>.md` —
  a task file with no id at all — then exits 0 reporting `Created:`. Same
  unchecked-`mktemp` class as the defect fixed here, and the same
  die-inside-`$( )` swallow this plan documents; found by the failing-TMPDIR test
  the review asked for. Out of scope for AC4/AC5 (the guard and the retry path),
  and it is why D3 is driven at function level rather than through `create`.

**Issues encountered:**

- `tests/test_draft_finalize.sh:282` is **flaky, pre-existing**: it derives ids
  with `ls … | grep -oE 't[0-9]+'` over full paths, so a `mktemp -d` directory
  whose name happens to contain `t<digits>` inflates the unique-id count and the
  "All task IDs are unique" assertion fails. Seen once; three consecutive re-runs
  green. A test defect rather than a product one, so it is recorded here rather
  than as an upstream defect.

**Sweep:** the four above plus `test_create_silent_stdout` 14,
`test_update_check` 7, `test_claim_id` 54, `test_gate_active_gates` 114,
`test_draft_finalize` 38, `test_note_append` 121, `test_note_read_receipts` 74,
`test_note_section_order` 20, `test_plan_externalize` 264,
`test_migrate_archives` 28, `test_gate_record` 16, `test_gate_recorded_pass` 32,
`test_zip_old` 72, `test_verification_followup` 42 (+12 anchor), `test_archive_*`
86. shellcheck: zero new warnings (task_utils 8→8, update 1→1 pre-existing).
