---
Task: t2211_3_sitrep_tui_actions_respawn_launches_board_focus.md
Parent Task: aitasks/t2211_sitrep_two_pane_window_with_sitrep_tui.md
Sibling Tasks: aitasks/t2211/t2211_4_*.md, aitasks/t2211/t2211_5_*.md, aitasks/t2211/t2211_6_*.md, aitasks/t2211/t2211_7_*.md
Archived Sibling Plans: aiplans/archived/p2211/p2211_*_*.md
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5_5 @ 2026-11-08 18:47
---

# t2211_3: sitrep TUI actions, agent respawn, pick/board/push launches, `ait board --focus`

## Context

The sitrep TUI (t2211_1, made readable by t2211_8) is read-only today. Its "How"
lines still send the user to the sitrep agent for purely deterministic work:
`>r` refresh, `>x` dismiss, `/aitask-pick`, and a restore command typed in a
shell. This child adds those actions to the TUI as keys. It also adds a
respawn-agent key (through t2211_2's spawn roles) and launches from items: pick
in a new agent window, open the task in the board, show the push command. For
"open in board" it adds a new `ait board --focus <id>`, which can also hand off
to a board that is already running.

Out of scope: agentic requests typed into the agent pane (t2211_4), the skill
slim-down (t2211_5), user docs (t2211_6), manual checks (t2211_7).

Gate (verified 2026-11-08):
- t2211_2, t2211_8 and t2037_2 are archived.
- `git diff HEAD` is empty for `sitrep_tui/`, `monitor/sitrep_close.py`,
  `lib/agent_launch_utils.py`, `board/aitask_board.py` and `board/trails_app.py`.
- `monitor/monitor_core.py` has uncommitted edits from the concurrent t2242
  (`TmuxControlClient` attach target). **This plan does not edit `monitor_core.py`**;
  it only calls `find_sitrep_roles`.
- Re-run the diff check right before the first edit of each file.

## Verification of the earlier plan (what changed)

The previous plan's shape still holds. It has these corrections:
- **Keys and gating come from the t2211_8 model.** Gate on `model.classify(...)`
  keys and edit `NEXT_STEPS` "how" texts; do not add a parallel table. New lists use
  `SelectOnClickList`.
- **Pick from a pane TUI follows minimonitor, not trails.** Call
  `build_pick_screen(root, id, narrow=True)`. Only a `TmuxLaunchConfig` result
  launches; "run" is refused with a toast, because the TUI's pane cannot host the agent.
- **Writer calls need `cwd=root` and no `AITASK_SITREP_DIR`** (t2211_1 note).
  `sitrep_close.run_owned_group` takes neither today, so it gets optional `cwd=` /
  `env=` keyword arguments. Existing callers are unchanged.
- **Board handoff reuses the trails mailbox design** (t1957_2). It is addressed to
  one pane: a receiver stamp holding a pid, plus a request `<32-hex id> <payload>`
  that is overwritten and never unset. The previous plan's "set the option and clear
  it on read" is replaced by this design, because clear-after-read can erase a
  request written in between. The primitives are generalized; trails keeps its
  public functions as thin wrappers.
- **The board has no argv parsing at all** (`KanbanApp().run()`). `--focus` adds an
  argparse main. `KanbanApp()` with no arguments must stay valid, because every
  board test builds it that way.
- **Agent status comes from `monitor_core.find_sitrep_roles`** over a `tmux_run`
  duck type. The TUI pane is not in discovery (t2211_2 note).

## User decisions (plan review, 2026-11-08)

- **Rename the TUI's mixed "Pick now" section to "Now"**, including the header
  summary ("… · N open in Now"). The group holds picks, triage, decisions and
  actions, so "Pick" was wrong for it. This is **display only**:
  - the store's file format keeps its `### Pick now` heading (`sitrep_todo.SLOTS` /
    `SLOT_HEADINGS` parse it; `tests/test_sitrep_todo_format.py` and the
    `tests/fixtures/sitrep/` stores pin it);
  - the monitor title bar, the skill and the website are not the TUI and are
    untouched.
