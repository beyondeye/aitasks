---
Task: t2024_crew_git_network_timeout.md
Base branch: main
Output branch: main
---

# t2024 — Time-limit the crew git network operations

## Context

Since t2016, crew writes really talk to `origin`: `push -u origin HEAD` in init,
addwork, setmode, every runner iteration and every terminal `ait crew status set`,
plus a `pull --rebase` in addwork/setmode and the runner's fetch (t2018). None of them
has a time limit. An origin that is routable but never answers (TCP connect waits out
the kernel SYN retries, about 2 minutes on Linux; curl's connect default is 300s) can
stall crew init, brainstorm agent registration (`brainstorm_crew._run_addwork` runs
`ait crew addwork` with no subprocess timeout) and the runner, whose heartbeat goes
stale at 180s.

Goal: bound every crew git network operation, treat a timeout like any other
best-effort failure, and give `_run_addwork` a timeout surfaced as a registration
failure.

**t2018 landed** (`ab2cf4b37`). Its `_sync_with_upstream()` already splits the runner
pull into a narrowed `git fetch --quiet -- <remote> <merge_ref>` plus local steps, so
only that fetch needs bounding on the Python side. Its test harness wraps
`agentcrew_utils.git_cmd` and hooks the `fetch` call, so the bound goes **through
`git_cmd`**.

**Revision after review.** Two blocking points, both verified:
1. The first draft promised never to kill a step that writes the worktree, yet put a
   kill deadline over all of addwork. addwork writes the agent files, then commits,
   then rebases (`aitask_crew_addwork.sh:173–333`), all before any network step. The
   runner reads agents from those files on disk and commits whatever it finds
   (`git add -A`). No command removes an agent, and `Waiting → Aborted` is not a valid
   transition. So a torn registration is real, and "unknown" was not guidance.
2. `GIT_TERMINAL_PROMPT=0` and `</dev/null` do not make SSH non-interactive. git's
   `git_prompt()` still runs `GIT_ASKPASS` / `core.askPass` / `SSH_ASKPASS` first. A
   `set -m` job still has the controlling terminal. A new session without one makes
   OpenSSH use `SSH_ASKPASS` when `DISPLAY` is set (`ssh(1)`, OpenSSH 10.5 installed).
3. (Second review.) The nested runners' cleanups raced with equal graces. Decision 2
   now orders them explicitly, and D6/D7 test the real nesting.

## Design decisions

1. **One bounded runner: a new stdlib-only `lib/bounded_run.py`.** I searched
   `.aitask-scripts/lib/`: there is no generic helper. `aitask_sync.sh:_git_with_timeout`
   and `aitask_remote_drift_check.sh:_git_fetch_with_timeout` are script-local, and
   their macOS fallback kills only the direct child. `lib/github_release.sh`'s
   watchdog is private to `ls-remote` and keeps the terminal. The module has three
   parts:
   - `run_bounded(cmd, timeout, *, env=None, stop_grace=0)`: new session (no
     controlling terminal), stdin `/dev/null`, stdout/stderr in temp files (a
     lingering descendant such as an ssh ControlPersist master cannot block the
     reader), and kill on expiry only.
   - `noninteractive_env(base)`.
   - A CLI.

   Python callers import it. The shell crew helpers run its CLI, because a new session
   needs `setsid` and macOS has no such binary. The crew scripts already require Python
   (`launch_modes_sh.sh` runs `${_AIT_RESOLVED_PYTHON:-python3}` at source time). One
   implementation means one tested mechanism, and it is the target for the
   consolidation follow-up.
2. **Kill sequence on expiry:** SIGTERM to the session's process group (git removes
   its `*.lock` files), then SIGCONT, then poll **the group, not the leader** for the
   grace period, then SIGKILL. On a normal exit the group is never signalled. The CLI
   turns SIGINT/SIGTERM/SIGHUP into the same group kill. Repeat signals are ignored
   while it cleans up, and afterwards it re-raises the signal on itself, so bash sees
   a signal death and Ctrl-C still stops the script.

   **Nested runners get strictly ordered graces** (second review). The runners nest:
   brainstorm's `run_bounded` owns addwork's group, that group contains the
   `bounded_run.py` CLI, and the CLI starts git in a *separate* session the outer kill
   cannot reach. With equal graces the inner cleanup starts later, so the outer SIGKILL
   can land on the CLI before it escalates, and a TERM-ignoring transport survives
   (the reviewer reproduced this with scaled equal graces).

   Coordination: `run_bounded` exports `AIT_BOUNDED_RUN_GRACE = max(1.0, own_grace −
   2.0)` into its child's environment. Every `run_bounded` / CLI that finds that
   variable uses it as its own grace (normalized: a float in (0, 60]; otherwise the 5s
   default). The top level gets 5s and the nested CLI 3s. The 2s margin covers signal
   delivery, the Python handler, the 0.1s poll and the reap, so the inner TERM → CONT
   → KILL finishes, and the CLI exits, inside the outer grace. Ordering holds for two
   levels with the defaults (the deepest real nesting: brainstorm → addwork → CLI →
   git). A third level would floor at 1s and is documented as unsupported.
