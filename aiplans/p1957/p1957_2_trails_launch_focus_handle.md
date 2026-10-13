---
Task: t1957_2_trails_launch_focus_handle.md
Parent Task: aitasks/t1957_trail_cross_repo_blockers_and_linked_trails.md
Sibling Tasks: aitasks/t1957/t1957_1_*.md, aitasks/t1957/t1957_3_*.md, aitasks/t1957/t1957_4_*.md, aitasks/t1957/t1957_5_*.md
Archived Sibling Plans: aiplans/archived/p1957/p1957_*_*.md
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5_5 @ 2026-10-13 11:46
---

# t1957_2 — `ait trails --trail <handle>` + running-instance focus mailbox

## Context

t1957_4 (jump to a linked trail in another repo) must open a specific trail in
that repo's `ait trails`, both cold and in an already-running instance. Today
`trails_app.main()` accepts only `--tasks-dir`, `on_mount` always opens the
selector, and `_activate_trail(handle)` with no `_trail_infos` entry builds a
`doc=None` session that never loads — so a handle must go through discovery.

Running-instance delivery uses a **pane-addressed mailbox** (decided in parent
plan review): a tmux *pane user option* on exactly one receiving pane,
id-tagged, overwritten by writers and **never cleared** by anyone. A
session-wide env var (codebrowser pattern) is rejected: every `TrailsApp` in a
session would poll and clear it.

Parent plan: `aiplans/p1957_trail_cross_repo_blockers_and_linked_trails.md`.

## Verification findings (plan vs. current code)

Plan assumptions hold (`_activate_trail` ~1096, `_open_trail_select` ~968,
`_on_trail_discovery` ~990, `launch_or_focus_codebrowser` ~2523,
`HANDLE_RE` at `lib/artifact_manifest.py:58`, `mark_monitor_pane` uses
`set-option -p` ~2202). Refinements:

1. **Test safety — pane injected, not read from env inside the App.** Tests
   construct `TrailsApp` directly and the suite often runs inside the
   developer's tmux, so an App reading `$TMUX_PANE` itself would stamp the
   developer's real pane. `TrailsApp(..., focus_pane=None)`; only `main()`
   reads `os.environ["TMUX_PANE"]`. Two-instance tests pass distinct panes.
2. **Ordering of poll reads.** `exclusive=True` does not stop a cancelled
   thread worker from delivering its result, so an older read could land after
   a newer one and re-apply an older id. Use a **busy flag** (the
   `_trail_watch_busy` idiom): a tick is skipped while a read is in flight, so
   reads are strictly sequential and the observed value only moves forward.
3. **Modal at delivery time.** A request may arrive while the selector (or
   another modal) is up. Selector up → dismiss it (`None` is a no-op for its
   callback) and apply; any other modal → hold as `_pending_trail_focus`
   (latest wins), notify once, drain on `TrailsScreen.on_screen_resume`.
4. **Baseline read failure fails closed.** If the baseline read errors (rc≠0),
   do not stamp and do not poll — we cannot prove no leftover request would be
   replayed. Unset option reads use `show-options -p -q -v` (empty, rc 0).
5. **Pid liveness** reuses `monitor_marker._process_exists` (PermissionError /
   unverifiable ⇒ alive); a non-integer stamp is not a receiver.
6. **Receiver server identity (review, blocking).** `_TMUX` talks to the
   gateway socket (`-L ait` by default), but `$TMUX_PANE` names a pane on
   whatever server `$TMUX` points at. Pane ids are per-server (`%0` exists on
   every server), so `ait trails` launched in the user's personal tmux could
   read/stamp an unrelated pane on the ait server and steal its requests.
   `current_tmux_session()` (`agent_launch_utils.py:474`) already solves this
   for its own probe: query `#{socket_path}` for the pane on the gateway and
   trust it only if it realpath-equals the socket `$TMUX` names. Factor that
   check into a shared helper and require it **before any mailbox read, stamp
   or unstamp**; unverified → no registration, no poll, no cleanup.
7. **Latest-request-wins across deferral (review, blocking).** Every accepted
   delivery (the cold `--trail` and each new mailbox id) draws a fresh
   `_focus_delivery_seq`. A deferred request is stored with its seq; the drain
   applies it only if its seq is still current, and accepting a newer request
   immediately clears `_pending_trail_focus`. A by-handle open that needs a
   rescan passes an `is_current` predicate bound to its seq into the discovery
   continuation, so a superseded request's scan result activates nothing.

## Implementation

### Pre-phase (risk mitigations)

