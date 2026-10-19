---
Task: t2035_consolidate_bounded_git_helpers.md
Base branch: main
Output branch: main
---

# t2035 — Move sync, drift-check and github_release onto lib/bounded_run.py

## Context

t2024 added `.aitask-scripts/lib/bounded_run.py`, the framework's one tested
bounded runner. It starts the command in a new session, kills the whole process
group (TERM → CONT → grace → KILL), and with `--noninteractive` leaves the
command no way to prompt. Three older copies of the logic remain, and each one
leaks a transport process that ignores SIGTERM:

| caller | today | leak |
|---|---|---|
| `aitask_sync.sh:_git_with_timeout` (l.253) | coreutils `timeout` (TERM to the group, no KILL), or a macOS watchdog that kills the direct child only | the TERM-ignoring transport survives on Linux. On macOS every descendant survives |
| `aitask_remote_drift_check.sh:_git_fetch_with_timeout` (l.174) | same shape | same |
| `lib/github_release.sh:_github_ls_remote_tags` (l.150) | `set -m` job, then `kill -- -pgid` (TERM only), then a pgrep walk | a TERM-ignoring descendant survives. The job also keeps the controlling terminal, so an `insteadOf`-rewritten ssh URL can prompt |

Goal: all three run on `bounded_run.py`, each with its exit-code contract (124 on
timeout) and its own knob (`NETWORK_TIMEOUT`, `--timeout`,
`AIT_GIT_LSREMOTE_TIMEOUT`).

**This adds a nesting level, so the outer runners must be coordinated.**
bounded_run puts git in a session of its own, which the wrapper around the
caller cannot see. Two wrappers stop their child with a cleanup budget that is
shorter than bounded_run's default 5s grace:

- `lib/sync_action_runner.py:_stop_sync_session` (the syncer TUI and the board)
  TERMs the sync's session, waits `_TERM_GRACE_SECONDS=3`, and then KILLs
  whatever is left. That kills the bounded_run CLI mid-cleanup, before its KILL
  reaches a TERM-ignoring transport in the inner session. The outer runner then
  reports `stray_session=None` while the transport keeps running and writing.
  This was reported by review and verified against the code.
- `lib/framework_version.py:resolve_latest_version` (the syncer's
  update check) runs `github_release.sh` in a new session and SIGKILLs its
  group on timeout, with no grace at all. The inner ls-remote session survives.
  The old `set -m` job escaped that killpg too, so this is not a regression,
  but this task is where it gets fixed.

Pattern for callers: `lib/agentcrew_utils.sh:_crew_git_bounded` (l.116).
Pattern for outer coordination: bounded_run's own nesting contract. The parent
exports `AIT_BOUNDED_RUN_GRACE = child_grace(own grace)` (own − 2s, floored at
1s), so the inner cleanup finishes before the outer KILL. `bounded_run.py` is
already in `tests/lib/test_scaffold.sh`. No new shell lib is added.

**Out of scope:**
- `install.sh`'s `_install_ls_remote_tags` mirror: it runs before `lib/` exists,
  and its tests pin a private name.
- No edits to `lib/task_utils.sh` or `ait`, which carry another session's
  uncommitted hunks. `_git_with_timeout` only *calls*
  `_ait_detect_data_worktree`.

## Per-caller decision: non-interactive policy

Every caller runs with `--noninteractive` by default:
- **sync**: under the old `timeout`, a tty prompt could only stop until the
  kill fired. A GUI popup from a syncer timer is unwanted. Graphical auth stays
  available through the opt-out `AIT_SYNC_ALLOW_PROMPT=1` (post-phase).
- **drift-check**: always runs inside an agent session, with no human at a tty.
- **github_release**: it already sets `GIT_TERMINAL_PROMPT=0`. The policy also
  covers ssh via `insteadOf`.

## Implementation

1. **`aitask_sync.sh:_git_with_timeout`.** Keep the name, the `-C` argument
   building and all four call sites byte-identical:
   `test_sync_branch_mode_automerge.sh:1254-1269` greps those lines. Replace
   the `timeout`/watchdog branches with:
   ```bash
   local py
   py="$(resolve_python)"     # python_resolve.sh is already sourced (l.54)
   "${py:-python3}" "$SCRIPT_DIR/lib/bounded_run.py" \
       "${runner_args[@]}" -- git "${git_args[@]}"
   ```
   `runner_args` is set in post-phase step 1. Without the opt-out it is
   `--timeout "$NETWORK_TIMEOUT" --noninteractive`. The function returns git's
   status, or 124. Rewrite the comment header to describe bounded_run and the
   outer-grace contract (step 4).