3. **Non-interactive network policy** (every bounded crew fetch/push):
   - new session, so no ssh, plink or configured script can open `/dev/tty`;
   - `GIT_TERMINAL_PROMPT=0`;
   - `GIT_ASKPASS=""`: set but empty, so `git_prompt()` skips `core.askPass` and
     `SSH_ASKPASS` for git's own credential prompts;
   - `SSH_ASKPASS_REQUIRE=never` (OpenSSH ≥ 8.4);
   - `SSH_ASKPASS`, `DISPLAY` and `WAYLAND_DISPLAY` removed (older OpenSSH falls
     back to a default askpass whenever `DISPLAY` is set);
   - `GCM_INTERACTIVE=never` (Git Credential Manager).

   Configured SSH commands (`core.sshCommand`, `GIT_SSH_COMMAND`, `GIT_SSH`) are
   respected, with **no option injection**: `-o BatchMode=yes` would break
   plink-variant commands. The environment alone removes every prompt channel the
   operation itself owns. Credentials must come from ssh-agent or a credential helper.
   Outside the policy: a prompt raised by an already-running agent daemon (ssh-agent
   confirm, gpg-agent pinentry); the bound still applies to it.
4. **Bound only network steps.** addwork/setmode's `git pull --rebase` becomes a
   bounded fetch of the tracked branch plus a local `git rebase --no-autostash`, which
   runs only after a successful fetch (when `pull --rebase` would have rebased). The
   upstream is read the same way as t2018's `_upstream_source`.
5. **The registration deadline is a stop request, not a kill.** `_run_addwork` waits
   up to `2 × crew_git_timeout() + 60s`, then sends SIGTERM **to the addwork process
   only**.
   - addwork traps TERM and only records it. bash runs a trap after the current
     foreground step returns, so the write+commit subshell and the rebase always
     finish, and a fetch/push already running finishes within its own bound.
   - After the commit, a pending stop skips the remaining network steps. addwork still
     prints `ADDED:` and exits 0, the same outcome as an offline publish today, and
     `_run_addwork` succeeds.
   - The network calls move out of the `( cd … )` subshell, so the main shell sees the
     flag.
