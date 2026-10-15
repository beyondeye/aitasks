---
Task: t2018_crew_runner_pull_refusal_recovery.md
Base branch: main
Output branch: main
---

# t2018 — Crew runner pull converges past its own heartbeat

## Context

`run_loop` (`.aitask-scripts/agentcrew/agentcrew_runner.py` ~L870–878) calls
`update_runner_heartbeat()` — which rewrites `_runner_alive.yaml` — right before
every `git_pull()`. With t2008's `--no-autostash`, any incoming commit that touches
`_runner_alive.yaml` makes the merge refuse on **every** iteration: pushes stay
non-fast-forward and a remote `requested_action: stop` (read by
`check_requested_action()` from that same file) is never seen. t2016 (in flight in
another session) will give crew branches an upstream by default, which makes this
reachable for every user — so t2018 lands independently of it.

Intended outcome: the runner's own file is never dirty at its pull, so a remote stop
merges and is honoured — and no pull ever stashes, rewrites or reverts another
process's uncommitted file, or leaves a half-done merge for the runner to read or
commit.

**Revision (review feedback).** The first draft aborted a conflicted merge with
`git merge --abort`. Both review points were verified and are blocking:
(1) `merge --abort` is `reset --merge`, which restores every *unmerged* path to HEAD
unconditionally — it cannot tell git's conflict markers from an agent's write that
landed on that path after the merge wrote it, so the abort clobbers that write;
(2) an abort that fails (e.g. `index.lock`) left `MERGE_HEAD` and markers in place
while the callers carried on reading and staging. A second review then rejected a
git < 2.38 fallback to a plain live-worktree `git merge`: it leaves markers in agent
files, and holding the runner does not protect the agents, which still read their YAML
(`cmd_heartbeat`) and stage everything on terminal transitions
(`git_commit_push_if_changes`). The design below never creates a conflicted or
half-done merge in the live worktree, on any git version, so there is nothing to abort;
and it propagates an `unsafe` result for states other processes leave behind.

## Design

### 1. Pull before writing the heartbeat
Per iteration: **pull → stop check → heartbeat**. The end-of-iteration
`git_commit_push_if_changes` (`git add -A`) commits `_runner_alive.yaml` every
iteration, and `run_loop` commits it once before the loop ("runner: started"), so the
file is clean at every pull with no new git operation. The only dirty-at-pull case
left is a failed previous commit (e.g. `index.lock` contention with an agent's own
`git add -A`) — transient: the next commit sweeps it and the following pull merges.

### 2. `git_pull` becomes a guarded merge (reuses the t1731 design)
`aitask_sync.sh`'s guarded merge (`_guarded_merge_prepare` /
`_converge_by_guarded_merge`, ~L1551–1840) is the framework's established answer
for merging in a checkout other processes write: pin both SHAs, prove the merge clean
in memory with `merge-tree --write-tree`, build the commit with `commit-tree`, and
advance with `git merge --ff-only --no-autostash --no-overwrite-ignore` — "the ONE
command here that writes the worktree … refuses if HEAD moved off the pinned SHA, and
never leaves a MERGE_HEAD — so there is never an --abort, and a refusal is a deferral".
The crew version drops sync's path-disjointness policy (the runner *must* merge
same-file, different-line edits such as heartbeat lines vs `requested_action`) and
keeps the proof. New `git_pull(worktree, batch) -> tuple[str, str]`:

1. **Unsafe pre-check** — `crew_merge_state(worktree)` returns a reason or `None`:
   `merge_in_progress` (`MERGE_HEAD`), `rebase_in_progress` (`rebase-merge` /
   `rebase-apply` under `git rev-parse --git-path`), `unmerged_paths`
   (`git ls-files -u` non-empty), or `probe_failed` (git could not answer — an unknown
   state is not a clean one). Any reason → return `("unsafe", reason)` without
   running anything. This is also the negative control for "never touch a merge state
   this pull did not create" — nothing in `git_pull` ever aborts or resets.
2. **Fetch + fast-forward** — `git pull --rebase=false --ff-only --no-autostash`
   (same upstream resolution and network footprint as today; `--ff-only` never creates
   a merge state and refuses before writing a dirty path).