2. **`aitask_remote_drift_check.sh:_git_fetch_with_timeout`.** Add
   `source "$SCRIPT_DIR/lib/python_resolve.sh"` at column 0, next to the
   other startup sources. That is the format contract in
   `tests/test_shell_startup_closure.py`. Its dependency, `terminal_compat.sh`,
   is already sourced. The body becomes:
   `"${py:-python3}" "$SCRIPT_DIR/lib/bounded_run.py" --timeout "$NETWORK_TIMEOUT" --noninteractive -- git fetch --quiet origin "$BASE_BRANCH"`.
   The `FETCH_FAILED` mapping is unchanged.

3. **`lib/github_release.sh:_github_ls_remote_tags`.** bounded_run becomes the
   preferred path. The in-shell job stays as a fallback for two cases:
   - `git` is a **shell function** (the test seam). An exec'd helper would
     bypass the function and make a live network call.
   - **No usable Python ≥ 3.8.** `aitask_setup.sh` sources this lib before the
     venv exists. bounded_run needs 3.8 for `signal.raise_signal` and
     `from __future__ import annotations`.

   Changes:
   - Add `_AIT_GITHUB_RELEASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"`
     at source time.
   - Add `_github_bounded_python`. It prints an interpreter and returns 0 only
     when all three hold: `! declare -F git`, `bounded_run.py` exists, and the
     candidate passes `"$py" -c 'import sys; sys.exit(sys.version_info < (3, 8))'`.
     The candidate is `${_AIT_RESOLVED_PYTHON:-}`, else `command -v python3`.
   - Bounded path:
     ```bash
     rc=0
     GIT_HTTP_LOW_SPEED_LIMIT=1 GIT_HTTP_LOW_SPEED_TIME="$timeout_s" \
     "$py" "$_AIT_GITHUB_RELEASE_DIR/bounded_run.py" --timeout "$timeout_s" \
         --noninteractive -- git ls-remote --tags --refs "$url" 'v*' \
         >"$tmp" 2>/dev/null || rc=$?
     [[ $rc -eq 124 ]] || cat "$tmp" 2>/dev/null || true
     ```
     The function still always returns 0 and prints nothing on a timeout.
   - The `set -m` block moves unchanged into the `else` branch.
   - The header comment describes both paths and why the fallback exists.

4. **Coordinate the outer runners.**
   - `lib/sync_action_runner.py:_run_sync_process`: pass
     `env=_sync_child_env()` to the Popen. `_sync_child_env()` copies
     `os.environ` and sets `GRACE_ENV` to
     `min(effective_grace(), child_grace(_TERM_GRACE_SECONDS))`, which is 1s by
     default, imported from `bounded_run`. With that grace, the nested
     bounded_run CLI does three things when the outer TERM arrives: it records
     the signal, kills its own group (TERM, then 1s grace, then KILL), and
     exits. All of that happens inside the outer 3s TERM window, so
     `_wait_session_empty` sees an empty session before any outer KILL round.
     Ownership: the outer runner proves only its own session. The inner
     session is owned by the inner runner, and the ordered graces guarantee
     that its cleanup has finished before the outer runner reports. State this
     in the `_TERM_GRACE_SECONDS` comment. Leave the signature of
     `_run_sync_process` unchanged, because three tests patch it.
   - `lib/framework_version.py:resolve_latest_version`: replace the
     hand-rolled Popen, `communicate(timeout)` and killpg-SIGKILL sequence with
     `bounded_run.run_bounded(cmd, timeout)`. That gives a new session, a
     TERM → grace → KILL group stop, and an exported child grace of 3s for the
     nested CLI, which finishes inside the outer 5s. Error mapping is
     unchanged: `TimeoutExpired` → `(None, "timeout after %gs")`, and
     `FileNotFoundError` / `OSError` → `(None, str(exc))`. Update the
     docstring.