6. **Last resort: a hung local step.** If addwork has not exited 60s after the stop
   request, a git hook or commit signing is stuck. `run_bounded` kills the group, and
   `_run_addwork` reads the crew worktree back and reports **what is actually there**:

   | state read back | result |
   |---|---|
   | `crew_merge_state()` names a merge/rebase | RuntimeError: a rebase was cut off. `git -C <wt> rebase --abort` returns the branch to its registration commit, and the runner holds (`PULL_UNSAFE`) until then. After it, `<a>` stays registered, but brainstorm did not record it or write its input. |
   | `HEAD:<a>_status.yaml` exists | **success**, return the name: registered, and the next crew push publishes it |
   | `<a>_status.yaml` exists, not in HEAD | RuntimeError: written and staged, not committed. A running crew runner reads agents from these files and sweeps them into its next commit, so `<a>` may be launched with placeholder input. Complete with `git -C <wt> commit -m "crew: Add agent '<a>' …"`, or discard: unstage and delete `<wt>/<a>_*`, then drop `<a>` from `_crew_meta.yaml`'s agents list (check `git -C <wt> diff` first). |
   | none of the above | RuntimeError: killed before writing anything; nothing registered; retry |

   Every message names the cause first ("a git hook or commit signing in the crew
   worktree did not finish; fix it first") and the bound used. "Committed ⇒ success"
   is deliberate: with no command to remove an agent, raising for a committed
   registration would orphan an agent that brainstorm could have recorded.
7. **Bound value:** `AIT_CREW_GIT_TIMEOUT` (whole seconds), default **10**. That is
   the framework's existing network bound (`NETWORK_TIMEOUT=10`,
   `AIT_GIT_LSREMOTE_TIMEOUT`, `curl --max-time 10`). Values that are unset, empty,
   zero, negative, non-numeric or longer than 6 digits fall back to 10. Timeout
   warnings name the knob.
8. **Out of scope:** the `git push origin --delete` calls in crew cleanup, brainstorm
   delete and brainstorm reopen (spawned "after" mitigation).

## Implementation steps

1. **Probes (scratch dir, before editing; stop and revise if any disagrees):**
   - (a) a local HTTP server answering 401: `GIT_ASKPASS=""` suppresses a
     `core.askPass` and an `SSH_ASKPASS` sentinel, while plain git invokes them;
   - (b) `ssh-keygen -y -f <passphrase key>` under `setsid` with the policy env
     invokes no askpass sentinel, even with `SSH_ASKPASS_REQUIRE=force` in the parent;
   - (c) `push -u origin HEAD` sets the upstream when the remote is already up to date;
   - (d) a TERM to the bash leader alone is handled only after a running subshell or
     child returns;
   - (e) git 2.55 accepts a stub `gpg.program` for commit and rebase signing;
   - (f) the repo's `pre-commit` / `pre-rebase` hooks run in the crew worktree.

2. **`.aitask-scripts/lib/bounded_run.py`** (new, stdlib only):
   - `run_bounded()` as in decisions 1–2. With `stop_grace > 0`, on expiry it sends
     SIGTERM to the leader alone and waits `stop_grace`. An exit returns
     `BoundedResult(CompletedProcess)` with `stopped=True`; otherwise it kills the
     group and raises `subprocess.TimeoutExpired`. Any other `BaseException` (e.g.
     KeyboardInterrupt) kills the group and re-raises.
   - `kill_process_group(proc, grace)`, plus `effective_grace()`, which reads
     `AIT_BOUNDED_RUN_GRACE` or falls back to `KILL_GRACE_SECONDS = 5.0`.
     `run_bounded` sets `AIT_BOUNDED_RUN_GRACE` in the child env to
     `max(MIN_GRACE=1.0, grace − NESTING_MARGIN=2.0)` (decision 2).
   - `noninteractive_env(base=None)`, implementing decision 3.
   - CLI `bounded_run.py --timeout N [--noninteractive] -- <cmd…>`: the child's output
     on its stdout/stderr, and its exit code (124 on timeout, 127 if the command cannot
     be run). A signal triggers the group kill and is then re-raised.

3. **`.aitask-scripts/lib/agentcrew_utils.sh`:**
   - `_AIT_AGENTCREW_LIB_DIR`, captured at source time (this file overwrites
     `SCRIPT_DIR`), and `_AIT_CREW_GIT_TIMEOUT_DEFAULT=10`.
   - `crew_git_timeout`: the same normalization as the Python side.
   - `_crew_git_bounded <wt> <outfile> <git-args…>`: runs `bounded_run.py --timeout
     "$(crew_git_timeout)" --noninteractive -- git -C <wt> …`, output to `<outfile>`,
     and returns its rc.
   - `crew_push`: same contract (origin check, `push --quiet -u origin HEAD`, nothing
     on stdout, returns 1 on failure) through the helper and a mktemp file. rc 124
     gives `warn "git push of the crew branch to origin timed out after <N>s (origin
     did not answer in time; AIT_CREW_GIT_TIMEOUT sets the bound)"`; other failures
     keep the existing warning plus git's raw output.
   - New `crew_pull_rebase <wt>`: resolve the branch and its upstream (return 1
     quietly when there is none). Run the bounded `fetch --quiet -- <remote> <ref>`,
     and only on rc 0 run `git -C <wt> rebase --no-autostash --quiet`. All quiet; the
     t2008 rationale goes in its comment.

