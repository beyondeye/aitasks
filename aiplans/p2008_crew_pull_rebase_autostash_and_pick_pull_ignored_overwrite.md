---
Task: t2008_crew_pull_rebase_autostash_and_pick_pull_ignored_overwrite.md
Base branch: main
Output branch: main
---

# t2008 — Pin `--no-autostash` on every crew-worktree pull

## Context

t1792 and t1987 stopped a user's `rebase.autoStash` / `merge.autoStash` from
changing how the task-data pulls behave. Before that, the setting would stash and
re-apply other live sessions' uncommitted files. The crew worktree
(`.aitask-crews/crew-<id>/`) has the same defect class at three pull sites:

| site | command | follows |
|---|---|---|
| `.aitask-scripts/aitask_crew_addwork.sh:328` | `git pull --rebase --quiet 2>/dev/null \|\| true` | `rebase.autoStash` |
| `.aitask-scripts/aitask_crew_setmode.sh:125` | same | `rebase.autoStash` |
| `.aitask-scripts/agentcrew/agentcrew_utils.py:296` `git_pull()` (runner, every iteration) | `git pull --rebase=false` | `merge.autoStash` |

The user chose to include the runner pull as well.

**The task's open question, answered by code reading:** yes, a crew worktree is
routinely dirty with *other live processes'* uncommitted tracked files:
- running agents' heartbeats (`<agent>_alive.yaml`, `agentcrew_status.py cmd_heartbeat`);
- non-terminal `ait crew status set` writes (`<agent>_status.yaml`, plus the
  `_crew_status.yaml` recompute); only terminal states commit;
- `ait crew command send` queue entries (`<agent>_commands.yaml`, never committed by the CLI).

The runner commits all of these later with `add -A`. So autostash can stash and
rewrite another agent's file, and a failed re-apply leaves a pending command or
heartbeat only in the stash. The fix is not just about determinism.

**Reachability:** no crew path sets an upstream (`aitask_crew_init.sh` creates the
branch locally; no `push -u` anywhere). Without one, `pull` dies with "no tracking
information" before any stash happens. The pulls therefore reach the rebase or merge
only when the user's config gives the branch an upstream: `push.autoSetupRemote=true`
(set on the first crew push) or a manual `push -u`. The fix holds either way, and
the tests must set an upstream, or they pass vacuously.

**Out of scope here: the `task_utils.sh` item.** It is the behind-only `pull --rebase`
that overwrites an ignored file. t1956 is still open, and its goal 2 (behind-only →
fast-forward) plus goal 3 (keep `--no-autostash --no-overwrite-ignore`) close it
structurally. t1987's note in t1956's inbox (item 3) names it explicitly. Following the
task's instruction ("fold it into t1956 if that task is still open"), it is recorded
as handed to t1956. No code changes here, and no duplicate note.

## Implementation

Work on the current branch (`main`), repo root.

### 1. `.aitask-scripts/aitask_crew_addwork.sh` (~L328)

Replace the pull line with this (match the comment style of `_task_pull_rebase` in `lib/task_utils.sh`):

```bash
    # --no-autostash (t2008): the crew worktree holds other live agents'
    # uncommitted heartbeats, status and command files; a user's
    # rebase.autoStash would stash and re-apply them. Without it the pull
    # refuses on a dirty worktree, as under git's default.
    git pull --rebase --no-autostash --quiet 2>/dev/null || true
```

### 2. `.aitask-scripts/aitask_crew_setmode.sh` (~L125)

Same change, with a short comment pointing at addwork's ("same reason as
aitask_crew_addwork.sh"), keeping the existing indentation:

```bash
        # --no-autostash (t2008): see aitask_crew_addwork.sh's commit block.
        git pull --rebase --no-autostash --quiet 2>/dev/null || true
```

### 3. `.aitask-scripts/agentcrew/agentcrew_utils.py` `git_pull()` (~L294)

```python
def git_pull(worktree: str, batch: bool = False) -> None:
    """Pull latest changes in the worktree (best-effort).

    --no-autostash (t2008): agents' uncommitted heartbeat/status/command files
    live in this worktree, and a user's merge.autoStash would stash and
    re-apply them around the merge.
    """
    result = git_cmd(worktree, "pull", "--rebase=false", "--no-autostash", check=False)
```

### 4. New test `tests/test_crew_pull_no_autostash.sh`

Write the file **before** steps 1–3 (red proof, see Verification). Skeleton, following
`tests/test_task_push.sh` and `tests/test_crew_setmode.sh`:

