---
Task: t2016_crew_branch_never_gets_upstream.md
Branch: main
Base branch: main
Output branch: main
---

# t2016 — Publish crew branches with an upstream

## Context

`aitask_crew_init.sh` creates `crew-<id>` with `git update-ref` + `git worktree add`.
That leaves the branch with no upstream, and no crew path ever runs `push -u`. So every
crew `git push` (`aitask_crew_addwork.sh:333`, `aitask_crew_setmode.sh:127`,
`agentcrew_utils.py git_commit_push_if_changes()`) dies with "has no upstream
branch". The exception is a user who has `push.autoSetupRemote` set. The shell sites then warn
"git push failed (offline?)", which blames the wrong cause. The crew branch never reaches the
remote, even though the design assumes it does: `aidocs/agentcrew/agentcrew_architecture.md` (runner
"commit + push"), the brainstorm architecture docs ("multi-PC collaboration via
git"), `ait crew status set`'s terminal push (t653_3), the runner's cross-host
`enforce_single_instance`, and the `push origin --delete crew-<id>` cleanups.

**Decision (user-confirmed): crew branches are published.** When `origin` exists,
crew init publishes the branch with an upstream, and every push site pushes
`-u origin HEAD`. That way an offline init heals on the next successful push. Warnings
report git's own stderr. A repository with no `origin` has nothing to publish to, so
the push is skipped silently. This matches the framework's local-only convention
(`aitask_claim_id.sh has_remote`). The cost was accepted: crew writes now make real
network round-trips.

**Coordination:** t2018 (`crew_runner_pull_refusal_recovery`) is `Implementing` in
another session. It owns the runner pull ordering (`agentcrew_runner.py`,
`agentcrew_utils.py git_pull`) and Test 6 of `tests/test_crew_pull_no_autostash.sh`.
This plan therefore leaves `git_pull`, every pull site and that test file untouched,
and adds its tests in a new file.

## Implementation

1. **Shell helper**: add `crew_push <worktree>` to `.aitask-scripts/lib/agentcrew_utils.sh`,
   after `agentcrew_worktree_path`:
   ```bash
   # crew_push <worktree>
   # Publish the crew branch checked out in <worktree> to origin (best-effort).
   # Always `push -u origin HEAD` (t2016): crew init creates the branch with no
   # upstream, so a bare `git push` dies with "has no upstream branch" unless the
   # user sets push.autoSetupRemote; -u gives it one on the first push that
   # succeeds, so an offline init heals later. Naming the destination also keeps
   # a push.default=matching from publishing the repository's other branches.
   # No origin remote → nothing to publish to: returns 0 silently. On failure
   # warns with git's own stderr and returns 1. Never writes to stdout — callers
   # print machine-parsed CREATED:/ADDED:/UPDATED: lines there.
   crew_push() {
       local wt="$1" err
       git -C "$wt" remote get-url origin >/dev/null 2>&1 || return 0
       if ! err="$(git -C "$wt" push --quiet -u origin HEAD 2>&1)"; then
           warn "git push of the crew branch to origin failed:"
           printf '%s\n' "$err" >&2   # raw: warn() is echo -e and would interpret backslashes
           return 1
       fi
   }
   ```
   Capturing `2>&1` keeps git's "branch … set up to track …" message off stdout.
   During implementation, verify on the installed git whether `--quiet` prints that message.

2. **`aitask_crew_init.sh`**: after the worktree commit subshell (current L169-173),
   add `crew_push "$WT_PATH" || true` before `success …`/`CREATED:`. Update the header
   comment's "Creates:" list: "Publishes crew-<id> to origin with an upstream when
   an origin remote exists (best-effort)".

3. **`aitask_crew_addwork.sh`** (L333) and **`aitask_crew_setmode.sh`** (L127):
   replace `git push --quiet 2>/dev/null || warn "git push failed (offline?)"` with
   `crew_push . || true`. Both run inside `( cd "$WT_PATH" … )`, and both already source
   `lib/agentcrew_utils.sh`. Leave the preceding `--no-autostash` pull line unchanged.

4. **`agentcrew/agentcrew_utils.py`**: add `git_push(worktree, batch=False)` next to
   `git_pull`, mirroring the shell helper. Skip when
   `git_cmd(worktree, "remote", "get-url", "origin", check=False).returncode != 0`;
   otherwise run `git_cmd(worktree, "push", "--quiet", "-u", "origin", "HEAD", check=False)`
   and keep the existing `[HH:MM:SS] git push warning: <stderr>` print on failure when
   `not batch`. Give it a docstring with the same t2016 rationale. In
   `git_commit_push_if_changes`, replace the inline push and warning with `git_push(worktree, batch)`.
   This covers the runner (L806/842/864/961) and `ait crew status set` (agentcrew_status.py:146).

5. **Docs**: in `website/content/docs/commands/crew.md` § `ait crew init` (after the
   "orphan branch `crew-<id>` checked out under …" sentence), add one current-state
   sentence. When the repository has an `origin` remote, init publishes the branch
   there with an upstream, and crew commits (agent registration, launch-mode changes,
   runner and status writes) are pushed to it. A repository without `origin` keeps
   the branch local. Then run `python3 check_links.py --build` in `website/`.

6. **New test `tests/test_crew_publish_upstream.sh`**. It mirrors
   `test_crew_pull_no_autostash.sh`'s scaffold: `enter_scratch_cwd`, `test_scaffold.sh`,
   `asserts.sh`, `venv_python.sh`, PASS/FAIL/TOTAL init, then
   `git_config_isolation.sh` + `sync_isolate_git_config` + `assert_git_config_isolated`.
   A developer's global `push.autoSetupRemote` would otherwise hide the defect. The
   fixture is a fake aitask repo with the crew libs/scripts copied in, plus a bare
   `remote.git`.

   **Each entry point gets its own first-publish cell.** Once an upstream exists, a
   bare `git push` succeeds under the default `push.default=simple`, so a cell that
   runs an entry point *after* init has published cannot tell the new push from the
   old one. Helper `make_offline_crew <id> <agent?>`: `origin` points at a nonexistent
   path, init runs (and addwork w1 when asked), and the branch is left with no upstream
   and no remote copy. Then `remote set-url origin <bare>`. The cell's entry point is
   then the **first** successful publish. Cells:
   1. **init publishes** (origin is the bare remote from the start): `refs/heads/crew-<id>`
      on the remote equals the local tip; `@{u}` is `origin/crew-<id>`; init's **stdout**
      is the info/success lines plus `CREATED:<id>`, with no "track" text.
   2. **steady-state addwork** after cell 1's online init: the remote tip equals the
      worktree HEAD, stdout has `ADDED:w1`, and stderr has no push warning. This is a
      sanity check only; cells 3–5 are the discriminating ones.
   3. **offline init → addwork publishes**: the offline init exits 0 and prints
      `CREATED:`, and its stderr carries git's own failure text (assert a fragment such
      as "does not appear to be a git repository", and that it does not contain
      "offline?"). After set-url, addwork → the remote tip equals HEAD and `@{u}` is set.
   4. **offline crew → setmode publishes**: `make_offline_crew` with agent w1. The
      offline addwork's stderr also carries git's text, not "offline?". After set-url,
      `setmode` (flags per its `--help`) → the remote tip equals HEAD, `@{u}` is set, and
      `git -C <bare> show crew-<id>:w1_status.yaml` has the new `launch_mode:`.
   5. **offline crew → terminal status CLI publishes**: `make_offline_crew` with agent w1,
      then set-url. Drive the real CLI the way `test_agentcrew_terminal_push.sh` does:
      `$AITASK_PYTHON "$PROJECT_DIR/.aitask-scripts/agentcrew/agentcrew_status.py" --crew <id>
      --agent w1 set --status …` from cwd=`$REPO`, going Ready → Running (non-terminal,
      no commit) → Completed (terminal, commit + push, batch=True). The remote tip
      equals HEAD, `@{u}` is set, and `git -C <bare> show crew-<id>:w1_status.yaml` has
      `status: Completed`. This covers the shared `git_commit_push_if_changes` path that
      the runner also uses.
   6. **no origin**: init + addwork exit 0, and stderr has no push warning.
   7. **Python helper, no origin, batch=False**: `git_commit_push_if_changes(wt, msg)` via
      `$AITASK_PYTHON -c` (t2008's Test 5 import shape) on a crew with a change to commit
      prints no `git push warning` to stderr.
   8. **explicit destination**: push `main` to the remote, then make a local commit on
      `main` and set `push.default matching`. addwork → the remote `main` is unchanged
      and the crew branch is pushed.
   Footer: `[[ "$FAIL" -eq 0 ]]` guard. The bodies run in the main shell, as in t2008's file.
   If any body uses `( … )`, opt into `assert_counters_init`/`assert_counters_load`.

## Verification

- `bash tests/test_crew_publish_upstream.sh` passes.
- **Red proof:** export the pre-fix tree with `git archive HEAD .aitask-scripts tests |
  tar -x -C <scratch>/tree`, copy the new test into `<scratch>/tree/tests/`, and run it
  there. Every cell's discriminating assertion must FAIL pre-fix: 1–5 and 8 (no upstream,
  so the bare push fails), 6 (addwork warns "offline?"), and 7 (the Python helper warns
  "No configured push destination"). Record the per-cell result in the plan's Final
  Implementation Notes. Never stash or restore the shared tree.