1. [probe_pane_option_semantics] On an isolated tmux server
   (`tests/lib/tmux_isolation.sh` conventions / `AITASKS_TMUX_SOCKET`), confirm
   through the gateway: `show-options -p -q -v -t <pane> @unset` → rc 0, empty;
   after `set-option -p -t <pane> @x "id art:h"` → `id art:h\n`;
   `list-panes -s -F '#{pane_id} #{window_id} #{@x}'` shows the value per pane
   and empty for unstamped panes; `set-option -p -u` unsets. Encode the result
   as a small live test (`tests/test_trails_focus_mailbox_live.py`, skipped when
   tmux is absent) so the parsing contract is pinned against real tmux.

### Main steps

1. **`lib/agent_launch_utils.py`** — mailbox helpers + writer, all via `_TMUX`,
   next to `launch_or_focus_codebrowser`:
   - `TRAILS_FOCUS_OPTION = "@aitask_trails_focus"`,
     `TRAILS_RECEIVER_OPTION = "@aitask_trails_app"`.
   - `_gateway_pane_session(pane, tmux_env) -> str | None`: the body of
     `current_tmux_session()` lifted out (display-message `#{socket_path}\t
     #{session_name}` on `-t pane`, realpath-compare against `tmux_env`'s socket
     field); `current_tmux_session()` becomes `return
     _gateway_pane_session(os.environ TMUX_PANE, TMUX)` — behaviour unchanged.
     Public `pane_on_gateway_server(pane, tmux_env) -> bool` wraps it.
   - `read_trails_focus_request(pane) -> str | None`: `show-options -p -q -v
     -t <pane> TRAILS_FOCUS_OPTION`; rc≠0 → `None` (read failed), else stripped
     value (`""` = no request).
   - `parse_trails_focus_request(value) -> tuple[str, str | None] | None`:
     `""`/whitespace → `None`; else `(id, handle)` where id = first token and
     handle = remainder iff id matches `^[0-9a-f]{32}$` and handle matches
     `HANDLE_RE`, otherwise `(id, None)` (malformed — id still recorded).
   - `mark_trails_receiver(pane) -> bool` (`set-option -p -t pane
     TRAILS_RECEIVER_OPTION <os.getpid()>`), `unmark_trails_receiver(pane)`
     (`set-option -p -u ...`, best effort).
   - `launch_or_focus_trails(session, project_root, handle) -> (ok, err)`:
     refuse a handle failing `HANDLE_RE`; `list-panes -s -t
     tmux_session_scope_target(session) -F '#{pane_id} #{window_id}
     #{@aitask_trails_app}'`; receivers = rows whose stamp is an int pid with
     `_process_exists`; first receiver in emitted (window/pane) order →
     `set-option -p -t <pane> @aitask_trails_focus "<uuid4().hex> <handle>"`,
     `select-window -t <window_id>`, `select-pane -t <pane_id>`. No receiver →
     `new-window -t tmux_window_target(session, "") -c <root> -n trails ./ait
     trails --trail <handle>` (argv form). Each rc≠0 → `(False, "<verb>
     failed")`. No switch-client.

2. **`board/board_trail_screen.py`** (mixin):
   - `_open_trail_select(rescan=False, then=None)`; `_trail_discovery_worker(gen,
     overlay, then=None)` threads `then` to `_on_trail_discovery`, which calls
     `then()` instead of `_open_trail_select_from_cache()` after reconciling
     (torn-read and superseded paths unchanged). Cached path with `then` →
     `then()`.
   - `_open_trail_by_handle(handle, rescan=True, is_current=None)`: no-op under
     a modal or when `is_current` is given and returns False; open session
     (tabbed) or handle in `_trail_infos` → `_activate_trail(handle)`; unknown
     and `rescan` → `_open_trail_select(rescan=True, then=lambda:
     self._open_trail_by_handle(handle, rescan=False, is_current=is_current))`;
     unknown after rescan → `notify("Trail <h> not found in this project",
     warning)` + `_open_trail_select_from_cache()`. The board never passes
     `is_current`.

