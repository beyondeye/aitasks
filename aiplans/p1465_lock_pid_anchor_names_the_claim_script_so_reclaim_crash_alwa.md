---
Task: t1465_lock_pid_anchor_names_the_claim_script_so_reclaim_crash_alwa.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1465 — Anchor the task lock to the agent session, not the claim script

## Context

`aitask_lock.sh:83-85` anchors every task lock to `$PPID`:

```bash
get_lock_pid() { echo "$PPID"; }
```

The comment claims `$PPID` is "the agent's bash/claude process". On the path
that actually matters it is not: `aitask_pick_own.sh:227` invokes the lock
script via command substitution, so `$PPID` resolves to **`aitask_pick_own.sh`
itself** — a script that exits seconds after the claim. The anchor names a dead
process from almost the moment it is written.

Consequence: `RECLAIM_CRASH` fires on essentially every same-host re-pick, and
`crash-recovery.md` tells the user "Previous agent on this machine appears to
have crashed (PID N no longer running)" about a session that is still running.
Observed live: a `/aitask-pick 1427` session reclaimed t1427_5 from a healthy
sibling session and duplicated ~15 minutes of verification work.

**Intended outcome:** the lock names a process whose lifetime tracks the agent
session; `RECLAIM_CRASH` becomes a signal that means something; and
"we cannot tell" becomes its own state instead of collapsing to "crashed".

### What the anchor will be (decision)

**The tmux pane's process**, resolved from `$TMUX_PANE`.
`lib/agent_launch_utils.py::launch_in_tmux` hands tmux the *bare* agent command
string (`claude --model … "/aitask-pick 42"`), so tmux's `sh -c` execs straight
into the agent binary — verified live on this box: `#{pane_pid}` for this
session is `750488`, the `claude` process itself, whose parent is the tmux
server. The pane pid therefore **is** the agent CLI process and dies exactly
when the agent/pane dies.

Resolution ladder (first hit wins), implemented in `lib/pid_anchor.sh`:

| # | Rung | Notes |
|---|------|-------|
| 1 | `$AIT_AGENT_PID` | Documented override for out-of-tmux launchers and tests. Must be a positive integer naming a **live** process; otherwise it is ignored with a stderr warning (never fail open into a bad anchor). |
| 2 | tmux pane pid | `$TMUX_PANE` + `ait_tmux display-message -p '#{socket_path}\t#{pane_pid}'`, with the same-server guard `shadow_self_target()` already uses. |
| 3 | **UNKNOWN** (`pid: -`) | No silent fallback to a short-lived PID. |

Out-of-tmux claims record UNKNOWN and lose crash detection — which is strictly
better than today, where they get a *false* crash every time. `AIT_AGENT_PID`
is the escape hatch. (Explicitly **not** doing: an agent-CLI-name process-tree
walk — the framework classifies agents only by tmux window-name prefix and has
no process-name list to reuse; and wiring `AIT_AGENT_PID` through the launcher
— `launch_in_tmux` executes a plain command string, so even the existing
`export AITASK_AGENT_STRING` is bypassed on that path.)

### Scope boundary with t1466

`lock_holder_liveness()` will return **three** states. This task maps them to
the existing two same-host signals:

| liveness | signal |
|---|---|
| `dead` | `RECLAIM_CRASH` (honest crash) |
| `unknown` | `RECLAIM_STATUS` ("no PID anchor matches your environment") |
| `alive` | `RECLAIM_STATUS` — **t1466's territory** |

t1466 ("acquire-path liveness gate") explicitly owns giving a *live* holder its
own signal and a prompt whose default is not to take the lock, and names this
task's anchor as "the natural discriminator". So t1465 ships the tri-state
helper t1466 will consume, and does **not** invent a new signal, a new prompt
case, or touch any `.claude/skills/` file (which would force a rerender across
every profile and a port to `.agents/` + `.opencode/`). A forward-pointer
comment goes at the mapping site.

---

## Implementation

### Pre-phase (risk mitigations)

1. `[fixture_tmux_dep_audit]` Enumerate every test that copies the anchor lib
   standalone and prove each one also receives the gateway lib **before**
   `lib/pid_anchor.sh` starts sourcing it:

   ```bash
   grep -rln 'lib/pid_anchor\.sh' tests/            # every fixture that cp's it
   grep -rLn 'setup_fake_aitask_repo\|lib/tmux_exec\.sh' $(grep -rln 'lib/pid_anchor\.sh' tests/)
   ```

   The second command lists fixtures that get `pid_anchor.sh` but neither the
   scaffold nor an explicit `tmux_exec.sh` copy. For each hit, add
   `cp "$PROJECT_DIR/.aitask-scripts/lib/tmux_exec.sh" .aitask-scripts/lib/`
   next to the existing `pid_anchor.sh` copy. Expected result today: **zero
   hits** (`setup_fake_aitask_repo` already copies `tmux_exec.sh` and
   `terminal_compat.sh`) — record the verified hit count in the implementation
   notes rather than assuming it, since a silent zero-match and a real zero are
   indistinguishable without checking `grep`'s own exit status.

