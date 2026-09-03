---
Task: t1702_board_task_commits_need_a_pathspec.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1702 — Board task commits need a pathspec

## Context

`ait board` writes task/plan files and commits them with a **pathspec-less**
`git commit` against the **shared `.aitask-data` index**. Every session on the
machine shares that index, so a bare commit takes whatever anyone else staged
and publishes it under the board's message. This is the same defect class t1599
closed for `ait sync`, `aitask_pick_own.sh`, `aitask_create.sh` and
`aitask_fold_mark.sh`, and that t1677 refused to copy into Python.

### Call sites — re-derived (line numbers differ from the task body)

| site | line | what it commits |
|---|---|---|
| `KanbanApp._do_delete` | `.aitask-scripts/board/aitask_board.py:13858` | `ait: Delete task <n> and associated files` |
| `KanbanApp._do_rename_task` | `:13970` | `ait: Rename <n>: <name>` |
| `KanbanApp._do_git_commit_tasks` | `:14012` | the user's commit-dialog message |

All three are `[*_task_git_cmd(), "commit", "-m", …]` with no `--` pathspec.
No other Python commit site in the tree is in scope:
`agentcrew_utils.py::git_commit_push_if_changes` deliberately does `add -A`
inside a **private per-agent worktree**, not the shared data index.
`aitask_archive.sh:283,565,645` *are* the same defect but live in shell, outside
this task — surfaced as a follow-up below.

### The trap this fix must not spring

`_do_delete` currently relies on the commit being index-wide. Before it commits
it runs two uncommitted writers:

- `aitask_update.sh --batch <parent> --remove-child …` → rewrites the **parent
  task file** (`:13825`);
- `_unfold_deleted_primary_children` → `aitask_update.sh --batch <fid> --status
  Ready --folded-into ""` → rewrites each **revived folded task file**
  (`:13756`).

Neither passes `--commit`. Scoping the delete commit to only the doomed paths
would leave those writes dirty and **ownerless** — exactly the permanent
rebase-deferral state t1599_3 quarantines. The pathspec must be widened to
include them.

(`aitask_attach.sh decref-deleted` already self-commits path-limited, so it
needs nothing.)

### The second direction of the same race

`_do_delete` also calls `git rm -f` (`:13831`), and `git rm` removes the file
from the working tree **and from the index**. So the operation parks staged
deletions in the shared `.aitask-data` index for the whole window before its own
commit, where any concurrent index-wide commit — including the board's *own*
archive gesture (`:13661` → `aitask_archive.sh`, deferred by this plan) — will
publish them under a foreign message. Adding a pathspec to the commit closes the
swallow in one direction only; the staging must go too.

**A scoped commit is not enough on its own: an operation must also stage
nothing it does not have to.** `commit -o` takes worktree content for tracked
paths, so a deletion needs no index entry at all. Staging is unavoidable only
for an *untracked* path (a pathspec cannot name a file git does not know), and
that residue is what §1's cleanup contract covers.

---

## Implementation

### Pre-phase (risk mitigations)

1. `[characterize_delete_commit_contents]` Against **today's** unmodified code,
   in a throwaway git fixture, run a board child-task delete that also revives a
   folded task, and record `git show --stat HEAD`. Write the measured file list
   into `tests/test_board_scoped_task_commit.py`'s module docstring as the
   pathspec the fixed `_do_delete` must reproduce. The widened pathspec is then
   derived from measurement, not from reading the source.
2. `[probe_commit_o_pathspec_classes]` In a scratch git repo, pin the behaviour
   of `git commit -o -m … -- <path>` for each class: (a) tracked-but-deleted,
   (b) untracked-existing, (c) never known to git, (d) empty pathspec. Record
   the answers as comments at the top of `aitask_task_commit.sh`'s
   classification loop, so its rules are measured rather than assumed.

### 1. `.aitask-scripts/lib/task_utils.sh` — one shared staging/commit core

Add next to `task_git_commit_scoped`:

```bash
# ait_commit_paths_staging_untracked <msg> <path>... — commit exactly these
# paths, staging ONLY the ones git does not track yet, and unstaging exactly
# those again on ANY failure.
#
# The .aitask-data index is SHARED by every session on the machine: an
# unconditional `add` of a tracked path can replace an entry another session
# staged. `commit -o` needs no staging for a tracked path, so only an untracked
# one is ever added — and a path left staged is worse than a dirty one
# (invisible to the ownerless report, rides the next index-wide commit), so the
# cleanup is scoped to entries THIS call created.
#
# Returns 0 committed, 2 verified nothing to commit, 1 failed.
ait_commit_paths_staging_untracked() { … }

# ait_unstage_staged_by_us — the ONE cleanup path. Resets exactly the entries
# recorded in AIT_STAGED_BY_US (every one verified untracked before staging, so
# the reset has no HEAD version to restore) and empties it, so it is idempotent.
ait_unstage_staged_by_us() { … }
```

