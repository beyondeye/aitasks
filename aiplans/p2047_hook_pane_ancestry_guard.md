---
Task: t2047_hook_pane_ancestry_guard.md
Base branch: main
Output branch: main
---

# t2047 — SessionStart hook: record only from inside the pane's own process tree

## Context

`.aitask-scripts/aitask_session_hook.sh` trusts `$TMUX_PANE` from its environment.
t2040 measured live (codex 0.163.0) that a hand-started codex TUI (no
`-c tui.alternate_screen=never`) is routed through the shared app-server daemon.
That daemon runs every routed session's SessionStart hook with the `TMUX_PANE` of
the pane that started it (`%1`). A second hand-started codex therefore upserts its
session into `%1`'s record. It was saved only because that record was frozen.

The fix: the hook records nothing unless the pane's `#{pane_pid}` is an ancestor
of the hook process. Refusing is the fail-safe direction, because the freeze
engine's fallback upsert covers an unrecorded agent. The script is shared by the
Claude Code hook (`.claude/settings.json`, `seed/claude_settings.hooks.json`) and
the Codex hook (`seed/codex_config.seed.toml`), so one guard covers both. No other
agent (OpenCode, agy) installs a session hook (`grep session_hook` over
`.opencode`, `.agents`: no hits).

**Ancestry alone is not enough, and no single observation can make it enough.**
If the daemon is detached (reparented to init or a subreaper), a daemon-run hook
fails the walk. But nothing pins that. On a launch or codex version where the
daemon stays a descendant of the starting pane's codex, the walk *passes* for
every daemon-routed session attributed to `%1`, which is the exact bug. So the hook
**always** applies a second check: no process between the hook and the pane pid
may be the codex app-server daemon (Step 2b). This check is unconditional. Step 0
only validates its identifier forms; it never decides whether 2b exists.

**Identifier evidence available now, from disk (read-only, this machine, codex
0.163.0):**
- `~/.codex/app-server-daemon/daemon.pid` is JSON written by the daemon itself:
  `{"pid":49240,"processStartTime":…,"processIdentity":{"bootId":…,"startTicks":117924},…}`.
  It sits next to `daemon-updater.pid` (`{"pid":49407,…}`), `daemon.lock` and
  `daemon-updater.sock`.
- The daemon package is
  `~/.codex/packages/app-server-daemon/releases/<ver>-<target>/bin/codex`.
  `current` is a symlink to the release, and `codex-package.json` names
  `"entrypoint": "bin/codex"`.
- Neither recorded pid is running now (`ps -p 49240,49407`: no rows). So the
  daemon's live argv is **not observable today**, and the argv form below is a
  hypothesis until Step 0 or the post-phase sees a real daemon.

## Steps

### 0. Validate the daemon-hop identifier forms (live, isolated; read-only for the repo)

Isolated tmux (`env -u TMUX -u TMUX_PANE`, private `TMUX_TMPDIR`, `-L` socket),
throwaway `CODEX_HOME` under the scratchpad (copy only `auth.json`, never write
to `~/.codex`). Start a bare `codex` in pane A, then a second bare `codex` in pane
B. Then start one codex WITH `-c tui.alternate_screen=never` in pane C.

Capture **complete, unfiltered** evidence into scratch files, quoted verbatim in
the Final Implementation Notes:
- a full `ps -eo pid,ppid,sid,lstart,args` snapshot, with no grep;
- for every pane pid, every codex process, and the daemon pid named by
  `$CODEX_HOME/app-server-daemon/daemon.pid`: the full parent chain to pid 1,
  one `ps -o pid,ppid,sid,args -p <pid>` row plus `readlink /proc/<pid>/exe` per
  hop. Use the new `pid_chain_to` helper from Step 1, so the chain the guard
  walks is the one recorded.

Then classify each identifier form from Step 2b against that evidence. Each form
must **match the daemon process** and **match no hop of pane C's in-process
chain**. Outcomes (exhaustive):
- **daemon observed**: keep each form that matches the daemon and does not match
  pane C. Drop a form that matches pane C (a false refusal of the supported
  shape). Drop a form that misses the daemon, and record that. Record whether the
  daemon was a descendant of pane A, as a fact, not as a switch. If **no form
  survives**, stop and ask the user before implementing.