- `enter_scratch_cwd`, `test_scaffold.sh`, `asserts.sh`, `venv_python.sh`;
  `PASS=0 FAIL=0 TOTAL=0`; **then** source `tests/lib/git_config_isolation.sh`,
  `sync_isolate_git_config`, `assert_git_config_isolated`. That order matters:
  an assertion made before the counter init is erased (t1987). Top-level
  `pushd`/`popd` bodies, no `( … )` subshells, so no counter file is needed.
  `CLEANUP_DIRS` plus an EXIT trap.
- `file_sha` / `file_ident` (inode + ctime_ns) helpers, copied from `test_task_push.sh`.
- `setup_crew_remote_fixture <crew_id>` sets `ROOT REPO WT PEER`:
  1. `REPO`: `git init`, per-repo `user.*`. Use `setup_fake_aitask_repo`, then copy
     `agentcrew_utils.sh`, `launch_modes_sh.sh`, `launch_modes.py`, and
     `aitask_crew_{init,addwork,setmode}.sh`. Same set as `test_crew_setmode.sh`'s
     `setup_test_repo`. Add `userconfig.yaml` and commit.
  2. `crew_init --id <id> --add-type impl:claudecode/opus4_6 --batch`, then
     `addwork --name w1 --work2do /dev/null --type impl --batch`. This seeds a
     Waiting agent `w1` and a tracked `w1_alive.yaml`. Also commit a minimal
     `_runner_alive.yaml` in WT, with the same key order `write_runner_alive`
     writes: `status`, `pid`, `hostname`, `started_at`, `last_heartbeat`,
     `next_check_at`, `interval`, `requested_action: null`. Cell 6 needs it.
  3. `git init --bare remote.git`, `git -C REPO remote add origin …`, and
     `git -C WT push -u origin crew-<id>`. **Upstream set.** Assert it:
     `git -C WT rev-parse --abbrev-ref @{u}` = `origin/crew-<id>`.
  4. Clone the peer with `-b crew-<id>` and per-repo `user.*`, commit
     `peer_only.txt`, and push. The crew worktree is now behind by one.
  5. `git -C REPO config rebase.autoStash true` and `merge.autoStash true`. These
     are per-repo, so the linked worktree shares them and file-scope isolation
     does not remove them.
- `dirty_heartbeat`: append a line to `WT/w1_alive.yaml`, standing in for a
  running agent's uncommitted write. Record `dirty_sha`, `dirty_ident`, and
  `head_before`.

Cells (each on a fresh fixture):

| # | cell | asserts |
|---|---|---|
| 1 | addwork control: clean tree, run `addwork --name w2` | `ADDED:w2`; `peer_only.txt` present (the pull reached the rebase); remote `crew-<id>` == WT HEAD (push landed). Proves the fixture is live, so cell 2's refusal is not "no tracking information". |
| 2 | addwork, dirty `w1_alive.yaml`, `rebase.autoStash=true` | exit 0 + `ADDED:w2`; `w1_alive.yaml` bytes **and** inode+ctime unchanged; `git stash list` empty; `peer_only.txt` absent (the pull refused); HEAD subject `crew: Add agent 'w2'…` (own commit made); `w1_alive.yaml` still unstaged-modified (not swept into the commit) |
| 3 | setmode control: clean, `setmode --name w1 --mode interactive` | `UPDATED:w1:interactive`; `peer_only.txt` present; remote == HEAD |
| 4 | setmode, dirty `w1_alive.yaml`, `rebase.autoStash=true` | exit 0 + `UPDATED:w1:interactive`; same identity, stash, absent-peer, and still-dirty assertions as cell 2; HEAD subject contains `Set launch_mode=interactive` |
| 5 | runner `git_pull`, dirty `w1_alive.yaml` (disjoint from the incoming commit), `merge.autoStash=true` | call `git_pull(WT, batch=True)` through `"$AITASK_PYTHON" -c` with `sys.path.insert(0, <PROJECT_DIR>/.aitask-scripts/agentcrew)`. `peer_only.txt` **present**: the merge ran, so the cell is not vacuous. Merging is git's default with a disjoint dirty file. `w1_alive.yaml` bytes and inode+ctime unchanged; stash empty; file still dirty. **Disjoint edits only: says nothing about recovery.** |
| 6 | runner `git_pull`, **overlapping** edit, `merge.autoStash=true`. The peer commit (instead of `peer_only.txt`) sets `requested_action: stop` in `_runner_alive.yaml`. Locally `last_heartbeat` is rewritten and left uncommitted, as `update_runner_heartbeat` does before every pull. The two hunks are non-adjacent. | Pins the **accepted refusal**, not recovery. Local `_runner_alive.yaml` bytes and inode+ctime unchanged (heartbeat kept); stash empty; HEAD unchanged and no `MERGE_HEAD` (the merge refused cleanly, with no conflict markers). A comment in the test: the remote stop request stays unseen, and convergence belongs to the follow-up `crew_runner_pull_refusal_recovery` (see Risk). |