5. **Tests: the hang fixtures always have a parent and a distinct stubborn
   child.** A "direct-child-only" cleanup must fail each one. Every cell
   asserts four things: the stubborn child was reached (fixture guard), the
   call returned within its bound, the caller's status, and **parent and child
   are both gone**. Each file also gets one **negative control**: SIGKILL only
   the direct child and assert that the stubborn child is still alive, which
   proves the fixture can catch that kind of cleanup. Then clean up.
   - **drift (`tests/test_remote_drift_check.sh`, new Test 18) and sync
     (`tests/test_sync.sh`).** Origin is `ssh://…invalid/repo.git` with a
     `core.sshCommand` stub that appends `$$`, runs `trap '' TERM` and
     `exec sleep 30`. The shape is git (parent) → stub (distinct stubborn
     child), as in `test_crew_publish_upstream.sh` `make_hanging_origin`.
     Set `AIT_BOUNDED_RUN_GRACE=1`. The control is to background a plain
     `git fetch`, `kill -KILL` the git pid only, and assert the stub is alive.
     - drift: `--timeout 2` → `FETCH_FAILED` within 8s.
     - sync, fetch hang: origin url points at the stub → `NO_NETWORK` within
       20s (`NETWORK_TIMEOUT` is a fixed 10s).
     - sync, push hang: the real url stays and `remote.origin.pushurl` points
       at the stub. A local task edit makes a push necessary → `NO_NETWORK`.
   - **github_release (`tests/test_github_release.sh`, after Test 11).** These
     cells run with `unset -f git` and a PATH stub dir first. The PATH `git`
     stub, on `ls-remote`, does:
     `sh -c 'trap "" TERM; exec sleep 30' & echo "$$ $!" >>"$STUB_PIDS"; wait`.
     Its own shell is the parent, which dies on TERM; the `sleep` is the
     distinct child that ignores TERM.
     - **12, bounded hang:** empty result, rc 0, within 8s, both pids gone.
     - **12c, control:** run the PATH stub directly, `kill -KILL` its pid only,
       and assert the child is alive.
     - **13, non-interactive env:** with `DISPLAY=:99`, an instant PATH stub
       records `GIT_ASKPASS=${GIT_ASKPASS-unset}|SSH_ASKPASS_REQUIRE=…|DISPLAY=…`.
       Expect `0.10.0`, and the record reads
       `GIT_ASKPASS=|SSH_ASKPASS_REQUIRE=never|DISPLAY=unset`.
     - **14, the seam still wins:** both a function `git` and a logging PATH
       `git` exist. Expect the function's `0.10.0` and an empty PATH log.
     - **15, fallback:** `_AIT_RESOLVED_PYTHON=/bin/false` with a TERM-honouring
       PATH hang stub. The call is still bounded (rc 0, empty, within 8s) and
       the pids are gone. The fallback keeps its TERM-only kill, as documented.
   - **Nested-runner integration (`tests/test_sync_action_runner.py`,
     `TimeoutContainmentTests`).**
     - Extend `_WRITER` with an optional `ignore_term` argument that sets
       `signal.signal(SIGTERM, SIG_IGN)`.
     - The stand-in `aitask_sync.sh` runs the **real**
       `lib/bounded_run.py --timeout 30 --noninteractive -- sh -c '<writer ignore_term=1 delay=4> & echo $$ >>pids; wait'`.
       That is a nested bounded runner, a transport parent, and a distinct
       stubborn writer.
     - Clear `AIT_BOUNDED_RUN_GRACE` from the test environment.
     - `test_timeout_stops_a_nested_bounded_runner`: `run_sync_batch(timeout=0.5)`
       returns `STATUS_TIMEOUT` with `stray_session is None`. Then sleep past
       the writer's delay (5s total) and assert no marker and every recorded
       pid gone.
     - `test_control_nested_runner_outlives_an_uncoordinated_outer`: patch
       `_sync_child_env` to return the plain `os.environ`, so the inner grace
       stays 5s. Assert that the marker **is** written, which shows the fixture
       is sensitive. Kill the leftovers in tearDown (pidfile).
     - `test_child_grace_fits_inside_the_outer_term_window`:
       `float(env[GRACE_ENV]) + NESTING_MARGIN_SECONDS <= _TERM_GRACE_SECONDS`.
   - **`tests/test_framework_version.py`:** the existing
     `test_timeout_degrades_and_kills_grandchild` must still pass. Add a nested
     case: a stub helper that runs the real `bounded_run.py` around a
     TERM-ignoring child. After a 0.5s timeout, assert the child is gone
     (before the fix, killpg-SIGKILL left it alive).

