---
Task: t1705_1_spike_freeze_standin_and_session_id_capture.md
Parent Task: aitasks/t1705_frozen_codeagents_session_store_and_viewer_tui.md
Sibling Tasks: aitasks/t1705/t1705_2_*.md … aitasks/t1705/t1705_10_*.md
Archived Sibling Plans: aiplans/archived/p1705/p1705_*_*.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1705_1 — Spike: freeze stand-in respawn + session-id capture

## Step 0 — tmux preflight (run BEFORE anything else; blocking)

This task destructively manipulates tmux (`respawn-pane -k`, real `pane-died`
cleanup hooks, `kill-window`/`kill-server` on an isolated server). Its live
tests call `tests/lib/tmux_isolation.sh::require_clean_ait_server`, which
refuses to run from inside tmux or while the dedicated `-L ait` server has any
pane. Check this **first**, before planning or editing a file:

```bash
[ -z "${TMUX:-}" ] && echo "PREFLIGHT_OK: not inside tmux" || { echo "PREFLIGHT_BLOCKED: this session runs inside tmux ($TMUX)"; }
tmux -L ait list-panes -a -F '#{pane_id} #{window_name}' 2>/dev/null && echo "NOTE: the -L ait server has panes — stop 'ait ide' / close them before running the live suites" || echo "PREFLIGHT_OK: -L ait server idle"
```

- `PREFLIGHT_BLOCKED` → **do not implement.** Execute the workflow's **Task
  Abort Procedure** (`task-abort.md`) so the task reverts to `Ready` with its
  plan kept, and tell the user to re-pick from a terminal that is NOT inside
  tmux. Do not set `AIT_LIVE_TMUX_TEST_FORCE=1` — it is for a dedicated CI
  box only.
- `-L ait` server has panes → implementation may proceed, but the live suites
  will refuse until that server is stopped; say so in the Final
  Implementation Notes if verification had to wait.

## Context

The risk-mitigation spike `spike_frozen_standin_respawn` of the parent plan
(`aiplans/p1705_frozen_codeagents_session_store_and_viewer_tui.md`, `## Risk`).
Every later child pins contracts on tmux and code-agent facts that this repo
has never exercised: `respawn-pane` has zero call sites, agents run with
`remain-on-exit on` plus a `pane-died[N]` hook (`aitask_companion_cleanup.sh`)
that kills the window when no real agent sibling remains, and the
SessionStart hook mechanism has no precedent here for either agent. This
child proves each fact on an isolated server and records the answers as a
`## Spike findings (t1705_1) — PINNED` block in the parent plan, which the
parent's post-approval step copies into children 2–5. **Product code is out
of scope** — the deliverable is evidence plus the reusable probe and fixtures.

**Tmux-stress**: implement and verify from a shell **outside** the user's
`-L ait` server (`aidocs/framework/tui_conventions.md` §"Tmux-stress tasks").
`$TMUX` beats `TMUX_TMPDIR`; never `kill-server` from an agent pane.

## Files