### 1. `lib/tmux_exec.sh` — new `ait_tmux_self_pane_pid()`

There is no `#{pane_pid}` query in shell anywhere today (only the Python
`_query_first_pane_pid`). Add the shell-side helper to the gateway, next to the
other `ait_tmux_*` surfaces, so `tests/test_no_raw_tmux.sh` stays satisfied.

```bash
# ait_tmux_self_pane_pid
# Echo the PID of the tmux pane THIS process runs in; return 1 when it cannot
# be established.
#
# The framework launches every agent as the pane's own process
# (lib/agent_launch_utils.py::launch_in_tmux passes the bare `claude …` /
# `codex …` / `opencode …` command string to new-window/split-window), so a
# pane's pid IS the agent CLI process — the one PID available at claim time
# whose lifetime tracks the agent session. That is what makes it usable as the
# task-lock anchor (lib/pid_anchor.sh::get_session_anchor_pid).
#
# Same-server guard: pane ids (%N) are per-server and collide across servers,
# so an inherited or stale $TMUX_PANE could name a stranger's pane. $TMUX is
# "<socket-path>,<server-pid>,<session-index>"; `#{socket_path}` is the queried
# server's socket. Both are asked for in ONE display-message.
# (aitask_shadow_capture.sh::shadow_self_target applies the same guard for the
# shadow binding; it keeps its own copy because its return contract is a
# classification string, not a pid.)
ait_tmux_self_pane_pid() {
    local own_pane="${TMUX_PANE:-}" own_sock="${TMUX:-}"
    [[ -n "$own_pane" ]] || return 1
    own_sock="${own_sock%%,*}"
    [[ -n "$own_sock" ]] || return 1
    local out sock pid
    out="$(ait_tmux display-message -p -t "$own_pane" \
        "#{socket_path}"$'\t'"#{pane_pid}" 2>/dev/null || true)"
    [[ "$out" == *$'\t'* ]] || return 1
    sock="${out%%$'\t'*}"
    pid="${out#*$'\t'}"
    [[ "$sock" == "$own_sock" ]] || return 1
    [[ "$pid" =~ ^[0-9]+$ ]] && (( pid > 1 )) || return 1
    printf '%s' "$pid"
}
```

### 2. `lib/pid_anchor.sh` — anchor resolution + tri-state liveness

Add (keeping the file's "safe to source multiple times" property):

- `AIT_PID_ANCHOR_UNKNOWN="-"` — the sentinel written when no session process
  can be named. Documented as **distinct from a dead PID**.
- `_PID_ANCHOR_LIB_DIR` — resolved from `${BASH_SOURCE[0]}`.
- `_anchor_tmux_pane_pid()` — lazily sources `tmux_exec.sh` from
  `_PID_ANCHOR_LIB_DIR` **only if present and not already loaded**, then calls
  `ait_tmux_self_pane_pid`. Mirrors the lazy-source pattern
  `terminal_compat.sh::ait_tmux_new_session_persistent` already uses, and keeps
  `pid_anchor.sh` usable in the ~15 test fixtures that `cp` it standalone
  (`setup_fake_aitask_repo` already copies `tmux_exec.sh` + `terminal_compat.sh`,
  so every lock-related fixture has it).
- `get_session_anchor_pid()` — the ladder from the table above. On an invalid
  or dead `$AIT_AGENT_PID`, warn on stderr and fall through to rung 2; never
  substitute a value that was not asked for silently.
- `_pid_exists()` — a **tri-state existence probe**. Today's `kill -0` is used
  as a two-state check, and its exit code cannot distinguish ESRCH from EPERM:
  verified on this box, `kill -0 1` returns rc=1, exactly like the absent pid
  4000000. Worse, an existence test that reads `/proc` alone is **not**
  authoritative either — under a `hidepid=2`/`hidepid=invisible` procfs mount
  another user's live process is simply not there, and `ps -p` (which reads the
  same procfs) is hidden with it. Treating that as "confirmed absent" would
  emit `RECLAIM_CRASH` for a live holder — the exact failure this task exists
  to remove.

  The disambiguator is `kill`'s **errno message**, which is unambiguous even
  though its exit code is not. Verified under `LC_ALL=C` on this box:

  | probe | message | meaning |
  |---|---|---|
  | `kill -0 1` | `Operation not permitted` | EPERM ⇒ the process **exists** |
  | `kill -0 4000000` | `No such process` | ESRCH ⇒ **confirmed absent** |

  (Identical wording from the bash builtin and `/bin/kill`; `LC_ALL=C` pins it.)
  So a negative from `/proc`/`ps` is never trusted on its own — it must be
  corroborated by an explicit ESRCH:

  ```bash
  # 0 = exists, 1 = CONFIRMED absent, 2 = cannot inspect.
  #
  # No single probe is authoritative. /proc and ps answer without signal
  # permission but go blind under a hidepid mount; kill's exit code collapses
  # EPERM into ESRCH but its errno MESSAGE separates them, and EPERM is itself
  # positive proof of existence. A negative is therefore only believed when
  # kill says "No such process"; anything unrecognised is `cannot inspect`,
  # never `absent`.
  _pid_exists() {
      local pid="$1" err
      [[ -e "/proc/$pid" ]] && return 0
      ps -p "$pid" -o pid= >/dev/null 2>&1 && return 0
      err="$(LC_ALL=C kill -0 "$pid" 2>&1)" && return 0   # signalable ⇒ exists
      case "$err" in
          *"No such process"*)        return 1 ;;         # ESRCH  ⇒ absent
          *"Operation not permitted"*|*"not permitted"*)
                                      return 0 ;;         # EPERM  ⇒ exists
      esac
      return 2                                            # undecidable
  }
  ```

- `get_pid_starttime()` gains a **non-`/proc` fallback** so BSD/macOS gets an
  identity token at all: `LC_ALL=C ps -p <pid> -o lstart=`, whitespace-collapsed
  into one opaque word (`Mon_Aug_10_09:19:16_2026`). `/proc` field 22 stays the
  first choice, so Linux is bit-identical to today. When neither source yields a
  token it still returns `-`.

- **Token strength is recorded, not assumed** — new `get_pid_starttime_kind()`
  returning `proc` | `ps` | `none`. The `/proc` token is jiffies-resolution
  (~10 ms); the `ps` token is **second**-resolution (verified: `Sun Aug  9
  07:47:24 2026`), so a PID recycled within the same second can carry an equal
  token. A weak token therefore **cannot license an `alive` verdict**.

  The kind is written into the lock as a new `pid_starttime_kind:` field rather
  than re-derived by the reader from its own platform: it is provenance for the
  value stored beside it, and — decisively — it makes the weak-token branch
  **plantable, and therefore testable on Linux**, instead of only reachable on
  a platform this project cannot run tests on. Absent field + non-`-` token ⇒
  `proc` (every anchored lock in existence was written by the `/proc` path;
  the `ps` fallback is new here).

- `lock_holder_liveness() -> alive | dead | unknown`. `alive` means *this PID is
  provably the process the lock recorded* — it requires existence **and** a
  matching **strong** token. Everything unprovable is `unknown`; only positive
  evidence of absence or of a different process is `dead`. (t1466 consumes this
  verdict as its live-holder discriminator; a false `alive` would let it refuse
  a lock on behalf of a process that is not the holder, and a false `dead` is
  the bug being fixed.)

  | existence | token | kind | verdict |
  |---|---|---|---|
  | confirmed absent | — | — | `dead` |
  | cannot inspect | — | — | `unknown` |
  | exists | `-` / absent | — | `unknown` |
  | exists | mismatch | any | `dead` (proof of a different process) |
  | exists | match | `proc` (strong) | **`alive`** |
  | exists | match | `ps` (weak) | **`unknown`** |

```bash
# Echo exactly one of: alive | dead | unknown.  $3 = token kind (default proc).
#
# unknown is NOT dead, and it is NOT alive — it is "we cannot prove either".
# It is produced by: no usable anchor ("-", "0", non-numeric); a process we
# cannot inspect; a process with no recorded identity token (a bare PID cannot
# be told apart from a recycled one); and a process whose token matches but was
# only second-granular (`kind: ps`), which cannot exclude same-second recycling.
# Reporting any of those as a crash is what made RECLAIM_CRASH meaningless
# (t1465); reporting them as alive would mislead t1466's acquire gate.
lock_holder_liveness() {
    local pid="${1:-}" starttime="${2:--}" kind="${3:-proc}" current rc=0
    [[ "$pid" =~ ^[0-9]+$ ]] && (( pid > 0 )) || { echo unknown; return 0; }
    _pid_exists "$pid" || rc=$?
    case $rc in
        1) echo dead;    return 0 ;;   # confirmed absent
        2) echo unknown; return 0 ;;   # cannot inspect
    esac
    # Exists. Identity is required before we call it the same process.
    [[ -n "$starttime" && "$starttime" != "-" ]] || { echo unknown; return 0; }
    current=$(get_pid_starttime "$pid")
    [[ "$current" == "-" ]] && { echo unknown; return 0; }
    [[ "$current" == "$starttime" ]] || { echo dead; return 0; }
    [[ "$kind" == "proc" ]] || { echo unknown; return 0; }   # weak token
    echo alive
}
```

  Note this keeps macOS crash detection working where it matters: a crashed
  agent's PID is *absent*, which is decided before the token is consulted. The
  weak-token rule only withholds the `alive` verdict, i.e. it degrades in the
  safe direction.

- `is_lock_holder_alive()` becomes a thin wrapper
  (`[[ "$(lock_holder_liveness "$@")" == alive ]]`). Contract unchanged, so
  `aitask_backfill_pid_anchor.sh`'s `pid: 0` sentinel self-test keeps passing.
- The `$AIT_AGENT_PID` rung's validation uses `_pid_exists` too, for the same
  EPERM/hidepid reason.

**Effect on the existing hand-planted tests** (all stay green, one for a better
reason):

| Test | Before | After |
|---|---|---|
| 2 — `pid: 999999` | `kill -0` fails → dead → CRASH | ESRCH → confirmed absent → dead → CRASH |
| 3 — `pid: 1` + wrong starttime | passes on **EPERM**, never reaching the starttime check | EPERM ⇒ exists → token mismatch → dead → CRASH, i.e. for the reason the test documents |
| 5 — pre-anchor lock (no `pid:`) | accepts CRASH or STATUS | deterministically STATUS |

### 3. `aitask_lock.sh` — correct `get_lock_pid()` (AC #4)

Keep the function as the writer's named entry point; replace the false comment
and delegate:

```bash
# PID to anchor the lock to: a process whose lifetime tracks the AGENT SESSION.
#
# NOT $PPID. On the path that matters, aitask_pick_own.sh:227 runs this script
# inside a command substitution, so $PPID is the claim script itself — dead
# seconds later, which made RECLAIM_CRASH fire on every same-host re-pick
# (t1465). Resolution ladder, the AIT_AGENT_PID override, and the UNKNOWN ("-")
# outcome are documented in lib/pid_anchor.sh.
get_lock_pid() {
    get_session_anchor_pid
}
```

`lock_task()` (lines 207-215) gains **one** field — the token's provenance —
and is otherwise unchanged. `get_pid_starttime "-"` already returns `-`, so an
UNKNOWN anchor writes `pid: -` / `pid_starttime: -` and the existing "missing
field collapses to `-`" reader path (lines 172-178) already handles it:

```bash
        lock_pid=$(get_lock_pid)
        lock_starttime=$(get_pid_starttime "$lock_pid")
        lock_starttime_kind=$(get_pid_starttime_kind "$lock_pid")
        lock_yaml="task_id: $task_id