3. **`board/trails_app.py`**:
   - `__init__(..., initial_trail=None, focus_pane=None, focus_tmux_env="")`;
     state `_seen_focus_id`, `_focus_poll_busy`, `_focus_timer`,
     `_focus_stamped`, `_focus_delivery_seq`, `_pending_trail_focus`
     (`(seq, handle)` or None).
   - `on_mount`: `initial_trail` → `call_after_refresh(_deliver_trail_focus,
     initial_trail)`, else the selector as today; `focus_pane` → start the
     registration worker.
   - Registration `@work(thread=True, group="trails_focus")`: first
     `pane_on_gateway_server(pane, focus_tmux_env)` — False → stop (no read, no
     stamp, `_focus_stamped` stays False so unmount touches nothing); then
     `baseline = read_trails_focus_request(pane)`; `None` → stop (fail closed);
     else `mark_trails_receiver(pane)`; post `(baseline, stamped)` to the UI
     thread, which records `_seen_focus_id` from
     `parse_trails_focus_request(baseline)` and, only if stamped, sets
     `_focus_stamped` and starts `set_interval(1.0, _poll_trails_focus)`.
   - Poll: skip while busy; worker reads own (verified) pane only, posts value;
     UI callback clears busy, parses, ignores `None`/same id, records new id,
     malformed → one warning notify (value not echoed), valid →
     `_deliver_trail_focus(handle)`.
   - `_deliver_trail_focus(handle)`: `seq = ++_focus_delivery_seq`;
     `_pending_trail_focus = None`; then `_apply_trail_focus(seq, handle)`.
     `_apply_trail_focus(seq, handle)`: drop if `seq != _focus_delivery_seq`;
     selector on top → store `(seq, handle)` pending and dismiss it; other modal
     → store pending, notify once; else clear pending and
     `_open_trail_by_handle(handle, is_current=lambda: seq ==
     self._focus_delivery_seq)`. `_drain_trail_focus()` (queued by
     `TrailsScreen.on_screen_resume`) re-applies the pending pair only through
     `_apply_trail_focus`, so a superseded seq is dropped.
   - `on_unmount`: stop timer; only if `_focus_stamped`,
     `unmark_trails_receiver` (best effort).
   - `main()`: `--trail` validated with `HANDLE_RE` (`parser.error` otherwise);
     `TrailsApp(initial_trail=args.trail, focus_pane=os.environ.get("TMUX_PANE")
     or None, focus_tmux_env=os.environ.get("TMUX", ""))`. Update the
     module/`main` docstrings.

4. **`tests/lib/board_fixture.py`** — `make_trails_app(task_dir, **kwargs)`
   forwards `initial_trail` / `focus_pane`.

