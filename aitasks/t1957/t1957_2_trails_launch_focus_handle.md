---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Implementing
labels: [trails, tmux, cross_repo]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1957
created_at: 2026-10-12 21:31
updated_at: 2026-10-13 11:22
---

## Context

Part of t1957 (parent plan:
`aiplans/p1957_trail_cross_repo_blockers_and_linked_trails.md`). The jump to a
linked trail in another repo (t1957_4) needs to open a given trail in that
repo's `ait trails`, both on a cold launch and in an instance that is already
running.

Today `trails_app.py main()` accepts only `--tasks-dir`;
`.aitask-scripts/aitask_trails.sh` forwards `"$@"` to it. `on_mount` always
opens the trail selector. `_activate_trail(handle)` (`board_trail_screen.py`
~1061) is the single activation point, but with no matching `_trail_infos`
entry it builds a `doc=None` session that never fetches ("Loading trail…"), so
a handle must be resolved through discovery first.

**Pane-addressed mailbox (plan-review decision):** a session-wide tmux env var
(the codebrowser `AITASK_CODEBROWSER_FOCUS` pattern) must NOT be used — every
`TrailsApp` in a session would poll and clear it, and `owned_lookup_session`
proves project ownership, not recipient ownership. Requests go to exactly one
pane via tmux pane user options, are id-tagged, and are **never cleared** by the
reader (a read followed by an unset would erase a request written in between).

## Key Files to Modify

- `.aitask-scripts/board/trails_app.py` — `--trail`, `initial_trail`,
  receiver registration, poll worker.
- `.aitask-scripts/board/board_trail_screen.py` — `_open_trail_by_handle(handle, rescan)`.
- `.aitask-scripts/lib/agent_launch_utils.py` — `launch_or_focus_trails(session, project_root, handle)`.
- `tests/test_trails_app.py` (+ a gateway-stub test module for the writer if cleaner).

## Reference Files for Patterns

- `launch_or_focus_codebrowser` (`agent_launch_utils.py` ~2523) — writer shape.
- codebrowser `--focus` + poll (`codebrowser/codebrowser_app.py` ~561-584,
  ~659-721) — cold flag + `set_interval` poll.
- t1952 (commit 9605ad7d4): tmux lookups off the event loop.
- Pane options: `set-option -p` uses at `agent_launch_utils.py:2202`,
  `monitor/monitor_core.py:3881` (shadow stamps).
- `artifact_manifest.HANDLE_RE` (`lib/artifact_manifest.py:58`).
- `aidocs/framework/tmux_gateway.md` — all tmux via `_TMUX` (`lib/tmux_exec.py`);
  `tests/test_no_raw_tmux.sh` enforces it. `aidocs/framework/tui_conventions.md`.

## Implementation Plan

1. `main()`: `--trail <handle>` validated with `HANDLE_RE` (invalid →
   `parser.error`); `TrailsApp(initial_trail=...)`.
2. `on_mount`: with `initial_trail`, run discovery and then activate the handle
   if found; otherwise notify "Trail <h> not found in this project" and open the
   selector from cache. Shared mixin helper `_open_trail_by_handle(handle,
   rescan)`: known → `_activate_trail`; unknown → rescan once, then activate or
   notify.
3. Mailbox (only when `$TMUX_PANE` is set):
   - Request format: `@aitask_trails_focus` = `<uuid4 hex> <handle>`. Writers
     only overwrite; **nobody unsets it**. Latest request wins.
   - Registration (thread worker, gateway): read own pane's
     `@aitask_trails_focus` → record its id as baseline `_seen_request_id`,
     THEN stamp own pane `@aitask_trails_app <os.getpid()>`. `on_unmount` unsets
     the stamp only (best effort).
   - Consumption: started only from the registration worker's completion (never
     before the baseline exists). 1s `set_interval` → thread worker (exclusive
     group `trails_focus`) running
     `show-options -p -v -t <own pane> @aitask_trails_focus`; new id → record it,
     post `_open_trail_by_handle(handle)` to the UI thread; same id → nothing;
     malformed / bad `HANDLE_RE` → record id, ignore. Read-only; never reads
     another pane's option.
   - The board does not register or poll.
4. Writer `launch_or_focus_trails(session, project_root, handle) -> (ok, err)`:
   `list-panes -s -t =<session>: -F '#{pane_id} #{window_id} #{@aitask_trails_app}'`;
   receivers = stamped panes whose pid is alive (`os.kill(pid, 0)`); choose ONE
   deterministically (first in window/pane order); `set-option -p -t <pane>
   @aitask_trails_focus "<uuid4hex> <handle>"`; `select-window` + `select-pane`.
   No receiver → `new-window -t =<session>: -c <root> -n trails ./ait trails
   --trail <handle>` in argv form (no shell string). Does not switch-client.
5. Tests: argparse validation; cold `--trail` activates (fixture project,
   Pilot); unknown handle → selector + notice; baseline read before stamp and
   no replay of a pre-existing request; consume → activate, option left in
   place, same id not re-applied; interleaving: read A → B written → B applied;
   A and B both written between polls → only B; malformed value ignored and not
   retried; two `TrailsApp`s with distinct stubbed `$TMUX_PANE` and a fake
   per-pane option store → only the targeted one applies; dead-pid stamp not
   chosen; writer argv for one/two receivers and no-receiver.

## Verification

- `python3 -m pytest tests/test_trails_app.py -q` (+ new test module);
  `bash tests/test_no_raw_tmux.sh`.
- Manual (manual-verification sibling): two `ait trails` windows in one session
  plus a cross-session request → only the chosen one switches trail.
