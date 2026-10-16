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
  on macOS · severity: low · → mitigation: t2035
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
  reopen) stay unbounded · severity: low · → mitigation: t2036

### Planned mitigations
- timing: after | name: consolidate_bounded_git_helpers | type: refactor | priority: low | effort: medium | inline_risk: high | added_complexity: high | addresses: code-health — bounded-run implementations duplicated; sync/drift-check macOS fallback kills only the direct child | desc: Move aitask_sync.sh:_git_with_timeout, aitask_remote_drift_check.sh:_git_fetch_with_timeout and github_release.sh's ls-remote watchdog onto lib/bounded_run.py (new session, process-group kill with TERM→CONT→KILL, temp-file output, non-interactive env) | created: t2035
- timing: after | name: crew_branch_delete_push_timeout | type: enhancement | priority: low | effort: low | inline_risk: low | added_complexity: medium | addresses: goal-achievement — crew-branch deletion pushes stay unbounded | desc: Bound `git push origin --delete crew-<id>` in aitask_crew_cleanup.sh, aitask_brainstorm_delete.sh and brainstorm_app.py's reopen path with the t2024 crew helpers (_crew_git_bounded / git_cmd timeout=) | created: t2036

## Step 9 (Post-Implementation)

Current-branch mode (profile `fast`): no branch to merge. Archive via
`./.aitask-scripts/aitask_archive.sh 2024` and `./ait git push`.

## Post-Review Changes

### Change Request 1 (2026-10-16 07:45)
- **Requested by user:** `_shielded_kill` shielded only SIGINT. A SIGTERM/SIGHUP
  arriving after the CLI's ordinary timeout cleanup had begun ran `_on_signal`,
  raised `_Interrupted` out of the TERM→CONT→KILL loop, and the CLI died (-15)
  before SIGKILLing git's separate process group: a TERM-ignoring child survived
  (reproduced by the reviewer). This also broke nested ordering when an outer
  cancellation lands during the inner runner's own timeout cleanup. Defer the
  forwarded signals throughout cleanup, preserve the eventual signal exit, and add
  a test that sends TERM/HUP after the cleanup has begun.
- **Changes made:**
  - `_shielded_kill` now defers SIGINT, SIGTERM and SIGHUP while the group is being
    killed: it records the first one and re-delivers it with `signal.raise_signal`
    through the handler that was in place, so the process still raises or exits
    the way that signal says, after the SIGKILL. The previous handler is restored,
    and `None` (installed outside Python) becomes SIG_DFL.
  - The CLI's handlers only **record** (`_record_signal`). `run_bounded` gained a
    `cancelled=` callable that its wait polls (`_wait`): when set, it kills the group
    and raises `Cancelled`. No exception can therefore cut into the CLI's cleanup,
    even in the instant before the deferral is installed. `main()` ends the CLI by
    the first recorded signal on every path (cancelled, timed out, or a signal
    arriving after the command ended), so the shell still sees a signal death.
  - Tests: `test_bounded_run.py::TestCli::test_term_or_hup_during_the_timeout_cleanup`
    (SIGTERM and SIGHUP at 1.0s into a 0.3s timeout with a 2s grace: the CLI dies by
    the signal only after ≥ 2s and the TERM-ignoring child is gone);
    `TestRunBounded::test_a_signal_during_cleanup_is_deferred_until_the_group_is_dead`
    (in-process: a SIGHUP handler that raises surfaces only after the SIGKILL);
    `test_brainstorm_addwork_deadline.sh` D8 (real nesting: the fetch times out at
    about 1.4s, and the outer KeyboardInterrupt at 3s lands in the nested CLI's
    cleanup; the transport must still be reaped).
  - Red proofs (scratch worktree): M12, the original code (SIGINT-only shield plus a
    raising CLI handler), fails both new `test_bounded_run.py` cells and D8. M12a
    (SIGINT-only shield with the record-only CLI kept) fails the in-process deferral
    cell. M1 was re-run against the rewritten CLI: still RED.
- **Files affected:** `.aitask-scripts/lib/bounded_run.py`, `tests/test_bounded_run.py`,
  `tests/test_brainstorm_addwork_deadline.sh`

### Change Request 2 (2026-10-16 07:59)
- **Requested by user:** at the Step 8b upstream-defect offer: "fix it now" (in this
  task, not as a follow-up task).