5. **Tests** (`tests/test_trails_app.py` + `tests/test_trails_focus_writer.py`):
   - argparse: invalid `--trail` → `SystemExit`; valid → App constructed with it
     (App `run` stubbed).
   - cold `--trail HANDLE` activates the trail (no selector); unknown handle →
     selector + "not found" notice.
   - mailbox with a fake per-pane option store patched over the trails_app
     imports: baseline read before stamp (call-order log) and pre-existing
     request not replayed; failed baseline read → no stamp, no poll; new request
     → activated, store untouched (never cleared), same id not re-applied;
     interleaving read A → B written → B applied; A and B both written between
     polls → only B; malformed / bad handle → ignored, not retried; two Apps with
     distinct panes → only the targeted one applies; request while selector open
     → selector dismissed, trail active; request under another modal → applied
     after it closes; unmount unstamps.
   - server identity: pane check False (same pane id answered by a server whose
     `socket_path` ≠ `$TMUX`'s socket) → no read, no stamp, no poll, no unstamp
     on unmount; matching server → registers. Helper unit tests over a stubbed
     `_TMUX`: matching socket (incl. a symlinked path) → True; different socket
     → False; empty `$TMUX` / rc≠0 → False; `current_tmux_session()` existing
     tests keep passing.
   - ordering: A deferred under a modal → modal popped → B delivered before the
     queued drain runs → settle → B active, A never activated; A needing a rescan
     (unknown handle, scan in flight) superseded by B → A's continuation
     activates nothing.
   - writer with stubbed `_TMUX` (argv log): one receiver, two receivers (first
     chosen), dead-pid and non-int stamps skipped, no receiver → `new-window`
     argv, invalid handle refused, rc failures → `(False, err)`.
   - Polling driven directly (call `_poll_trails_focus` and settle workers) —
     no reliance on the 1s timer; workers drained before block exit.

## Verification

- `~/.aitask/venv/bin/python -m pytest tests/test_trails_app.py
  tests/test_trails_focus_writer.py tests/test_trails_focus_mailbox_live.py
  tests/test_trail_screen_host_protocol.py tests/test_board_bytrail_view.py -q`
- `bash tests/test_no_raw_tmux.sh`; `bash tests/run_all_python_tests.sh` (last line verdict).
- Manual (aggregate manual-verification sibling): two `ait trails` windows in
  one session plus a cross-session request → only the chosen one switches.

## Step 9 reference

After review: Step 9 — commit on main, archive this child (parent archives with
its last child).

## Risk

### Code-health risk: low
- New cross-process contract (stamp + id-tagged never-cleared request option, baseline at registration, liveness check) whose tmux semantics (`-q` on unset user options, `#{@opt}` in list-panes formats) are assumed, not yet exercised against real tmux · severity: low · → mitigation: inline pre-phase probe_pane_option_semantics
- Pane ids are per-server; an ambient `$TMUX_PANE` from a non-gateway server would address an unrelated ait-server pane · severity: medium · → mitigation: none (addressed in-plan: finding 6 server-identity check before any mailbox mutation + tests)
- Deferred / rescan-pending deliveries could resurrect an older request after a newer one · severity: low · → mitigation: none (addressed in-plan: finding 7 delivery seq + ordering tests)
- `current_tmux_session()` is refactored onto the shared server-identity helper · severity: low · → mitigation: none (pure extraction; existing tests)
- Mixin `_open_trail_select` / discovery worker gain a `then` continuation shared with the board's `z` view · severity: low · → mitigation: none (default `None` keeps the board path identical; existing by-trail tests cover it)

### Goal-achievement risk: low
- Interaction with modals on delivery (selector dismissed, others deferred) is new UX not specified by the parent plan · severity: low · → mitigation: none (covered by tests; manual verification sibling)

### Planned mitigations
- timing: pre-phase | name: probe_pane_option_semantics | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — assumed tmux pane-option semantics | desc: live isolated-tmux test pinning show-options -q / list-panes #{@opt} / set-option -u behaviour the mailbox parses

## Final Implementation Notes

- **Actual work done:** All plan steps implemented as written.
  `agent_launch_utils.py`: `pane_on_gateway_server` (shared
  `_gateway_pane_session`, which `current_tmux_session` now delegates to),
  `read_trails_focus_request`, `parse_trails_focus_request`,
  `mark_trails_receiver` / `unmark_trails_receiver`, `_live_trails_receivers`,
  `launch_or_focus_trails`. `board_trail_screen.py`: `then` continuation on
  `_open_trail_select` / discovery worker / `_on_trail_discovery`, and
  `_open_trail_by_handle(handle, rescan, is_current)`. `trails_app.py`:
  `--trail`, `initial_trail` / `focus_pane` / `focus_tmux_env`, registration +
  busy-guarded poll workers, `_deliver_trail_focus` / `_apply_trail_focus` /
  `_drain_trail_focus` with the delivery seq, `on_unmount` unstamp.
- **Deviations from plan:** The pre-phase probe changed the read primitive.
  `show-options -p -q -v` and `display-message` BOTH answer a missing pane with
  rc 0 and empty output, so neither can distinguish "no request" from "read
  failed". The read is `display-message -p -t <pane> '#{pane_id}\t#{@opt}'`
  and is trusted only when the echoed pane id matches. The live test pins this,
  including the `show-options -q` control.
- **Issues encountered:** Two existing `test_board_bytrail_view.py` stubs
  replaced `_trail_discovery_worker` with a two-argument lambda; updated them to
  accept the new optional `then`.
- **Key decisions:** The App never reads `$TMUX_PANE` itself (only `main()`
  does), so a test App can never stamp the developer's real pane. The deferred
  request is superseded at four layers (delivery clears pending, direct apply
  clears pending, seq check, `is_current` in the mixin). Mutants confirmed the
  supersession, server-check, baseline-order, same-id and baseline tests each
  fail when their guard is removed; the deferred-request test passes even with
  three of the four layers removed, because the `is_current` layer alone holds.
- **Upstream defects identified:**
  - `.aitask-scripts/monitor/monitor_core.py:2246-2250 — get_pane_option uses show-options -pqv and treats rc 0 as a verified read, but tmux answers a MISSING pane with rc 0 and empty output under -q (measured on tmux 3.7c, pinned by tests/test_trails_focus_mailbox_live.py), so a vanished pane reads as (True, "") "verified unset" — the t1451 failure shape its docstring says the tuple exists to prevent`
- **Notes for sibling tasks:** t1957_4 calls
  `launch_or_focus_trails(session, root, handle)` → `(ok, err)` and then
  switches the client itself. Its version-skew check can test for
  `--trail` in the target's `board/trails_app.py`. A mailbox request delivered
  while a modal is open is held and applied when the modal closes (the trail
  selector is dismissed instead), and the user gets a notify.


## Post-Review Changes

### Change Request 1 (2026-10-13)
- **Requested by user:** (1) the live cold-launch test raced a failing `./ait` (window could vanish before the assertion); (2) receiver-stamp parsing used `str.isdigit()`, so `²` crashed `int()` and an oversized pid overflowed `os.kill`.
- **Changes made:** (1) the live test installs a controlled `ait` stub in the project root that records its argv and stays alive; the test waits (bounded) for the argv file, asserts `trails --trail <handle>`, then the window. Passed 3/3 runs. (2) stamps must fullmatch `[1-9][0-9]{0,9}` (ASCII) and be ≤ 2**31-1; new writer test covers `²`, `٣`, 20-digit, 2**31, `0`, `-5`, `+12`, each continuing to the next receiver and to the cold-launch path. Negative control: the new test fails with `ValueError` under the old parsing.
- **Files affected:** `.aitask-scripts/lib/agent_launch_utils.py`, `tests/test_trails_focus_writer.py`, `tests/test_trails_focus_mailbox_live.py`