…
pid: $lock_pid
pid_starttime: $lock_starttime
pid_starttime_kind: $lock_starttime_kind"
```

The reader side of `lock_task()` (the `prior_*` capture, lines 168-178) parses
the new field alongside `pid:` / `pid_starttime:`, collapsing an absent value
to `proc` (backward compat, see §2), and `PRIOR_LOCK:` gains it as a fifth
`|`-separated field. `aitask_pick_own.sh`'s `IFS='|' read` is extended to match;
a 4-field line from an older writer leaves the new variable empty, which the
`${…:-proc}` default covers.

### 4. `aitask_pick_own.sh` — branch on the tri-state (lines 391-427)

```bash
        local current_host liveness
        current_host=$(hostname 2>/dev/null || echo "unknown")
        liveness=$(lock_holder_liveness "$prior_pid" "$prior_starttime" \
                                        "${prior_starttime_kind:-proc}")
        # Only a provably DEAD same-host anchor is a crash. `alive` and
        # `unknown` both fall to the RECLAIM_STATUS anomaly path: giving a
        # verifiably-live holder its own signal/prompt is t1466's scope (it
        # names this anchor as the discriminator) — do not split it here.
        if [[ "$prior_lock_host" == "$current_host" && "$liveness" == "dead" ]]; then
            echo "RECLAIM_CRASH:${prior_locked_at}|${prior_lock_host}|${prior_pid}"
        else
            echo "RECLAIM_STATUS:${prev_status}|${prev_assigned}"
        fi