6. **Red proofs, without touching the shared worktree.** No stash and no
   restore. Run `git archive HEAD .aitask-scripts tests ait | tar -x -C <scratch>/old`,
   copy the *new* test files over that tree, and run them there. Expected: the
   "both gone" assertions fail on old drift, sync and github_release, and on
   the old `sync_action_runner` / `framework_version`. Test 13 also fails. The
   negative controls pass in both trees. Record the exact failing assertion
   lines in the plan's Final Implementation Notes.

### Post-phase (risk mitigations)

1. [sync_interactive_optout] **`AIT_SYNC_ALLOW_PROMPT=1`.** Prompts stay off by
   default. `runner_args=(--timeout "$NETWORK_TIMEOUT")`, plus `--noninteractive`
   unless `[[ "${AIT_SYNC_ALLOW_PROMPT:-}" == 1 ]]`. Only the exact value `1`
   enables prompts. The opt-out changes **only** the prompt policy: the same
   bounded_run new session, the same `NETWORK_TIMEOUT`, the same group kill
   and the same outer-grace contract. With no controlling terminal it enables
   **graphical** authentication only: `SSH_ASKPASS` on `DISPLAY` /
   `WAYLAND_DISPLAY`, a `GIT_ASKPASS` / `core.askPass` helper, or GCM's UI.
   That authentication has to finish inside the 10s bound. Scope: `ait sync`
   only.
2. [sync_interactive_optout] **Document it.**
   - `aitask_sync.sh`: an `Environment:` paragraph in `show_help`, and one line
     in the header.
   - `website/content/docs/commands/sync.md`: a short "Network timeout and
     authentication prompts" subsection under `## ait sync`, covering the 10s
     bound, the process-tree kill, prompts off by default, and when and how to
     set `AIT_SYNC_ALLOW_PROMPT=1`. Current-state prose. Then run
     `python3 check_links.py --build` in `website/`.
   - **Shared-file gate (sync.md).** Another session has uncommitted hunks in
     this file. Do every other step first.
     - **Before the first edit,** require both
       `git diff --quiet -- website/content/docs/commands/sync.md` (unstaged)
       **and** `git diff --cached --quiet -- website/content/docs/commands/sync.md`
       (staged) to pass. Re-check immediately before editing. If either fails,
       stop and ask the user.
     - **After my edit,** save `git diff HEAD -- <file>` to a scratch patch.
     - **Immediately before staging or committing,** recompute
       `git diff HEAD -- <file>` and require it to be byte-identical to the
       saved patch. Also require `git diff --cached -- <file>` to be empty or
       identical to it. On any mismatch, stop and ask; never stage that file as
       a whole.
     - **Commit path-scoped** (`git commit -- <paths>`) so no other staged
       paths ride along.
3. [sync_interactive_optout] **Test both modes** (`tests/test_sync.sh`). A PATH
   `git` wrapper execs the real git. For `fetch` / `push` only, it logs
   `GIT_ASKPASS=${GIT_ASKPASS-unset}|SSH_ASKPASS=${SSH_ASKPASS-unset}|SSH_ASKPASS_REQUIRE=${SSH_ASKPASS_REQUIRE-unset}|DISPLAY=${DISPLAY-unset}`.
   Each cell runs with `DISPLAY=:99 SSH_ASKPASS=/fake/askpass`, and a local
   change → `PUSHED`.
   - **default:** every line reads
     `GIT_ASKPASS=|SSH_ASKPASS=unset|SSH_ASKPASS_REQUIRE=never|DISPLAY=unset`.
   - **`AIT_SYNC_ALLOW_PROMPT=1`:** every line reads
     `GIT_ASKPASS=unset|SSH_ASKPASS=/fake/askpass|SSH_ASKPASS_REQUIRE=unset|DISPLAY=:99`.
   - **`AIT_SYNC_ALLOW_PROMPT=yes`:** the result matches the default.
   - **Opt-out keeps the bound and the cleanup:** the fetch-hang cell with
     `AIT_SYNC_ALLOW_PROMPT=1` → `NO_NETWORK` within 20s, both stub processes
     gone.
   - A guard asserts that the wrapper logged ≥1 fetch line.