- **Changes made:**
  - First confirmed the mechanism in a scratch Hugo site: `hugo list future` lists a
    bare `date:` that is tomorrow in UTC (read as `…T00:00:00Z`). An offset timestamp
    keeps its instant (`…+03:00`) and is not future. The site's `hugo.toml` sets no
    `timeZone`.
  - The defect's pin was refined: the date comes mainly from line 132,
    `%(creatordate:short)`, which formats in the tag's own +03:00 zone. Line 136
    (`date +%Y-%m-%d`) is only the fallback.
  - `website/new_release_post.sh`: `RELEASE_DATE` is now the exact RFC 3339 instant
    with its offset. The tag path uses `%(creatordate:iso-strict)`; the fallback uses
    `date +%Y-%m-%dT%H:%M:%S%z` with the colon inserted (one call; BSD date has no
    `%:z`). This value goes into both front-matter templates. `RELEASE_DAY` (first 10
    chars, the local day) feeds only the landing page's "Mon DD, YYYY" display.
  - New `tests/test_release_post_date.sh` runs the real script in a fixture repo:
    - cell 1 (`--auto`, tag at 2026-10-16T01:49:12+03:00, inside the window): the
      date is that exact instant, it is not after the release instant, the old bare
      day is shown to be after it (control), and the landing page shows "Oct 16, 2026";
    - cell 2 (scaffold, no tag): the fallback is an RFC 3339 timestamp with an offset
      between the run's start and end.
  - Red proof: the pre-fix script (HEAD, in a scratch worktree) fails 4 cells, including
    "not dated after the release". `tests/test_update_landing.sh` passes 29/29, and
    `shellcheck` is clean.
- **Files affected:** `website/new_release_post.sh`, `tests/test_release_post_date.sh`

## Final Implementation Notes
- **Actual work done:**
  - New stdlib-only `lib/bounded_run.py`. `run_bounded()` runs the command in a new
    session with stdin `/dev/null` and output in temp files. On expiry it kills the
    whole process group (TERM → CONT → poll the group → KILL). `stop_grace` turns the
    expiry into a stop request first. `cancelled=` lets the caller end the wait.
    Signals are deferred during cleanup. Nested runners get a strictly smaller grace
    via `AIT_BOUNDED_RUN_GRACE` (own − 2s, floor 1s).
  - `noninteractive_env()`: `GIT_TERMINAL_PROMPT=0`, `GIT_ASKPASS=""`,
    `SSH_ASKPASS_REQUIRE=never`, `GCM_INTERACTIVE=never`, and `SSH_ASKPASS` /
    `DISPLAY` / `WAYLAND_DISPLAY` removed.
  - The CLI (`--timeout N [--noninteractive] -- cmd`) is used by the shell side.
  - Shell (`lib/agentcrew_utils.sh`): `crew_git_timeout`, `_crew_git_bounded` (the
    CLI), `crew_push` through it (124 → a timeout warning naming
    `AIT_CREW_GIT_TIMEOUT`), and a new `crew_pull_rebase` (bounded fetch of the
    tracked branch, then a local `rebase --no-autostash` only after a successful
    fetch). addwork and setmode use it. addwork traps TERM as a stop request, and its
    network tail moved out of the commit subshell.
  - Python (`agentcrew_utils.py`): `crew_git_timeout()`, `git_cmd(timeout=)` (runs
    through `run_bounded` and `noninteractive_env`; a timeout gives rc 124 plus a
    message), the `_sync_with_upstream` fetch and the `git_push` push. `../lib` is
    made importable.
  - `brainstorm_crew._run_addwork`: `run_bounded(cmd, 2×bound + 60s,
    stop_grace=60)`; TimeoutExpired goes to `_addwork_outcome`, which reads the
    worktree back (merge state → RuntimeError with remedy; committed → success;
    staged → RuntimeError with complete/discard remedies; nothing → RuntimeError).
  - Docs: `website/content/docs/commands/crew.md` (init section) and
    `aidocs/agentcrew/agentcrew_architecture.md` (Runner Orchestration).
    `tests/lib/test_scaffold.sh` copies `bounded_run.py`.
- **Deviations from plan:**
  - t2018's harness in `tests/test_crew_pull_no_autostash.sh` did
    `r.time.sleep = fake_sleep`. `r.time` is the global time module, so it also
    replaced the `time.sleep` that `Popen.wait(timeout)` polls with, and cells 6/11/11b
    hit the 600-call cap. The fake is now scoped to the runner module (a
    `types.SimpleNamespace` copy of `time`), and the wrapper forwards `**kw` as
    planned.
  - Plan cell 14 expected `ait crew status set` to print a push warning. It pushes
    with `batch=True`, which never warns, so the cell asserts the silent contract
    instead (no warning, no traceback).
  - The CLI's signal handling was changed in review (Change Request 1).
  - `test_bounded_run.py` gained `test_expiry_terms_the_whole_group_before_any_sigkill`
    after mutant M2 (leader-only SIGTERM) survived.