```

### 5. `aitask_backfill_pid_anchor.sh` — correct the stated purpose

Its header (lines 1-24, 37-45) says the `pid: 0` sentinel exists so re-picks
fire `RECLAIM_CRASH:` "instead" of `RECLAIM_STATUS:`. Under the fix `0` is
UNKNOWN, so it routes to `RECLAIM_STATUS:` — which is the honest verdict for a
lock that never had an anchor. Rewrite the "Why" block to say so and note the
script is now effectively a no-op for signalling. No behavior change; the
sentinel self-test still holds.

### 6. Tests — `tests/test_crash_recovery_pid_anchor.sh` (append Tests 8-13)

The existing suite plants **every** anchor by hand, so the writer's choice of
PID is never exercised. New cases, all on the existing `setup_paired_repos`
fixture (which already copies `tmux_exec.sh` via `setup_fake_aitask_repo`):

- **Test 8 — writer, deterministic seam (AC #2).** `sleep 300 &` → claim via
  the real `aitask_pick_own.sh` with `AIT_AGENT_PID=$sleep_pid` and *no planted
  state* → read the anchor back from `origin/aitask-locks` → assert
  `pid: $sleep_pid`, assert `pid_starttime` equals `get_pid_starttime
  $sleep_pid` (Linux), assert `lock_holder_liveness` reports `alive`.
- **Test 9 — live holder ⇒ no false crash (AC #3).** Same sleep still running,
  task set to `Implementing`/same email → re-pick → assert `OWNED`, assert
  `RECLAIM_STATUS`, assert **not** `RECLAIM_CRASH`.
- **Test 10 — positive control: a real crash is still caught.** `kill` the
  sleep and `wait` to reap it → re-pick → assert `RECLAIM_CRASH:` carrying that
  pid. Proves the new anchor did not simply disable crash detection.
- **Test 11 — negative control for the defect itself.** Claim with
  `AIT_AGENT_PID` **unset** (`env -u`) → read `pid:` back → assert it is either
  the UNKNOWN sentinel `-` **or** a currently-live PID; never a dead one. This
  is environment-independent (passes in tmux and in bare CI) and is exactly the
  assertion the pre-fix `$PPID` writer fails: `aitask_pick_own.sh`'s own PID is
  dead by the time the assertion runs.
- **Test 12 — UNKNOWN is its own state (AC #1).** Plant `pid: -` and (second
  scenario) `pid: 0` with the task `Implementing` → re-pick → assert
  `RECLAIM_STATUS` and **not** `RECLAIM_CRASH`.
- **Test 13 — `AIT_AGENT_PID` never fails open.** `AIT_AGENT_PID=999999` (dead)
  → claim → assert the stderr warning is emitted and the recorded `pid:` is not
  `999999`.
- **Test 14 — live PID, no identity token ⇒ `unknown`.** Plant
  `pid: <live sleep pid>` with `pid_starttime: -` and the task `Implementing` →
  re-pick → assert `RECLAIM_STATUS`, **not** `RECLAIM_CRASH`. Pins the
  starttime-identity contract at the signal level, so a later change that
  relaxes it back to `alive` is caught.
- **Test 15 — `_pid_exists` / `lock_holder_liveness` unit table.** Source
  `lib/pid_anchor.sh` directly and assert:

  | input | expected |
  |---|---|
  | `_pid_exists <live self-owned pid>` | rc 0 |
  | `_pid_exists 4000000` | rc 1 (confirmed absent, via ESRCH) |
  | `_pid_exists 1` | **rc 0** — a live process this user cannot signal. This is the EPERM case a bare `kill -0` gets wrong, and the same code path a `hidepid` mount exercises. |
  | live pid + matching token + kind `proc` | `alive` |
  | live pid + wrong token | `dead` |
  | live pid + token `-` | `unknown` |
  | live pid + matching token + kind **`ps`** | `unknown` — the weak-token rule, plantable on Linux precisely because the kind is recorded rather than re-derived from the platform |
  | absent pid | `dead` |
  | `-` / `0` / `abc` | `unknown` |

- **Test 16 — the `ps` token generator itself.** Linux `ps` also supports
  `lstart` (verified), so the BSD/macOS *implementation* is exercisable here
  even though its *dispatch* is not: assert `get_pid_starttime`'s ps branch
  returns a non-empty, whitespace-free token for a live pid, that two
  consecutive calls agree, and that two different processes started seconds
  apart get different tokens. Only the platform dispatch remains untested on
  this box — call that out in the implementation notes.
- **Test 17 — weak token at the signal level.** Plant a lock with a live PID,
  its **real** `ps`-format token, and `pid_starttime_kind: ps`, task
  `Implementing` → re-pick → assert `RECLAIM_STATUS`, **not** `RECLAIM_CRASH`
  (unknown, not a crash) — and separately that the identical lock with
  `pid_starttime_kind: proc` and a real `/proc` token also yields
  `RECLAIM_STATUS` (alive, also not a crash). The pair shows the strength gate
  changes the *verdict* without changing this task's *signal*, which is what
  hands t1466 a clean discriminator.
- Extend Test 7's syntax sweep with `lib/tmux_exec.sh`.

Existing Tests 1-6 stay untouched and must stay green.

### 7. New file: `tests/test_lock_anchor_tmux_live.sh` (the tmux rung, live)

Everything above drives the anchor through the `AIT_AGENT_PID` seam or through
the tmux rung's *failure* branch. Neither proves the rung that every managed
agent actually uses. A socket mismatch, a quoting slip, or an over-strict
same-server guard would make every real claim persist `pid: -` while the whole
suite above stays green — silently deleting the crash detection this task
exists to restore. That is the one failure mode a mock cannot see, so it gets a
live test.

Modelled on `tests/test_monitor_shadow_spawn_live.sh`:

- `command -v tmux || { echo "SKIP: tmux not available"; exit 0; }`.
- Source `tests/lib/tmux_isolation.sh` and call `require_isolated_tmux` (it
  unsets the ambient `TMUX`/`TMUX_PANE` and repoints `TMUX_TMPDIR`, so the
  user's server is unreachable for the whole process). `require_clean_ait_server`
  is **not** needed: every tmux call here is gateway- or fixture-routed, and the
  test arms no hooks and kills no shared server.
- Build the standard `setup_paired_repos` fixture (reuse it — factor it into
  `tests/lib/` only if that is a pure move).
- `export AITASKS_TMUX_SOCKET="ait-anchortest-$$"` **before** creating the
  session, so the value is inherited by the pane and the gateway inside the
  claim targets the same server the pane lives on. This is the load-bearing
  detail: `ait_tmux_self_pane_pid`'s same-server guard compares
  `#{socket_path}` against `${TMUX%%,*}`, and a mismatch is indistinguishable
  from "not in tmux".