Footer: print `PASS/FAIL/TOTAL`, `[[ $FAIL -eq 0 ]] || exit 1`.

## Verification

1. **Red proof (before steps 1–3).** Write the test, then run
   `bash tests/test_crew_pull_no_autostash.sh` against the unfixed scripts.
   Expect the controls (cells 1 and 3) to PASS. Expect cells 2, 4 and 5 to FAIL on
   inode+ctime, and cells 2 and 4 also on "peer_only absent". Expect cell 6 to FAIL
   on inode+ctime and on "HEAD unchanged": pre-fix, stash → fast-forward → pop
   carries both edits through. That is the accidental recovery the fix gives up,
   and it shows the trade-off in the Risk section. The file must exit non-zero.
   If cell 5 or 6 does not fail (in case git's fast-forward skips the autostash),
   switch that cell to a diverged history: make a local commit to `w1_status.yaml`
   before the pull, so the merge is a real merge. Then re-prove red. Probe once in
   scratch that `git pull --rebase=false --no-autostash` is accepted by the
   installed git.
2. Apply steps 1–3, then run the new test again. All cells PASS, exit 0.
3. Regression: `bash tests/test_crew_setmode.sh`, `tests/test_crew_groups.sh`,
   `tests/test_crew_addwork_output_instructions.sh`, `tests/test_crew_init.sh`,
   `tests/test_crew_runner.sh`, and `tests/test_agentcrew_error_recovery.sh`. Run
   the Python crew modules with
   `bash tests/run_all_python_tests.sh --test-dir tests` limited to them, or the
   modules that import `agentcrew_utils` directly. Read the last-line verdict.
4. `shellcheck .aitask-scripts/aitask_crew_addwork.sh .aitask-scripts/aitask_crew_setmode.sh tests/test_crew_pull_no_autostash.sh`.

## Out-of-scope findings (for Final Implementation Notes → Step 8b)

- `.aitask-scripts/aitask_crew_init.sh` creates the crew branch with no upstream,
  so the `git push` calls in addwork, setmode and `agentcrew_utils.py` fail
  ("no upstream branch") unless the user sets `push.autoSetupRemote`. addwork and
  setmode then warn "git push failed (offline?)", which misattributes the cause.
  This is pre-existing. Confirm during implementation before listing it.

## Step 9

Post-implementation: commit the code (`bug: … (t2008)`) and plan separately. Step 8d
spawns the `crew_runner_pull_refusal_recovery` follow-up from `### Planned
mitigations`. Run the Step 9 gates (`risk_evaluated`), and archive with
`./.aitask-scripts/aitask_archive.sh 2008`. Current-branch mode, so there is no merge.

## Risk

This plan promises only one thing: user config can no longer make a crew pull
autostash. It accepts git's default refusal, and it does **not** promise that a
refused pull recovers.

### Code-health risk: medium
- With `rebase.autoStash=true`, a crew branch that has an upstream, and a dirty
  worktree, the addwork and setmode pulls now refuse. The push is then rejected
  non-fast-forward when the remote is ahead. That is exactly git's default-config
  behaviour today, and it is best-effort (`|| true` / `warn`). The runner's next
  `git_pull` + `add -A` + push reconciles it **only when no incoming commit touches
  a file that is dirty at the runner's pull** (see the next bullet). ·
  severity: low · → mitigation: none (accepted; matches default-config behaviour;
  recovery depends on the next bullet's follow-up)
- The runner merge pull no longer stashes, and that pull is not guaranteed to
  converge. `run_loop` (`agentcrew_runner.py`, ~L870–878) calls
  `update_runner_heartbeat()`, which rewrites `_runner_alive.yaml`, right before
  every `git_pull()`. If an incoming commit touches that file, the merge refuses on
  **every** iteration. Pushes then stay non-fast-forward, and a remote
  `requested_action: stop` (read by `check_requested_action()` from that same
  file) is never seen. This already happens under git's default config. For
  `merge.autoStash` users, stash → merge → pop could sometimes get through, so
  this change removes an accidental recovery path for them. Cell 6 pins the
  refusal; nothing here claims recovery. · severity: medium · → mitigation:
  crew_runner_pull_refusal_recovery

### Goal-achievement risk: low
- A vacuous test: without an upstream the pull dies before any stash, so a
  "nothing changed" assertion would pass with or without the fix. ·
  severity: low · → mitigation: none needed (covered in this plan by the control
  cells 1 and 3, the "peer_only present" assertion in cell 5, and the red proof
  in Verification step 1)

The user set the disposition in chat (plan review): runner recovery becomes a
separate follow-up, so it is spawned as an `after` task at Step 8d.

### Planned mitigations
- timing: after | name: crew_runner_pull_refusal_recovery | type: bug | priority: medium | effort: medium | inline_risk: high | added_complexity: high | addresses: code-health bullet 2 (runner pull never converges when an incoming commit touches _runner_alive.yaml) | desc: Make the crew runner's per-iteration pull converge when an incoming commit touches a file the runner dirtied before pulling (_runner_alive.yaml heartbeat written right before git_pull in run_loop), so pushes stop being non-fast-forward and a remote requested_action: stop is seen; options include pulling before the heartbeat write or committing the heartbeat first; pre-existing under git's default config

## Final Implementation Notes
- **Actual work done:** Added `--no-autostash` to all three crew-worktree pulls: `aitask_crew_addwork.sh` and `aitask_crew_setmode.sh` (`git pull --rebase --no-autostash`), and `agentcrew_utils.git_pull()` (`git pull --rebase=false --no-autostash`). Added `tests/test_crew_pull_no_autostash.sh`, six cells on a fixture that gives the crew branch an upstream and sets per-repo `rebase.autoStash=true` and `merge.autoStash=true`: addwork and setmode controls (1, 3); addwork and setmode with another agent's dirty heartbeat (2, 4); the runner pull with a disjoint dirty file (5); the runner pull with an overlapping `_runner_alive.yaml` edit, which pins the clean refusal (6).
- **Deviations from plan:** None. The plan was revised once during plan review, before approval. The recovery claim was qualified, cell 6 was added, and the runner-recovery follow-up was recorded as an `after` mitigation.
- **Issues encountered:** None. Red proof against the unfixed scripts gave 8 failures, exactly the predicted ones. Controls 1 and 3 passed. Cells 2, 4, 5 and 6 failed on inode+ctime. Cells 2 and 4 also failed on "peer commit did not land". Cell 6 also failed on bytes and on "HEAD did not move", because the pre-fix stash → fast-forward → pop merged the remote `requested_action: stop` into the heartbeat. That is the accidental recovery this change gives up. With the fix: 54/54 pass. git 2.55 accepts `pull --rebase=false --no-autostash` (cell 5's merge ran). Regressions: 14 crew/agentcrew bash test files pass, and the Python crew modules pass (75). shellcheck shows only pre-existing SC1091/SC2001 notes.
- **Key decisions:** Answer to the task's open question: crew worktrees are routinely dirty with other live processes' uncommitted tracked files (agent heartbeats, non-terminal status writes, `ait crew command send` queues, the runner heartbeat). So autostash could rewrite files the caller does not own; it was not only a determinism issue. The user chose to include the runner pull. The `task_utils.sh` behind-only `pull --rebase` ignored-file item was not touched. It is handed to t1956, which is still open: its goals 2–3 cover it structurally, and t1987's inbox note (item 3) names it. No duplicate note was sent.
- **Upstream defects identified:**
  - `.aitask-scripts/aitask_crew_init.sh:117-118` — the crew branch is created and checked out with no upstream, and no crew path ever runs `push -u`. So the `git push` in `aitask_crew_addwork.sh:333`, `aitask_crew_setmode.sh:127` and `agentcrew_utils.py git_commit_push_if_changes()` fails with "has no upstream branch" unless the user sets `push.autoSetupRemote`. The crew branch never reaches the remote, and addwork/setmode warn "git push failed (offline?)", which misattributes the cause. Verified by probe: a repo with a working `origin`, `crew init` + `crew addwork` gives the warning, the remote has no crew branch, and `git push` in the worktree reports "fatal: The current branch crew-pr has no upstream branch."