- **Action-specific wording stays** in the "What to do" cells: "Pick …" for
  `/aitask-pick`, "Triage …" for triage, "Decide …", "Do …", and so on.
- **`p` launches `/aitask-pick` only for pick items.** It is shown iff
  `model.classify(item, check) == "pick"` (a task item with a local ref, state
  open). It is never shown for triage items, even though a triage item's title and
  ref name a task.

## Steps

0. **"Now" label** (`sitrep_tui/sitrep_tui_model.py`, `sitrep_tui_app.py`).
   - Add `GROUP_LABELS = {"now": "Now"}`, a TUI display override keyed by slot.
     `group_items` returns `GROUP_LABELS.get(slot, <stored heading>)` as the
     heading.
   - `_render_header`: "{now} open in Now".
   - Module docstring: "grouped Now / Next / Waiting".
   - Update `tests/test_sitrep_tui_app.py` (`"Now (4)"` for `hdr:now`, "open in
     Now"). Add a test that the written `todo.md` still carries `### Pick now`
     (format unchanged).

1. **Gate re-check.** Run `git diff HEAD --stat --` over every file below, including
   `aitask_sitrep_todo.sh` and `tests/test_sitrep_todo.sh`.
   Non-empty means stop and check who owns the hunk before editing.

2. **Runner with cwd/env** (`.aitask-scripts/monitor/sitrep_close.py`).
   - Add `run_owned_group(argv, *, stdin=None, timeout, cwd=None, env=None)`.
   - Pass both through to `create_subprocess_exec`. Nothing else changes.
   - Unit test: a stub script that echoes `pwd` and an env var shows that `cwd`
     and `env` are honoured.

3. **Model additions** (`sitrep_tui/sitrep_tui_model.py`, Textual-free).
   - `parse_refresh_output(rc, out) -> RefreshReport`:
     - frozen dataclass with `final_kind` (`REFRESHED` / `REFRESH_NONE` /
       `REFRESH_FAILED` / `missing`), `reason`, `rc`, `counts: dict`,
       `items: tuple[str]` (the `REFRESH_ITEM:` rows) and `warns`;
     - `ok` (rc 0 and final in REFRESHED / REFRESH_NONE) and `verdict()`;
     - only the LAST final line counts, and `ERROR:` lines are recorded. This is
       the same rule as `sitrep_close.parse_harvest_output`, which is reused
       as-is for harvest.
   - `task_ref_id(item) -> str | None`: the local `t<N>[_M]` id. Kind must be `task`
     and `_LOCAL_REF_RE` must match; xrefs give None.
   - `push_command(root, branch) -> str`:
     - if `<root>/.aitask-data` is a worktree whose checked-out branch is `branch`
       → `./ait git push`;
     - else `git push <remote> <branch>`, with the remote resolved by the same
       precedence as `sitrep_refresh.push_verdict`
       (`branch.<b>.pushRemote` → `remote.pushDefault` → `branch.<b>.remote`);
     - with none configured, show `git push origin <branch>` plus a note saying
       "no push remote configured".
     - Read-only `git -C root` calls with a timeout, never raises. The branch is
       already validated by `parse_push_ref`. The result is only ever displayed.
   - `NEXT_STEPS` "how" texts take `{k_*}` key placeholders. `next_step(item, check,
     keys=None)` fills them from `keys`, defaulting to `DEFAULT_KEYS`. The app passes
     keys resolved through `keybinding_registry.resolve_key("sitrep_tui", action,
     default)`, so a remapped key shows correctly. Rows that change:
     - `pick`: "Press {k_pick} to launch /aitask-pick {pick_id} in a new agent
       window, or {k_board} to show it in the board."
     - `push`: "Press {k_push} to show the push command (copyable; the TUI never
       runs it). Refresh marks this done once the commit is on the remote."
     - `do`: "... when it is done or no longer needed, press {k_dismiss} to dismiss
       it with a reason."
     - `watch` and `unknown`: "Press {k_refresh} to harvest + refresh ..."
     - `unknown_manual`: keep `>q`; replace the `>x` part with "press {k_dismiss}".
     - `watch_manual`: append "or press {k_dismiss} to dismiss it".
     - Unchanged: `triage`, `review`, `decide`, `pick_xref` (agentic, or foreign;
       t2211_4 owns those).