- Create a detached session running a long-lived shell, then `send-keys` the
  claim so it runs **inside** the pane (tmux sets `TMUX`/`TMUX_PANE` there;
  exporting them by hand would test the fixture, not the product):

  ```bash
  ait_tmux new-session -d -s "$sess" -n anchor
  pane_pid=$(ait_tmux display-message -p -t "=$sess:anchor" '#{pane_pid}')
  ait_tmux send-keys -t "=$sess:anchor" \
    "cd '$local_dir' && env -u AIT_AGENT_PID PATH='$local_dir/bin:\$PATH' \
     TEST_HOSTNAME=pc-A ./.aitask-scripts/aitask_pick_own.sh 1 \
     --email alice@test.com > claim.out 2>&1; echo \$? > claim.rc" Enter
  ```

  Then poll for `claim.rc` under a bounded budget (~30s) rather than
  `capture-pane` — a redirected pane produces no visible output to capture.
- Assertions:
  1. `claim.rc` is `0` and `claim.out` contains `OWNED:1`;
  2. the lock's `pid:` **equals `$pane_pid`** — the positive proof that the
     tmux rung resolved, not a fallback;
  3. `pid:` is **not** `-` (states the failure mode in its own assertion, so a
     regression reads as "fell back to UNKNOWN" rather than a confusing
     inequality);
  4. `pid_starttime:` is non-`-`, `pid_starttime_kind:` is `proc`, and
     `lock_holder_liveness "$pane_pid" "$recorded_starttime" proc` reports
     `alive` while the pane is up.