Three rules make the cleanup total, because a partial staging run and an aborted
process leave the same wreckage:

1. **Pre-flight the abort.** `assert_data_worktree_clean` (`task_utils.sh:236`)
   treats `add`/`commit`/`reset` as non-readonly and **`die`s** — exiting the
   process — while `ls-files` is readonly. So the first `add` is the first call
   that can abort, and it can abort *mid-loop*. Call
   `assert_data_worktree_clean commit` once **before** the staging loop, so that
   die lands with nothing staged.
2. **Fail fast, then clean.** The staging loop records each path into
   `AIT_STAGED_BY_US` **as it is staged**; a failing `add` calls
   `ait_unstage_staged_by_us` and returns 1 immediately rather than continuing
   into a commit that cannot succeed anyway.
3. **Cover the abort that is left.** Each helper script installs
   `trap 'ait_unstage_staged_by_us' EXIT` **before** its first call, so a signal
   or an unforeseen `die` still unwinds this invocation's entries. The trap
   lives in the scripts, not the library, so it cannot clobber a caller's own
   EXIT trap; both callers set none today.

Body = the block currently inlined in `aitask_metadata_commit.sh::main`
(stage-untracked → `task_git_commit_scoped --no-stage` → `task_git reset` the
entries we staged), plus the three rules above. **Migrate
`aitask_metadata_commit.sh` onto it in the same commit** — this is subtle
correctness logic and must exist once, not twice. Its external behaviour is
unchanged and pinned by `tests/test_metadata_commit_seam.sh`.

### 2. New `.aitask-scripts/aitask_task_commit.sh`

The task/plan-file analogue of `aitask_metadata_commit.sh`. Differences, all
deliberate:

- **scope** = `${TASK_DIR:-aitasks}/` or `${PLAN_DIR:-aiplans}/`; absolute paths
  and `..` segments refused (fail-closed, same as the metadata helper);
- **message is caller-supplied** (`-m <msg>`) — delete/rename/dialog messages
  differ, so there is nothing to derive;
- **untracked-but-existing paths are accepted without a flag.** A new task file
  is a *normal* board commit (`refresh_git_status` collects `??` entries), so an
  `--allow-new` gate would be always-passed dead weight. The scope check is what
  bounds it;
- **untracked-and-missing paths are dropped** (`SKIPPED:unknown:<path>`). The
  delete path falls back to `os.remove` when `git rm` fails, and `commit -o --`
  fails *outright* on a pathspec git has never seen — one such path would abort
  the whole commit.

Output contract (stdout is a data channel), mirroring the metadata helper:
`COMMITTED:<n>:<subject>` / `NOCHANGE` / `SKIPPED:unknown:<path>` /
`REFUSED:out_of_scope:<path>` / `FAILED:<detail>`; exit `0|2|1`. **Never
pushes.**

No allowlist / `ait` dispatcher entry — its only caller is a Python TUI
(`aidocs/framework/aitasks_extension_points.md:321`), same as
`aitask_metadata_commit.sh`.

Bonus: routing through `task_git` picks up `assert_data_worktree_clean`, which
the board's raw `git -C .aitask-data commit` currently bypasses.

### 3. New `.aitask-scripts/lib/task_commit.py`

Thin wrapper, shaped exactly like `lib/metadata_commit.py` (which the board
already imports at `:67`):

- `commit_command(message, paths, *, root=None) -> (argv, cwd)` — pure
  resolution seam, unit-testable without git;
- `remedy_command(message, paths) -> str` — built *through* `commit_command` so
  the advertised command cannot drift from the one run;
- `commit_task_paths(message, paths, *, root=None, timeout=15) -> CommitResult`
  — `CommitResult(status, subject, detail)`; **never raises on a git failure**
  (the write already landed on disk), raises `ValueError` on an empty path list
  because an empty pathspec is the bug itself.

### 4. Board wiring — `.aitask-scripts/board/aitask_board.py`

Add `from task_commit import commit_task_paths, remedy_command as task_remedy_command`
beside the existing `metadata_commit` import.

Module-level resolver (glob, not manager state, so it is valid inside a worker):

```python
def _task_file_paths_for_ids(ids) -> list[str]:
    """Resolve bare task ids to their on-disk task files (parent or child)."""
```

**(a) `_execute_delete` / `_do_delete`** — two changes.