## Verification

- Shell tests: `bash tests/test_remote_drift_check.sh`,
  `bash tests/test_sync.sh`, `bash tests/test_github_release.sh`,
  `bash tests/test_install_tarball_download.sh`,
  `bash tests/test_crew_publish_upstream.sh`, every `tests/test_sync_*.sh`,
  `tests/test_plan_approved_marker_drift.sh`, `tests/test_plan_paths_seam.sh`.
- Python: `bash tests/run_all_python_tests.sh --test-dir <scratch dir holding
  test_sync_action_runner.py, test_framework_version.py, test_bounded_run.py,
  test_shell_startup_closure.py>`, or run each one directly with python3.
  Read the last line for the verdict and keep `PIPESTATUS`.
- `shellcheck` on the three edited shell scripts.
- The red proofs from step 6.

Then Step 9 (Post-Implementation): commit, archive, merge per the task workflow.

## Risk

### Code-health risk: medium
- Adding a nesting level means every outer runner that wraps a migrated caller must order its cleanup budget ahead of bounded_run's grace. A missed wrapper would leak a transport and still report a clean stop. Both known wrappers (`sync_action_runner`, `framework_version`) are covered and tested here. A future wrapper could miss it. · severity: medium · → mitigation: step 4 + the nested integration tests (in scope)
- `ait sync` now runs non-interactive by default, which suppresses GUI askpass/GCM prompts. · severity: low · → mitigation: inline post-phase sync_interactive_optout
- `website/content/docs/commands/sync.md` carries another session's uncommitted hunks, staged or unstaged. · severity: low · → mitigation: the two-sided shared-file gate in post-phase step 2
- The worst-case bound grows by up to 5s of grace when a transport ignores TERM. · severity: low · → mitigation: None (inherent to a kill that reaps)

### Goal-achievement risk: low
- `github_release.sh` keeps its in-shell job as a bootstrap fallback, and `install.sh`'s mirror is unchanged, both for bootstrap reasons. The plan says so. · severity: low · → mitigation: None (constraint-driven)

### Planned mitigations
- name: sync_interactive_optout · timing: inline post-phase · inline_risk: low · added_complexity: low · addresses: the sync non-interactive policy suppressing GUI auth prompts (user chose to include it: default off, `AIT_SYNC_ALLOW_PROMPT=1`, documented, both modes tested)

Post-inline reassessment: code-health rises to **medium** because the
outer-runner coordination touches two more modules. Goal-achievement stays
**low**.

## Post-Review Changes

### Change Request 1 (2026-10-19)
- **Requested by user:** `_stop_sync_session` sent SIGTERM only to its first
  membership snapshot; a bounded runner the sync started after that snapshot was
  never asked to stop, was SIGKILLed after the 3s window mid-cleanup, and left its
  separate git session running while `stray_session=None` was reported.
  Reproduced by the reviewer by holding the first listing. Add the
  snapshot-versus-spawn interleaving as a regression test.