- **Negative control** (proves assertion 2 can fail): repeat the claim in a
  second pane with `AITASKS_TMUX_SOCKET` overridden to a nonexistent socket
  *inside the send-keys command only*, and assert that claim records `pid: -`.
  Same fixture, one variable changed.
- Teardown: `ait_tmux kill-session` / `kill-server` on the fixture socket only,
  guarded by a `trap`.

Cost: one tmux server boot. Kept in its own file (not appended to
`test_crash_recovery_pid_anchor.sh`) so the fast hand-planted suite stays
boot-free, matching how the other live tmux tests are separated.

### 8. Docs — `website/content/docs/workflows/crash-recovery.md`

- **Line 9 intro:** "The PID liveness signal is binary — alive or dead — so
  there is … no false positives from a still-running agent" is the claim this
  bug falsified, *and* the binary framing is now wrong. Rewrite around the
  session anchor and the **three** liveness states.
- **§Same-host crash:** describe *which* process the lock anchors to and the
  resolution ladder; state that only a provably dead same-host anchor emits
  `RECLAIM_CRASH:`. Replace the `kill -0` description: existence is decided by
  `/proc` → `ps` → `kill`'s **errno**, and an absence is only believed on an
  explicit "No such process" — so a restricted (`hidepid`) procfs yields
  "cannot tell", not "crashed".