- **daemon not observed, pane C observed** (no daemon came up in the throwaway
  home): forms (a) and (c) are checked for no-false-positive against pane C only.
  Form (b) cannot false-positive: it requires the pid, boot id and start ticks
  to all match. Its `startTicks` reading, though, is unconfirmed without a live
  daemon. Keep all three, and mark "validated against a real daemon: no; (b)
  startTicks reading unconfirmed" in the notes.
- **codex not runnable at all** (no auth or network): keep forms (b) and (c) only.
  Form (b) cannot match a non-daemon (triple identity). Form (c) needs the exact
  argv word `app-server`, which a TUI launch does not carry. Drop form (a),
  because its no-false-positive check against an in-process codex is the one that
  cannot be done. Record this as **inconclusive**.
- In the **daemon observed** branch, also confirm form (b)'s reading: the live
  daemon's `processIdentity.startTicks` == its `/proc/<pid>/stat` field 22, and
  `bootId` == `/proc/sys/kernel/random/boot_id`. If either differs, fix the
  reading to whatever the measured value corresponds to, or drop (b).

### 1. `lib/pid_anchor.sh`: parent-pid and ancestry helpers

Follow the existing `_pid_starttime_proc` / `_pid_starttime_ps` /
`get_pid_starttime` idiom in the same file:

```bash
# Linux: /proc/<pid>/stat field 4. Split after the LAST ')' — comm may hold spaces/parens.
_pid_ppid_proc() {
    local pid="$1" raw fields
    [[ -r "/proc/$pid/stat" ]] || return 1
    raw=$(cat "/proc/$pid/stat" 2>/dev/null) || return 1
    read -ra fields <<<"${raw##*) }"
    [[ "${fields[1]:-}" =~ ^[0-9]+$ ]] || return 1
    printf '%s\n' "${fields[1]}"
}
# BSD / macOS (no /proc).
_pid_ppid_ps() {
    local raw
    raw=$(ps -o ppid= -p "$1" 2>/dev/null | tr -d '[:space:]') || return 1
    [[ "$raw" =~ ^[0-9]+$ ]] || return 1
    printf '%s\n' "$raw"
}
get_pid_ppid() { _pid_ppid_proc "$1" || _pid_ppid_ps "$1"; }

AIT_PID_ANCESTOR_WALK_MAX=20
# pid_chain_to <ancestor> <start>
#   Prints every pid walked, one per line: <start>, its parent, ..., stopping
#   BEFORE <ancestor> (the ancestor itself is not printed). It prints on every
#   return code, so a refusal can report the chain it saw.
#   0 = <ancestor> is <start> or one of its ancestors
#   1 = proven not (the walk reached pid 1 / the bound without meeting it)
#   2 = could not tell (a parent was unreadable mid-walk, or bad arguments)
pid_chain_to() { ... }
# get_pid_exe <pid> — readlink /proc/<pid>/exe; else `ps -o comm= -p` (a full
#   path on macOS). Return 1 when neither is readable.
# get_pid_args <pid> — /proc/<pid>/cmdline, NUL-separated and kept that way (so
#   argv words stay exact); else `ps -o args= -p` (space-joined). Return 1 when
#   neither is readable.
```

Rules:
- Reject `<ancestor>` ≤ 1 or non-numeric with return 2. PID 1 is an ancestor of
  everything, so accepting it would make the guard vacuous.
- The loop compares *before* stepping. It stops at pid ≤ 1 (return 1), or after
  `AIT_PID_ANCESTOR_WALK_MAX` hops (return 1; the same reasoning as
  `AIT_TMUX_PANE_WALK_MAX` in `lib/tmux_exec.sh`), or when `get_pid_ppid` fails
  (return 2).
- All helpers are generic: they hold no codex knowledge. The daemon predicate
  lives in the hook (Step 2b).
- Update the file's header "Sourced by" list to add `aitask_session_hook.sh`.
- `ait_tmux_pane_for_pid`'s walk is left alone. It has its own `ps`-only reader
  and other callers, so changing it is out of scope.

### 2. `aitask_session_hook.sh`: the guard

- In §5, also `source "$root/.aitask-scripts/lib/pid_anchor.sh" 2>/dev/null || exit 0`.
- Right after `[ -n "$pane_id" ] && [ -n "$pane_pid" ] || exit 0` (before §6, so
  the upsert, the `@aitask_record` stamp **and** the §9 `@aitask_agent_session`
  write are all behind it):