- **Issues encountered:**
  - M2 surviving showed that no cell checked that the whole group gets SIGTERM before
    any SIGKILL; the test above covers it.
  - A second variant (M2b, leader-only everything) showed that
    `test_expiry_kills_a_term_ignoring_grandchild` was vacuous: `echo $$` nested in the
    outer `sh -c "…"` was expanded by the outer shell and recorded the leader's pid.
    It is now escaped (`\$\$`), and M2b turns it red.
- **Key decisions:**
  - One Python runner for both languages. A new session (no ctty) needs `setsid`,
    which macOS lacks as a binary, and one implementation means one tested mechanism.
  - No `-o BatchMode` injection: it would break plink-variant configured commands.
    The environment alone removes the prompt channels.
  - Committed registration counts as success (no remove-agent command exists, and
    `Waiting→Aborted` is invalid).
  - The default bound of 10s matches the framework's other network bounds.
- **Verification (all against the final tree):**
  - Probes (a)–(f) from step 1 all matched the plan:
    - `GIT_TERMINAL_PROMPT=0` alone still ran `core.askPass` twice, and `GIT_ASKPASS=""`
      suppressed it;
    - `ssh-keygen -y` under `setsid` ran the sentinel with `SSH_ASKPASS` + `DISPLAY`, and
      not under the policy env;
    - `push -u` on an up-to-date remote set the upstream;
    - a leader-only TERM ran its trap only after the subshell returned;
    - a stub `gpg.program` was called "no-rebase" for the commit and "in-rebase" for the
      re-sign;
    - hooks ran in a linked worktree.
  - Shell suites: `test_crew_publish_upstream.sh` 127/127,
    `test_crew_git_noninteractive.sh` 22/22, `test_brainstorm_addwork_deadline.sh`
    61/61, `test_crew_pull_no_autostash.sh` 208/208. Also green: `test_crew_init`,
    `_setmode`, `_status`, `_runner`, `_groups`, `_cleanup`, `_report`,
    `_runner_config_delivery`, `_template_includes`, `_addwork_output_instructions`,
    `test_agentcrew_terminal_push`, `_pythonpath`, `_error_recovery`,
    `test_brainstorm_cli`, `test_launch_mode_field`.
  - Python: `test_bounded_run.py` 20/20 and `test_brainstorm_crew.py` pass; the full
    `run_all_python_tests.sh` gave `PYTHON SUITE: PASSED (runner=pytest, exit=0)`
    (before Change Request 1, which touched only `bounded_run.py` and its tests;
    those were re-run).
  - Red proofs, each in a detached scratch worktree. Every one turned RED:
    - M1 (CLI ignores `--timeout`; re-run on the rewritten CLI);
    - M2a (leader-only SIGTERM) and M2b (leader-only kill);
    - M3 (no SIGKILL escalation);
    - M4 (`start_new_session=False`);
    - M5 (no `GIT_ASKPASS=""`);
    - M6 (no `SSH_ASKPASS_REQUIRE` and no askpass/display strip);
    - M7 (deadline kills at once);
    - M8 (network calls back in the subshell);
    - M9 (committed state raises);
    - M10 (child grace ≥ parent);
    - M11 (runner ignores `AIT_BOUNDED_RUN_GRACE`);
    - M12 (the pre-CR1 signal handling);
    - M12a (SIGINT-only shield).
  - `shellcheck` reports no new warnings on the changed scripts or the new tests.
    `check_links.py --build` reports only the pre-existing blog link below.
- **Upstream defects identified:**
  - `website/new_release_post.sh:132,136` — `%(creatordate:short)` / `date +%Y-%m-%d` take the LOCAL date, and the post's
    `date:` is read by Hugo as UTC midnight. A release cut between local midnight and UTC midnight (00:00–03:00 IDT)
    therefore produces a post Hugo treats as future-dated and leaves out of the build, so `check_links.py --build`
    (which CI runs after the release build) reports the home page's link to it as missing-page.
    Observed here: v0.38.0 (`1aa6a5b6e`, committed 22:49 UTC Oct 15, post dated 2026-10-16) failed the sweep, and the
    same check passed hours later with no change. The future-date exclusion is a hypothesis that fits both runs;
    Mechanism since confirmed with `hugo list future`; FIXED in this task (Change Request 2).