4. **`aitask_crew_addwork.sh`:**
   - `trap '_AIT_CREW_STOP=1' TERM` near the top, with a comment pointing at the stop
     request.
   - The commit subshell keeps only `git add` + `git commit`.
   - After it, `[[ -n "${_AIT_CREW_STOP:-}" ]] || crew_pull_rebase "$WT_PATH" || true`,
     then the same guard on `crew_push "$WT_PATH"`. A skipped tail prints one stderr
     note ("publishing skipped: stop requested").

   **`aitask_crew_setmode.sh`:** the pull becomes `crew_pull_rebase . || true` (no
   stop requester exists for setmode). `aitask_crew_init.sh` is unchanged.

5. **`.aitask-scripts/agentcrew/agentcrew_utils.py`:**
   - Make `../lib` importable, appended to `sys.path` if missing. Importers differ
     (the t2018 harness, Test 7, the runner, agentcrew_status).
   - Import `run_bounded`, `noninteractive_env`.
   - `CREW_GIT_TIMEOUT_DEFAULT`, `GIT_TIMED_OUT = 124`, `crew_git_timeout()`.
   - `git_cmd(…, timeout=None)`: unchanged without `timeout`. With it, `run_bounded`
     plus `noninteractive_env()`; a TimeoutExpired becomes `CompletedProcess(124,
     stderr="timed out after <N>s (the remote did not answer in time;
     AIT_CREW_GIT_TIMEOUT sets the bound)")`, and `check` is honoured.
   - `_sync_with_upstream`'s fetch and `git_push`'s push pass
     `timeout=crew_git_timeout()`. A timeout goes down the existing `fetch_failed:` /
     push-warning paths (warned when not batch).

6. **`tests/test_crew_pull_no_autostash.sh` harness:**
   `wrapped_git_cmd(worktree, *a, check=True, **kw)` forwards `**kw`.

7. **`.aitask-scripts/brainstorm/brainstorm_crew.py`:**
   - Import `run_bounded` (lib) and `crew_git_timeout`, `crew_merge_state`,
     `crew_worktree_path` (agentcrew_utils).
   - `_ADDWORK_LOCAL_HEADROOM_S = 60`, `_ADDWORK_STOP_GRACE_S = 60`,
     `_addwork_timeout()`.
   - `_run_addwork`: `run_bounded(cmd, _addwork_timeout(),
     stop_grace=_ADDWORK_STOP_GRACE_S)`. A normal or stopped result goes through the
     existing rc / `ADDED:` handling. TimeoutExpired goes to `_addwork_outcome(crew_id,
     agent_name, limit)`, which applies the decision-6 table and returns the name or
     raises RuntimeError.

8. **`tests/lib/test_scaffold.sh`:** copy `lib/bounded_run.py` (stdlib leaf; reached
   by `agentcrew_utils.sh` whenever an origin exists), with a comment.