```bash
# --- 5b. ancestry guard (t2047) --------------------------------------------
_chain="$(pid_chain_to "$pane_pid" "$PPID")"; _anc=$?
_chain_txt="$(printf '%s' "$_chain" | tr '\n' ' ')"
if [ "$_anc" -ne 0 ]; then
    case "$_anc" in
        1) echo "aitask_session_hook: pane $pane_id (pid $pane_pid) is not an ancestor of this hook (chain: $_chain_txt); nothing recorded" >&2 ;;
        *) echo "aitask_session_hook: could not establish this hook's process ancestry (chain: $_chain_txt); nothing recorded" >&2 ;;
    esac
    exit 0
fi
# Then 2b over every pid in $_chain, before anything is recorded.
```

  The walk starts from `$PPID`, as the task specifies. Both framework shapes pass:
  pane pid = agent (`env … codex`/`claude` exec through), with the hook a child
  or grandchild via the agent's shell; or pane pid = a shell that spawned the
  agent.
- Add **HARD CONTRACT 5** to the header block: "Record ONLY when the pane's
  `#{pane_pid}` is an ancestor of this hook". Give the daemon-routing reason (t2040
  measurement) and why refusing is fail-safe. Note that it also refuses an agent
  in a different PID namespace from the tmux server (e.g. a container started from
  the pane), and that this is accepted.
- Amend the CODEX TIMING paragraph's "It runs from the pane's own codex process,
  with the right TMUX_PANE": a daemon-routed TUI does not, and is refused here.

### 2b. Daemon-hop refusal (ALWAYS on, whatever Step 0 observed)

A hook-local function `_codex_daemon_hop <pid>` runs over every pid in `$_chain`
(from `$PPID` up to, excluding, the pane pid). It returns 0 when the pid is a
daemon hop, 1 when it is not, and 2 when its identity is unreadable. A hop is a
daemon hop when **any** surviving form (per Step 0) matches:

- **(b) declared identity, not a bare pid.** The file is
  `${CODEX_HOME:-$HOME/.codex}/app-server-daemon/daemon.pid` (or
  `…/daemon-updater.pid`). The hook inherits the daemon's environment, so this
  `CODEX_HOME` is the daemon's own. A pid alone is never proof: these files
  outlive their process, and the one on this machine is from a **previous
  boot** (recorded `bootId` `2d058e96…` ≠ current `0be18695…`). So a later process
  reusing that pid could be a legitimate hop. Form (b) matches only when **all
  three** agree:
  1. `"pid"` equals the hop pid;
  2. `processIdentity.bootId` equals `/proc/sys/kernel/random/boot_id`;
  3. `processIdentity.startTicks` equals the hop's `/proc/<pid>/stat` field 22.
     Use the existing `_pid_starttime_proc` in `lib/pid_anchor.sh`. On-disk
     evidence fits this reading: 117924 ticks at `CLK_TCK=100` is ~19.6 min
     after that boot, against a recorded `processStartTime` of Fri Oct 16
     10:57:55. Step 0 confirms it on a live daemon.

  Extract the three fields with `sed` (no python, keeping the hook cheap). A
  missing file, an unparsable or absent `processIdentity`, or no `/proc` (macOS)
  means the form **does not match**, so it never refuses on uncorroborated
  evidence. If Step 0 shows `startTicks` means something else, condition 3 never
  holds and (b) degrades to "never matches", not to a false refusal. In that case
  fix the reading or drop the form, and record which.
- **(a) executable path.** `get_pid_exe` contains `/packages/app-server-daemon/`.
- **(c) argv word.** Some argv element is exactly `app-server` (an element, not
  a substring, so a prompt that mentions it does not count), and argv0's basename
  is `codex`.

**Unidentifiable hop fails safe.** If both `get_pid_exe` and `get_pid_args` fail
for a hop, `_codex_daemon_hop` returns 2. The hook then refuses: "could not
identify process <pid> between this hook and its pane; nothing recorded". A dead
hop (the walk raced its exit) lands here too. The ancestry walk already proved
every hop's ppid readable, so for one's own processes this is a race, not a
steady state.

Any rc 0 → "aitask_session_hook: hook runs under the codex app-server daemon
(pid <p>, form <a|b|c>); nothing recorded", then exit 0. Naming the form in the
message makes a false refusal diagnosable from stderr alone. Forms that Step 0
dropped are not implemented. The header comment cites the codex version and the
evidence each kept form rests on.

### 3. `tests/test_session_hook.sh`

- Copy `lib/pid_anchor.sh` into the scratch `lib/` alongside the three already
  copied.
