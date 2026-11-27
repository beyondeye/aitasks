---
Task: t2372_switch_to_pane_anywhere_half_move_and_implicit_client.md
Base branch: main
Output branch: main
---

# t2372 — `switch_to_pane_anywhere` half move + implicit client

## Context

`switch_to_pane_anywhere` (`.aitask-scripts/lib/agent_launch_utils.py:2116`)
takes two name lookups and then makes three separate calls: `switch-client`,
`select-window` and `select-pane`.

- **Half move.** If the pane dies or moves after the lookup while its session
  and window survive, the switch succeeds and the later select fails. The
  function returns False, but the client sits in the destination session on
  another pane. This is case 9dX in t2349.
- **Implicit client.** Without `client=`, tmux picks the client, so a gone
  initiator is replaced by whichever client tmux finds. This is case 5X in t2338.

`spawn_sitrep`'s focused branch (`monitor_core.py:6001`) and repair branch
(`:6116`) still use it. Only the cold path uses t2349's guarded
`switch_client_to_pane`.

### Measured in this session (private `-L` sockets, tmux 3.8 AND the real 3.3a)

| probe | 3.8 | 3.3a |
|---|---|---|
| `display-message -t <caller pane>` (today's `_sitrep_launch_client` read), the caller's session unviewed, a terminal elsewhere | names the other session's terminal | same |
| two terminals in one session, identical `TMUX`/`TMUX_PANE`/args | names the NEWER one; both have `client_session == session_name` | same |
| grouped session viewed, the original unviewed | an equality check passes for the grouped session's terminal | same |
| `list-clients` `#{pane_id}` | each client's CURRENT pane; clients of one session share the current window | same |
| `attach -r` (read-only) | `client_control_mode=0`, `#{client_readonly}=1`, its `pane_id` is the caller pane | same |
| selecting `new-window` in a viewed session | redirects every viewer (including one that attached after any earlier read); `-d` does not | same |
| companion split (`agent_launch_utils.py:2992`) | no `-d`, then an async `select-pane` refocus: it changes the active pane for every viewer | (code) |

What follows from these measurements:

- No current read identifies the initiator.
- Skipping the jump does not leave focus alone: the selecting creation and the
  companion refocus still move viewers.
- A restore does not leave focus alone either: re-selecting the "original"
  pane undoes a choice a viewer made during the repair.

**Trusted identity.** No caller has one today. No tmux binding expands
`#{client_name}`/`#{client_pid}` for sitrep: the callers are `sitrep_open.py`
from a shell, the switcher overlay, and the monitor/minimonitor `S` key, each
with only `TMUX_PANE`. This task therefore defines a pane-only **inference**,
and an explicit identity goes to the follow-up (§6).

**Decided with the user:** the monitor's own jump (`TmuxMonitor.switch_to_pane`,
`monitor_core.py:4590`, used by monitor, minimonitor and applink `focus`) gets
only the half-move fix here, because it calls the fixed primitive. Its client
source is a follow-up task.

### Focus contract

tmux keeps ONE current window per session, shared by every client viewing it,
and one active pane per window. A *client switch* (a client's session, window
or pane chosen by `spawn_sitrep`) is therefore different from a *shared-view
change* (the session's current window or a window's active pane changes, and
every viewer of it sees that).

- **Forbidden:**
  - switching any client other than the inferred initiator to another
    session (no implicit `switch-client`, ever);
  - changing any window's selection or active pane as a side effect of
    *creating* something: windows, splits and companions are all created with
    `-d`, with no `select-pane` refocus and no restore.