9. **Tests.** `$SECONDS` timing; `AIT_CREW_GIT_TIMEOUT=2` unless stated.
   - **`tests/test_crew_publish_upstream.sh`** (task-requested), hang fixture: origin
     `ssh://crew-hang.invalid/repo.git`, `core.sshCommand` = a stub appending `$$` to
     `hang.pids` with `trap '' TERM; exec sleep 30`, `ssh.variant=ssh`.
     `assert_hang_reaped` requires a non-empty pid file and every pid gone.
     - 9 **control:** a plain `git ls-remote origin` is still running after 3s.
     - 10 init: exit 0, `CREATED:`, ≤ 10s, "timed out after 2s", nothing on stdout,
       no upstream, reaped.
     - 11 heal: point origin at `$REMOTE`, run addwork, `ADDED:` and
       `assert_published`.
     - 12–14 a published crew whose origin then hangs:
       - addwork: fetch and push both reach the transport;
       - setmode;
       - `ait crew status set … Completed`.

       Each exits 0 with its structured line, ≤ 16/16/10s, reaped, local commit made,
       remote tip unchanged. Status set prints `git push warning: timed out`.
     - 15 `git_pull(wt, batch=False)`: `deferred` / `fetch_failed: timed out…`,
       ≤ 10s, no merge state, reaped.
     - 16 `crew_git_timeout` normalization: `""`/0/-1/abc/08x/1234567 → 10; 08 → 8; 3 → 3.
   - **`tests/test_bounded_run.py`** (new, unittest):
     - normal output and rc;
     - expiry kills a TERM-ignoring grandchild within timeout + grace + 1;
     - a normal exit with a lingering descendant holding stdout returns in < 2s and the
       descendant is **still alive** (killed in cleanup);
     - KeyboardInterrupt (SIGALRM handler) kills the child;
     - `stop_grace`: a child that traps TERM and exits cleanly gives `stopped=True` and
       is not killed; a child ignoring TERM is killed after the grace with
       TimeoutExpired;
     - CLI: rc passthrough, 124 on timeout, SIGINT to the CLI kills it by SIGINT and
       the grandchild is gone;
     - grace propagation: a child sees `AIT_BOUNDED_RUN_GRACE=3.0` under a default
       parent, and the CLI honours an inherited value (a TERM-ignoring grandchild is
       SIGKILLed after it, measured);
     - `noninteractive_env` keeps `GIT_SSH_COMMAND`/`GIT_SSH` and sets or removes
       exactly the decision-3 variables;
     - `crew_git_timeout` normalization.
   - **`tests/test_crew_git_noninteractive.sh`** (new; concern 2). Hostile parent env:
     `GIT_ASKPASS`, `core.askPass` and `SSH_ASKPASS` all set to a sentinel that logs
     its invocation, `SSH_ASKPASS_REQUIRE=force`, `DISPLAY=:0`.
     - (a) HTTP-401 origin (python `http.server` on 127.0.0.1): `crew_push` and
       `git_cmd(timeout=)` never run the sentinel and fail fast with git's "terminal
       prompts disabled"; **control** — plain `git ls-remote` runs it.
     - (b) a configured SSH command reaching OpenSSH's own `read_passphrase`
       (`ssh-keygen -y -f <passphrase-protected key>`, then exit 255): the sentinel is
       not run through either crew path; **control** — plain git runs it. Visible SKIP
       when `ssh-keygen` is absent.
     - (c) **terminal-backed**: under a pty (`python -c` with `pty.fork`, the child
       owning the pty as its controlling terminal), the configured SSH command records
       whether `/dev/tty` opens: through `crew_push` and `git_cmd(timeout=)` → `no-tty`;
       **control** — plain git in the same pty → `tty`.
   - **`tests/test_brainstorm_addwork_deadline.sh`** (new; concern 1, deterministic).
     A fixture repo with a published crew and a stub `./ait` (`crew addwork` → `exec`
     the script). The real `_run_addwork` is driven by a Python harness that patches
     `_addwork_timeout`, `_ADDWORK_STOP_GRACE_S` and `AIT_CREW_GIT_TIMEOUT`.
     - D1 slow commit: a `pre-commit` hook writes `start`, sleeps 4s and writes `end`;
       deadline 1s, grace 15s. Returns the name, `end` exists (the hook was not killed),
       elapsed ≥ 4s, HEAD has the registration, no merge state, remote tip unchanged
       (stop honoured: publishing skipped).
     - D2 slow rebase: a peer commit on the remote, `commit.gpgSign` with a stub
       `gpg.program` that is fast on the commit's signature and sleeps 4s on the
       rebase's re-sign, recording whether `rebase-merge` exists. Deadline 1s. Returns
       the name; the stub recorded `in-rebase`; the rebase completed (HEAD contains the
       peer commit and the registration); no merge state; push skipped.
     - D3 hung commit (last resort): the stub `gpg.program` hangs with
       `trap '' TERM` on the commit; deadline 1s, grace 2s. RuntimeError with the
       "written and staged, not committed" text and both remedies; the agent's files
       are in `git diff --cached`; no `index.lock`; stub pid reaped; elapsed < 12s.
     - D4 network stop: the origin hangs (`AIT_CREW_GIT_TIMEOUT=3`), deadline 1s. Returns the name within
       ≤ 9s, only the fetch reached the transport (push skipped), the registration is
       committed.
     - D5 `_addwork_outcome` on constructed worktrees: a rebase stopped on a conflict
       gives the merge-state message; committed gives success; staged gives the staged
       message; empty gives "nothing registered".
     - D6 **nested cancellation, KeyboardInterrupt**. The real nesting is
       `_run_addwork` → addwork → CLI → git → TERM-ignoring ssh stub, with
       `AIT_CREW_GIT_TIMEOUT=30` so the fetch hangs. A SIGALRM handler raises
       KeyboardInterrupt at 1s. Assert: KeyboardInterrupt propagates, elapsed ≤ 1 +
       5 + 2s, every stub pid is gone, and no fixture process survives (a unique marker
       in the stub's argv is checked with `ps`).
     - D7 **nested cancellation, last resort**: the same hang, deadline 1s, stop grace
       1s. The outer group kill fires at about 2s, and the inner CLI must reap the stub
       at about 5s, before the outer SIGKILL at about 7s. Assert: stub reaped,
       elapsed ≤ 10s, and the outcome is read back (committed → success).
   - **`tests/test_brainstorm_crew.py`:** the two `subprocess.run` seams also patch
     `brainstorm.brainstorm_crew.run_bounded`. New: `_run_addwork` calls it with
     `_addwork_timeout()` and the stop grace, and TimeoutExpired is routed through
     `_addwork_outcome`.

10. **Docs** (read `aidocs/framework/documentation_conventions.md` first,
    current-state only):
    - `website/content/docs/commands/crew.md`, init section: every fetch and push to
      origin is limited to 10s (`AIT_CREW_GIT_TIMEOUT`) and runs without a terminal or
      askpass program, so it never asks for a passphrase or password (use ssh-agent or
      a credential helper). A push that times out is retried by the next crew commit.
    - `aidocs/agentcrew/agentcrew_architecture.md` "Runner Orchestration": one
      sentence on the bound and policy.
    - `cd website && python3 check_links.py --build`.

## Verification

- Step 1 probe results recorded in the plan notes.
- `bash` each of: `test_crew_publish_upstream.sh`, `test_crew_git_noninteractive.sh`,
  `test_brainstorm_addwork_deadline.sh`, `test_crew_pull_no_autostash.sh`,
  `test_crew_init.sh`, `test_crew_setmode.sh`, `test_crew_runner.sh`,
  `test_crew_status.sh`, `test_agentcrew_terminal_push.sh`, `test_crew_groups.sh`,
  `test_crew_addwork_output_instructions.sh`, `test_brainstorm_cli.sh`,
  `test_agentcrew_pythonpath.sh`.
- `bash tests/run_all_python_tests.sh` (background; the verdict is the last line).
- **Red proofs**, in a detached scratch worktree with my files copied in, never in the
  shared tree. Each outcome is recorded.

  | mutant | cell that must turn red |
  |---|---|
  | M1 CLI ignores `--timeout` | hang-cell elapsed |
  | M2 leader-only kill on expiry | reaped |
  | M3 no SIGKILL escalation | reaped |
  | M4 `start_new_session=False` | (c) sees `tty` |
  | M5 no `GIT_ASKPASS=""` | (a) sentinel runs |
  | M6 no `SSH_ASKPASS_REQUIRE`/`DISPLAY` strip | (b) sentinel runs |
  | M7 deadline kills the group at once | D1/D2 |
  | M8 network calls back inside the subshell | D4 |
  | M9 committed state raises | D5 |
  | M10 child grace ≥ parent grace (e.g. `+2.0` instead of `−2.0`) | D6/D7 stub survives |
  | M11 CLI ignores `AIT_BOUNDED_RUN_GRACE` | D6/D7 |
- `shellcheck` on the three shell files; `python3 -m py_compile` on the changed modules.
- Commit only the named paths (other sessions have dirty files on main); `git add` the
  three new files.

## Risk

### Code-health risk: medium
- addwork's commit/publish block is restructured (TERM stop-request trap; network
  calls out of the subshell), and every crew network operation now runs through a new
  module that both languages share. A mistake breaks crew registration or publishing.
  Bounded by the hang cells, D1–D5 and mutants M1–M9 · severity: medium ·
  → mitigation: none