*Stop staging.* Replace the `git rm -f` loop + `os.remove` fallback (`:13830-40`)
with a single worktree unlink:

```python
for path in paths:
    try:
        os.remove(path)
    except OSError:
        pass          # already gone, or never existed — the seam drops it
```

The scoped `commit -o` records a tracked path's deletion from worktree state
(`task_utils.sh:355`: "a pure deletion needs no staging at all"), and an
untracked one is dropped by §2's classification. The delete operation therefore
touches the shared index **only** through its own commit — closing the second
direction of the race. The tracked/untracked branch `git rm`'s exit status used
to provide is no longer needed by the caller; the helper classifies.

`_do_archive`'s `git rm` (`:13661`) is deliberately **left alone**: its commit is
`aitask_archive.sh`'s index-wide one, which *depends* on the staging. The
spawned `archive_sh_pathspec_scope` follow-up owns both halves of that site.

*Widen the pathspec.* `_execute_delete` additionally resolves the *co-written*
paths and passes them to the worker:

- the parent task file, via `_task_file_paths_for_ids([parent_num])`, when
  `parent_num` is set;
- each revived folded task file, via `_task_file_paths_for_ids(folded_ids)`.

`_do_delete` commits `paths + extra_paths` (order-preserving dedup) through
`commit_task_paths`.

**(b) `_do_rename_task`** — drop both explicit `git add` calls; pass
`[old_task, new_task]` plus `[old_plan, new_plan]` when a plan was renamed. The
seam stages the untracked *new* paths; the tracked-and-now-missing *old* paths
need no staging (`commit -o` records the deletion from worktree state).

**(c) `_do_git_commit_tasks`** — drop the per-path `git add` loop; pass
`filepaths`. Scope is the task files the dialog listed, so a dirty *plan* file
no longer rides along — that is the intended bystander exclusion, and the
message names tasks.

All three map the result the same way, following `_notify_metadata_commit`
(`:8908`): `committed` → the existing success toast; `nochange` → a
`warning` "Nothing to commit"; `failed` / `refused` → `error` naming
`task_remedy_command(...)`, never silent.

### 5. Docs

`aidocs/framework/tui_conventions.md` — extend the "an explicit save commits"
section with the task/plan-file rule: always
`./.aitask-scripts/aitask_task_commit.sh` (Python:
`lib/task_commit.commit_task_paths`), never a hand-rolled
`subprocess.run([..., "commit", ...])`. Plus the two rules review surfaced:

- a scoped commit must name **every file the operation wrote**, not only the
  ones it deleted — otherwise the writes it drops become ownerless;
- **scoping the commit is only half of it: stage nothing you do not have to.**
  `git rm` stages, and a staged entry sitting in the shared index is collectable
  by anyone's index-wide commit. Delete from the worktree and let `commit -o`
  record it; stage only an untracked path, and unstage it again on any failure.

---

## Verification

**New — `tests/test_task_commit_scoped.sh`** (helper level, real git fixtures):

- create / delete / rename shapes each commit only their own paths while a
  **bystander** (a tracked file another session dirtied *and* staged) is absent
  from the commit and left staged;
- out-of-scope, absolute and `..` paths refused; **no arguments never reaches a
  commit**;
- an untracked-and-missing path is skipped rather than aborting the commit;
- **partial-staging failure leaves nothing staged.** Fault injected through a
  documented seam: two untracked paths, the second `.gitignore`d so `git add`
  refuses it. Assert non-zero exit, **no commit created**, and
  `git diff --cached --name-only` empty — the first path was unstaged again;
- **an aborted run leaves nothing staged.** Plant a `MERGE_HEAD` marker in the
  data gitdir so `assert_data_worktree_clean` dies, and assert the index is
  untouched — i.e. the pre-flight fired before the staging loop, not inside it;
- **the same run twice** — `ait_unstage_staged_by_us` is idempotent, so the
  script's EXIT trap firing after an explicit cleanup is a no-op;
- **negative control** — the same fixtures driven through a legacy pathspec-less
  `git commit -m`, asserting *positively* that the bystander **does** land.

**New — `tests/test_board_scoped_task_commit.py`** (board level, real git
fixture, real worker bodies via `__wrapped__` as in
`tests/test_board_dialog_subprocess_degrade.py`):

- each of `_do_git_commit_tasks`, `_do_delete`, `_do_rename_task` commits only
  its own paths, bystander untouched;
- `_do_delete`'s pathspec **includes** the parent task file and each revived
  folded task file (the regression §"the trap" describes);