- **Expected shared-view changes.** These are inherent, are documented in
  `sitrep.md`, and are pinned by live cases:
  1. **The guarded jump.** `switch-client -c <initiator> -t $S:@W.%P` makes
     `@W` the current window of `$S` and `%P` its active pane. **Every client
     already viewing `$S` sees `@W` too.** For a cross-session jump, that
     means the destination session's existing viewers. Measured on 3.8 and
     3.3a by the review. Their session never changes. This holds the same way
     for a same-session jump: any client viewing that session at the moment
     of the jump sees it, including a writable one that attached after the
     inference.
  2. **The relocation** (`join-pane -d`, which moves the one TUI out of its
     occupied window into the new one). The source window loses a pane. A
     viewer whose active pane was the TUI falls back to another pane of the
     SAME window (tmux's choice). Its session and window are unchanged.
     Measured by the review.
- Nothing else changes anyone's view.

## Implementation

### 1. `lib/agent_launch_utils.py`

- Move `switch_to_pane_anywhere` below the `# --- the guarded client jump
  (t2349)` constants.
- Add a shared helper:
  ```python
  def _pane_switch_target(pane_id: str) -> str | None:
      """`$S:@W.%P` for ``pane_id`` from ONE id read, or None."""
      if not _JUMP_PANE_RE.fullmatch(pane_id or ""):
          return None
      rc, out = _TMUX.run(["display-message", "-p", "-t", pane_id, _JUMP_IDS_FORMAT])
      if rc != 0:
          return None
      sid, _, wid = (out.splitlines() or [""])[0].strip().partition("\t")
      if not (_JUMP_SESSION_RE.fullmatch(sid) and _JUMP_WINDOW_RE.fullmatch(wid)):
          return None
      return f"{sid}:{wid}.{pane_id}"
  ```
- `switch_to_pane_anywhere(pane_id, *, client=None) -> bool` keeps its
  signature, which Tier 1 pins. It does one `_pane_switch_target` read, then ONE
  `switch-client [-c <client>] -t <target>`, and returns `rc == 0` (False when
  there is no target).
  - Docstring: tmux refuses a dead or moved pane before anything moves.
    Without `client=` tmux still picks the client, so a caller that knows its
    initiator uses `switch_client_to_pane`.
- `switch_client_to_pane`: use `_pane_switch_target`. Keep the pane check
  (`failed`) and the client check (`skipped`) in their current order; a `None`
  target is `failed`. Fix the stale "three separate calls … unchanged"
  docstring sentence.
- `maybe_spawn_minimonitor(..., detached: bool = False)` threads through to
  `_companion_check_and_split`. Detached means `split-window -d` and NO
  `select-pane` refocus. The default is unchanged for the other 29 call sites.

### 2. `monitor/monitor_core.py`

- **Initiator inference.** Replace `_sitrep_launch_client` /
  `_SITREP_CLIENT_FORMAT` with
  `_sitrep_initiator(monitor, caller_pane) -> tuple[_SitrepClient | None, str]`.
  It makes one read, which does not depend on `-t` or on the client that
  routes the command, so a control-routed `monitor.tmux_run` is fine:
  `list-clients -F '#{client_name}\t#{client_pid}\t#{client_control_mode}\t#{client_readonly}\t#{client_session}\t#{pane_id}'`.
  - Without a well-formed `%N` caller pane → `(None, "no_pane")`.
  - Any malformed row (wrong field count, non-digit pid, control or readonly
    flag not `0`/`1`, empty name or session) → `(None, "unreadable")`. This
    fails closed, because the row could hide a second viewer.
  - Candidates are the rows with `control == "0"`, `readonly == "0"` and
    `pane_id == caller_pane`. Control and read-only clients can never type
    into the pane, so they are never the requester.
    - None → `(None, "no_client")`.
    - Two or more → `(None, "ambiguous")`; clients of one session share the
      current window, so they cannot be told apart.
    - Exactly one → `(_SitrepClient(name, pid, session), "")`.
  - The docstring calls this an **inference**, not an identity: the lone
    writable viewer of the caller pane is taken to be the requester.
  - Documented residuals, which cannot be closed without a trigger-time
    identity from tmux: between the key press and this read, (a) the
    initiator leaves the pane while a writable bystander who was already
    viewing it stays, or (b) the initiator leaves and one other writable
    client arrives. Input could also come from `send-keys`. In each case the
    lone remaining viewer is moved. That is still at most one client, and
    only one that is viewing the caller pane.
- **`spawn_sitrep`**: right after `find_sitrep_roles` succeeds (before any
  window or split exists), set
  `initiator, why = _sitrep_initiator(monitor, caller_pane) if select_window else (None, "")`.
  Remove the read from the cold branch.
  - **Focused** (`agent and tui`, `select_window`):
    - no initiator → `SitrepSpawn("focus_failed", agent, "", "focus_" + why, tui)`;
    - otherwise `switch_client_to_pane` → `moved` = `focused`, and every other
      result is `focus_failed` with detail `focus_failed` / `focus_skipped` /
      `focus_absent`.
    - The wire is unchanged (`SITREP_FOCUS_FAILED:<pane>`, exit 1).
  - **Cold**:
    - `_sitrep_launch_agent_window(..., select_window=False)`: always
      `new-window -d`. The `select_window` parameter is removed from that
      helper.
    - **Same-session initiator** (`initiator.session == session`): call
      `switch_client_to_pane(agent, …)` IMMEDIATELY after the agent window
      exists and is stamped, before the TUI split, the `join-pane` and the
      companion. This takes the place of the selecting `new-window`, keeps its
      timing (so a user who navigates during startup stays where they went),
      and adds the name+pid guard. A replacement who attached before creation
      is not moved.
    - **Cross-session initiator**: the jump stays after the companion (as
      today).
    - The companion is spawned with `detached=True`, and the TUI split is
      already detached. The agent therefore remains the new window's active
      pane.
  - **Repair** (`added_tui` / `respawned_agent`):
    - Role splits are already detached; the companion is spawned with
      `detached=True`.
    - With an initiator → `switch_client_to_pane(agent, …)` at the end.
    - Without one (`select_window` False, or no inference) → nothing.
  - **Remove the active-pane restore entirely.** That means the
    `original_active` read and restore, `_sitrep_active_pane`,
    `_sitrep_pane_window`, `_SITREP_PANE_ID_RE` if it becomes unused, and the
    `focus_not_restored` warning. A repair no longer moves focus itself, so a
    restore could only undo a viewer's own choice. All of these are used only
    by this sitrep code, checked with grep.
  - Warnings come from one map,
    `_SITREP_JUMP_WARNINGS = {"failed": "focus_failed", "skipped": "focus_skipped"}`,
    used by the same-session, cross-session and repair jumps. For
    `select_window` with no inference: `ambiguous` and `unreadable` warn
    `focus_skipped`; `no_client` and `no_pane` stay silent (the cold path's
    existing rule).
- Update the `spawn_sitrep` docstring (the focus contract: forbidden vs the
  two expected shared-view changes) and the cold-jump and relocation
  comments.

### 3. Other files

- `lib/tui_switcher.py:1763`: drop the stale "switch_to_pane_anywhere's
  precedent" clause.
- `aidocs/framework/sitrep.md` "The sitrep window" (the table, **Focus**,
  **Cold jump**) and `aitask_sitrep.sh` header line 29:
  - the focus contract, including the two expected shared-view changes,
    stated as distinct from switching a bystander's client;
  - the inference (lone writable viewer; control and read-only clients are
    excluded) and its residuals;
  - `focus_not_restored` removed;
  - the new `focus_failed` details.
- `sitrep_open.py` docstring: the wire lines are unchanged. Adjust the warning
  list only.

### 4. Unit tests

- **`tests/test_multi_session_primitives.sh` Tier 1b.** The fake answers `$3\t@7`.
  - Exactly 2 calls: `display-message -p -t %42 #{session_id}\t#{window_id}`,
    then `switch-client -t $3:@7.%42` (with `-c /dev/pts/7` in the `client=`
    case).
  - New cases: a malformed id read → False and no switch; a non-`%N` pane →
    False and zero calls; a failing switch → False. The tmux-missing case and
    Tier 1c are kept.
- **`tests/test_sitrep_window.py`**
  - FakeMon answers `list-clients` from
    `clients=[(name, pid, ctl, ro, session, pane)]`. The default is one
    writable terminal on the caller pane `%1`.
  - `_sitrep_initiator` table:
    - one writable viewer → picked;
    - two → `ambiguous`;
    - a sole read-only viewer → `no_client`;
    - a read-only plus a writable viewer → the writable one;
    - a control client on the pane → excluded;
    - a terminal on another pane → excluded;
    - a grouped-session viewer on the pane → picked;
    - one malformed row → `unreadable`;
    - no/invalid caller pane → no read.
  - Focused: each jump outcome and each no-inference reason → status and
    detail. `switch_to_pane_anywhere` is never called.
  - Cold:
    - `launch_window_pane` always gets `select_window=False`;
    - a same-session initiator's jump runs BEFORE the TUI split, the
      `join-pane` and the companion (order recorded);
    - a cross-session jump runs after the companion;
    - the companion always gets `detached=True`.
  - Repair: with an inference → jump plus the warnings table. Without one →
    no jump and **no `select-pane` at all**. This replaces the five restore
    tests (`test_no_select_restores_…`, `…_leaves_an_unmoved_…`,
    `test_a_failed_restore_warns`, `…_one_mover`, `…_not_selected_elsewhere`)
    with one test: "no select-pane on a no-focus repair, even when the active
    pane changes during it".
  - `CompanionFullHeightTests`: `detached=True` adds `-d` and issues no
    `select-pane`; the default argv is unchanged.
  - `OpenCliTests`: drop `focus_not_restored` where it appears; otherwise
    unchanged.

### 5. Live tests — `tests/test_sitrep_window_select_live.sh` (update the header list)

- A `place <tty> <pane>` helper: `switch-client -c <tty> -t $S:@W.%P`, then
  asserts that the client is on exactly that pane. **Every** case and EVERY
  control first places each terminal it asserts on and asserts that placement,
  so an earlier case cannot satisfy a later assertion. Existing same-session
  cases 3 and 4 put `$TTY` on exactly `$B_PANE` before the request, because
  after case 2 it sits on the agent pane in another window. Cases 1 and 2 put
  it on `$CALLER_PANE`.
- A `snapshot` helper:
  `list-clients -F '#{client_control_mode}|#{client_tty}|#{client_session}|#{window_id}|#{pane_id}'`
  for terminals only, sorted.
- **`jump.py`**
  - `pre_fix` mode: inline the verbatim pre-fix three-call switch (two name
    reads, then `switch-client` + `select-window` + `select-pane` through
    `alu._TMUX.run`). Case 9dX then keeps its control.
  - New `anywhere` mode: `switch_to_pane_anywhere(pane, client=name)`, with one
    read before the dispatch.
  - **9dA**: kill or break after the id read → `failed`, and the client is
    where it was.
  - **9e**: without a seam → `moved`, and the client is on the destination
    pane in E.
- **Case 7** (rewrite: the read is `list-clients` through a control client).
  - 7a: A's terminal is the one viewer of `$CALLER_PANE`, and it is accepted.
  - 7b: the control client's own row never counts; `$B_PANE` with nobody
    viewing B → `no_client`.
- **Case 10: unviewed caller** (new session `sel_f`, which nobody views, used
  as the caller via `CALLER_IN_F=1`). One terminal is placed in `sel_d` and
  one in `sel_b`, on the sitrep agent's window: the destination viewer.
  Snapshot before and after each subcase.
  - **10a** focused on `$ROOT` → `focus_failed`, snapshot unchanged.
  - **10b** repair WITH the companion created: kill `$ROOT`'s TUI AND its
    companion first, so the detached companion split really runs. A seam
    (`AIT_LIVE_SELECT_PANE=<pane>`, after the real companion spawn) makes the
    `sel_b` viewer select the agent window's other pane during the repair.
    Expect: `added_tui`; a companion pane now exists in the window; the viewer
    is still on the pane IT chose (no restore, no refocus); the `sel_d`
    terminal is unchanged.
  - **10c** cold for B → `spawned`, snapshot unchanged (the `-d` new-window).
  - **Controls**, each after re-placing the terminals and asserting it:
    - 10aX `AIT_LIVE_MUTANT_UNGUARDED_FOCUS=1` (the old focused code, an
      implicit `switch_to_pane_anywhere`) → some terminal ends on the agent
      pane;
    - 10bX `AIT_LIVE_MUTANT_RESTORE=1` (the old restore, re-implemented in the
      driver around the call: read the window's active pane before, and
      `select-pane` it back after if it changed) → the viewer's own choice is
      undone;
    - 10cX `AIT_LIVE_MUTANT_SELECTING_CREATE=1` (the old selecting
      `new-window`) → the `sel_b` viewer's window changes.
- **Case 11: no single writable viewer**
  - **11a** both terminals placed on `$CALLER_PANE` (A), focused → `focus_failed`;
    neither moves. 11b: the same with a cold spawn for B → `spawned` +
    `focus_skipped`; neither moves.
  - **11X** `AIT_LIVE_MUTANT_OLD_READ=1` (the pre-fix
    `display-message -t <caller pane>` read) → the newer terminal is moved to
    B.
  - **11c** a sole READ-ONLY terminal (`attach -r`) on `$CALLER_PANE`, focused
    → `focus_failed`; it does not move.
  - **11cX** `AIT_LIVE_MUTANT_ALLOW_READONLY=1` → it is moved.
- **Case 12: same-session disconnect-and-replace before creation.**
  - `$TTY` is placed on `$B_PANE` with `CALLER_IN_B=1`. A seam
    (`AIT_LIVE_REPLACE_BEFORE_CREATE=…`, which wraps
    `_sitrep_launch_agent_window` and runs `_replace` first) closes the
    initiator after the inference and attaches a replacement to `sel_b`.
  - Expect: `spawned`; the replacement's window and pane are unchanged (the
    `-d` creation, and the guarded jump refuses it as `absent`, or as
    `skipped` on 3.3a).
  - **12X** `AIT_LIVE_MUTANT_SELECTING_CREATE=1` → the replacement is
    redirected to the new window. Note whether the pty was reused, as cases
    6/8 do. The redirect does not depend on the name.