4. **Actions module** (new `sitrep_tui/sitrep_tui_actions.py`, to keep the app file
   bounded).
   - It holds the modal dialogs, all `GuardedModalScreen`, with store text as plain
     `Content` only:
     - `DismissDialog(item, rev, notice="")`: title, an optional notice, a reason
       `Input`, and Confirm / Cancel. It returns the reason or None.
     - `ConfirmDialog(question)`: for restore and respawn.
     - `ResultDialog(title, lines)`: the harvest/refresh panel and the error panel.
     - `PushCommandDialog(cmd, note)`: the command in a read-only field, Copy
       (`tui_clipboard.copy_to_system_clipboard`) and Close. **No run path exists.**
   - It holds `SitrepActionsMixin` with the async flows. Each flow re-checks its
     precondition at the top, because a binding gate is not a guard.
   - Register the module in the shortcut-scope manifest (`lib/shortcut_scopes.py`
     t2211_1 row / `KNOWN_BINDING_SOURCES`) if its screens carry bindings, and add
     scopes `sitrep_tui.dialog` as needed. Check what `tests/test_shortcut_scopes.py`
     sweeps.

5. **Command runner and harvest + refresh.**
   - Add `_run_cli(argv, timeout)` → `run_owned_group(..., cwd=self.root,
     env=<os.environ minus AITASK_SITREP_DIR>)`. It is a constructor seam
     (`runner=`) for tests.
   - Key `r` (main screen, action `harvest_refresh`) and startup (only when
     `startup_harvest=True`; `main()` passes True, tests default to False) run one
     worker:
     - `aitask_sitrep_harvest.sh all --root <root>` with `HARVEST_ALL_TIMEOUT`;
     - then `aitask_sitrep_refresh.sh --root <root> --budget 60` with timeout 75,
       sharing monitor_shared's constants; import them, or define one pair in the
       model if importing monitor_shared is too heavy.
   - `_harvest_inflight` refuses a second run with a toast.
   - After both: `await self._poll_store()` (immediate reload). Then:
     - a key run opens `ResultDialog` showing both verdicts, the warn / review /
       failed lines and the REFRESH_ITEM rows;
     - a startup run only toasts the combined verdict (warning severity on failure).
   - The header gains "refreshed HH:MM ok|failed".

6. **Dismiss** (action `dismiss_item`, key `x`). It runs on the current item and is
   gated on classify ∉ {done, dismissed}.
   - Open `DismissDialog` with the item's `rev` from the loaded store. On confirm,
     run `aitask_sitrep_todo.sh dismiss c<N> --outcome <reason> --expect-rev <rev>`.
   - Parse the result:
     - `STATE:c<N>|dismissed|<rev>` → reload, toast, and pop an open detail screen
       for that item (details are snapshots).
     - `STALE:c<N>|<rev2>` (exit 0) → reload. If the item is still open/unknown,
       re-open the dialog with the notice "c<N> changed since you looked (rev
       a→b)", the typed reason pre-filled and rev2. Otherwise toast "c<N> is now
       <state>". **Never a blind retry.**
     - exit 3 → re-open the dialog with the notice "store busy — Confirm to retry".
     - exit 2 → `ResultDialog` error.
     - exit 4 → error dialog plus the restore hint (key `R`).
   - Cancel writes nothing.