- `DISPLAY_LINE`, and the `deadbeef` variant, use pane pid `$$` (the test shell is
  an ancestor of `run_hook`'s `bash "$HOOK"`) instead of `4242`. Update the
  `--pane-pid` assertion to `$$`.
- New section "--- t2047: ancestry guard ---":
  - **direct-parent shape** (pane pid IS the agent): `bash -c` that exports
    `TMUX_STUB_DISPLAY` with its own `$$` and then runs the hook as its direct
    child → one upsert, stamped. This covers the hop-0 boundary (`pane_pid ==
    $PPID`).
  - **multi-hop shape** (pane pid is a shell that spawned the agent): the
    baseline already covers it with `$$`. Add an explicit 2-level `bash -c 'bash
    -c …'` nesting assertion.
  - **negative, live non-ancestor**: pane pid = the pid of a background `sleep
    30 &` started by the test (a sibling). Assert: exit 0, stdout empty, **0
    upsert calls**, no `@aitask_record` set-option, **no
    `@aitask_agent_session` set-option**, stderr contains "not an ancestor".
    Kill the sleep afterwards.
  - **negative, pid 1** → nothing recorded (this guards against vacuous
    ancestry).
  - **negative, a dead pid** (the reaped `sleep`'s pid) → nothing recorded.
  - **negative control** for the positive tests: the same payload and env as the
    baseline, differing only in pane pid, flips from 1 upsert to 0. This makes
    the guard's effect attributable to the pane pid.
- **Pitfall for every intermediate-process shape:** `bash -c '…; bash "$HOOK"'`
  may exec its last simple command, which removes the intermediate from the
  chain. End every such script with `bash "$HOOK" <"$pl"; exit $?`. Each refusal
  case is paired with a control that differs only in the marker. If the
  intermediate were exec'd away, the marked case would be recorded too and fail
  visibly, so no hook-side test probe is needed.
- New direct unit cases for the helpers (source `lib/pid_anchor.sh` in the test):
  `_pid_ppid_proc $$` == `_pid_ppid_ps $$` == the real `$PPID` (this exercises
  the macOS reader on Linux). `pid_chain_to $$ <child>` → 0 and prints the
  child's chain. `pid_chain_to <sibling> <child>` → 1. `pid_chain_to 1 $$` → 2.
  `pid_chain_to abc $$` → 2. `get_pid_args` keeps a word containing a space as
  one element.
- **Daemon-hop refusal, one case per kept form, each with a negative control.**
  The pane pid is always `$$`, so ancestry passes and only 2b can refuse:
  - (b) the intermediate `bash -c` writes its own identity into
    `$TMP/codexhome/app-server-daemon/daemon.pid`: `{"pid":$$,
    "processIdentity":{"bootId":"<current boot_id>","startTicks":<its stat
    field 22>}}`, in the real file's key order. With `CODEX_HOME` pointed there,
    it then runs the hook → 0 upserts, no stamps, stderr names `form b`.
    Controls, each → 1 upsert:
    - an unrelated pid;
    - the right pid with a **stale bootId** (the pid-reuse case, modelled on this
      machine's real stale file);
    - the right pid with a wrong `startTicks`;
    - the right pid with no `processIdentity`;
    - a malformed file.

    Also cover the `daemon-updater.pid` variant. Linux-only case: skip with an
    explicit SKIP line when `/proc/self/stat` is absent.
  - (a) `cp "$(command -v bash)"` to
    `$TMP/codexhome/packages/app-server-daemon/releases/t/bin/codex` (a copy, not
    a symlink, because `/proc/<pid>/exe` resolves symlinks), and run the hook
    under it → refused, `form a`. Control: the same copy at
    `$TMP/elsewhere/bin/codex` → recorded.
  - (c) `exec -a codex bash -c 'bash "$1" <"$2"; exit $?' app-server "$HOOK" "$pl"`
    → refused, `form c`. Controls: argv0 `codex` with the word `xapp-server`
    and with `"fix app-server"` as one element → recorded; argv0 `bash` with
    `app-server` → recorded.
  - These synthetic processes are representative of the evidence each form rests
    on: the daemon's declared pid file, its package path, and the `app-server`
    subcommand word. They are not a substitute for Step 0's real daemon, and the
    notes say which forms were validated against which.
  - Unidentifiable hop: unit-test that `get_pid_exe` and `get_pid_args` both
    return 1 for a reaped pid. Driving the hook into its rc-2 branch
    deterministically would need a racing exit. That branch is reviewed, not
    tested, and the Final Implementation Notes say so.

### 4. `tests/test_session_hook_live.sh`

The live test currently fires the hook from the test shell. The pane runs `sleep
300`, so it is not an ancestor, and the test would now fail. Rewrite the pane
command as a small **fire loop**, `$TMP/pane_agent.sh`, written by the test. It
reads payload-file paths from a FIFO and runs the real hook as its own child with
`< payload > out.N 2> err.N; echo $? > rc.N`, so the pane pid is the agent (the
real framework shape). The real `TMUX` and `TMUX_PANE` come from tmux itself. Pass
`AITASKS_TMUX_SOCKET` / `AITASKS_AGENT_SESSIONS_FILE` / `AITASK_AGENT_STRING`
explicitly on the pane command line. `fire_hook` writes the payload, sends its
path and waits (bounded, ~10 s) for `rc.N`.
- Add the live negative FIRST, before any record exists: fire the hook from the
  test shell with the pane's `TMUX_PANE` (the daemon-shaped case). Assert the
  store lists no `SESSION:` row and both pane options are empty.
- The existing first-fire / second-fire / blank-session assertions then run
  through the fire loop unchanged.

### 5. Docs (current-state only)

- `website/content/docs/concepts/framework-session.md`, "The session hook": one
  short paragraph. The hook records only when it runs inside the agent's own
  pane process tree. A Codex agent started by hand, without the framework's
  launch overrides, can run through Codex's shared app-server daemon, and its
  hook then reports from the daemon's process, so it is ignored. Such an agent is
  restored by re-picking its task.
- `aidocs/framework/tmux_gateway.md:196` table row: "the SessionStart hook, on
  `$TMUX_PANE`" → add "(only when the hook descends from that pane's process)".
- Run `cd website && python3 check_links.py --build` (no new links expected).

### 6. Note to t2046 (in flight, `Implementing`)

`./ait note 2046 --from 2047 --with-live --file -`. The content: after t2047, a
daemon-routed codex's hook records nothing. It is refused for every pane, the
starting pane included: by the ancestry walk when the daemon is detached, and by
the always-on daemon-hop refusal when it is attached. So t2046's
"hook-vouched stored id outranks a MISS_NO_MATCH" candidate never gets evidence for
a daemon-routed codex, and a daemon-routed record carries no hook session id to
clear. Include the Step 0 outcome, and hedge that this is uncommitted until t2047
lands (cite the commit SHA once committed).

### Post-phase (risk mitigations)

1. [hook_guard_real_agent_check] With the guard in place, use an isolated tmux
   server (private `TMUX_TMPDIR`, `-L` socket, `env -u TMUX -u TMUX_PANE`) and a
   scratch aitasks project carrying the seed hook blocks. A scratch
   `AITASKS_AGENT_SESSIONS_FILE` and a throwaway `CODEX_HOME` (`auth.json`
   copied; trust entry for the scratch path) keep the user's state untouched.
   In the scratch settings, wrap the hook command so it first dumps
   `pid_chain_to` plus a `ps -o pid,ppid,args -p` row per hop into a per-fire
   scratch file, then runs the real hook with its stderr appended to that file.
   This records each real chain and the hook's verdict.

   **Positive agents — must record:**
   - (a) `claude -p "say ok"` as pane P1's own command;
   - (b) a codex in pane P2, launched with `CODEX_TUI_OVERRIDES`
     (`-c tui.alternate_screen=never`), given one turn via send-keys.

   For each of (a) and (b), assert that `aitask_agent_sessions.sh list` shows a
   `SESSION:` row whose pane is P1 / P2, and that `@aitask_record` and
   `@aitask_agent_session` are both set on that pane.

   **Daemon-routed agent — must refuse:**
   - (c) a bare `codex` in pane P3 (and, if the daemon's starting pane differs,
     that pane too), given one turn.

   Assert that **no** `SESSION:` row was added or changed by its fire: compare
   the store listing before and after, including P1/P2's rows, so a wrong-pane
   upsert is caught too. Assert that `@aitask_record` / `@aitask_agent_session`
   are **unset** on P3. Assert that its wrapper log carries a refusal line naming
   the non-ancestor branch or a daemon-hop form. If no daemon-routed launch can be
   produced, mark (c) **inconclusive**.

   A failure of (a) or (b) blocks the commit: refusals for real agents are the
   regression this check exists to catch. A failure of (c) also blocks: it is
   the bug itself. Record every outcome and chain in the Final Implementation
   Notes. If an agent cannot run (no auth or network), mark that case
   **inconclusive**, never passed.

## Verification

- `bash tests/test_session_hook.sh` — all pass, including the new negatives.
- `env -u TMUX -u TMUX_PANE TMUX_TMPDIR=<private> bash tests/test_session_hook_live.sh`.
- `bash tests/test_agent_sessions_stamp.sh`, `bash tests/test_tmux_pane_for_pid.sh`,
  `bash tests/test_crash_recovery_pid_anchor.sh` (other `pid_anchor.sh`
  consumers), plus any `tests/test_*pid_anchor*` / `test_aitask_lock*` that source
  it.
- `shellcheck .aitask-scripts/aitask_session_hook.sh .aitask-scripts/lib/pid_anchor.sh`.
- Real-chain check, recorded in the Final Implementation Notes:
  `pid_chain_to <this pane's pane_pid> $$` (rc 0, chain printed) from this Claude Code session's
  Bash tool, read-only on the real `-L ait` server. This is a proxy for the
  Claude hook chain. The Step 0 in-process codex chain covers codex.

## Step 9

Post-implementation: commit code (`enhancement: … (t2047)`) and plan separately,
then archive via the standard Step 9 flow (current branch, no merge).

## Risk

### Code-health risk: low
- A false refusal is silent. If a real agent runs its hook outside the pane's
  process tree (a hook runner that daemonizes, a PID namespace, `ps` unavailable
  under a sandbox), every SessionStart records nothing. Freeze then falls back
  to its own upsert, and restores degrade to re-pick with no visible error, since
  hook stderr is not shown · severity: low (residual: real Claude Code and codex
  chains checked by inline post-phase hook_guard_real_agent_check; future agent
  versions remain unpinned) · → mitigation: inline post-phase
  hook_guard_real_agent_check
- `lib/pid_anchor.sh` is shared with the lock/pick scripts. The additions are
  new functions only and change no existing behaviour · severity: low · →
  mitigation: none

### Goal-achievement risk: medium
- An attached daemon (on any launch or version) makes ancestry alone pass the
  bug. The always-on daemon-hop refusal (Step 2b) covers this, whatever Step 0
  observes. The residual risk is identifier drift: a future codex that renames
  the pid file, the package path *and* the subcommand would slip past all three
  forms. Step 0 records complete chains, and every refusal names its form on
  stderr · severity: medium · → mitigation: none (in-plan Step 0 / 2b)
- The daemon's live argv is unobserved today (the recorded daemon pids are not
  running). If Step 0 also sees no daemon, form (c) rests on synthetic evidence
  only. Forms (a) and (b) rest on on-disk evidence from this machine · severity:
  low · → mitigation: none
- The interaction with in-flight t2046 (its "hook-vouched id" candidate loses its
  evidence for a daemon-routed codex). Handled by the Step 6 note · severity:
  low · → mitigation: none

### Planned mitigations
- timing: post-phase | name: hook_guard_real_agent_check | type: test | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — a silent false refusal for real Claude Code / codex hook chains | desc: run real claude -p and a wrapper-launched codex in an isolated tmux pane through the guarded hook; assert record + pane stamps and record the real ppid chain

## Final Implementation Notes

- **Actual work done:** Steps 0–5 and the post-phase as planned.
  - `lib/pid_anchor.sh` gained the generic parent-chain helpers: `_pid_ppid_proc`
    / `_pid_ppid_ps` / `get_pid_ppid`, `pid_chain_to`, `get_pid_exe` and
    `pid_argv_match` (which replaced `get_pid_args` in review round 1).
  - `aitask_session_hook.sh` gained HARD CONTRACT 5, a DAEMON ROUTING header
    note, and the §5b guard: the ancestry walk plus the always-on daemon-hop
    refusal with forms a/b/c. The guard runs before the upsert, the
    `@aitask_record` stamp and the `@aitask_agent_session` write.
  - Tests: `tests/test_session_hook.sh` grew from 69 to 156 assertions.
    `tests/test_session_hook_live.sh` now fires the hook from inside the pane
    through a FIFO fire loop, plus an outside-fire negative.
  - Docs: `website/content/docs/concepts/framework-session.md`, plus two rows
    in `aidocs/framework/tmux_gateway.md`.
- **Step 0 evidence (codex 0.163.0, Linux, isolated tmux, throwaway CODEX_HOME,
  2026-10-19).** The daemon was observed, and all three forms were kept.
  - The daemon is **attached**: `2292178 ppid=2291806 (pane A's pane pid)
    sid=2292178`. It calls setsid but is not reparented while its starter
    lives. After the starter's tmux server was killed it was reparented to
    `systemd --user` (1481). So attachment depends on timing, as review
    predicted.
  - Hook chains recorded by a dump hook:
    - fire 1, pane A's own session: `TMUX_PANE=%0`, `PPID=2292178
      (…/packages/app-server-daemon/releases/0.163.0-x86_64-unknown-linux-musl/bin/codex)`
      → `2291806 (mise codex, pane A)` → tmux → systemd → init;
    - fire 2, **pane B's** session: `TMUX_PANE=%0`, the identical chain. This
      is the bug, and it passes ancestry alone;
    - fire 3, pane C (with `CODEX_TUI_OVERRIDES`): `TMUX_PANE=%2`, `PPID=2293515`,
      which is the pane pid itself (hop 0).
  - Daemon argv: `…/bin/codex app-server --listen unix:// --analytics-default-enabled --managed-daemon`.
  - `daemon.pid` `processIdentity` matches the live process. `bootId` ==
    `/proc/sys/kernel/random/boot_id`. `startTicks` == `/proc/<pid>/stat`
    field 22 on two daemons (9660830 == 9660830; 9666770 == 9666770).
  - The full unfiltered `ps -eo pid,ppid,sid,lstart,args` snapshots were kept
    in the session scratchpad.
- **Post-phase hook_guard_real_agent_check (real agents through the guarded
  hook, isolated server `-L s1`, scratch store):**
  - (a) `claude -p` (Claude Code 2.1.302) in pane %0, pane pid = the spawning
    bash. Hook chain: `PPID=claude` → bash (the pane pid). Record
    `ce961308|live|…|%0` was created, and both pane options were set.
    **PASS**.
  - (b) codex with `CODEX_TUI_OVERRIDES` in pane %1. The hook's PPID is the
    pane pid (hop 0). Record `e6f21524|live|…|%1` was created, and both pane
    options were set. **PASS**.
  - (c) two bare codex panes, %2 (the daemon's starter; daemon 2658056 is a
    child of %2's pane pid) and %3. Both turns fired the hook from the daemon
    with `TMUX_PANE=%2`. Both were refused: `hook runs under the codex
    app-server daemon (pid 2658056, form a); nothing recorded`. The store
    listing was unchanged (diff empty), and %2 / %3 carry no
    `@aitask_record` or `@aitask_agent_session`. **PASS**.
  - Each form also matched the real daemon individually through the hook's own
    function: form a, then c with a masked, then b with a and c masked. The
    real non-daemon codex TUIs (bare and overrides) read rc 1.
- **Verification:** `tests/test_session_hook.sh` 167/167; `test_session_hook_live.sh` 22/22 (isolated);
  `test_agent_sessions_stamp`, `test_tmux_pane_for_pid`, `test_crash_recovery_pid_anchor`
  and every other `pid_anchor.sh`-sourcing suite (`test_lock_*`, `test_task_lock`,
  `test_pick_own_scoped_commit`, `test_archive_*`, `test_live_endpoint_*`, `test_task_push`, …) pass;
  shellcheck clean on the hook and lib; `check_links.py --build` SWEEP: PASSED.
  - Red proofs:
    - M1 (ancestry forced to pass) fails exactly the 10 non-ancestor
      assertions.
    - M2 (daemon check disabled) fails exactly the 16 daemon-form assertions.
    - The live test against HEAD's hook fails the 4 outside-fire assertions.
  - Real-chain proxy from this session: `pid_chain_to 956020 $$` → rc 0, 2
    hops.
- **Deviations from plan:** none in behaviour.
  - Step 2b was implemented unconditionally, with all three forms, as revised
    in review.
  - The shape-1/2 test intermediates became small scripts rather than inline
    `bash -c` strings, for readability.
- **Issues encountered:** `fire_hook` is called inside `$( )`, so a shell
  counter for request ids would not survive the subshell. It uses unique
  `mktemp -u` names instead.
  - The hook's rc-2 branch ("could not identify process") is reviewed, not
    tested: driving it would need a racing exit. The helpers' rc-1-on-reaped-pid
    is unit-tested.
- **Key decisions:**
  - The form check order is a, c, b (cheapest first). Form b needs pid,
    bootId and startTicks to all match, so a stale pid file (this machine's
    real one is from a previous boot) can never refuse.
  - A hand-started bare codex now records nothing, not even in the daemon's
    starting pane, because hooks run by the daemon cannot be attributed to a
    pane. It restores by re-pick, as documented.
- **Upstream defects identified:** None

## Post-Review Changes

### Change Request 1 (2026-10-19 13:40)
- **Requested by user:** three blocking findings from review, all verified
  valid.
  1. `get_pid_args` turned argv NULs into newlines, so a multiline prompt
     argument containing an `app-server` line falsely matched form c. Its `ps`
     fallback split on spaces in the same way.
  2. The `/proc` ppid unit assertion was not gated, so it would fail on macOS.
  3. The live test's `fire_hook` opened the FIFO write-only before its bounded
     wait, so a dead pane agent blocked it forever.
- **Changes made:**
  1. Replaced `get_pid_args` with `pid_argv_match <pid> <argv0-basename>
     <element>`. It reads `/proc/<pid>/cmdline` NUL-delimited, element by
     element (`read -d ''`), and answers 0/1, or 2 when element boundaries are
     unavailable. There is no `ps` fallback: form c is declined, never guessed.
     The hook's unidentifiable-hop rule is now "exe unreadable AND argv rc 2".
     New units cover an exact element (0), a multiline element (1), a spaced
     element (1), the wrong argv0 (1) and a reaped pid (2). There is a new
     hook-level control: a multiline `WORD` containing an `app-server` line is
     recorded. Red proof: a newline-split mutant fails exactly those 2
     assertions. Re-probed against a live daemon: `pid_argv_match` gives the
     daemon rc 0 and the bare TUI codex rc 1.
  2. The `/proc` reader assertion is gated on `/proc/self/stat`, with an
     explicit SKIP. The `ps` reader assertion runs everywhere.
  3. The live test holds `exec 4<>"$FIFO"`. Sends and cleanup's `quit` go
     through fd 4, so they never block on open. Proof: a mutant whose pane
     agent exits immediately fails in 10 s (rc 1, "did not answer within
     10s"), with no hang.
- **Files affected:** `.aitask-scripts/lib/pid_anchor.sh`,
  `.aitask-scripts/aitask_session_hook.sh`, `tests/test_session_hook.sh`,
  `tests/test_session_hook_live.sh`.

### Change Request 2 (2026-10-19 15:47)
- **Requested by user:** two findings, both verified valid. (1) The form-c
  refusal test ran unconditionally and would fail on macOS, where
  `pid_argv_match` declines (rc 2) by design. (2) The plan's Step 6 note to
  in-flight t2046 had not been sent.
- **Changes made:**
  1. The form-c refusal case is gated on `/proc/self/cmdline`, with an explicit
     SKIP. Its controls run everywhere, since they are recorded either way.
  2. The note was sent: `./ait note 2046 --from 2047 --with-live` →
     `NOTE_APPENDED:2026-10-19T12:46:57Z.d5fc69228fc1f733ddc617ac`, plus
     `LIVE_NONE:agent_unknown` (durable success, no live lane). It is hedged as
     uncommitted until the `(t2047)` commit lands.
- **Files affected:** `tests/test_session_hook.sh`.

### Change Request 3 (2026-10-19 16:05)
- **Requested by user:** form c accepted `app-server` as ANY later argv
  element, so an ordinary `codex exec app-server` (the word as a prompt) under a
  pane shell was falsely refused. Verified valid.
- **Changes made:** `pid_argv_match <pid> <argv0> <argv1> [<later>]` now checks
  argv[1] by POSITION, and optionally requires a later exact element. The hook
  now calls `pid_argv_match "$pid" codex app-server --managed-daemon`, the
  measured daemon invocation.
  - The units and hook-level tests build argv with a controllable argv[1] by
    running `bash <script>` under `exec -a`, with the script's file name as the
    subcommand word.
  - New controls, each recorded:
    - `codex exec app-server`;
    - `codex exec app-server --managed-daemon`;
    - `codex app-server --listen unix://` (no `--managed-daemon`);
    - a multiline prompt with both words as lines;
    - the daemon argv under argv0 `bash`.
  - The units also cover a multiline argv[1].
  - Red proof: an any-position mutant fails exactly the 3 new
    ordinary-invocation controls (6 assertions). A live daemon still reads
    rc 0, and the bare TUI codex rc 1.
- **Files affected:** `.aitask-scripts/lib/pid_anchor.sh`,
  `.aitask-scripts/aitask_session_hook.sh`, `tests/test_session_hook.sh`.