3. **Classify** with pinned `H = HEAD^{commit}`, `U = @{u}^{commit}`
   (`merge-base --is-ancestor`; an indeterminate answer → deferred):
   no upstream / unresolvable → `deferred`; `U` ancestor of `H` (incl. a successful
   fast-forward) → `ok`; `H` ancestor of `U` (the ff was refused: dirty, untracked or
   ignored overlap) → `deferred`; otherwise **diverged** → step 4.
4. **Guarded merge** of the pinned SHAs:
   `merge-tree --write-tree --no-messages --name-only H U` —
   exit 1 → `deferred` naming the conflicted paths, **nothing written**; exit 0 →
   `commit-tree <tree> -p H -p U -m "crew: merge <U12> into <H12>"`, then
   `merge --ff-only --no-autostash --no-overwrite-ignore --quiet <c>` → `ok`, or
   `deferred` with git's reason (a path became dirty after the proof, HEAD moved, …).
   Any other `merge-tree` exit → `deferred`, **no live-worktree fallback**: exit 129
   (git < 2.38 has no `--write-tree`) → detail
   `merge_proof_unsupported: divergent histories need git >= 2.38 (merge-tree
   --write-tree)`; any other exit → `merge_proof_failed: <git stderr>`. Older git
   therefore fast-forwards only and never auto-merges a divergent crew branch; this is
   documented (step 4).
