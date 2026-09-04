---
Task: t1705_frozen_codeagents_session_store_and_viewer_tui.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1705 — Frozen code agents: session store + `ait frozenagent` viewer

## Context

`ait monitor` / `ait minimonitor` list every code-agent window across every
aitasks tmux session on the machine. Today an agent has two lifecycle states:

- **live** — process running, captured and classified every tick;
- **parked** (t1685) — a *mark kind* in `lib/agent_marks.py` (schema v2,
  `~/.config/aitasks/agent_marks.json`) that drops the agent out of the live
  partition, stops capture/classification, and gets its own `Np` session-bar
  term. **The process stays alive.**

With 10–20 parallel agents most finished sessions are kept only for their
*content* — the task-workflow summary, the spawned-task list, an analysis, the
next sibling's task number. Parking keeps that reachable but pays full process
cost for it.

This task adds a third state, **frozen**: the process is gone, the terminal
output is persisted, and a new viewer TUI takes over the agent's own pane in
the agent's own tmux window (viewer left, companion minimonitor right — the
live-agent layout, unchanged). Minimonitor lists a frozen agent as an
agent-like row (no live state dot, no capture), mirroring the parked row. From
the viewer or minimonitor the user can **restore** the agent (`claude --resume
<id>` / `codex resume <id>`) or, when the record carries a task id, **re-pick**
(`/aitask-pick <id>`). Freezing needs a durable machine-wide record, so the task
also introduces the **framework session** concept: every agent across every
aitasks tmux session / project on this machine, persisted under
`~/.config/aitasks/` beside `agent_marks.json` / `projects.yaml`.

**The task file mandates decomposition at planning time.** This plan fixes the
architecture and pins the cross-child contracts; the code lands in ten child
tasks (eight implementation/test, two documentation), each with its own
self-contained plan. The parent writes no code.

## Decisions taken with the user (2026-09-04) — PINNED, do not re-decide