- `lib/bounded_run.py` is a fifth bounded-run implementation until sync, drift-check
  and github_release move onto it, and two of those still kill only the direct child
  on macOS · severity: low · → mitigation: consolidate_bounded_git_helpers
- Crew fetch/push can no longer prompt at all (no terminal, no askpass, no display). A
  user who answered an ssh passphrase or host-key prompt during `ait crew init` now
  gets a timeout or auth failure and must use ssh-agent or a credential helper
  (documented) · severity: low · → mitigation: none
- Nested cleanup is ordered by time, not by handshake: the 2s margin assumes the
  inner CLI is scheduled within it. Under extreme load an outer SIGKILL could still
  pre-empt the inner escalation, leaving a TERM-ignoring transport alive. Bounded by
  D6/D7 and mutants M10/M11 · severity: low · → mitigation: none
- `git_cmd` gains `timeout=`, and `_run_addwork` changes seam (`run_bounded`): t2018's
  harness wrapper and two brainstorm test seams must forward or patch it · severity:
  low · → mitigation: none

### Goal-achievement risk: low
- The 10s default could be tight for a slow link or a large `_output.md` push; each
  attempt then times out until `AIT_CREW_GIT_TIMEOUT` is raised (the warning names the
  knob) · severity: low · → mitigation: none