- **New** `tests/test_frozen_standin_spike.sh` — the probe, permanent (child 4's live control).
- **New** `tests/lib/fake_agent.sh` — long-running fake agent; `--resume <id>` / `resume <id>` print the id then sleep; `FAKE_AGENT_EXIT=1` exits 1 immediately. Reused by children 5 and 8.
- **New** `tests/data/session_hooks/claude_sessionstart.json`, `codex_sessionstart.json` — real payloads, cwd redacted.
- **New** `tests/data/session_hooks/README.md` — how each was captured (command, agent version, date).
- **Edit** `aiplans/p1705_frozen_codeagents_session_store_and_viewer_tui.md` — append the findings block.
- **Maybe** `tests/test_guard_live_tmux.sh` (case 7).

## Implementation steps

1. **Scaffold** `tests/test_frozen_standin_spike.sh` on the
   `tests/test_shadow_capture.sh` shape: `source tests/lib/asserts.sh`,
   `assert_counters_init` (cases run in `( … )` subshells), `source
   tests/lib/tmux_isolation.sh`, `require_isolated_tmux`,
   `require_clean_ait_server`. Every tmux call through `ait_tmux` from
   `.aitask-scripts/lib/tmux_exec.sh` (sources `AITASKS_TMUX_SOCKET` as the
   isolation helper pinned it).
2. **Fixture builder** `make_agent_window()` — mirrors
   `tests/test_kill_agent_pane_smart.sh`'s `make_window()` but through the
   *shipped* Python helpers: `python3 - <<EOF` importing
   `agent_launch_utils` (`sys.path` to `.aitask-scripts/lib`), calling
   `launch_in_tmux(fake_agent_cmd, TmuxLaunchConfig(session=…, window="agent-pick-1", new_window=True, …))`,
   then `attach_companion_cleanup_hook(agent_pane, companion_pane)` after a
   `split-window` running `sleep 1000` as the "companion" stamped with
   `@aitask_monitor_kind=minimonitor:<pid>` (so the cleanup script sees it
   as a companion). Read t1699's task file first — it reorders this fixture.
3. **Case 1 — stand-in respawn keeps the window.** Instrument
   `aitask_companion_cleanup.sh` by prepending a wrapper dir to `PATH` that
   logs argv + `#{@aitask_frozen}` of the dying pane to a file before
   exec'ing the real script. Stamp `@aitask_frozen=abc123` on the agent
   pane; `ait_tmux respawn-pane -k -t "$agent_pane" 'sleep 1000'`; sleep 1;
   assert window exists, companion pane exists, agent pane id unchanged and
   `#{pane_current_command}` is `sleep`. Record in `FINDINGS` whether the
   log shows a `pane-died` invocation and whether the stamp was visible.
   **Negative control**: repeat with the cleanup script *unmodified* and no
   stamp-aware abstention (i.e., the real current script) — if the window
   survives even without abstention, that too is a finding (pane-died may
   simply not fire on `-k` respawn); if it dies, the control proves the
   abstention is load-bearing.
4. **Case 2 — options survive respawn; pane_pid changes.** Assert
   `#{@aitask_frozen}` reads `abc123` after the respawn; assert new
   `#{pane_pid}` ≠ old.
5. **Case 3 — env prefix keeps pane_pid.** `respawn-pane -k … 'env
   AITASK_RESTORE_RECORD=x sleep 1000'`; assert `#{pane_pid}` == `pgrep -f
   'sleep 1000'` inside that pane and `tr '\0' '\n' </proc/<pid>/environ |
   grep AITASK_RESTORE_RECORD=x`.
6. **Case 4 — `run-shell -b` outlives the caller pane.** From the agent
   pane's shell: `ait_tmux run-shell -b 'sleep 2; touch <marker>'`, then
   immediately `respawn-pane -k` that pane; assert the marker appears within 4 s.
7. **Case 5 — Claude SessionStart** (guarded by `command -v claude` and
   `AITASKS_SPIKE_REAL_AGENTS=1`). Scratch project dir with
   `.claude/settings.json`:
   `{"hooks":{"SessionStart":[{"matcher":"startup|resume","hooks":[{"type":"command","command":"<abs>/capture_hook.sh","timeout":10}]}]}}`
   where `capture_hook.sh` writes stdin + `env | grep -E '^(TMUX_PANE|AITASK_AGENT_STRING)='`
   to a file. Launch `env AITASK_AGENT_STRING=claudecode/opus5 claude -p 'say hi'`
   in a pane (headless keeps it short); assert the payload has
   `session_id`, `transcript_path`, `cwd`, `source`; assert `TMUX_PANE` and
   `AITASK_AGENT_STRING` were visible. Relaunch `claude --resume <id> -p 'hi again'`
   in a respawned pane; assert a second payload with `source: resume` and
   the same id. Save the redacted first payload as the fixture.
8. **Case 6 — Codex SessionStart + `codex resume`.** Try `.codex/config.toml`
   `[hooks]` first, then `.codex/hooks.json` (per t1705's task notes); note
   whether the project layer must be trusted. `codex exec 'say hi'`, capture,
   then `codex resume <id>` in a respawned pane. **Failures are findings**:
   write `codex hooks: unsupported` / `codex resume: fails` into the block;
   the parent's fallback (codex = re-pick only) becomes pinned.
9. **Case 7 — live-tmux guard.** Pipe a synthetic PreToolUse payload with
   `command: "tmux -L spike respawn-pane -k -t %1 sleep 1"` into
   `.claude/hooks/guard_live_tmux.py`; assert no `deny`. And with a bare
   `tmux respawn-pane …`, assert `deny` (the existing behaviour). If a
   socketed respawn is denied today, fix the guard and extend
   `tests/test_guard_live_tmux.sh`.
10. **Findings block.** The script prints a `FINDINGS:` summary; copy it
    into the parent plan under `## Spike findings (t1705_1) — PINNED` in the
    exact format the task file shows, and commit with `./ait git`.

## Verification

```bash
bash tests/test_frozen_standin_spike.sh
AITASKS_SPIKE_REAL_AGENTS=1 bash tests/test_frozen_standin_spike.sh
bash tests/test_guard_live_tmux.sh
bash tests/test_no_raw_tmux.sh
grep -A8 'Spike findings' aiplans/p1705_frozen_codeagents_session_store_and_viewer_tui.md
```

Step 9 (Post-Implementation) of the task workflow handles commit, sibling
context and archival.

## PINNED contracts (from p1705 — do not re-decide)

Copied verbatim from `aiplans/p1705_frozen_codeagents_session_store_and_viewer_tui.md` §A–§D. On any discrepancy the parent plan wins; if a child must deviate, update the parent plan and every sibling plan in the same commit.


#### A. Session store — `lib/agent_sessions.py` + `aitask_agent_sessions.sh`

- Path `~/.config/aitasks/agent_sessions.json`, env override
  `AITASKS_AGENT_SESSIONS_FILE`, lock dir derived from the resolved path
  (`<file>.lockd`), 0600 with `_target_mode` preservation, write via
  `lib/atomic_write.py`. Captures under `~/.config/aitasks/frozen/<id>/`
  (0700 dir; `capture.ansi`, `capture.txt`), env `AITASKS_FROZEN_DIR`.
- Schema v1:
  ```json
  {"version": 1, "sessions": [{
    "id": "7f3a2c1d",                 // record id (8 hex, os.urandom) — PRIMARY KEY
    "root": "/real/path/project",     // realpath, both sides         ┐ DURABLE IDENTITY
    "window": "agent-pick-1705",      //                               │ (root, window, window_slot)
    "window_slot": 0,                 // assigned once; >0 only for a 2nd agent in the same window ┘
    "pane_id": "%104", "pane_pid": 41233,   // LOCATION / GENERATION data — replaceable, never identity
    "session": "aitasks",             // tmux session name — display only
    "operation": "pick", "task_id": "1705",          // task_id "" when unbound
    "agent_string": "claudecode/opus5", "agent_kind": "claudecode",
    "codeagent_session_id": "", "transcript_path": "",  // "" = unknown → re-pick only
    "started_at": "2026-09-04T09:12:03Z",
    "state": "live",                  // live | freezing | frozen | restoring | aborting
    "state_at": "2026-09-04T09:12:03Z",
    "op_nonce": "", "op_owner_pid": 0, "op_started_at": "",   // LEASE of the in-flight freeze/restore (see below)
    "frozen_at": "", "capture_ansi": "", "capture_txt": "",
    "capture_lines": 0, "last_phase": "",
    "standin_pid": 0,                 // #{pane_pid} of the stand-in viewer, written at freeze-commit and every stand-in respawn
    "launch_pid": 0,                  // #{pane_pid} of the replacement agent, written by restore-launched (nonce-bound)
    "restore_attempts": 0, "restore_mode": "",   // "" | resume | repick (current attempt)
    "ack": "",                        // "" | hook | liveness — how the last restore was confirmed
    "last_error": ""                  // "" | "<nonce>:session_mismatch" | "<nonce>:<reason>" — coordinator-readable outcome channel
  }]}
  ```
  `pane_id` / `pane_pid` are **location and generation data**: a tmux server
  restart, a reattach or a respawn replaces them on the same record. They
  are never part of the identity key and a recycled `%N` can attach to
  nothing on its own — attachment needs either `@aitask_record` on the pane
  (options die with the pane, so a recycled pane never carries a stale one)
  or a `(root, window)` match under the conflict policy below.
  Unknown `state` = corruption (not a default). `load()` raises
  `MalformedSessionsError`; `load_safe()` returns empty. Generation normalised
  to `SCHEMA_VERSION` on read.
- **Record ownership (one allocator) and the `(root, window)` conflict
  policy.** The `upsert` verb is the *only* creator of records. Resolution
  order for a caller without `--restore-of`:
  1. `--id <rid>` (from `@aitask_record` on the caller's pane) → that record,
     whatever its `(root, window)` (a renamed window keeps its record).
  2. Else, **among `live` records only** with the caller's `(root, window)`,
     the relocation candidates are: the one whose `pane_id` equals the
     caller's pane, else those whose `pane_pid` is dead or whose pane no
     longer exists. **Exactly one candidate** → it is the same agent slot:
     replace `pane_id`/`pane_pid`, update session id / transcript / agent
     string, print `UPSERTED:<id>|updated` (the tmux-restart and reattach
     case — no second record). **More than one candidate** (two agents shared
     the window before a server restart; nothing on the caller's side can
     tell them apart) → **fail closed on relocation**: fall through to rule 3
     and print `UPSERTED:<id>|created_slot<N>|ambiguous_relocation`; the stale
     records are left for purge (rule: a `live` record whose `pane_pid` is
     dead and whose `pane_id` is absent from an enumerated window →
     `DROPPED:…|dead_pane`), never guessed.
     Transitional records (`freezing`/`restoring`/`aborting`) are **never**
     relocated or updated by an unstamped caller: they are touched only by
     `--restore-of` + the current nonce, or by `reconcile`. If the caller's
     pane *is* a transitional record's pane → refuse
     (`UPSERT_REFUSED:<id>|<state>_unacknowledged`, a stray session in a
     transacting pane); otherwise they are simply not candidates.
  3. Else every `(root, window)` record is `live` in **another** pane (a
     second agent split into the same window), transitional, or `frozen`
     (retained state whose window name is being reused, e.g. the same task
     re-picked after a tmux restart) → **create beside it**: new record,
     `window_slot` = lowest unused slot for that `(root, window)`, print
     `UPSERTED:<id>|created_slot<N>`. A retained frozen record never blocks a
     live launch and is never attached to; it stays restorable into a fresh
     window (`unique_window_name` disambiguates) and is listed distinctly by
     its `frozen_at`.
  4. Else → create (`state=live`, `window_slot=0`), print `UPSERTED:<id>|created`.
  In every create/update branch the caller's pane is stamped
  `@aitask_record=<id>`.
  Other branches:
  - record exists in `restoring` **and** the caller passes
    `--restore-of <id> --nonce <n>` (the hook forwards them from the
    replacement agent's environment, §D) → the **restore acknowledgement**:
    nonce must equal `op_nonce`; in `resume` mode `--session-id` must equal
    `codeagent_session_id` — else the store **persists**
    `last_error="<nonce>:session_mismatch"` (state unchanged) and prints
    `RESTORE_SESSION_MISMATCH:<id>` exit 7. The hook has no return channel to
    the detached coordinator, so the record *is* the channel: the coordinator
    and `reconcile` both read `last_error` for the current nonce and take the
    abort branch, never the liveness fallback. In `repick` mode the new
    session id is adopted. On success: `pane_id`/`pane_pid` updated from the
    caller's pane, `@aitask_record` stamped on it, state `live`, `ack=hook`,
    capture files deleted, print `UPSERTED:<id>|restored`;
  - record exists in `restoring` without `--restore-of`/`--nonce` → refuse,
    print `UPSERT_REFUSED:<id>|restoring_unacknowledged` (a stray session in
    a restoring pane is never an ack);
  - record exists in `freezing` / `frozen` → refuse, print
    `UPSERT_REFUSED:<id>|<state>` (a hook firing in a stand-in pane is a bug).
  Two callers: the SessionStart hook (child 3, normal path) and the freeze
  engine (child 4, fallback when the hook never fired). Both read
  `@aitask_record` off the pane first and pass `--id` when present, so a pane
  that was already recorded is never duplicated even after a `pane_id`
  recycle. A restore into a **new** pane (window gone) carries the record id
  in the environment, never on the pane, so it selects the old record instead
  of creating a second one.
- **Operation lease.** `freeze-begin`, `restore-begin` and `lease-take` mint
  `op_nonce` (8 hex), record `op_owner_pid` (the coordinator) and
  `op_started_at`, and print the nonce. **Every verb that mutates a record
  holding a lease** (`freeze-commit`, `freeze-abort`, `restore-launched`,
  `restore-confirm`, `restore-abort`, `standin-respawned`, the ack form of
  `upsert`) requires `--nonce <n>`; a mismatch prints `NONCE_MISMATCH:<id>`
  exit 6 and writes nothing — a coordinator that lost the race to
  `reconcile` fails closed instead of double-acting. `lease-take <id>` →
  `LEASED:<id>|<nonce>` is how `reconcile` (or a stand-in relaunch on a
  `frozen` record) acquires ownership: it is refused (`LEASE_HELD:<id>`)
  while a lease exists whose `op_started_at` is younger than
  `stale_op_grace` (default 60 s) **or** whose `op_owner_pid` is alive; a
  stale lease with a dead/unverifiable owner is taken over. Within the grace,
  or with a live owner, reconcile leaves the record alone. Lease-clearing
  transitions (`freeze-commit`, `freeze-abort`, `restore-confirm`, hook ack,
  `standin-respawned` out of `aborting`) clear the lease.
- **State machine** (every transition is one locked verb; illegal transitions
  print `TRANSITION_REFUSED:<id>|<from>|<verb>` exit 5 and write nothing):
  ```
  live ──freeze-begin──▶ freezing ──freeze-commit──▶ frozen ◀────────────────┐
   ▲                        │                          │                      │
   └────freeze-abort────────┘                          │ restore-begin        │ standin-respawned
   ▲                                                   ▼                      │ (same nonce)
   └──upsert (hook ack) / restore-confirm── restoring ──restore-abort──▶ aborting
  drop: any state → record removed + capture files removed
  ```
  `aborting` is **nonce-owned**: the record stays leased by the aborting
  attempt until its stand-in is back (`standin-respawned --nonce` → `frozen`,
  lease cleared). `restore-begin` on `aborting` → `TRANSITION_REFUSED`, so a
  user or a second controller cannot start another restore in the gap and
  an old coordinator cannot respawn over a newer attempt: its `standin-respawned`
  carries a stale nonce and is refused.
  **Captures are deleted only on a verified ack** (`ack=hook`). A
  liveness-only `restore-confirm` transitions to `live` but **keeps** the
  capture files (`ack=liveness`); they are removed on `drop` or liveness
  purge. This is what stops a malformed resume that starts a fresh session
  from destroying the only copy.
- Wrapper verbs (sole writer; `list`/`show` take no lock; exit 0/2/3
  `LOCK_BUSY`/4 `ERROR`/5 `TRANSITION_REFUSED`/6 `NONCE_MISMATCH`/7
  `RESTORE_SESSION_MISMATCH`/8 `LEASE_HELD`):
  `upsert --root <r> --window <w> --pane <id> --pane-pid <pid> [--id <rid>] [--session-id <sid>] [--transcript <p>] [--agent-string <s>] [--operation <op>] [--task-id <t>] [--restore-of <rid> --nonce <n>]`;
  `freeze-begin <id> --capture-ansi <p> --capture-txt <p> --lines <n> [--phase <t>]` → `FREEZING:<id>|<nonce>`;
  `freeze-commit <id> --nonce <n> --pane <pane_id|""> --pane-pid <pid|0>` → `FROZEN:<id>` (writes the stand-in's location: `pane_id`/`standin_pid` from the arguments; `--pane "" --pane-pid 0` is the gone-pane commit used by reconcile; `--pane` without `--pane-pid` or vice versa → usage error exit 2);
  `freeze-abort <id> --nonce <n>` → `LIVE:<id>` (captures deleted);
  `restore-begin <id> --mode resume|repick` → `RESTORING:<id>|<nonce>` (captures **retained**, `restore_attempts`+1, `launch_pid=0`, `last_error=""`);
  `restore-launched <id> --nonce <n> --pane <id> --pane-pid <pid>` → `LAUNCHED:<id>` (records the replacement's `launch_pid` + location; written by the coordinator right after `respawn-pane`/`launch_in_tmux` returns — the nonce-bound evidence that the respawn happened);
  `restore-confirm <id> --nonce <n> --pane <id> --pane-pid <pid>` → `LIVE:<id>|liveness` (captures **kept**; refused with `TRANSITION_REFUSED` unless `launch_pid != 0` and equals `--pane-pid`);
  `standin-respawned <id> --nonce <n> --pane <id> --pane-pid <pid>` → `STANDIN:<id>` (records the stand-in's `standin_pid` + location; from `aborting` it also transitions to `frozen` and clears the lease; from `frozen` (a `lease-take`n relaunch of a dead stand-in) it just updates and clears the lease; `freeze-commit` folds the same write in);
  `restore-abort <id> --nonce <n>` → `ABORTING:<id>` (captures retained; lease kept by the same nonce);
  `lease-take <id>` → `LEASED:<id>|<nonce>` / `LEASE_HELD:<id>` exit 8;
  `drop <id>` → `DROPPED:<id>`;
  `list [--state <s>] [--root <r>]` → `SESSION:<id>|<state>|<root>|<window>|<pane_id>|<task_id>|<agent_string>|<state_at>`;
  `show <id>` → `KEY:value` lines;
  `purge --observed <file>` → `DROPPED:<id>|<reason>` + `PURGED:<n>`.
  **Observation protocol (superset of the marks one, backward-compatible):**
  ```
  ROOT<TAB><root>                                   -- successfully enumerated root
  WINDOW<TAB><root><TAB><window>                    -- observed agent window
  PANE<TAB><root><TAB><window><TAB><pane_id><TAB><pane_pid><TAB><pane_dead>   -- every pane of that window
  INCOMPLETE                                        -- suppress every sweep
  ```
  `monitor_shared._write_observation_file()` gains a `panes=` argument and
  writes the `PANE` rows from `TmuxMonitor.last_discovered_panes()` (the
  `_LIST_PANES_FORMAT` already carries `pane_id` and `pane_pid`; `pane_dead`
  is appended to the format — see §B arity rule). The marks reader
  (`agent_marks._read_observed`) is extended to **skip** `PANE` rows so one
  file serves both purges; `agent_sessions` requires them. A file with
  `ROOT`/`WINDOW` but no `PANE` rows for an enumerated root is treated as
  pane-incomplete for that root: `dead_window` still applies, `dead_pane`
  does not (fail closed).
- **Purge policy** (fail-closed on `INCOMPLETE`, mirrors `sweep_liveness`):
  a `live` record whose `(root, window)` is absent from a successfully
  enumerated root → `DROPPED:…|dead_window`; a `live` record whose window has
  a `WINDOW` row **and** `PANE` rows, but whose `pane_id` appears in none of
  them (or appears with `pane_dead=1`) and whose `pane_pid` is dead
  (`os.kill(pid, 0)` → `ESRCH`; an `EPERM`/unverifiable pid is treated as
  alive) → `DROPPED:…|dead_pane` — this is what retires the stale candidates
  left behind by an ambiguous relocation. Two producers feed `purge`: the
  monitor maintenance tick (observation file above) and `aitask_frozen.sh
  reconcile`, which builds the same file from its own `list-panes` pass so
  retirement does not depend on a TUI being open. `freezing` / `frozen` / `restoring` /
  `aborting` records are never purged by liveness — they are reconciled by
  `aitask_frozen.sh reconcile` (§C/§D). A frozen record whose capture file is
  missing → `DROPPED:…|capture_missing`.
- `SessionsView` (mtime+size+inode gated) for the TUIs; `invalidate()` after
  every write. `standin_command(record_id) -> str` returns
  `ait frozenagent --record <id>` unless `AITASKS_FROZEN_STANDIN_CMD` is set
  (documented **test seam**; production never sets it).

#### B. Pane options (tmux user options, pane-scoped)

| Option | Set by | Cleared by | Read by | Meaning |
|---|---|---|---|---|
| `@aitask_record=<id>` | `upsert` (hook or freeze engine) | `drop`; pane death | freeze engine, restore coordinator, hook (`--id`) | the pane-visible join to its store record |
| `@aitask_frozen=<id>` | freeze engine, immediately before `respawn-pane` | `restore-confirm` path (coordinator), `drop` | `_LIST_PANES_FORMAT` (appended), `kill_agent_pane_smart` format, `aitask_companion_cleanup.sh`, `maybe_spawn_minimonitor` occupancy | this pane is a frozen stand-in — **authoritative** classifier |
| `@aitask_standin_ready=<id>` | **the viewer itself**, after mount (only the app stamps its own pane — `mark_monitor_pane` rule) | freeze engine + restore coordinator (`set-option -pu`) immediately **before** every `respawn-pane`; `drop` | `reconcile` | positive proof that the stand-in is up — the only signal that distinguishes "stamped, viewer running" from "stamped, agent still running" |
| `@aitask_agent_session=<sid>` | SessionStart hook on `$TMUX_PANE` | pane death | freeze engine fallback when the store has no session id | codeagent session id |

**Pane user options survive `respawn-pane`** (they are pane-scoped, not
process-scoped), which is why `@aitask_standin_ready` must be explicitly unset
before each respawn and why `@aitask_record` stays valid across freeze/restore
on the same pane. `#{pane_current_command}` is a process basename and is
**never** used as identity; `#{pane_pid}` (stored as `pane_pid`) and the
options above are the only server-observable identities reconcile reads.

Constants live in `monitor/monitor_core.py` beside `SHADOW_TARGET_OPTION`
(`RECORD_OPTION`, `FROZEN_OPTION`, `STANDIN_READY_OPTION`,
`AGENT_SESSION_OPTION`) and are mirrored in `lib/agent_sessions.sh` for shell
callers.

#### C. Freeze — `lib/agent_freeze.py` + `aitask_frozen.sh freeze <pane>|--all`

Runs **out of the agent pane** (from a TUI, a shell, or `run-shell -b`).
Every step is persisted before the next irreversible one:

1. Resolve the record: `@aitask_record` → `show`; else `upsert` (fallback).
   Read `codeagent_session_id`; if empty, try `@aitask_agent_session`.
2. `capture-pane -p -e -J -t <pane> -S -<cap>` via `TmuxClient.run` →
   `capture.ansi`; strip via `monitor/ansi_utils` → `capture.txt`.
3. `freeze-begin` → state `freezing`, capture paths persisted, **lease
   minted** (`op_nonce`, `op_owner_pid`=this coordinator).
4. `set-option -p -t <pane> @aitask_frozen <id>`; `set-option -pu -t <pane>
   @aitask_standin_ready` (clear any stale ready mark from a previous cycle).
5. `respawn-pane -k -t <pane> '<standin_command(id)>'` via the gateway.
   Window name unchanged, so `classify_pane` / `task_id_from_window_name`
   keep working. The viewer stamps `@aitask_standin_ready=<id>` on mount.
6. `freeze-commit --nonce <n> --pane <pane> --pane-pid <stand-in pid>` →
   state `frozen`, `standin_pid` + location recorded (read via
   `display-message -p -t <pane> '#{pane_id}\t#{pane_pid}'` after the
   respawn), lease cleared.

Failure at 1–3 → nothing to undo beyond temp files (`FREEZE_FAILED:<stage>`).
Failure at 4 → `freeze-abort --nonce`. Failure at 5 (tmux refused) → unstamp +
`freeze-abort --nonce`; the agent is still running. Failure at 6 (store busy)
→ the record stays `freezing`; **reconcile** completes it once the lease is
stale. A `NONCE_MISMATCH` at 6 means reconcile already resolved the record;
the coordinator reports it and exits without touching the pane.

**`aitask_frozen.sh reconcile`** (idempotent; run by the coordinator after
every freeze/restore, by the monitor maintenance tick beside
`_maybe_purge_marks`, and manually) resolves every non-`live` record **whose
lease is stale** (`op_started_at` + `stale_op_grace` elapsed **and**
`op_owner_pid` dead/unverifiable — otherwise the record is skipped as
in-flight) from server-observable facts only
(`list-panes -F '#{pane_id}\t#{pane_pid}\t#{pane_dead}\t#{@aitask_frozen}\t#{@aitask_standin_ready}\t#{@aitask_record}'`;
"agent alive" = `pane_pid == record.pane_pid`; "viewer here" =
`pane_pid == record.standin_pid`; "replacement here" =
`pane_pid == record.launch_pid`; "stand-in up" = `@aitask_standin_ready == id`;
"mismatch" = `last_error` begins with the current `op_nonce`):

| record state | pane observation | action |
|---|---|---|
| `freezing` | `@aitask_frozen==id` **and** stand-in up | `freeze-commit --pane <pane> --pane-pid <observed pid>` |
| `freezing` | agent alive, stand-in not up | unstamp both options, `freeze-abort` (captures deleted) |
| `freezing` | `@aitask_frozen==id`, stand-in not up, neither agent nor viewer pid, pane not dead | **indeterminate — no transition** (viewer may still be booting); re-checked next pass |
| `freezing` | `@aitask_frozen==id`, pane dead | respawn the stand-in (clear ready first), `standin-respawned`, then re-check |
| `freezing` | pane gone | `freeze-commit --pane "" --pane-pid 0` |
| `frozen` | pane gone | keep (restorable into a new window) |
| `frozen` | `@aitask_frozen==id`, pane dead | `lease-take`, respawn the stand-in, `standin-respawned --nonce` |
| `restoring` | mismatch recorded for this nonce | `restore-abort` (→ `aborting`), kill the wrong agent via `respawn-pane -k` back to the stand-in, `standin-respawned --nonce` (→ `frozen`) — **never** liveness-confirm |
| `restoring` | viewer here (`pane_pid==standin_pid`) — the coordinator died before or during the respawn, whether or not the ready mark survived | `restore-abort`; respawn the stand-in so it re-stamps ready; `standin-respawned --nonce` |
| `restoring` | `launch_pid==0` and pane pid is neither the viewer's nor the agent's | **indeterminate — no transition** (respawn may be mid-flight); after `stale_op_grace` ×2 → `restore-abort` + respawn stand-in + `standin-respawned --nonce` |
| `restoring` | replacement here (`pane_pid==launch_pid`), pane not dead, no mismatch, `state_at` + `restore_ack_grace` (default 20 s) elapsed | `restore-confirm --pane --pane-pid` (`ack=liveness`, captures kept) |
| `restoring` | pane dead | `restore-abort`, clear ready, respawn the stand-in, `standin-respawned --nonce` |
| `restoring` | pane gone | `restore-abort` with `pane_id=""`, then `standin-respawned --nonce --pane "" --pane-pid 0` (→ `frozen`, restorable into a new window) |
| `aborting` (stale lease taken over) | stand-in up (`@aitask_standin_ready==id`) | `standin-respawned --nonce` (→ `frozen`) |
| `aborting` (stale lease taken over) | anything else | clear ready, respawn the stand-in, `standin-respawned --nonce` (→ `frozen`) |

Every reconcile action on a leased record is preceded by `lease-take`; a
`LEASE_HELD` answer means a live coordinator owns it and reconcile skips.

A liveness confirm therefore requires **positive evidence** that the
process in the pane is the one the coordinator launched (`launch_pid`), and
a viewer whose ready mark was cleared is still recognised by `standin_pid`.

Failure injection: `AITASKS_FREEZE_FAIL_AT=capture|begin|stamp|respawn|commit`,
`AITASKS_RESTORE_FAIL_AT=begin|respawn|ack`, and `AITASKS_FROZEN_PAUSE_AT=<stage>`
(the coordinator `SIGSTOP`s itself so a test can run a concurrent
`reconcile` and then `SIGCONT`) — documented test seams, honoured only under
`AITASKS_TEST_MODE=1`.

**Cleanup contract** (`aitask_companion_cleanup.sh` + `count_other_real_agents`
must agree — pinned by the parity test):
- a `@aitask_frozen`-stamped pane **counts as a real agent sibling** (the
  window exists to hold it; killing agent B must not destroy frozen A's viewer);
- when the *dying* pane is the stamped one, the cleanup script **abstains
  entirely** (it is being respawned, not departing);
- `kill_agent_pane_smart` on a frozen pane = `drop` + kill by the same rule.

#### D. Restore — `lib/agent_restore.py` + `aitask_frozen.sh restore <id> [--repick] | --all`

**Never runs inside the pane it replaces.** The viewer's `R`/`p` keys and the
minimonitor keys invoke `run-shell -b "<repo>/.aitask-scripts/aitask_frozen.sh restore <id>"`
through the gateway; the coordinator is a detached process that outlives the
respawn. Two-phase, acknowledged:

1. Build the argv: `aitask_codeagent.sh --agent-string <s> --resume-session <sid> --dry-run invoke raw`
   (resume) or the existing pick launch argv (`--repick`, task id required).
   Empty session id and no `--repick` → `RESTORE_FAILED:no_session` (nothing changes).
2. `restore-begin --mode <m>` → state `restoring`, lease minted (nonce `n`);
   captures and `@aitask_frozen` retained.
3. Prefix the argv with the **restore identity environment** (the
   `explore-relay` `env` precedent — `env` execs into the agent, so the pane
   pid is still the agent's):
   `env AITASK_RESTORE_RECORD=<id> AITASK_RESTORE_NONCE=<n> AITASK_RESTORE_MODE=<m> AITASK_RESTORE_EXPECT_SESSION=<sid> <argv>`.
   Then `set-option -pu @aitask_standin_ready` and
   `respawn-pane -k -t <stand-in> '<env argv>'` — or, when `pane_id=""`,
   `launch_in_tmux` into a new window with the recorded name. Immediately
   after tmux returns, read the new `#{pane_pid}` and write
   `restore-launched --nonce --pane --pane-pid` — the nonce-bound evidence
   that a replacement was actually started. The replacement agent's
   SessionStart hook forwards the four variables as `upsert --restore-of
   --nonce --session-id` (§A ack rules), which is what selects the **old**
   record from a brand-new pane, verifies the resumed session id, and stamps
   `@aitask_record` there.
4. Wait for the ack: poll `show <id>` until `state=live`, `last_error`
   carries this nonce, **or** `restore_ack_grace` elapses.
   - `live` with `ack=hook` → clear `@aitask_frozen`, print `RESTORED:<id>|hook`
     (captures already deleted by the ack).
   - `last_error="<nonce>:session_mismatch"` (the hook reported a different
     session in `resume` mode; persisted by the store because the hook has
     no channel to this process) → `restore-abort --nonce` (→ `aborting`,
     still owned by this nonce), `set-option -pu @aitask_standin_ready`,
     `respawn-pane -k` back to the stand-in, then `standin-respawned --nonce
     --pane --pane-pid` (→ `frozen`), print `RESTORE_FAILED:<id>|session_mismatch`;
     **capture intact**. The same abort → respawn → `standin-respawned --nonce`
     sequence is used by every failure branch below; a `NONCE_MISMATCH` at
     any step means reconcile already finished the abort.
   - grace elapsed, pane alive, `pane_pid == launch_pid`, no hook ack and no
     error → `restore-confirm --nonce --pane --pane-pid` → `live` with
     `ack=liveness`, **captures kept**, clear the stamp, print
     `RESTORED:<id>|liveness` (the viewer/minimonitor show "restored,
     unverified — capture kept").
   - pane dead at any poll (invalid session, binary missing, immediate exit)
     → `restore-abort --nonce`, clear ready, respawn the stand-in,
     `standin-respawned --nonce`, print `RESTORE_FAILED:<id>|agent_exited` —
     **the capture is intact and the viewer is back**.
   - `NONCE_MISMATCH` on any verb → reconcile already settled it; exit
     without touching the pane.
5. Coordinator crash between 2 and 4 → `reconcile` (§C table) settles it
   once the lease is stale.

`aitask_codeagent.sh` gains a global `--resume-session <sid>` (template
`OPT_HEADLESS`): `claude --model <id> --resume <sid>`, `codex resume <sid>`
(model flag per codex CLI), opencode → `RESUME_UNSUPPORTED:opencode` exit 2.
Resolution stays single-sourced in `lib/agent_string.sh`. Restore-All iterates
`frozen` records; per-record failures are reported, never abort the batch.