7. **Restore** (action `restore_store`, key `R`, main only). It is gated on
   `todo_error or qa_error`.
   - **Writer: conditional restore** (`.aitask-scripts/aitask_sitrep_todo.sh`
     `cmd_restore`, plus its header). Add `restore todo|qa [--if-damaged]`:
     - with the flag, **under the store lock** and before anything is written, run
       `"$PY" "$CORE" verify "$kind" "$live"`, the same check that validates the
       backup;
     - if the live file exists, is not a symlink and verifies → print
       `RESTORE_NOT_NEEDED:<kind>.md`, release, exit 0. Nothing is preserved and
       nothing is installed;
     - otherwise run the existing path unchanged.
     - Without the flag, restore stays unconditional, which is the intentional CLI
       recovery (an operator may roll back a file that parses but holds bad data).
   - TUI flow: confirm "Restore todo.md / qa.md from the last good generation?"
     (each damaged kind, todo first), then run `restore <kind> --if-damaged`.
     - `RESTORED:` line → show `recovered/<name>` or `no-damaged-copy`;
     - `RESTORE_NOT_NEEDED:` → toast "<kind>.md is healthy again — nothing
       restored". Either way, reload.
     - The cached `todo_error` / `qa_error` only gate the binding; the writer's
       under-lock check is the authority.
   - The banner text replaces the shell command with "press R to restore".

8. **Agent status and respawn.**
   - Add a constructor seam `roles_probe` (None means not in tmux → status
     "unknown").
   - `main()` builds it from `$TMUX_PANE` / `$TMUX`, only when
     `pane_on_gateway_server` accepts the pane. It is a lazy-imported
     `monitor_core.find_sitrep_roles(_Gateway(), root)`, where `_Gateway.tmux_run`
     wraps `tmux_exec.TmuxClient().run` (the `sitrep_open._Gateway` shape).
   - Poll every 3 s with `asyncio.to_thread`. The busy flag gives one read in
     flight at most.
   - The header shows "agent: running" / "agent: not running — press A" / "agent:
     unknown". A state change calls `refresh_bindings()`.
   - `A` (action `respawn_agent`, main only) is shown only when the last probe said
     ok and no agent. The action re-probes, then confirms. It then runs
     `aitask_sitrep.sh open --root <root> --session <own session>` (timeout
     `SITREP_OPEN_TIMEOUT` 45 s). The own session is `pane_session($TMUX_PANE)`;
     none means refuse with a toast. It toasts
     `sitrep_cli.sitrep_open_message(rc, out)`, then re-probes.
   - No second spawn implementation.