5. **Post-check** — `crew_merge_state()` again; any reason → `("unsafe", reason)`.
   `git_pull` itself never produces such a state; this catches one another process
   created during the pull (e.g. `addwork`'s concurrent `pull --rebase`).

Outcomes: `ok` | `deferred` (the worktree holds no merge state; best-effort, callers
continue — non-batch prints the existing `git pull warning:` line) | `unsafe`
(callers must not read, rewrite or stage crew files).

Concurrent writes: git writes only paths that were clean when it checked them, never
reverts a path, and a refused ff writes nothing. An agent write landing after the
in-memory proof makes the ff refuse; one landing after the ff wrote the path simply
wins. The remaining window is git's own per-file check→write inside a single checkout,
which every pull the crew scripts already run has today.

### 3. Callers act on `unsafe`
- `main()` startup pull: report and `return 1` before `enforce_single_instance` reads
  `_runner_alive.yaml`.
- `cmd_check()`: report and `return 1` before reading the alive file.
- `run_loop`: on `unsafe` **hold** — report, then skip the rest of the iteration (no
  stop check, no heartbeat, no reads, no commit) and sleep; the next iteration
  re-probes, and the runner resumes once a human resolves the state ("until recovery
  succeeds"). `--once` returns 1. A SIGTERM/SIGINT while holding skips
  `graceful_shutdown` (it writes and stages crew files) and returns 1.
- Report shape (new runner helper `report_unsafe_pull`): batch → stdout
  `PULL_UNSAFE:<reason>`; non-batch → stderr line naming the worktree, the reason and
  the remedy ("resolve it in `git -C <wt> status`; the runner resumes / start it again").

### 4. Other processes' files
`<agent>_alive.yaml`, non-terminal `<agent>_status.yaml`, agent-recomputed
`_crew_status.yaml` and queued `<agent>_commands.yaml` are dirty at the pull only if
their owner wrote them during the sleep window. They keep t2008's clean refusal
(never stashed, rewritten or reverted); the runner does not commit them before the
pull. The existing end-of-iteration `git add -A` commits them, so the next pull merges
unless the owner rewrote that same file again.

## Implementation steps

0. **Rebase check before editing** — t2016 is `Implementing` and may touch
   `agentcrew_utils.py` (push helper) and this test's fixture: `git status --short` and
   `git log -3 --format='%h %s'` on the five files below; if any moved since
   7d077e308, re-read and apply on top. **Observed at planning time:** t2016 has live,
   uncommitted hunks in `agentcrew_utils.py` (new `git_push()`; `git_commit_push_if_changes`
   now calls it) and in `crew.md` (the `init` section). Edit around them — this task
   changes only `git_pull` and adds helpers above it, and only the runner section of
   `crew.md` — and never revert, reformat or stage their hunks (see Step 9).

1. **Tests first (red).** Extend `tests/test_crew_pull_no_autostash.sh` (step 5) and
   run it before touching the code; record which cells are red.

2. **`.aitask-scripts/agentcrew/agentcrew_utils.py`:** `PULL_OK` / `PULL_DEFERRED` /
   `PULL_UNSAFE` constants, `crew_merge_state()`, and the new `git_pull` per Design §2
   (small private helpers for rev-parse / is-ancestor; hex-validate the tree and commit
   ids like sync's `^[0-9a-f]{40,64}$`). Docstring keeps the t2008 paragraph and adds the
   t2018 contract (outcomes, never aborts, never merges in the live worktree, git >= 2.38
   for divergent histories). `git_commit_push_if_changes` is not touched (t2016's
   surface).

3. **`.aitask-scripts/agentcrew/agentcrew_runner.py`:** import the constants;
   `report_unsafe_pull(worktree, reason, batch)`; `main()` and `cmd_check()` per
   Design §3; `run_loop` reorder (Design §1) with the hold:

   ```python
           if not dry_run:
               pull_status, pull_detail = git_pull(worktree, batch)
               if pull_status == PULL_UNSAFE:
                   unsafe_hold = True
                   report_unsafe_pull(worktree, pull_detail, batch)
                   if once:
                       return 1
                   _sleep_interval(interval)   # existing 1s loop, factored out
                   continue
               unsafe_hold = False
           action = check_requested_action(worktree)
           ...
           if not dry_run:
               update_runner_heartbeat(worktree, interval)
   ```
   and the final cleanup becomes `if _should_stop and not once and not unsafe_hold:
   graceful_shutdown(...)`, returning 1 when it skipped for an unsafe hold.

4. **Docs.** `aidocs/agentcrew/agentcrew_architecture.md` "Runner Orchestration":
   items 1–3 become `Git pull (guarded: fast-forward or a merge proven clean in memory;
   never leaves a merge half-done)` → `Check for stop request` → `Update runner
   heartbeat`, plus three sentences: why the pull precedes the heartbeat; that an
   unfinished merge/rebase in the crew worktree makes the runner hold; and that a
   divergent crew branch is merged only on git >= 2.38 — older git fast-forwards only
   and defers (`merge_proof_unsupported`). In
   `website/content/docs/commands/crew.md`'s runner section, one short paragraph on the
   hold (`PULL_UNSAFE:<reason>` in `--batch`) and the git >= 2.38 requirement for
   divergent histories, then run `python3 check_links.py --build` in `website/`.

5. **`tests/test_crew_pull_no_autostash.sh`.** A Python harness written once at test
   start (heredoc → temp file, removed by the cleanup trap), run with
   `"$AITASK_PYTHON"`, importing `agentcrew.agentcrew_utils` /
   `agentcrew.agentcrew_runner` from `$PROJECT_DIR/.aitask-scripts`. Modes:
   - `pull <wt>` — `git_pull(wt, batch=True)`; prints `PULL_RESULT:<status>|<detail>`.
   - `--write-after <trigger> <path> <bytes-file>` — wraps `agentcrew_utils.git_cmd`;
     after the triggering call returns it writes `<bytes-file>` into `<path>` once (an
     agent landing its write in that window). Triggers: `conflict` = the call was
     `merge-tree` **or** `MERGE_HEAD` now exists (design-agnostic, so an abort-based
     recovery would be caught); `proof` = the call was `commit-tree`.
   - `--inject-after pull` — after the `pull` call returns, the wrapper starts an
     independent merge in `$WT` the way another process would (a side commit adding
     `injected.txt`, built with `hash-object` / `mktree` / `commit-tree`, then
     `merge --no-commit --no-ff <side>`), leaving `MERGE_HEAD` + a staged entry.
   - `HARNESS_MERGE_TREE_RC=<rc>` — the wrapper answers `merge-tree` with that exit
     status and no output (129 = git < 2.38; 128 = a failed proof).
   - `runner <crew> <stub_root> [--once]` — `run_loop(WT, crew, 30, 3, once, False,
     True)` with `_repo_root` → a stub `ait` that logs its argv and exits 0, and
     `launch_agent` → prints `LAUNCH_STUB:<name>`. Without `--once`, `time.sleep` is
     replaced: the first call after an unsafe pull snapshots `HOLD_CHECK` (HEAD,
     `git ls-files -s`, bytes + inode/ctime of `_runner_alive.yaml` and the agent file,
     `MERGE_HEAD` present) against the snapshot taken when `git_pull` returned unsafe,
     prints `HOLD_CHECK:ok` or `HOLD_CHECK:changed:<what>`, then runs the recovery
     command given in `HARNESS_RECOVER`; a hard cap on sleep calls aborts a loop that
     never ends.

   Cells (helpers `file_sha` / `file_ident` / `assert_dirty_untouched` reused):
   - **T1–T5** unchanged (T5 now asserts `PULL_RESULT:ok`).
   - **T6 — runner converges (updated cell, task requirement):** fixture `runner_stop`,
     agent heartbeat dirty; `runner --once`. Assert exit 0, `SHUTDOWN:complete`, no
     `LAUNCH_STUB:`, peer commit is an ancestor of HEAD, remote head == HEAD,
     `HEAD:_runner_alive.yaml` has `status: stopped`, stub log has `send-all`, no
     `MERGE_HEAD`, no stash, agent file bytes + inode/ctime unchanged. (git 2.55 here;
     the cell self-skips with a visible SKIP line if `merge-tree --write-tree` is
     unavailable.)
   - **T7 — overlapping dirty file refuses cleanly** (previous T6 body; `pull`):
     `PULL_RESULT:deferred`, no stash / rewrite / merge state, HEAD unchanged.
   - **T8 — conflict + concurrent agent write (review point 1):** new fixture mode
     `agent_conflict` — local unpushed commit and peer commit set different
     `last_heartbeat:` values in `w1_alive.yaml`; `--write-after conflict` writes the
     agent's fresh heartbeat. Assert `PULL_RESULT:deferred` naming `w1_alive.yaml`,
     file bytes == the agent's bytes, HEAD unchanged, no `MERGE_HEAD`, no unmerged
     entries, no stash.
   - **T9 — clean merge, agent writes after the proof:** fixture `agent_disjoint` —
     peer changes `last_message:` in `w1_alive.yaml`, local unpushed commit adds
     `local_only.txt`; `--write-after proof`. Assert `deferred` naming `w1_alive.yaml`,
     agent bytes kept, HEAD unchanged, no `MERGE_HEAD`.
     **T9b control** — same fixture, no hook: `PULL_RESULT:ok`, HEAD is a 2-parent merge
     whose tree has the peer's `last_message`, `local_only.txt` kept, no `MERGE_HEAD`.
   - **T10 — pre-existing unsafe state blocks every caller (review point 2, entry
     points):** (a) a conflicted merge started by hand (markers + `MERGE_HEAD`);
     (b) a `pull --rebase` stopped on a conflict, then `git add`-resolved without
     `--continue`. For each: real CLI `agentcrew_runner.py --crew pull --once --batch`
     (cwd `$REPO`) → exit 1, `PULL_UNSAFE:merge_in_progress` /
     `PULL_UNSAFE:rebase_in_progress`, no traceback; `--check --batch` → exit 1 +
     `PULL_UNSAFE:`; non-batch run → stderr names the worktree. After all three: HEAD,
     `git ls-files -s`, `_runner_alive.yaml` bytes + ident unchanged, the
     remote-tracking ref `origin/crew-pull` unchanged although the remote is ahead (the
     pre-check ran before any fetch), and the state is still there (`MERGE_HEAD` /
     rebase dir — never aborted).
   - **T11 — unsafe state appears during the pull, runner holds then resumes (review
     point 2, batch loop):** fixture `runner_stop`, agent heartbeat dirty;
     `runner --inject-after pull` (no `--once`) — the injected merge lands during
     iteration 1's pull, after `run_loop`'s "runner: started" commit, so nothing before
     the pull could have staged it. `HARNESS_RECOVER` = `git -C $WT merge --abort` (a
     human recovering; nothing writes concurrently in the test). Assert
     `PULL_UNSAFE:merge_in_progress` exactly once, `HOLD_CHECK:ok` (nothing read into
     a write, rewritten or staged while holding), then `SHUTDOWN:complete`, exit 0,
     remote head == HEAD, `injected.txt` absent from HEAD's tree.
     **T11b** — same with `--once`: exit 1, `PULL_UNSAFE:merge_in_progress`, no
     `SHUTDOWN:`, `MERGE_HEAD` still the injected side, index still has `injected.txt`
     staged, `_runner_alive.yaml` unchanged since "runner: started".
   - **T12 — no merge proof → deferred, worktree untouched (review point 3):** fixture
     `peer_only` + local unpushed `local_only.txt` (diverged, clean).
     (a) `HARNESS_MERGE_TREE_RC=129` → `PULL_RESULT:deferred|merge_proof_unsupported…`;
     (b) `HARNESS_MERGE_TREE_RC=128` → `deferred|merge_proof_failed…`. Each: HEAD
     unchanged (1 parent), no `MERGE_HEAD`, no unmerged entries, `peer_only.txt`
     absent, no `commit-tree` / `merge` call made after `merge-tree` (the harness logs
     git subcommands; assert the log).
   - Header comment + banner updated (`t2008, t2018`).

6. **Mutant checks** (edit one line in place, run, restore by the same edit — never
   `git stash` / `git restore`): (M1) drop the pre-check → T10's remote-tracking-ref
   assertion must fail; (M2) make the diverged branch run `git merge` and
   `git merge --abort` on failure → T8 must fail on the agent bytes; (M3) proceed past
   `PULL_UNSAFE` in `run_loop` → T11 must fail; (M4) drop the post-check → T11 must
   fail; (M5) re-add a live `git merge` fallback for a non-0/1 `merge-tree` exit → T12
   must fail.

7. **Verify green** (Verification), then Step 9.

8. **After the code commit:** note t2016 (`/aitask-note` flow, `--from 2018`) with the
   commit SHA: runner pulls now converge (guarded merge) and hold on an unfinished
   merge/rebase, and divergent histories need git >= 2.38;
   `test_crew_pull_no_autostash.sh` cells 6–12 rely on
   `setup_crew_remote_fixture`'s manual `push -u` — re-run them if t2016 changes it.

### Out-of-scope finding (raise at Step 8b)
`aitask_crew_addwork.sh` / `aitask_crew_setmode.sh` run `git pull --rebase
--no-autostash … || true`: a conflicting rebase is left in progress in the crew
worktree. With this change the runner holds on it (`rebase_in_progress`) instead of
committing onto the detached HEAD — safer, but the scripts themselves still strand
the rebase. Upstream-defect candidate.
Related: `git_commit_push_if_changes` (`git add -A`, used by the runner's end-of-
iteration commit and by agents' terminal transitions) stages whatever is there, so an
unfinished merge/rebase another process creates *mid-iteration* can still be committed.
The runner's hold covers states present at its pull; a `crew_merge_state()` guard in
that helper would close the rest. It is t2016's surface, so it is raised as a
follow-up rather than edited here.

## Verification

- `bash tests/test_crew_pull_no_autostash.sh` — red cells recorded before steps 2–3
  (expected: T6, T8, T9, T10, T11, T12), all green after.
- Mutants M1–M5 each turn their cell red; restored afterwards.
- `bash tests/test_crew_runner.sh`, `bash tests/test_crew_status.sh`,
  `bash tests/test_crew_runner_config_delivery.sh`, `bash tests/test_crew_groups.sh`.
- `python3 -m py_compile` on both Python files.
- `cd website && python3 check_links.py --build`.
- `git diff` of the five files reviewed; commit only those paths.

## Risk

### Code-health risk: medium
- `git_pull` is rewritten from one `git pull` into a multi-step guarded merge that all
  three runner pull sites use; a classification mistake could defer a pull that should
  merge, or merge one that should defer. Bounded by reusing the t1731 structure and by
  T5–T12 plus mutants M1–M5 · severity: medium · → mitigation: none
- The runner gains an `unsafe` hold; while holding it writes no heartbeat, so another
  host may treat it as stale and take over (the existing risk for any stalled runner)
  · severity: low · → mitigation: none
- The `run_loop` reorder changes a load-bearing iteration order (stop check and
  heartbeat now follow the pull) · severity: low · → mitigation: none
- The tests drive `run_loop` / `git_pull` through a harness that monkeypatches
  `git_cmd`, `launch_agent`, `_repo_root` and `time.sleep`, which couples them to those
  names · severity: low · → mitigation: none

### Goal-achievement risk: medium
- A true content conflict on `_runner_alive.yaml` (adjacent-line edits since the merge
  base: a runner restarted with a new `interval` while a remote stop is pending, or a
  takeover runner rewriting the file) is deferred on each iteration, not converged; the
  remote stop stays unseen until resolved by hand. Outside "a file the runner
  dirtied", but reachable · severity: low · → mitigation:
  crew_runner_alive_conflict_convergence
- Other processes' files that are dirty at the pull still refuse (t2008 rule);
  convergence relies on the runner's end-of-iteration sweep commit · severity: low ·
  → mitigation: none
- On git < 2.38 the runner never merges a divergent crew branch (deferred,
  `merge_proof_unsupported`): pushes stay non-fast-forward until git is upgraded or
  someone merges by hand. That includes this task's own scenario (an unpushed runner
  commit plus a peer stop), and a regression from today's plain merge for the clean
  divergent case. Accepted in review in exchange for never writing a half-done merge
  into live files; documented · severity: medium · → mitigation: none

### Planned mitigations
- timing: after | name: crew_runner_alive_conflict_convergence | type: bug | priority: low | effort: medium | inline_risk: high | added_complexity: medium | addresses: goal-achievement — content conflict on _runner_alive.yaml is deferred, not converged | desc: Converge a conflicted runner pull on _runner_alive.yaml (keep the incoming requested_action, re-write the runner's own heartbeat fields after the merge) instead of deferring it | created: t2029

## Step 9 (Post-Implementation)

Current-branch mode (profile `fast`): no worktree/branch to merge. Review, commit the
five code/doc/test paths with `git commit -- <paths>` (other sessions' dirty files must
not ride along), commit the plan via `./.aitask-scripts/aitask_task_commit.sh`, then
archive per the workflow. A pathspec commit takes whole files: before committing,
check `git diff -- <file>` holds only this task's hunks; if t2016 has uncommitted hunks
in the same file, stage only ours (`git apply --cached <our.patch>`) and commit the
index for those paths.

## Post-Review Changes

### Change Request 1 (2026-10-16 00:00)
- **Requested by user:** three verified review findings — (1) the initial
  `git pull --ff-only` lacked `--no-overwrite-ignore`, so an incoming file overwrote
  a locally ignored one while `git_pull` returned ok; (2) `commit-tree` ignores
  `commit.gpgSign`, so the synthetic merge commit was silently unsigned where
  `git merge` would sign or fail; (3) a failed fetch with matching cached refs was
  reported as "up to date".
- **Changes made:** `git_pull` no longer calls `git pull`. `_sync_with_upstream`
  fetches exactly the tracked branch (`git fetch -- <remote> <merge ref>`, resolved
  via `symbolic-ref` + `for-each-ref %(upstream:remotename)/%(upstream:remoteref)`);
  a fetch failure defers as `fetch_failed: <git stderr>`. Both the fast-forward and
  the proven merge go through one `_advance()` =
  `merge --ff-only --no-autostash --no-overwrite-ignore <pinned sha>`. `_sign_args()`
  passes `-S` to `commit-tree` when `commit.gpgSign` is true; a signing failure (or
  an unreadable setting) defers. Harness injection point moved from the `pull`
  subcommand to `fetch`. New cells 13a/13b (ignored overlap, ff and diverged),
  14a/14b (failing / working signer stub), 15 (unreachable origin, cached
  upstream == HEAD, batch and non-batch). Architecture doc mentions signing,
  ignored files and fetch failure.
- **Files affected:** `.aitask-scripts/agentcrew/agentcrew_utils.py`,
  `tests/test_crew_pull_no_autostash.sh`, `aidocs/agentcrew/agentcrew_architecture.md`

### Change Request 2 (2026-10-16 00:00)
- **Requested by user:** the merge-tree capability probe ran against the source
  repository and treated every failure as "unsupported git", so a permission error
  silently skipped the core cells with a passing verdict.
- **Changes made:** the probe runs in a disposable repository; exit 0 → supported,
  exit 129 (git's usage exit, i.e. no `--write-tree`) → visible SKIP of the
  dependent cells, any other exit → a recorded FAIL with git's message.
- **Files affected:** `tests/test_crew_pull_no_autostash.sh`

## Final Implementation Notes
- **Actual work done:** `run_loop` now pulls → checks the stop request → writes the
  heartbeat, so `_runner_alive.yaml` is clean at every pull and a remote
  `requested_action: stop` merges and is honoured. `git_pull` was rewritten as a
  guarded sync returning `(status, detail)` with `PULL_OK` / `PULL_DEFERRED` /
  `PULL_UNSAFE`: pre-check for an unfinished merge/rebase (`crew_merge_state`),
  separate fetch, fast-forward or (diverged) `merge-tree --write-tree` proof →
  `commit-tree` (signed per `commit.gpgSign`) → protected `merge --ff-only`, then a
  post-check. It never opens a merge in the live worktree and never aborts or resets
  anything. `main()` and `cmd_check()` refuse on `PULL_UNSAFE`; `run_loop` holds
  (no reads, writes, stages or graceful shutdown) and resumes once the state clears;
  `--once` returns 1. Batch prints `PULL_UNSAFE:<reason>`. Docs: aidocs runner
  iteration list + paragraph; website `crew.md` runner section (git >= 2.38 for
  divergent histories, the hold). Tests: `tests/test_crew_pull_no_autostash.sh`
  cells 5–15 through a Python harness wrapping `agentcrew_utils.git_cmd`.
- **Deviations from plan:** (a) the first-draft `git merge --abort` recovery and the
  git < 2.38 live-merge fallback were both dropped during plan review (see the plan's
  Revision paragraph); (b) the plan's `git pull --ff-only` step became a separate
  fetch + protected `merge --ff-only` (Change Request 1); (c) the harness gained a
  ticking clock (`now_utc` +1s per call): in-process, `write_runner_alive` and the
  first `update_runner_heartbeat` land in the same second, leave the file
  byte-equal to its commit, and T6 then passed even on the old code; (d) T11's
  injection point is after the fetch; (e) 11b asserts the agent file's bytes/ident
  rather than "still uncommitted", because `run_loop`'s "runner: started"
  `git add -A` sweeps it before the loop; (f) per t2016's note, the fixture comment
  about the seeding push was corrected.
- **Issues encountered:** harness `argparse.REMAINDER` swallowed options after the
  worktree (fixed by splitting at `--`); a mutant with a non-unique restore anchor
  (M7) left `_sign_args` mutated — restored by hand, verified, full suite re-run
  green. With `MERGE_HEAD` present `git pull` refuses before fetching, so the
  pre-check's signal is the fetch: it shows in 10a once the fetch runs first.
- **Key decisions:** reuse aitask_sync.sh's t1731 guarded-merge structure without its
  disjoint-paths policy (the runner must merge same-file, different-line edits);
  hold instead of exit on `PULL_UNSAFE` in the loop (transient states such as a
  concurrent `addwork` rebase clear by the next iteration); no live-worktree merge
  on any git version (git < 2.38 defers divergent pulls as `merge_proof_unsupported`
  — documented); the synthetic merge commit runs no commit hooks, as in t1731.
  Verification: red baseline recorded (T5–T12 red on the old code), 208/208 green,
  mutants M1–M8 each turn their own cells red (M1 pre-check → 10a, M2 merge+abort →
  8/9/…, M3 no hold → 11/11b, M4 no post-check → 11/11b, M5 live fallback → 12/129,
  M6 overwrite-ignored → 13a/13b, M7 unsigned → 14a/14b, M8 read past fetch
  failure → 15); `test_crew_runner`, `test_crew_status`,
  `test_crew_runner_config_delivery`, `test_crew_groups` green; `check_links.py
  --build` passed.
- **Upstream defects identified:**
  - `.aitask-scripts/aitask_crew_addwork.sh:332` — `git pull --rebase --no-autostash --quiet 2>/dev/null || true` leaves a conflicting rebase in progress (detached HEAD, possibly markers) in the shared crew worktree; the runner now holds on it (`rebase_in_progress`), but the script strands it. Same at `.aitask-scripts/aitask_crew_setmode.sh:126`.
  - `.aitask-scripts/agentcrew/agentcrew_utils.py:499` — `git_commit_push_if_changes` stages with `git add -A` without checking `crew_merge_state()`, so an unfinished merge/rebase another process creates mid-iteration can be committed by the runner's end-of-iteration commit or an agent's terminal transition.
  - `aidocs/agentcrew/agentcrew_architecture.md:222` — "Mark stale agents as Error" is stale (the runner only logs stale heartbeats; status is unchanged), and line 300 ("Agents never touch git directly") is stale (`ait crew status set` commits and pushes terminal transitions).