- **Changes made:** new `_term_session(sid, members)` in
  `lib/sync_action_runner.py` replaces the single-snapshot SIGTERM +
  passive wait. Every poll re-lists the session and SIGTERMs members not yet
  signalled. Escalation to the existing SIGKILL rounds waits until every live
  member has had `_TERM_GRACE_SECONDS` since its OWN SIGTERM, capped at
  2 × `_TERM_GRACE_SECONDS`, so a session that keeps spawning still escalates.
  Unknown membership still returns at once, which is fail-closed. Tests:
  `test_a_runner_started_after_the_first_listing_is_still_stopped` holds the
  first listing until the stand-in has launched the real bounded_run CLI and
  both transport processes. It fails on a single-snapshot mutant ("a
  late-started runner's transport outlived the result") and passes on the fix.
  `test_term_window_is_capped_for_a_session_that_keeps_spawning` covers the
  cap.
- **Files affected:** `.aitask-scripts/lib/sync_action_runner.py`,
  `tests/test_sync_action_runner.py`

### Change Request 2 (2026-10-19)
- **Requested by user:** (a) the 6s TERM cap could SIGKILL a late bounded runner
  mid-cleanup, leaving its separately-sessioned transport running while
  `stray_session=None` was reported (reviewer's real-process probe: marker
  written after 6.56s); (b) the outer TERM pass sent no SIGCONT, so a stopped
  runner could not run its cleanup before the SIGKILL rounds (marker written
  after 3.57s). Both need real-process regressions.
- **Root cause and changes made:** both hazards came from bounded_run always
  moving git into a NEW SESSION that the session-scoped outer stop cannot see.
  - `lib/bounded_run.py` `_child_isolation()`: a new session only when this
    runner HAS a controlling terminal, because that is the only way to drop
    one. Otherwise the child leads its own process group inside the caller's
    session: `process_group=0` on Python 3.11+, or `preexec_fn=os.setpgrp`
    while single-threaded (the CLI always is), else a new session as a last
    resort. There is still no prompt channel, because a non-leader can never
    acquire a terminal. Under `sync_action_runner` (a terminal-less session)
    every transport is now a member, so the SIGKILL rounds reach it and an
    empty session proves it gone. That holds even when the runner itself was
    cut down, which also makes the recovery probe sound.
  - `lib/bounded_run.py` `run_bounded`: when a stop was requested, the group
    is reaped even if the leader ended first. A session-scoped stop SIGTERMs
    the leader directly, which bounded_run used to read as a normal exit,
    leaving a TERM-ignoring member behind.
  - `lib/sync_action_runner.py` `_term_session`: SIGCONT follows each SIGTERM.
  - Comments updated in the sync, drift-check, github_release, and both crew
    helpers ("a new session" → "its own process group, no controlling
    terminal").
- **Tests:**
  - `test_sync_action_runner.py`: the stopped-runner case (SIGSTOP the real
    runner and expect an orderly stop within the TERM window), the cap case
    (a TERM-resistant spawner keeps the window open while its runner carries
    a 30s grace, so the cap's kill rounds cut it down mid-cleanup, and the
    transport must still die), and the main nested test now also asserts an
    orderly stop. The former "uncoordinated grace leaks" control became
    "uncoordinated grace falls to the kill rounds yet nothing escapes".
  - `test_bounded_run.py`: `TestChildIsolation`, covering the isolation
    policy, the actual sid/pgid in both modes, and a deterministic post-exit
    reap.
- **Red proofs (mutants in scratch, the shared worktree untouched):**
  - M1 (always a new session) fails the cap test with a surviving transport.
  - M2 (no SIGCONT) fails the stopped-runner test: 4.60s, not < 4.5s.
  - M3 (no post-exit reap) fails the main nested test (3.59s, not < 3.5s) and
    `test_a_stop_reaps_the_group_even_after_the_leader_ended`
    ("Cancelled not raised").
- **Files affected:** `.aitask-scripts/lib/bounded_run.py`,
  `.aitask-scripts/lib/sync_action_runner.py`, `.aitask-scripts/aitask_sync.sh`,
  `.aitask-scripts/aitask_remote_drift_check.sh`,
  `.aitask-scripts/lib/github_release.sh`,
  `.aitask-scripts/lib/agentcrew_utils.sh`,
  `.aitask-scripts/agentcrew/agentcrew_utils.py`,
  `tests/test_sync_action_runner.py`, `tests/test_bounded_run.py`

### Change Request 3 (2026-10-19)
- **Requested by user:** (a) in `test_a_stop_reaps_the_group_even_after_the_leader_ended`
  the stubborn child's `$$` sat inside a double-quoted `sh -c` string, so the
  leader shell expanded it. `child.pid` was the leader's pid, and the liveness
  check passed even with `_shielded_kill` as a no-op. (b) The
  `framework_version.resolve_latest_version` docstring still described
  unconditional separate sessions.
- **Changes made:** (a) the stubborn child is now its own script file, so its
  `$$` is its own pid. The test asserts that the child started and that its pid
  differs from the leader's, and it registers temp-dir and child-kill cleanup
  through `addCleanup`. Red-proved: the no-op-cleanup mutant fails on "the stop
  left the leader's child running", and the no-post-exit mutant fails with
  "Cancelled not raised". (b) The docstring now states the `_child_isolation`
  policy (own group; new session only with a controlling terminal) and keeps
  the ordered-grace explanation.
- **Files affected:** `tests/test_bounded_run.py`,
  `.aitask-scripts/lib/framework_version.py`

## Final Implementation Notes
- **Actual work done:**
  - `aitask_sync.sh:_git_with_timeout`, `aitask_remote_drift_check.sh:_git_fetch_with_timeout`
    and `lib/github_release.sh:_github_ls_remote_tags` run git through
    `lib/bounded_run.py --noninteractive`. Each keeps its 124 contract and its
    own knob. The sync's four call sites are byte-identical.
  - `github_release.sh` keeps the in-shell `set -m` job only as a fallback, used
    when `git` is a shell function (the test seam) or no Python ≥ 3.8 is
    available (bootstrap).
  - `AIT_SYNC_ALLOW_PROMPT=1` (exactly `1`) drops `--noninteractive` for
    `ait sync`. The bound, the missing terminal and the group kill are
    unchanged. It is documented in `show_help`, the script header and
    `sync.md` "Network Handling → Authentication prompts". The stale
    coreutils/watchdog paragraph there was rewritten.
  - The outer runners are coordinated. `sync_action_runner` exports
    `AIT_BOUNDED_RUN_GRACE = min(effective, child_grace(3s))`, and
    `framework_version` uses `run_bounded`.
- **Deviations from plan:**
  - Driven by three review rounds (Post-Review Changes 1–3). `bounded_run`
    now creates a new session only when it has a controlling terminal;
    otherwise git leads its own process group inside the caller's session.
    That makes every transport visible to `sync_action_runner`'s
    session-scoped stop and recovery probe.
  - A stop request reaps the group even after the leader exited.
  - `_term_session` signals late joiners, sends SIGCONT, waits a per-member
    grace and caps the window at 2× the grace.
  - Fail-closed preflights were added when the sweep caught a regression:
    with an unusable Python, the drift check printed `FETCH_FAILED` and sync
    would have printed `NO_NETWORK`, which hides a broken install behind
    "offline". The drift check now emits `EXTRACT_FAILED` (exit 3), as
    before, and sync emits `ERROR:no_python`. Both are checked before
    fetching.
  - `website/content/docs/commands/sync.md` passed the two-sided gate. It was
    clean both staged and unstaged after t1739 committed its hunks, and it
    was re-checked immediately before the edit.
  - Stale "new session" comments in `lib/agentcrew_utils.sh` and
    `agentcrew/agentcrew_utils.py` were corrected as well.
- **Issues encountered:**
  - `set -e` in `test_remote_drift_check.sh` turned the control's
    `wait <SIGKILLed pid>` (status 137) into a script exit, so the calls are
    now guarded with `|| true`.
  - With in-session groups, the outer SIGTERM reaches the transport leader
    directly. bounded_run read that as a normal exit, which led to the
    post-exit reap.
  - Timing-fragile cap fixture: a runner launched mid-stop was SIGTERMed
    during Python startup. It was replaced by a runner whose 30s cleanup
    grace outlasts the cap.
  - A `$$` expanded in the wrong shell in a test fixture (CR 3).
- **Key decisions:** the session/group policy is decided by bounded_run from a
  runtime fact (whether it has a controlling terminal), not by a caller flag,
  so every caller gets the right isolation without new plumbing. The non-interactive
  policy is on by default for all three callers.
- **Red proofs (old code = `git archive HEAD` snapshot plus the new test files,
  run in scratch):**
  - Drift `18e: every hanging transport process was killed (expected '', got '<pid>')`.
  - github_release `12: parent and stubborn child were both killed` and
    `13: GIT_ASKPASS empty, ssh askpass never, no display` (got
    `GIT_ASKPASS=unset|SSH_ASKPASS_REQUIRE=unset|DISPLAY=:99`).
  - Sync `17/17b/18: every hanging transport process was killed`.
  - `test_timeout_stops_a_nested_bounded_runner` (survivor) and
    `test_timeout_reaps_a_nested_bounded_runner` (2 survivors).
  - The controls (16, 12c, 18a) pass in both trees.
  - Mutants: M1/M2/M3 and the no-op-cleanup mutant, as recorded under CR 2/3.
- **Upstream defects identified:**
  - `.claude/skills/task-workflow/remote-drift-check.md:47` — the output-parsing
    list has no `EXTRACT_FAILED` branch, although `aitask_remote_drift_check.sh`
    emits it (exit 3) for an unreadable plan, an unreachable `plan_paths.py`
    and, now, an unusable Python. An agent following the procedure gets no
    instruction for the infra-failure token.