- **§Lock anomaly fallback:** add the UNKNOWN cases alongside the legacy-lock
  case — an out-of-tmux claim, a live PID with no recorded identity token, a
  PID that cannot be inspected, and a PID whose identity token is only
  second-granular; drop the "run the backfill so re-picks route through
  `RECLAIM_CRASH`" advice.
- **§End-to-End Example** steps 1 and 3: `pid: <agent-pid>` → the pane/agent
  process; the crash is the pane dying; step 3's `kill -0 <dead-pid>` → the
  existence probe.
- **Tips:** replace the backfill bullet (pre-anchor locks now get the honest
  `RECLAIM_STATUS:` fallback and the backfill is no longer needed); rewrite the
  **macOS portability** bullet — macOS/BSD now gets an `lstart`-based identity
  token, but it is **second-granular and explicitly best-effort**, so a match
  yields "cannot tell" rather than "alive" and same-second PID recycling can
  never be mistaken for a live holder (a crashed agent is still detected, since
  its PID is absent); add a bullet for out-of-tmux claims + `AIT_AGENT_PID`.
- **New lock field:** `pid_starttime_kind:` is documented wherever the lock
  metadata fields are listed on this page, including the backward-compatible
  default for locks written before it existed.

### Post-phase (risk mitigations)

1. `[tmux_unreachable_degradation]` Add a test to
   `tests/test_crash_recovery_pid_anchor.sh` that drives the tmux rung's
   failure branch through a documented seam: claim via the real
   `aitask_pick_own.sh` with `AIT_AGENT_PID` unset, `TMUX_PANE=%999` and
   `AITASKS_TMUX_SOCKET=ait-nonexistent-<pid>` (the gateway's own socket
   selector — no test-only override), and assert **all** of:
   - the claim still exits 0 and prints `OWNED:1` (a wedged tmux must never
     abort a claim under `set -euo pipefail`);
   - the recorded `pid:` is the UNKNOWN sentinel `-`;
   - the whole invocation completes inside a bounded wall-clock budget
     (wrap in `timeout 30` and assert the exit status is not `124`).

2. `[launcher_assumption_pin]` Pin the assumption at the place that can break
   it. In `lib/agent_launch_utils.py::launch_in_tmux`, add a comment stating
   that the command string is handed to tmux **unwrapped on purpose** — the
   pane's pid is the agent CLI process, and `lib/pid_anchor.sh` anchors task
   locks to it, so introducing a wrapper that outlives the agent would make a
   dead agent's lock read "alive". Make the reference bidirectional: name
   `launch_in_tmux` from `ait_tmux_self_pane_pid`'s comment (already drafted in
   §1) and name `ait_tmux_self_pane_pid` from the launcher comment. Then read
   `tests/test_launch_in_tmux_pane_pid.py`; if it already asserts on the
   command handed to tmux, extend it with a no-wrapper assertion — if it does
   not, record that in the implementation notes rather than inventing a new
   test harness here.

---

## Verification

```bash
# 1. Targeted suites (the files that own this contract)
bash tests/test_crash_recovery_pid_anchor.sh
bash tests/test_lock_anchor_tmux_live.sh      # boots an isolated tmux server;
                                              # SKIPs cleanly without tmux

# 2. Everything that copies or drives the lock scripts
bash tests/test_task_lock.sh
bash tests/test_lock_reclaim.sh
bash tests/test_lock_force.sh
bash tests/test_lock_diag.sh
bash tests/test_no_raw_tmux.sh

# 2b. Python side touched by the launcher_assumption_pin post-phase
bash tests/run_all_python_tests.sh --test-dir tests   # read only the last line
#   (or, narrowed: the venv pytest on tests/test_launch_in_tmux_pane_pid.py)

# 3. Lint
shellcheck .aitask-scripts/aitask_lock.sh \
           .aitask-scripts/aitask_pick_own.sh \
           .aitask-scripts/aitask_backfill_pid_anchor.sh \
           .aitask-scripts/lib/pid_anchor.sh \
           .aitask-scripts/lib/tmux_exec.sh

# 4. Live end-to-end on this repo: the anchor of the CURRENT session's own lock
#    must be alive and must be the pane process, not a claim script.
source .aitask-scripts/lib/pid_anchor.sh
./.aitask-scripts/aitask_lock.sh --check 1465
#   -> pid: must equal `ait_tmux display-message -p -t "$TMUX_PANE" '#{pane_pid}'`
#      and `lock_holder_liveness <pid> <pid_starttime> <pid_starttime_kind>`
#      must print `alive`.
```