9. **Launches from an item.** The bindings are App-level in scope `sitrep_tui`,
   hidden on viewer and Q&A screens.
   - **Item resolution (freshness):** `_action_item()` returns `(item, origin)`:
     - From the main list: the highlighted cid resolved against `app.store`. The
       list is rebuilt in the same `_apply` that swaps the store, so the row and
       the item are one generation.
     - From an `ItemDetailScreen`: the snapshot's `num` is re-resolved against the
       current `app.store`. Revs are store-wide and never reused, so an equal
       `rev` means the same meaning.
     - If the item is gone, or its `rev` differs from the snapshot's, then:
       - replace the stale detail screen with a fresh `ItemDetailScreen` for the
         same num (or pop it, if the item is gone);
       - toast "c<N> changed since these details were opened — details refreshed;
         press <key> again";
       - **launch nothing.** Neither the old nor the new target runs without a new
         explicit key press.
     - While `app.todo_error` is set, `app.store` is only the last good view: the
       launch actions refuse ("store unusable — press R"). Dismiss is refused too,
       since the writer would exit 4 anyway.
   - The action predicate runs on the **resolved current** item, never on the
     snapshot.
   - Dismiss keeps `--expect-rev <snapshot rev>` (the rev the user saw), and its
     STALE path stays as in step 6.
   - The pick dialog's callback re-resolves once more before `launch_in_tmux`. If
     the item no longer classifies `pick` with the same task id → refuse with a
     toast.
   - `p` `pick_task`: only when `classify(item, check) == "pick"` (never triage /
     review / decide / unknown / xref). In order:
     - `focus_existing_agent_window(id, root)` → toast "switched";
     - else `build_pick_screen(Path(root), id, narrow=True)`. None → toast error. On
       a `TmuxLaunchConfig` result: `launch_in_tmux` → error toast (`markup=False`)
       or `maybe_spawn_minimonitor` when it is a new window, then a toast. "run" →
       toast "run in a tmux window instead".
   - `b` `open_in_board`: `task_ref_id` set, any state. Runs off-loop in a thread
     worker:
     - `own = current_tmux_session()`. None → refuse with "not in an aitasks tmux
       session — run ./ait board --focus <id>", because `switch-client` could not
       reach this client.
     - Destination: `own` when `session_owned_by(own, root)`, else
       `live_project_session(root)`. None → refuse ("no tmux session for this
       project").
     - Re-check `session_owned_by(dest, root)` immediately before launching (the
       `finish_linked_trail_jump` rule: a session name can be reused).
     - Run `launch_or_focus_board(dest, root, id)`. Then, when `dest != own`,
       `switch_client_to(dest)`. A failed switch → error toast "board opened in
       session '<dest>' but switching there failed — switch with: tmux
       switch-client -t =<dest>".
     - Same-session: no switch call; the selected window is already visible to
       this client.
     - Toast the result or warning only when no switch happened. After a
       successful switch, nobody is looking at this pane.
   - `P` `show_push`: `parse_push_ref(item.ref)` set. `PushCommandDialog(
     model.push_command(root, branch))`, computed off-loop. Nothing is executed.
   - Foreign `<proj>#<N>` refs: p and b are hidden (classify `pick_xref`).

10. **Dynamic bindings** (`SitrepTuiApp.check_action`).
    - Add `_ITEM_ACTIONS` (`pick_task`, `open_in_board`, `show_push`, `dismiss_item`),
      visible on the main screen or an `ItemDetailScreen`.
    - Extend `_MAIN_ACTIONS` with `harvest_refresh`, `restore_store`,
      `respawn_agent`.
    - Each action's predicate is one helper (`_item_action_ok(action, item)`), shared
      by `check_action` (False → hidden) and the action body (refuse with a toast).
    - `refresh_bindings()` runs on highlight change (exists), in `_apply`, on agent
      state change and on harvest start/end.
    - Pick the binding keys after checking `TuiSwitcherMixin.SWITCHER_BINDINGS` /
      `ShortcutsMixin` for collisions.

11. **Generalized pane mailbox** (`lib/agent_launch_utils.py`).
    - Extract the parameterized primitives:
      - `read_pane_request(pane, option)`;
      - `mark_pane_receiver(pane, option)` / `unmark_pane_receiver(pane, option)`;
      - `_live_pane_receivers(session, option)`;
      - `parse_pane_request(value, payload_re)`.
    - `read_trails_focus_request` / `parse_trails_focus_request` /
      `mark_trails_receiver` / `unmark_trails_receiver` / `_live_trails_receivers`
      become one-line wrappers with **unchanged argv** (pinned by
      `tests/test_trails_focus_writer.py`).
    - Add `BOARD_FOCUS_OPTION = "@aitask_board_focus"`,
      `BOARD_RECEIVER_OPTION = "@aitask_board_app"` and `_BOARD_TASK_ID_RE =
      ^[0-9]+(_[0-9]+)?$`, plus `read_/parse_board_focus_request`,
      `mark_/unmark_board_receiver`.
    - Add `launch_or_focus_board(session, project_root, task_id) -> (ok, msg)`:
      - validate the id before any tmux call;
      - first live receiver → set the request `<uuid4 hex> <id>`, `select-window`,
        `select-pane` → (True, None);
      - else a window named `board` exists (`list-windows`) → select it and return
        (True, "the running board cannot take focus requests — restart it to jump
        to t<id>"), so a second board is never started beside an older one;
      - else `new-window -c <root> -n board ./ait board --focus <id>` (argv form).
    - All of it goes through `_TMUX` (the gateway); no raw tmux.

12. **Board `--focus`** (`board/aitask_board.py` + new flat module
    `board/board_focus_request.py`).
    - `main(argv=None)` uses argparse with `--focus ID`, accepting `t`-prefixed or
      bare ids; an invalid id → `parser.error`. `$TMUX_PANE` / `$TMUX` are read only
      here. Then `KanbanApp(focus_task=..., focus_pane=..., focus_tmux_env=...)`.
      All kwargs default to None/"", so `KanbanApp()` is unchanged.
    - `KanbanApp.focus_task_by_id(id)`:
      - `manager.find_task_by_id(f"t{id}")`. None → `find_task_including_archived`
        → toast "t<id> is archived — not on the board", else "t<id> not found";
      - a child: add the parent's filename to `expanded_tasks`, then
        `refresh_board(refocus_filename=child.filename)`; a parent:
        `_queue_refocus(filename)`;
      - a later `call_after_refresh` verifies that `_focused_card()` is the target,
        else toasts "t<id> is not visible in the current view (filter / collapsed
        column)";
      - while a modal is active, keep it as `_pending_focus_task` and apply it in
        `_resume_detached_focus`'s resume hook.
    - The cold path queues `focus_task_by_id` from `on_mount` after
      `_claim_startup_focus`.
    - `BoardFocusMailboxMixin` (in `board_focus_request.py`) follows the trails
      consumer shape:
      - a thread worker: `pane_on_gateway_server` → baseline read → stamp;
      - a 1 s poll with a busy flag;
      - last-seen id dedupe, latest wins, malformed → warning toast (not echoed);
      - unstamp on unmount.
      - Delivery calls `focus_task_by_id`.
    - Add the module to the board package map in `aidocs/framework/tui_conventions.md`.

13. **Docs (framework only; user docs are t2211_6).**
    - `aidocs/framework/tmux_gateway.md` `@aitask_*` inventory gets rows for
      `@aitask_board_app` / `@aitask_board_focus`, and the missing
      `@aitask_trails_app` / `@aitask_trails_focus` rows, which are the same
      mechanism.
    - Update the `sitrep_tui_app.py` module docstring ("read-only" → the writes it
      now makes, through the writer only).
    - `aidocs/framework/sitrep.md`: one short paragraph on the TUI's write paths
      (dismiss / restore through the writer with `--expect-rev`, harvest+refresh at
      startup) and the respawn path.

14. **Tests.**
    - `tests/test_sitrep_tui_actions.py` (run_test). The fixture store is built
      through the real writer: import `build_fixture` / `writer` / `_AppCase` by name
      from `tests/test_sitrep_tui_app.py`, never a test class. Coverage:
      - dismiss success; STALE (a concurrent `dismiss`/`update` between open and
        confirm) → dialog re-opened with the new rev and no second write; cancel →
        `list --machine` unchanged; exit 3 via a stubbed runner → retry dialog;
      - restore: break `todo.md` → `R` shown → `RESTORED:` line, reload;
      - **restore race:** break `todo.md`, then open the `R` dialog. While it is
        open, repair the store through the CLI (`restore todo`) and make a newer
        write (`add` an item). Confirm → `RESTORE_NOT_NEEDED`, the new item is
        still in `todo.md`, and no new `recovered/` file exists. Pre-fix control:
        the same sequence with the unconditional verb rolls the new item back,
        which proves the test sees the hazard;
      - **detail freshness:** open details of a pick item, then from outside
        (a) `update` its ref to another task and (b) `dismiss` it. In each case
        `p` / `b` launch nothing (stubbed launchers not called), the details are
        refreshed or closed, and a second `p` after refresh acts on the current
        meaning (case a). The pick-dialog callback refuses when the item changed
        while the dialog was open;
      - **board session:** stub `current_tmux_session` / `session_owned_by` /
        `live_project_session` / `launch_or_focus_board` / `switch_client_to`.
        Destination = own session → no switch. A different destination → switch
        called with it; a failed switch → error toast naming the session. Not in
        tmux → refused before any launch. Destination no longer owned at
        re-check → refused;
      - harvest/refresh: a stubbed runner returns sample outputs (ok, REFRESH_FAILED,
        missing final line) → panel lines; a second `r` while in flight → toast and
        no second run;
      - a bindings matrix over classify keys × {main, detail, viewer}, including a
        triage item whose title/ref names `t<N>` → `p` and `b` hidden; agent states
        (running / not running / unknown) × the `A` binding;
      - respawn: stubbed probe + runner returning each `SITREP_*` line →
        `sitrep_open_message` toast;
      - push: dialog shows `./ait git push` for the data branch and `git push
        <remote> <b>` otherwise, and the runner is never called with it;
      - the "how" texts follow a remapped key.
    - `tests/test_sitrep_tui_model.py` additions (or within the new file):
      `parse_refresh_output` cases, `push_command` against a scratch git repo with a
      configured pushRemote and none.
    - `tests/test_sitrep_todo.sh`: new cases for `restore <kind> --if-damaged`:
      - healthy live → `RESTORE_NOT_NEEDED`, live bytes unchanged, no
        `recovered/` entry;
      - damaged live → `RESTORED:` exactly as without the flag;
      - missing live in an established store → restored;
      - the flag on a busy lock → exit 3, nothing written.
      - Existing unconditional-restore cases stay as they are.
    - `tests/test_board_focus_writer.py`: `launch_or_focus_board` argv against a stub
      gateway (receiver, two receivers → first only, a fresh id each time, dead
      stamps skipped, an existing board window without a receiver → select and
      warn, new window argv, a malformed id refused before tmux), plus the board
      request parse.
    - `tests/test_board_focus.py`: `main` argv parsing (valid / `t`-prefixed /
      invalid). KanbanApp run_test over a fixture task tree: focus a parent card, a
      child card (parent expanded), an archived id (toast), a filtered-out card
      (toast). Mailbox: a value delivered → card focused; the baseline is not
      replayed; a repeated id is ignored.
    - Existing suites that must stay green: `tests/test_trails_focus_writer.py`,
      `tests/test_trails_app.py`, `tests/test_sitrep_tui_app.py`,
      `tests/test_monitor_sitrep_harvest_close.py`, `tests/test_shortcut_scopes.py`.

### Pre-phase (risk mitigations)

Runs before step 11 (the mailbox refactor). Steps 1–10 do not touch trails.

1. [characterize_trails_mailbox] Before editing `agent_launch_utils.py`, run
   `tests/test_trails_focus_writer.py`, `tests/test_trails_app.py` and
   `tests/test_trails_focus_mailbox_live.py`, and record the pass counts in the plan.
   - After step 11, the same three must pass with **no edits to those files**. Their
     argv/parse assertions are the characterization.
   - Mutant check in an isolated scratch copy: change one wrapper's option name
     (e.g. `TRAILS_FOCUS_OPTION` → `BOARD_FOCUS_OPTION` inside
     `read_trails_focus_request`). The writer tests must turn red. Record the result.

### Post-phase (risk mitigations)

1. [board_mailbox_live_test] Extend `tests/test_trails_focus_mailbox_live.py`, or
   add a sibling `tests/test_board_focus_mailbox_live.py` built on the same
   throwaway-server scaffold (`AITASKS_TMUX_SOCKET` private socket, `-f /dev/null`,
   `_TMUX` rebuilt), so the same live assertions run for the board option pair:
   - an unset request reads as empty, and a missing pane reads as None;
   - the `list-panes -s` format names each pane's own `@aitask_board_app` stamp, so
     `launch_or_focus_board` writes only to the stamped pane;
   - the request survives the read, and unmark removes the stamp;
   - with no receiver and no `board` window, a new `board` window is created with
     the `./ait board --focus <id>` argv. Assert through `list-windows`, with
     `./ait` stubbed by a `sleep` command so no real board boots.
   - Skipped when tmux is missing. Mutant: a writer that targets the session
     instead of the stamped pane must fail.

## Verification

- New and touched tests above. `bash tests/run_all_python_tests.sh --test-dir tests`
  (read the last line, with `set -o pipefail`).
- `bash tests/test_no_raw_tmux.sh`; `bash tests/test_no_lib_to_tui_import.sh`;
  `shellcheck` on any changed `.sh`.
- Manual (t2211_7 owns the checklist), in a real sitrep window:
  - `r` shows the harvest/refresh panel;
  - `x` dismisses with a reason;
  - kill the agent → the header says not running → `A` respawns it;
  - `b` on a task focuses the running board's card, or opens a board on it;
  - `p` launches a pick; `P` shows the push command.

## Risk

### Code-health risk: medium
- Generalizing the trails mailbox primitives (step 11) touches a working, live-tested handoff path. A wrapper whose argv drifts would silently break `ait trails` focus requests · severity: low (residual — addressed by inline pre-phase characterize_trails_mailbox) · → mitigation: inline pre-phase characterize_trails_mailbox
- The board gains argparse and `KanbanApp` kwargs. It is the most central TUI, and a mount-order mistake could disturb its startup focus (t1491). Defaults stay unchanged, and `tests/test_board_startup_focus_live.py` runs in the suite's serial carve-out · severity: medium · → mitigation: none
- The sitrep TUI grows a lot (dialogs, three async flows, a poller). Moving them into `sitrep_tui_actions.py` keeps the app file bounded · severity: low · → mitigation: none
- The store writer gains `restore --if-damaged`. The default restore path is
  untouched, and the new branch runs under the same lock before any write · severity:
  low · → mitigation: none
- `run_owned_group` gains `cwd=` / `env=`. Monitor maintenance shares it; the kwargs are optional and existing calls are byte-identical · severity: low · → mitigation: none

### Goal-achievement risk: low
- The plan tests the board mailbox only against a stub gateway. The tmux behaviour it relies on is assumed rather than proven: the stamp read through a `list-panes -s` format, the request option surviving the read, a missing pane reading as failure · severity: low (residual — addressed by inline post-phase board_mailbox_live_test) · → mitigation: inline post-phase board_mailbox_live_test
- "Open in board" reports, but does not reveal, a card hidden by the current view, a search filter, a collapsed column or trail mode. The user gets a toast instead of the card · severity: low · → mitigation: none
- The startup harvest+refresh can collide with the monitor's own maintenance pass on the store mutex. The result is a LOCK_BUSY toast at startup and nothing written · severity: low · → mitigation: none

### Planned mitigations
- timing: pre-phase | name: characterize_trails_mailbox | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — trails mailbox refactor drift | desc: run the trails writer/app/live mailbox tests green before and unchanged after the primitive extraction, plus one wrapper mutant
- timing: post-phase | name: board_mailbox_live_test | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: goal-achievement — board mailbox unproven against real tmux | desc: run the live mailbox assertions for the board option pair on a throwaway tmux server

## Step 9

Commit `feature: … (t2211_3)` (code) and `ait: Update plan for t2211_3`, then archive
per the shared workflow. After commit, send a note to t2211_6 listing the keys, the
wire lines shown and the board `--focus` flag. Send a note to t2211_7 listing the
manual checks.