- A stop request that arrives during a fetch/push takes effect only when that
  operation ends (≤ its bound), because the leader-only signal waits for the
  foreground step · severity: low · → mitigation: none
- The last resort (a hook or signing hung for more than 2 minutes) can still leave a
  staged-but-uncommitted registration or a cut-off rebase. Both are reported from the
  read-back state with remedies, but no command removes an agent, so `<a>` can still
  be launched with placeholder input if the user does not act · severity: low ·
  → mitigation: none
- Prompts raised by an already-running agent daemon (gpg-agent pinentry, ssh-agent
  confirm) are outside the policy; only the bound applies · severity: low ·
  → mitigation: none
- The crew-branch deletion pushes (`ait crew cleanup`, brainstorm delete, brainstorm
  reopen) stay unbounded · severity: low · → mitigation: crew_branch_delete_push_timeout

### Planned mitigations
- timing: after | name: consolidate_bounded_git_helpers | type: refactor | priority: low | effort: medium | inline_risk: high | added_complexity: high | addresses: code-health — bounded-run implementations duplicated; sync/drift-check macOS fallback kills only the direct child | desc: Move aitask_sync.sh:_git_with_timeout, aitask_remote_drift_check.sh:_git_fetch_with_timeout and github_release.sh's ls-remote watchdog onto lib/bounded_run.py (new session, process-group kill with TERM→CONT→KILL, temp-file output, non-interactive env)
- timing: after | name: crew_branch_delete_push_timeout | type: enhancement | priority: low | effort: low | inline_risk: low | added_complexity: medium | addresses: goal-achievement — crew-branch deletion pushes stay unbounded | desc: Bound `git push origin --delete crew-<id>` in aitask_crew_cleanup.sh, aitask_brainstorm_delete.sh and brainstorm_app.py's reopen path with the t2024 crew helpers (_crew_git_bounded / git_cmd timeout=)

## Step 9 (Post-Implementation)

Current-branch mode (profile `fast`): no branch to merge. Archive via
`./.aitask-scripts/aitask_archive.sh 2024` and `./ait git push`.