- **`_do_delete` stages nothing.** Patch `ab.commit_task_paths` with a spy that
  snapshots `git diff --cached --name-only` at call time and then delegates to
  the real seam; assert the snapshot is empty, so the deletions were never in
  the shared index before the scoped commit. A second assertion re-runs it with
  a *foreign* staged entry present and asserts that entry survives untouched;
- **negative control** — patch `ab.commit_task_paths` with the pre-fix
  index-wide commit; every assertion above must flip;
- **source guard** — no `[*_task_git_cmd(), "commit"` literal remains in
  `.aitask-scripts/board/aitask_board.py`.

**Regression (the §1 migration):**
`bash tests/test_metadata_commit_seam.sh`,
`bash tests/test_setup_metadata_commit_scope.sh`,
`bash tests/test_pick_own_scoped_commit.sh`,
`python3 tests/test_metadata_writer_inventory.py`.

**Lint / suite:** `shellcheck .aitask-scripts/aitask_task_commit.sh
.aitask-scripts/lib/task_utils.sh .aitask-scripts/aitask_metadata_commit.sh`;
`bash tests/run_all_python_tests.sh`.

**Manual:** in `ait board`, with a second shell holding a staged foreign edit
under `.aitask-data`, exercise commit / rename / delete and confirm
`./ait git show --stat HEAD` lists only the operation's own files.

Post-implementation cleanup, archival and merge follow **Step 9**.

---

## Risk

### Code-health risk: medium

- Scoping `_do_delete` drops the parent-task and revived-folded-task writes
  unless the pathspec is widened, leaving ownerless dirty files — the exact
  state t1599_3 quarantines · severity: high · → mitigation: inline pre-phase
  characterize_delete_commit_contents
- `commit -o --` aborts outright on a pathspec git has never seen; a wrong
  tracked/untracked/unknown classification breaks the delete path entirely
  rather than degrading · severity: medium · → mitigation: inline pre-phase
  probe_commit_o_pathspec_classes
- Migrating `aitask_metadata_commit.sh` onto the new shared shell function
  touches a shipped t1677 seam · severity: medium · → mitigation: covered by the
  pinned regression runs in Verification
- The three call sites are `@work(thread=True)` workers; a wiring change
  verified only by shape could pass while production commits nothing
  · severity: medium · → mitigation: covered by the real-worker-body tests and
  their negative control in Verification
- **[raised in review]** `git rm` in `_do_delete` parks staged deletions in the
  shared index, so a scoped commit alone leaves the race open in the opposite
  direction · severity: high · → mitigation: closed in design — §4(a) removes
  the staging; pinned by the "stages nothing" spy assertion
- **[raised in review]** Cleanup that runs only after a *commit* failure misses
  a partial staging run and a mid-loop `die`, stranding this call's entries in
  the shared index · severity: high · → mitigation: closed in design — §1's
  pre-flight + fail-fast + script-owned EXIT trap, one cleanup path; pinned by
  the injected partial-staging and aborted-run tests

### Goal-achievement risk: low

- The same defect remains in `aitask_archive.sh` (3 sites), so "the board never
  swallows a bystander" is true only for these three paths — the board's
  archive gesture still routes through that script · severity: medium
  · → mitigation: archive_sh_pathspec_scope

### Planned mitigations
- timing: pre-phase | name: characterize_delete_commit_contents | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — scoping _do_delete strands the parent/folded writes | desc: measure today's delete-commit file list in a fixture and pin it as the pathspec the fixed _do_delete must reproduce
- timing: pre-phase | name: probe_commit_o_pathspec_classes | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — commit -o aborts on an unknown pathspec | desc: pin `git commit -o --` behaviour for tracked-deleted / untracked-existing / never-known / empty pathspecs before writing the classification loop
- timing: after | name: archive_sh_pathspec_scope | type: bug | priority: medium | effort: low | inline_risk: high | added_complexity: medium | addresses: goal-achievement — the same defect remains in aitask_archive.sh | desc: route aitask_archive.sh's three pathspec-less `task_git commit` calls (lines 283, 565, 645) through the scoped seam, and retire the staged-deletion window its board caller opens with `git rm` at aitask_board.py:13661

### Reassessment (post-inline, post-review)

With both pre-phases inlined, the delete-pathspec and `commit -o`-classification
risks are measured before the code is written; the two review findings are
closed in the design rather than deferred, each with a failing-capable test.
**Code-health risk: medium** (the t1677 seam migration and the worker-level
wiring remain, both covered by Verification). **Goal-achievement risk: low**
(unchanged; the archive residue is now owned by a spawned follow-up — whose
scope grew to include that site's `git rm` staging as well as its pathspec).