Negative control for the fix (run **before** editing, expect failure; after,
expect pass): Test 11's assertion against the unpatched writer.

## Step 9 (Post-Implementation)

Standard: merge approval, `ait gates run 1465` (active set: `risk_evaluated`),
archival of task + plan.

## Risk

Levels below are the **post-inline reassessment** — they describe the plan as
approved (implementation body + the two mitigation phases), not the
pre-insertion plan.

### Code-health risk: medium
- `lib/pid_anchor.sh` gains a lazy `source` of `lib/tmux_exec.sh`; ~15 test
  fixtures `cp` `pid_anchor.sh` standalone, and any that lack `tmux_exec.sh`
  would silently degrade to UNKNOWN anchors · severity: low (residual —
  addressed by inline pre-phase fixture_tmux_dep_audit, which converts the
  assumption into a checked hit count before the source is added) · → mitigation: inline pre-phase fixture_tmux_dep_audit
- Every `ait lock` acquisition now spawns a `tmux display-message` subprocess;
  a wedged or unreachable tmux server must degrade to UNKNOWN, not hang or
  abort the claim under `set -euo pipefail` · severity: low (residual —
  addressed by inline post-phase tmux_unreachable_degradation, which drives the
  failure branch through the gateway's own socket selector under a timeout) · → mitigation: inline post-phase tmux_unreachable_degradation
- Behavior change hidden in a shared reader: `unknown` no longer emits
  `RECLAIM_CRASH`, which silently redefines what
  `aitask_backfill_pid_anchor.sh` and the published docs promise · severity: low · → mitigation: none (covered by §5/§8 of this plan)
- **New (introduced by the augmented plan):** the two inline phases widen the
  change to a third file (`lib/agent_launch_utils.py`) and a Python test, so
  the commit now spans shell libs, shell tests, Python, and docs · severity: low · → mitigation: none
- **New:** the `ps -o lstart=` starttime fallback dispatches only on a platform
  without `/proc`, which cannot be executed on this Linux box. Contained on
  three sides: `/proc` is tried first (Linux is bit-identical to today); the
  generator itself *is* exercised here (Linux `ps` supports `lstart`, Test 16);
  and its second-granular token is classified `weak`, so it can never produce
  an `alive` verdict. What remains untested is the dispatch decision alone ·
  severity: low · → mitigation: none
- **New:** the lock YAML gains a field (`pid_starttime_kind:`) and
  `PRIOR_LOCK:` gains a fifth `|`-separated field. Both are additive with
  documented defaults for older writers, but a wire-format change to a
  cross-machine artifact is worth calling out · severity: low · → mitigation: none

The dimension stays **medium** rather than dropping to low: the mitigations cut
the likelihood of each specific failure, but the blast radius is unchanged — a
shared reader lib (`pid_anchor.sh`), the tmux gateway, and the lock critical
path are all load-bearing for every pick on every machine.

### Goal-achievement risk: low
- The pane-pid anchor is only correct while `launch_in_tmux` execs the bare
  agent command. If a launch path ever wraps the agent in a shell that outlives
  it, the anchor would report "alive" after the agent died — a false negative
  that is harder to notice than today's false positive · severity: low
  (residual — addressed by inline post-phase launcher_assumption_pin, which
  makes the dependency visible at the site that can break it) · → mitigation: inline post-phase launcher_assumption_pin
- Out-of-tmux claims record UNKNOWN, so those users get no crash detection at
  all. Accepted and confirmed by the user; `AIT_AGENT_PID` is the escape hatch · severity: low · → mitigation: none (accepted)

### Planned mitigations
- timing: pre-phase | name: fixture_tmux_dep_audit | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: lazy source of tmux_exec.sh could silently degrade standalone-cp fixtures to UNKNOWN anchors | desc: enumerate every test that cp's lib/pid_anchor.sh and verify each also receives lib/tmux_exec.sh, adding the copy where missing, before the source is introduced
- timing: post-phase | name: tmux_unreachable_degradation | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: every ait lock acquisition now spawns a tmux display-message on the critical path | desc: test that a claim against an unreachable tmux socket still exits 0 with OWNED, records the UNKNOWN sentinel, and completes within a bounded timeout
- timing: post-phase | name: launcher_assumption_pin | type: documentation | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: the pane-pid anchor is only correct while launch_in_tmux execs the bare agent command | desc: add a bidirectional comment between launch_in_tmux and ait_tmux_self_pane_pid naming the anchor contract, and extend tests/test_launch_in_tmux_pane_pid.py with a no-wrapper assertion if that test already inspects the launch command