- **Case 13: the expected shared-view changes, pinned.**
  - **13a relocation with a viewer on the moved pane.**
    - Fixture: in `$ROOT_RELOC`'s sitrep window, split an unstamped occupant
      (`tail -f /dev/null`), kill the agent, and place a `sel_b` terminal on
      that window with the TUI as the active pane.
    - The caller is unviewed (`CALLER_IN_F=1`).
    - Expect: `spawned` + `tui_moved`. The viewer's session AND window id are
      unchanged, and its pane is now another pane of that same window (not the
      TUI, which is in the new window). The viewer is not on the new window,
      and the `sel_d` terminal is unchanged.
    - **13aX** `AIT_LIVE_MUTANT_SELECTING_CREATE=1` → the viewer's window
      changes to the new one, which shows the creation-side redirect that the
      fix removes.
  - **13b destination viewer + cross-session jump.**
    - `$TTY` is placed alone on `$CALLER_PANE` (A), and a second terminal is
      placed in `sel_b` on its base window. A cold spawn for B follows.
    - Expect: `$TTY` is moved to B on the agent pane. The `sel_b` viewer is
      still in `sel_b` and now sees the agent's window. That is the expected
      shared current window, asserted as such, and it is distinct from a
      session switch. The `sel_d` terminal is unchanged.