| Decision | Value |
|---|---|
| Viewer TUI name | **`ait frozenagent`** — package `.aitask-scripts/frozenagent/`, launcher `aitask_frozenagent.sh`, scope `frozenagent`, switcher key `f` (free in `_TUI_SHORTCUTS`) |
| `frozen` vs the mark store | **Coexist.** `frozen` is *not* a mark kind. It lives in the new session store; a priority/parked mark survives a freeze/restore cycle. Row render composes both: `<mark glyph><F> <name>  frozen`. Precedence: `frozen` wins for *behaviour* (no capture, no state partition, `F` filter, restore keys); the mark glyph is display-only on a frozen row |
| Identity vs t1389 | **Do not gate on t1389.** Reuse today's `classify_pane()` prefix match and `task_id_from_window_name()`; stamp only what this task needs (`@aitask_record`, `@aitask_frozen`). Leave a bidirectional note: t1389 sweeps the session-store readers when it lands |
| Capture / retention | Full scrollback (`capture-pane -p -e -J -S -`) with a config cap (`frozen_capture_max_lines`, default 50000) as a runaway guard. **A confirmed restore automatically deletes the capture files** (record transitions back to `live`). Otherwise captures persist until the user drops the record (`k` on a frozen row / viewer `k`). No age-based expiry. *(Assumption: the user's answer added the restore-deletes rule without picking a cap option; the recommended cap is applied and can be changed in child 2.)* |
| Risk mitigations | All five applied; the spawned one is child 1 (see `## Risk`) |

## Survey findings that shape the split

- **`parked` is entirely App-side + a store**, not a tmux option: `MarksView` →
  `_parked_agent_pairs()` → `TmuxMonitor.set_parked_agents()` (publish-down
  before capture) → `commit_snapshots` builds `_parked_snapshot`. Every
  partition site excludes it (`monitor_app.py` ×9, `minimonitor_app.py` ×5).
  Frozen follows the same *shape*, but its source of truth is the pane option
  read in `_LIST_PANES_FORMAT` (like `@aitask_shadow_target`), not a marks pair.
- **`respawn-pane` has zero call sites in `.aitask-scripts/`.** Agents launch
  with `remain-on-exit on` and a pane-scoped `pane-died[N]` hook running
  `aitask_companion_cleanup.sh`, which kills the companion and the primary
  when no other real agent remains. `.claude/hooks/guard_live_tmux.py` denies a
  bare `tmux respawn-pane` from agent shells — every test and probe goes
  through `tests/lib/tmux_isolation.sh`.
- **No `SessionStart` hook precedent.** `.claude/settings.json` (PreToolUse
  guard) is dev-repo-only: not seeded, not in the release tarball, not in either
  framework-path list (`install.sh:1006-1019`, `aitask_setup.sh:3387-3404`).
  `merge_claude_settings()` merges `permissions.allow` only. Codex has no
  `[hooks]` block anywhere; `merge_codex_settings()` re-serializes TOML with a
  hand-rolled `toml_serialize` (`aitask_setup.sh:2601-2655`) that drops
  comments and must be verified against the hook shape.
- **`aitask_codeagent.sh:611` exports `AITASK_AGENT_STRING`** before `exec`,
  so a SessionStart hook inherits the agent string. There is no `--resume`
  seam; the template for a new global flag is `OPT_HEADLESS` (`:36`,
  `:688-691`, consumed at `:483/:496`).
- **Shared `list-panes` format arity is pinned** (`test_monitor_companion_filter.py:106`
  = 11 fields; `test_multi_agent_window_substrate.sh:386`). New fields must be
  **appended**, never inserted, in `monitor_core.py:2124`, `:3239`,
  `aitask_companion_cleanup.sh:47,:79`, `agent_launch_utils.py:1725`.
- **Store template**: `lib/agent_marks.py` + `aitask_agent_marks.sh` —
  `realpath` both sides, `mkstemp`+`fchmod`+`os.replace`, `load()` raises /
  `load_safe()` never, shell wrapper is the sole writer under
  `registry_lock.sh` (exit 0/2/3 `LOCK_BUSY`/4 `ERROR`, `list` takes no lock),
  `MarksView` mtime+size+**inode** gated, purge dispatched never awaited with a
  60 s startup grace (`monitor_shared.py:361-384`, `_dispatch_refresh_maintenance`).
  `~/.config/aitasks/review_loop_events/` is the blob-dir precedent.
- **Viewer building blocks**: `logview/logview_app.py` (RichLog +
  `Text.from_ansi`, `r` raw toggle, `/`,`n`,`esc` substring search, the t1486
  startup-focus trap), `codebrowser/code_viewer.py` (shift+up/down range
  selection, `get_selected_range()`), `lib/tui_clipboard.copy_to_system_clipboard`
  (seam enforced by `tests/test_tui_clipboard_seam.sh`), `lib/section_viewer.py`
  (Textual `Markdown`). Textual 8.2.7 has `ALLOW_SELECT`/`get_selection` —
  unused in the repo so far.
- **TUI registration** = `tui_registry.py` row + `tui_switcher.py`
  (`_TUI_SHORTCUTS`, `_QUICK_JUMP_BINDINGS`, `action_shortcut_<name>`) +
  `shortcut_scopes.py:KNOWN_BINDING_SOURCES` + `tests/test_shortcuts_registry_coverage.sh`
  `TUIS` + `tests/test_no_lib_to_tui_import.sh` `TUI_PACKAGES` + `ait`
  dispatcher (usage block + case) + website page. `diffviewer` is the minimal
  analogue; `codebrowser_app.py` the full one (`TuiSwitcherMixin, ShortcutsMixin`).
- **`aitask_create.sh --parent` auto-adds `depends` on the previous sibling**
  (`--no-sibling-dep` / explicit `--depends` available) — child order below is
  therefore the dependency order.
- **In-flight overlap**: t1699 (Implementing) reworks the
  `tests/test_kill_agent_pane_smart.sh` live fixture ordering; child 4 touches
  the same `list-panes` format and sibling count and must rebase on it.
  t1389 (Ready) is the identity-stamping successor — coordination note only.

## Architecture — PINNED contracts (copied verbatim into every child plan)

### A. Session store — `lib/agent_sessions.py` + `aitask_agent_sessions.sh`

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

### B. Pane options (tmux user options, pane-scoped)

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

### C. Freeze — `lib/agent_freeze.py` + `aitask_frozen.sh freeze <pane>|--all`

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

### D. Restore — `lib/agent_restore.py` + `aitask_frozen.sh restore <id> [--repick] | --all`

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

## Decomposition (children, in dependency order = creation order)

Children are siblings in scope (planning_conventions: no "deferred follow-ups").
The **riskiest assumptions are proven in child 1 before any contract-consuming
code exists**. Restore lands **before** the viewer: the viewer only shells out
to `aitask_frozen.sh restore` (a CLI seam, no import), and the restore
rollback's stand-in respawn is tested through `AITASKS_FROZEN_STANDIN_CMD`
until the real viewer exists.

| # | Child | Type / effort | Delivers | Tmux-stress |
|---|---|---|---|---|
| 1 | `spike_freeze_standin_and_session_id_capture` | test / medium | On an isolated tmux server: stamp + cleanup abstention + `respawn-pane -k` keeps window and companion alive, and **whether `pane-died` fires on `respawn-pane -k`** (decides the abstention shape); real SessionStart payloads for claude **and** codex captured to `tests/data/session_hooks/`; `claude --resume` and `codex resume` relaunch in a respawned pane; `run-shell -b` outlives a killed pane; **pane user options survive `respawn-pane -k`** and `#{pane_pid}` changes with it; an `env VAR=… <agent>` prefix leaves `#{pane_pid}` equal to the agent pid (the unwrapped-launch contract) and the hook sees the variables. Output: `tests/test_frozen_standin_spike.sh` (kept as a live probe) + a PINNED findings block appended to this plan and to children 2–5. If codex hooks or `codex resume` fail, the fallback (codex = re-pick only) is decided **here** | **yes** |
| 2 | `framework_session_store` | feature / medium | `lib/agent_sessions.py`, `aitask_agent_sessions.sh`, `SessionsView`, `standin_command`, schema + verbs + state machine + **lease/nonce rules + ack matching** (§A), purge policy, tests (`tests/test_agent_sessions.py`, `_identity.py` (every branch of the `(root, window)` conflict policy: tmux-restart relocation updates in place, **two dead-pane `live` candidates after a restart → new slot + `ambiguous_relocation`, neither stale record touched, both purged as `dead_pane` on the next enumeration**, second agent in the same window gets `window_slot=1`, a retained frozen record is created-beside and never attached to, a recycled `pane_id` attaches to nothing, **an unstamped caller never relocates a `freezing`/`restoring`/`aborting` record even when its pane is dead**, stray session in a transacting pane refused), `_transitions.py` (incl. `restore-begin` on `aborting` refused; `standin-respawned` with a stale nonce refused; **`freeze-commit` mounted-viewer form persists `pane_id`+`standin_pid` and the gone-pane form persists `""`/`0`, half-specified location is a usage error**), `_observation.py` (`PANE` rows parsed; a root with `WINDOW` but no `PANE` rows never yields `dead_pane`; `agent_marks._read_observed` skips `PANE` rows — round-trip with the marks purge on one shared file), `_lease.py` (stale-lease takeover via `lease-take`, `LEASE_HELD` with a live owner, nonce mismatch fails closed, session-mismatch persists `last_error` and leaves state unchanged, `restore-confirm` refused without matching `launch_pid`, repick adopts a new session), `_liveness.py`, `_concurrency.sh` mirroring the marks suites; every illegal transition pinned) | no |
| 3 | `session_id_capture_hooks` | feature / medium | `.aitask-scripts/aitask_session_hook.sh` (reads the hook JSON from stdin, no-op when `$TMUX_PANE` is empty, resolves root from `cwd`, window + `pane_pid` via `display-message`, forwards `AITASK_RESTORE_*` env as `--restore-of/--nonce`, calls `upsert` best-effort, stamps `@aitask_agent_session`); `seed/claude_settings.hooks.json`; `[hooks]` block in `seed/codex_config.seed.toml`; `install.sh` `install_seed_*` + call before `rm -rf seed`; `aitask_setup.sh`: `ensure_agent_config_seeds` pair, a **hooks-aware merge** beside `merge_claude_settings` (dedupe by `matcher`+`command`), `toml_serialize` verified for the codex shape, both framework-path lists, release tarball; fallback resolver (newest transcript for cwd). Tests: child-1 fixture payloads; **merge-safety fixtures for both formats** — pre-existing user hooks survive, `ait setup` ×3 leaves exactly one aitasks entry, comments-lost warning documented; fresh `install.sh --dir` smoke | no |
| 4 | `freeze_engine` | feature / high | `lib/agent_freeze.py`, `aitask_frozen.sh freeze|--all|reconcile`, `FROZEN_OPTION`/`RECORD_OPTION`/`STANDIN_READY_OPTION`/`#{pane_dead}` appended to every `list-panes` format + arity constants, `TmuxMonitor.last_discovered_panes()`, cleanup abstention + sibling rule in `aitask_companion_cleanup.sh` and `count_other_real_agents`, `maybe_spawn_minimonitor` occupancy, Freeze-All over `discover_aitasks_sessions()`, `reconcile` (§C table, lease-gated). Pre-phase `characterize_list_panes_arity`; post-phase `cleanup_rule_parity_test`; failure-injection tests at every §C boundary **plus the paused-coordinator race** (`AITASKS_FROZEN_PAUSE_AT=begin` → concurrent `reconcile` must skip the fresh lease; after `stale_op_grace` with the owner killed it must take over and the resumed coordinator must get `NONCE_MISMATCH`); the indeterminate row must be pinned as "no transition"; **rebase on t1699** | **yes** |
| 5 | `restore_and_repick_flows` | feature / high | `--resume-session` in `aitask_codeagent.sh`, `lib/agent_restore.py`, `aitask_frozen.sh restore|--all`, the acknowledged two-phase protocol with the restore identity environment and `restore-launched` evidence (§D), reconcile rows for `restoring` (incl. coordinator killed between clearing the ready mark and the respawn → viewer recognised by `standin_pid`, never liveness-confirmed), edge cases (`no_session`, binary missing, agent exits immediately, **session mismatch read from `last_error`** by both the coordinator and reconcile, **gone-pane restore into a new window selects the old record**, liveness-only confirm keeps captures and requires `launch_pid`). Live tests with a fake agent binary (honours `--resume <sid>` / `resume <sid>`, invokes the shipped hook with the env it inherited) and `AITASKS_FROZEN_STANDIN_CMD` | **yes** |
| 6 | `frozenagent_viewer_tui` | feature / high | `frozenagent/frozenagent_app.py` (`TuiSwitcherMixin, ShortcutsMixin`): stamps `@aitask_standin_ready=<id>` on its own pane after mount (and only then); `--record <id>` viewer — RichLog `Text.from_ansi`, `r` plain toggle, `m` markdown render of all/selected lines, `/`,`n`,`esc` search over `capture.txt`, shift+up/down range + native `ALLOW_SELECT`, `y` copy via `copy_to_system_clipboard`, header (project · window · task id/title · agent · frozen_at · lines · restore status), `R` restore / `p` re-pick / `k` drop via `run-shell -b aitask_frozen.sh …` (the viewer shows `restoring…` and is itself replaced on success, or refreshed with the failure reason on rollback); bare `ait frozenagent` = cross-project list of frozen records. Launcher, `ait` dispatcher, 4-part switcher change, `KNOWN_BINDING_SOURCES`, both test lists, startup-focus pin | no |
| 7 | `monitor_minimonitor_frozen_rows` | feature / high | `PaneSnapshot.frozen` + `frozen_record_id`, `_frozen_snapshot` beside `_parked_snapshot`, `TmuxMonitor.last_discovered_panes()` + `PANE` rows in `_write_observation_file(panes=…)` feeding a `_maybe_purge_sessions()` twin of `_maybe_purge_marks()`, exclusion at every partition site, `FROZEN_GLYPH="F"` + font-coverage manifest regen, rows `<mark><F> name  frozen` in both apps, `Nf` / `N frozen` terms, `F` filter (hint folded onto an existing line — 10-row budget), keys: freeze followed (`z`), freeze-all (`Z`), restore/re-pick on a frozen row, `k` = drop, `space` mark cycle stays enabled; `reconcile` dispatched from the maintenance tick. Tests mirror `test_monitor_parked_*.py` | partly |
| 8 | `frozen_agents_acceptance_test` | test / medium | `tests/test_frozen_agents_acceptance.sh`, isolated tmux, **through the shipped wrappers only**: install the hooks into a scratch project (`install.sh --dir`), launch via `aitask_codeagent.sh` with a fake `claude`/`codex` binary on `PATH` that emulates the SessionStart hook call and honours `--resume`/`resume <id>` (prints the id it received); assert hook binding (`upsert|created`, `@aitask_record`, `pane_pid`), freeze (record `frozen`, `@aitask_standin_ready` set by the real viewer, capture rendered in the pane, companion alive), **failed restore** (fake binary exits 1 → `restore-abort`, capture intact, stand-in back and ready again), **mismatched restore through the real detached path** (the coordinator is the actual `run-shell -b` process, the fake binary execs the shipped hook script with its inherited env, the hook reports a different session → the store persists `last_error`, the coordinator observes it via `show`, aborts, and the stand-in is back with the capture intact — the 20 s liveness fallback must **not** fire), **coordinator killed after clearing ready but before respawn** (viewer still running → reconcile aborts by `standin_pid`, never confirms), **abort handoff race** (coordinator `SIGSTOP`ped in `aborting` before its `standin-respawned`; a second `restore` is refused with `TRANSITION_REFUSED`; reconcile past the grace takes the lease and finishes; the resumed coordinator's `standin-respawned` gets `NONCE_MISMATCH` and touches no pane), **successful restore** (fake binary receives the captured session id and the `AITASK_RESTORE_*` env → `live`, `ack=hook`, captures deleted, stamp cleared), **gone-pane restore** (window killed → new window, old record acknowledged, no second record), reconcile after a `SIGKILL`ed coordinator past `stale_op_grace`, final `drop`. Real-agent behaviour is the MV sibling's job | **yes** |
| 9 | `frozenagent_tui_docs` | documentation / medium | **TUI-surface docs**: `website/content/docs/tuis/frozenagent/{_index,how-to,reference}.md` (viewer keys, list view, header fields, restore/re-pick/drop, "restored, unverified — capture kept"); `tuis/minimonitor/{_index,how-to}.md` (frozen row `<mark><F> name  frozen`, `Nf` term, `F` filter, `z`/`Z` freeze keys, restore/re-pick/`k` on a frozen row, coexistence with parked/priority marks); `tuis/monitor/reference.md` keybinding table + `N frozen` term; `tuis/_index.md` bullet + switcher paragraph; `commands/_index.md` (`ait frozenagent`); `aidocs/framework/tui_conventions.md` + `tmux_gateway.md` (respawn-pane, `run-shell -b`, the four `@aitask_*` options, stand-in self-stamp rule), `aitasks_extension_points.md` (hook install surface); `check_links.py --build` | no |
| 10 | `freeze_restore_workflow_docs` | documentation / medium | **Workflow + concept docs**: new `website/content/docs/workflows/freeze-and-restore-agents.md` — when to freeze vs park vs kill, the day-to-day loop (freeze finished agents from minimonitor, Freeze-All before shutdown, browse/search/copy a frozen transcript, restore vs re-pick decision, Restore-All after a tmux restart, what "unverified" means, dropping records), failure stories (restore fails → viewer is back; session mismatch; hooks not installed → re-pick only), and the manual `ait frozen reconcile`; entry in the **manual** list in `workflows/_index.md`; new `concepts/framework-session.md` (the store, record identity + slots, state machine, leases, hooks, reconcile, purge) and a link from `concepts/_index.md`; a "Session hooks" section in the setup/install docs (what `ait setup` writes into `.claude/settings.json` / `.codex/config.toml`, merge safety); `check_links.py --build` | no |

Then the workflow's own **manual-verification aggregate sibling** (child 11,
`manual_verification_frozen_codeagents`) covering children 4–7 with real
claude/codex agents.

**Sequencing note for the implementer:** children 1, 4, 5, 8 and the live parts
of 7 are tmux-stress tasks (`tui_conventions.md` §"Tmux-stress tasks") — pick
them from a shell **outside** the `-L ait` server. This planning session runs
inside it (`TMUX=/tmp/tmux-1000/ait,…`), which is why the parent stops after
creating the children. Between child 4 and child 6 landing, `aitask_frozen.sh
freeze` exists but its stand-in command does not; the verb is not user-facing
until child 7 wires the keys and child 9 documents it.

## Cross-task coordination notes (written at child creation)

- **t1389** (`stamped_agent_and_task_pane_identity`, Ready): add under
  `## Notes for sibling tasks` — "t1705 children read agent identity via
  `classify_pane()` prefix + `task_id_from_window_name()` and key
  `agent_sessions.json` on `(root, window, window_slot)` with the
  `@aitask_record` stamp as the pane join (pane id/pid are location data); when `@aitask_agent` / `@aitask_task_id`
  land, sweep `lib/agent_sessions.py`, `lib/agent_freeze.py`,
  `aitask_session_hook.sh` and the frozen discovery branch in
  `monitor_core.py`." Child 2's task file carries the reverse link.
- **t1699** (Implementing): child 4's task file records the dependency on its
  fixture ordering; no edit to t1699 (in-flight).

## Post-approval actions (this session, after ExitPlanMode)

### Pre-phase (risk mitigations)

1. `[pinned_block_in_every_child_plan]` Before writing any child plan, extract
   the **Architecture — PINNED contracts** section (§A–§D) into a single
   `## PINNED contracts (from p1705 — do not re-decide)` block and paste it
   verbatim into every `aiplans/p1705/p1705_<n>_*.md`. The parent verification
   `grep -l 'PINNED contracts' aiplans/p1705/*.md | wc -l` must equal the
   number of child plans before the plans are committed.

1. Create children 1–10 via the Batch Task Creation Procedure (`--parent 1705`,
   default sibling dependency = the order above), each with Context / Key
   files / Reference patterns / Implementation plan / Verification / PINNED
   contracts.
2. Revert parent to `Ready`, clear `assigned_to`, unlock.
3. Write `aiplans/p1705/p1705_<n>_*.md` for every child; commit together.
4. Offer the manual-verification sibling (children ≥ 2).
5. Write the t1389 sibling note (task file edit, `./ait git` commit).
6. Child checkpoint → expected "Stop here" (tmux-stress children need an
   outside-tmux shell).

## Verification (parent)

```bash
./.aitask-scripts/aitask_ls.sh -v --children 1705 99        # 10 children + MV sibling, chained deps
ls aiplans/p1705/                                             # one plan per child
grep -l 'PINNED contracts' aiplans/p1705/*.md | wc -l         # == number of child plans
./.aitask-scripts/aitask_query_files.sh has-children 1705     # HAS_CHILDREN:11
grep -n 't1705' aitasks/t1389_stamped_agent_and_task_pane_identity.md   # sibling note present
```
Feature-level proof is child 8 (automated, shipped wrappers, isolated tmux)
plus the MV sibling (real agents); per-child tests cover their own seams.

## Risk

### Code-health risk: medium
- The `list-panes` format gains fields in four places whose arity is pinned by three test files; an inserted (not appended) field silently shifts `history_size` · severity: medium · → mitigation: inline pre-phase characterize_list_panes_arity (in child 4's plan)
- The cleanup-script sibling rule is duplicated between `aitask_companion_cleanup.sh` and `count_other_real_agents`; a frozen-aware change to one without the other kills a live window · severity: high · → mitigation: inline post-phase cleanup_rule_parity_test (in child 4's plan)
- The SessionStart hook is a new install surface (seed → install.sh → setup merge → framework-path lists → tarball); a missed site fails only on fresh installs, and an unsafe merge can clobber or duplicate user hooks on every `ait setup` · severity: medium · → mitigation: inline post-phase fresh_install_hook_smoke (in child 3's plan, extended with preservation + repeated-setup fixtures)

### Goal-achievement risk: high
- `respawn-pane -k` on a `remain-on-exit` pane with a `pane-died` hook has no precedent here; whether the hook fires before or after the stamp is read decides if freezing kills the window · severity: high · → mitigation: spike_frozen_standin_respawn (child 1)
- Codex hooks (`[hooks]` in config.toml) and `codex resume <id>` are asserted from docs, not exercised; if either fails, restore for codex degrades to re-pick only · severity: medium · → mitigation: spike_frozen_standin_respawn (child 1)
- Ten children implemented in separate contexts can drift on the record schema / state machine / pane-option names unless every plan carries the same PINNED block; per-child tests can pass with incompatible joins · severity: medium · → mitigation: inline pre-phase pinned_block_in_every_child_plan + child 8 acceptance test
- The freeze/restore transactions span several locked verbs and a detached coordinator; a concurrent `reconcile`, a crash between stamp and respawn, a coordinator death after clearing the ready mark, a stray SessionStart in a restoring pane, or a hook outcome the coordinator cannot see could double-act or mis-acknowledge · severity: high · → mitigation: the lease/nonce contract, `@aitask_standin_ready` + `standin_pid` / `launch_pid` positive evidence, and the persisted `last_error` channel in §A–§D (pinned into children 2, 4, 5, 6) plus the paused-coordinator race test in child 4 and the mismatch / gone-pane / dead-coordinator cases in children 5 and 8
- Identity keyed on volatile pane ids would duplicate records after a tmux restart and let a retained frozen record block or capture a legitimate new launch · severity: high · → mitigation: the `(root, window, window_slot)` identity and conflict policy in §A, pinned by child 2's `test_agent_sessions_identity.py`

### Planned mitigations
- timing: before | name: spike_frozen_standin_respawn | type: test | priority: high | effort: medium | inline_risk: high | added_complexity: medium | addresses: respawn/pane-died ordering unproven; codex hooks + `codex resume` unexercised | desc: isolated-tmux spike proving stand-in respawn keeps window+companion, capturing real SessionStart payloads for claude and codex, and exercising `claude --resume` / `codex resume` — realised as child 1 of the decomposition (created at decomposition time, not by Step 7)
- timing: pre-phase | name: characterize_list_panes_arity | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: pinned list-panes arity | desc: characterization test pinning the 11-field arity and appended-vs-inserted semantics, run green before child 4 changes the format — lives in child 4's plan
- timing: post-phase | name: cleanup_rule_parity_test | type: test | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: duplicated sibling rule | desc: one pane-record table driven through `aitask_companion_cleanup.sh` (isolated tmux) and `count_other_real_agents`, asserting agreement for every frozen/live/helper combination — lives in child 4's plan
- timing: post-phase | name: fresh_install_hook_smoke | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: hook install surface invisible to unit tests; merge safety on upgrades | desc: `bash install.sh --dir <scratch>` + `ait setup`, assert the SessionStart entries in the installed `.claude/settings.json` and `.codex/config.toml`; plus fixtures with pre-existing user hooks in both formats that must survive, and `ait setup` run three times leaving exactly one aitasks entry — lives in child 3's plan
- timing: pre-phase | name: pinned_block_in_every_child_plan | type: chore | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: cross-child contract drift | desc: verbatim PINNED contract block in every child plan, grep-verified before commit — parent pre-phase above