- **Partial-fix mutants** (in a second scratch tree: the pre-fix export overlaid with this
  task's fixed files, never the shared checkout): revert only setmode's push line to
  the old bare push → cell 4 must FAIL while 3 and 5 pass. Revert only the Python
  `git_commit_push_if_changes` push → cell 5 must FAIL. This proves each first-publish
  cell pins its own entry point.
- Regression: `tests/test_crew_init.sh`, `test_crew_setmode.sh`, `test_crew_groups.sh`,
  `test_crew_addwork_output_instructions.sh`, `test_crew_status.sh`,
  `test_agentcrew_terminal_push.sh`, `test_crew_pull_no_autostash.sh`,
  `test_crew_cleanup.sh`, `test_crew_runner.sh`, and
  `bash tests/run_all_python_tests.sh --test-dir` covering `test_brainstorm_crew.py`.
- `shellcheck .aitask-scripts/aitask_crew_init.sh .aitask-scripts/aitask_crew_addwork.sh
  .aitask-scripts/aitask_crew_setmode.sh .aitask-scripts/lib/agentcrew_utils.sh tests/test_crew_publish_upstream.sh`.
- `website/`: `python3 check_links.py --build`.
- **Commit hygiene:** t2018 may also be editing `agentcrew_utils.py` in this checkout.
  Before the Step 8 commit, run `git diff -- <each file>` and confirm that every hunk is
  this task's. If a file carries foreign hunks, commit only this task's hunks
  (`git apply --cached` of a filtered patch, then `git commit` with no worktree pathspec
  for that file). Never sweep another session's edits in.

## Post-implementation

- Step 8e: offer a note to t2018 saying that t2016 now publishes crew branches by default.
  Its "reachable for every user once t2016 lands" condition then holds whenever a second
  writer exists. Also, its fixture comment "the seeding addwork's own pull and push fail
  quietly" now reads "pull fails quietly, push is skipped (no origin)".
- Step 9: archival via `aitask_archive.sh 2016` (current-branch mode, no merge).

## Risk

### Code-health risk: medium
- Crew writes now make real network round-trips: a pull plus a push in addwork/setmode, and a push in init and in every runner and status commit. Before, they failed instantly with no network access. `brainstorm_crew._run_addwork` runs `ait crew addwork` without a subprocess timeout, so an origin that is unreachable but routable (TCP timeout rather than DNS failure) can stall brainstorm agent registration and init. Users who set `push.autoSetupRemote` already have this behavior. · severity: medium · → mitigation: crew_git_network_timeout
- t2018's runner pull non-convergence becomes reachable whenever a second writer pushes to the crew branch. No shipped path attaches a second machine, so this requires a manual clone; t2018 already owns the fix. · severity: low · → mitigation: none (existing task t2018; Step 8e note)
- t2018 is concurrently editing in the same checkout and may touch `agentcrew_utils.py`. A path-scoped commit would sweep its hunks in. · severity: low · → mitigation: none (commit-hygiene step in Verification)

### Goal-achievement risk: low
- Publishing makes the branch reach the remote, but there is still no shipped command for a second machine to attach to a remote crew branch, so "multi-PC" stays partial. This is outside the scope of the defect (the branch never being published). · severity: low · → mitigation: none

### Planned mitigations
- timing: after | name: crew_git_network_timeout | type: enhancement | priority: medium | effort: medium | inline_risk: medium | added_complexity: medium | addresses: code-health bullet 1 (crew writes now make real network round-trips with no time limit; brainstorm _run_addwork has no subprocess timeout) | desc: Time-limit the crew git network operations (init/addwork/setmode push+pull, Python git_push/git_pull) and brainstorm's _run_addwork subprocess, portably (no macOS `timeout` binary), so an unreachable origin cannot stall crew init or agent registration

## Final Implementation Notes
- **Actual work done:** As planned. `crew_push <wt>` in `lib/agentcrew_utils.sh` (`git push --quiet -u origin HEAD`, skip silently with no `origin`, warn with git's raw stderr via `printf` after a `warn` header, never stdout); `aitask_crew_init.sh` publishes after the init commit (`crew_push "$WT_PATH" || true`); `aitask_crew_addwork.sh` / `aitask_crew_setmode.sh` push via `crew_push . || true` (pull lines untouched); `agentcrew_utils.py` gains `git_push()` with the same semantics and `git_commit_push_if_changes` calls it (runner + `ait crew status set`); one sentence in `website/content/docs/commands/crew.md`; new `tests/test_crew_publish_upstream.sh` (8 cells, 68 assertions).
- **Deviations from plan:** Plan revised before approval on review: each push entry point (addwork, setmode, terminal `ait crew status set`) got its own first-publish cell on an offline-created crew, because a cell running after init has published cannot tell `push -u origin HEAD` from a bare `git push` under push.default=simple. Docs wording made exact: status pushes happen on terminal `ait crew status set` transitions only. `git_pull` and `tests/test_crew_pull_no_autostash.sh` left untouched (t2018 owns them).
- **Issues encountered:** None. Probe on git 2.55 (global/system config isolated) confirmed `git push -u origin HEAD` WITHOUT `--quiet` prints `branch 'crew-x' set up to track 'origin/crew-x'.` on **stdout** — it would have corrupted the machine-parsed `CREATED:`/`ADDED:`/`UPDATED:` lines; with `--quiet` stdout is empty, and the helper captures both streams anyway. Bad-URL push stderr: `fatal: '<path>' does not appear to be a git repository`; bare push with no origin: `fatal: No configured push destination.`
- **Key decisions:** User confirmed crew branches are published (documented design: runner commit+push, brainstorm multi-PC). Always pass an explicit destination (`-u origin HEAD`) rather than a bare push once an upstream exists: it self-heals an offline init and keeps `push.default=matching` from publishing the repo's other branches (cell 8 shows the pre-fix bare push moving the remote primary branch). No `origin` → silent skip, matching the framework's local-only convention (`aitask_claim_id.sh has_remote`).
- **Verification evidence (durable):**
  - `bash tests/test_crew_publish_upstream.sh` → `PASS: 68 FAIL: 0 TOTAL: 68`.
  - Red proof — pre-fix tree, shared checkout untouched:
    ```bash
    S=<scratchpad>/red; mkdir -p "$S/tree"
    git archive HEAD .aitask-scripts tests | tar -x -C "$S/tree"   # HEAD = 7d077e308 (pre-fix)
    cp tests/test_crew_publish_upstream.sh "$S/tree/tests/"
    bash "$S/tree/tests/test_crew_publish_upstream.sh"
    ```
    Result `PASS: 47 FAIL: 21 TOTAL: 68`; every cell fails its discriminating assertion:
    ```
    FAIL: 1: the remote crew branch is at the local tip (expected '<sha>', got '')
    FAIL: 1: the crew branch tracks origin (expected 'origin/crew-c1', got '')
    FAIL: 2: no push warning (expected output NOT containing 'push', got 'Warning: git push failed (offline?)')
    FAIL: 2: the remote crew branch is at the local tip (expected '<sha>', got '')
    FAIL: 2: the crew branch tracks origin (expected 'origin/crew-c1', got '')
    FAIL: 3: the offline init warning carries git's own text (expected output containing 'does not appear to be a git repository', got '')
    FAIL: 3: the remote crew branch is at the local tip (expected '<sha>', got '')
    FAIL: 3: the crew branch tracks origin (expected 'origin/crew-c3', got '')
    FAIL: 4: the offline addwork warning carries git's own text (... got 'Warning: git push failed (offline?)')
    FAIL: 4: the offline addwork warning does not guess 'offline?' (... got 'Warning: git push failed (offline?)')
    FAIL: 4: the remote crew branch is at the local tip (expected '<sha>', got '')
    FAIL: 4: the crew branch tracks origin (expected 'origin/crew-c4', got '')
    FAIL: 4: the remote carries the new launch mode (expected output containing 'launch_mode: interactive', got '')
    FAIL: 5: the remote crew branch is at the local tip (expected '<sha>', got '')
    FAIL: 5: the crew branch tracks origin (expected 'origin/crew-c5', got '')
    FAIL: 5: the remote carries the terminal status (expected output containing 'status: Completed', got '')
    FAIL: 6: addwork prints no push warning (expected output NOT containing 'push', got 'Warning: git push failed (offline?)')
    FAIL: 7: no push warning without origin (expected output NOT containing 'git push warning', got '[..] git push warning: fatal: No configured push destination. ...')
    FAIL: 8: the remote crew branch is at the local tip (expected '<sha>', got '')
    FAIL: 8: the crew branch tracks origin (expected 'origin/crew-c8', got '')
    FAIL: 8: the remote primary branch is untouched (expected '3a9c4331…', got '2b4fd88c…')
    ```
  - Partial-fix mutants (pre-fix export overlaid with this task's fixed files): (A) setmode's push line reverted to `git push --quiet 2>/dev/null || warn "git push failed (offline?)"` → only cell 4 fails (3 FAIL: remote tip, upstream, remote launch_mode), `PASS: 65`; (B) `git_commit_push_if_changes` push reverted to `git_cmd(worktree, "push", check=False)` → only cell 5 fails (3 FAIL: remote tip, upstream, remote status), `PASS: 65`.
  - Regression, all exit 0: `test_crew_init`, `test_crew_setmode`, `test_crew_groups`, `test_crew_addwork_output_instructions`, `test_crew_status`, `test_agentcrew_terminal_push`, `test_crew_pull_no_autostash`, `test_crew_cleanup`, `test_crew_runner`, `test_crew_report`, `test_agentcrew_error_recovery`, `test_crew_runner_config_delivery`, `test_crew_template_includes`, `test_brainstorm_init_proposal_file`; pytest over `test_agentcrew_rollup`, `test_brainstorm_crew`, `test_brainstorm_cli_python`, `test_brainstorm_dag`, `test_brainstorm_module_sync`, `test_brainstorm_group_recovery`, `test_brainstorm_module_sync_apply_contract`, `test_metadata_writer_inventory`, `test_collection_structure` → 155 passed. `website/check_links.py --build` → SWEEP: PASSED. shellcheck: only SC1091 info + a pre-existing SC2001 at `aitask_crew_addwork.sh:181`.
- **Upstream defects identified:** None