- Case 3 keeps its assertion, now through the early guarded jump. Case 4 does
  too (a session switch during startup is not pulled back). Cases 1, 2, 5, 6
  and 8 are unchanged apart from the placement.
- New driver seams, mutants and `mkrepo` roots go next to the existing ones.

### 6. Follow-up task (Step 8)

`aitask_create.sh --batch` (bug; labels monitor, tmux; anchor 2175): "the client
source for `TmuxMonitor.switch_to_pane`'s cross-session jump". It covers:

- monitor and minimonitor: each TUI's own pane, through the
  `_sitrep_initiator` inference over the subprocess gateway, then
  `switch_client_to_pane`;
- applink `focus` (no local terminal, so a decision is needed);
- an explicit trusted identity (`--client`/`--client-pid`, from a tmux
  binding's `#{client_name}`/`#{client_pid}`) for `ait sitrep open`, which
  closes the inference residuals;
- the producer contract (it never reads `TMUX_PANE`).

It references this task's archived plan.

Step 9 (Post-Implementation) handles cleanup, archival and the commit to `main`.

### Post-phase (risk mitigations)

1. [implicit_full_target_probe] Live case **9f**, `jump.py` mode
   `anywhere_implicit`: `switch_to_pane_anywhere(pane)` with NO `client=`, in
   the caller's `TMUX`/`TMUX_PANE` (A, viewed by `$TTY` only, placed first).
   Assert `moved`, client in `sel_e` on the destination pane. This is the
   monitor's exact call shape.
2. [live_33a_run] Run the live file again with
   `AIT_LIVE_TMUX_BIN=/tmp/aitask-2349-tmux.opQN0foR/usr/bin/tmux`. Record the
   per-case results, and every case whose outcome differs between 3.8 and 3.3a,
   in Final Implementation Notes. A missing binary is stated, not skipped
   silently. A 3.3a divergence in a new case (7, 9dA/9e/9f, 10–13) is fixed in
   this task.

## Verification

- `bash tests/test_multi_session_primitives.sh`;
  `bash tests/test_multi_session_monitor.sh`
- `python3 -m pytest -q tests/test_sitrep_window.py` (unittest fallback)
- `bash tests/test_sitrep_window_select_live.sh`: all pass, and every X control
  goes red where stated
- `bash tests/test_sitrep_window_live.sh` (no-select spawns: the restore
  removal and the detached companion); grep tests that patch or assert
  `maybe_spawn_minimonitor`'s argv or `focus_not_restored`, and run them
- `bash tests/run_all_python_tests.sh --test-dir tests`: the last line only
- `shellcheck` on the edited test scripts; `bash tests/test_no_raw_tmux.sh`

## Risk

### Code-health risk: medium
- The shared `switch_to_pane_anywhere` (monitor, minimonitor and applink jumps) becomes one full-target call; the implicit-client form was measured only with `-c` · severity: medium · → mitigation: inline post-phase implicit_full_target_probe
- The sitrep focus semantics change: detached creation everywhere, the restore is removed, a same-session focus moves to the early guarded jump, and with no single writable viewer a `focused` open exits 1 and spawns/repairs move nothing · severity: medium · → mitigation: none (covered by live cases 3, 4, 10–13 with controls; fail-safe direction; the expected shared-view changes are stated in the focus contract and pinned by case 13)
- `maybe_spawn_minimonitor` gains `detached` (29 other call sites, default unchanged) · severity: low · → mitigation: none (default-argv unit test in step 4)
- The live file grows (case 7 rewrite, 9dA/9e/9f, 10–12, about 7 mutants), and its state is shared · severity: low · → mitigation: none (placement reset + snapshot design in step 5)

### Goal-achievement risk: low
- The inference (lone writable viewer of the caller pane) is not an identity; its residuals are documented and their closure is in the follow-up. It relies on `list-clients` `#{pane_id}`/`#{client_readonly}`, measured on 3.8 and 3.3a · severity: low · → mitigation: inline post-phase live_33a_run

### Planned mitigations
- timing: post-phase | name: implicit_full_target_probe | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: shared primitive's implicit-client call shape | desc: live case 9f — switch_to_pane_anywhere without client= from the caller's context lands on the destination pane
- timing: post-phase | name: live_33a_run | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: tmux < 3.4 semantics of the viewer read and the full-target switch | desc: run the live file under AIT_LIVE_TMUX_BIN=<3.3a> and record per-case results
