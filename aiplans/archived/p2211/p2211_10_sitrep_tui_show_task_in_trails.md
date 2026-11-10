---
Task: t2211_10_sitrep_tui_show_task_in_trails.md
Parent Task: aitasks/t2211_sitrep_two_pane_window_with_sitrep_tui.md
Sibling Tasks: aitasks/t2211/t2211_4_*.md, aitasks/t2211/t2211_5_*.md, aitasks/t2211/t2211_6_*.md, aitasks/t2211/t2211_7_*.md
Archived Sibling Plans: aiplans/archived/p2211/p2211_*_*.md
Base branch: main
Output branch: main
---

# t2211_10 — sitrep TUI: show a task in `ait trails` (trail opened, card focused)

## Context

A sitrep task item names a local task (`kind=task`, `model.task_ref_id`). When that
task is a member of one or more implementation trails, the user wants to see it in
`ait trails` with one key: the trail opens and the task's card is focused. The item
details also list the task's trails, and Enter on a trail row does the same jump.
Today `launch_or_focus_trails` and `TrailsApp` handle a trail handle only. Nothing
can focus a card inside a trail, and the sitrep TUI knows nothing about trails.

User decision (planning, 2026-11-09): the key is **`z`**, the board's By-Trail key.

Reality checks (HEAD 6d44bd275, 2026-11-09):
- `git diff HEAD` is empty for `sitrep_tui/`, `lib/agent_launch_utils.py`,
  `board/trails_app.py`, `lib/trail_discovery.py` and the trails/sitrep tests. Re-run it
  right before the first edit of each file (shared dirty worktree; other sessions
  have uncommitted edits elsewhere).
- **An older running TrailsApp refuses `<handle> <task>`.** `parse_trails_focus_request`
  = `parse_pane_request(value, HANDLE_RE)`. HANDLE_RE is anchored
  (`^art:[a-z0-9][a-z0-9._-]{0,127}$`), and `tests/test_trails_focus_writer.py::test_parse`
  pins `"<id> <handle> extra" → (id, None)`. Such an app toasts "Ignored a malformed trail
  request" and opens nothing. So the task's e.g. payload alone would break the
  "an older running TrailsApp must still open the trail" requirement. The writer must
  know whether the receiver understands the task form → a **capability stamp** (step 2).
- **Membership:** `trail_discovery` is cwd-relative (artifact CLI, `TASK_DIR`), while the
  sitrep TUI's `root` is an argument (a fixture dir in tests). `lib/trail_links.py`
  already runs discovery for a given root in a subprocess:
  - `_collect_export(name, root)` runs `trail_links.py export` with cwd=root and
    `TASK_DIR=aitasks`;
  - it returns the trails (`handle`, `name`, `load_error`, `members`), `local_project`,
    `unreadable` and `scan_errors`;
  - its error rows are typed: TIMEOUT / EXPORT_FAILED (no data) vs PARTIAL (data plus
    unreadable trails/files).

  It goes through the content-keyed discovery cache, so no new cache is needed. The
  export does not carry waves yet.
- Member refs are canonical `<project>#<id>` (e.g. `aitasks#2211_3`; `parse_ref` accepts
  `#t<id>` and child ids). A member is local iff its project equals `project.name`. This
  is the board's `trail_ref_to_local_id` rule, so an unset `project.name` matches nothing.
- Card focus in `TrailsApp`: activation goes through `_activate_trail` (fresh session →
  `refresh_board`; open tab → `_switch_trail_session` → `_show_trail_session` restores
  the tab's saved focus). The drift re-render keeps the focused card by filename
  (`board_trail_screen.py:1624/1653`). Cards carry `trail_entry["task"]`; ghosts too.
- `SelectOnClickList` lives in `sitrep_tui_app.py`, and `sitrep_tui_actions.py` cannot
  import the app (circular).

## Design decisions (pinned)

- **Payload grammar.**
  - `@aitask_trails_focus` takes `"<32-hex id> <handle>"` (unchanged), or
    `"<32-hex id> <handle> <task id>"` with the task id in `BOARD_TASK_ID_RE` grammar.
  - The task form is written **only** to a receiver that stamped the new capability
    option `@aitask_trails_card_focus <pid>`, with the pid equal to its
    `@aitask_trails_app` stamp.
  - Any other receiver (an older app, a mismatched or stale capability, a failed read)
    gets the bare `<handle>`, and the writer returns the warning "the running ait trails
    cannot focus a card — restart it to show t<id>". The trail still opens.
  - A malformed request (bad task id, extra tokens) is refused whole, as malformed
    requests are today: recorded as seen, warning toast, not echoed, never a crash.
- **Cold path:** `./ait trails --trail <h> --task <id>`. It is used only when
  `trails_supports_task_focus(root)` (text probe for `"--task"` in the project's
  `trails_app.py`; `--tasks-dir` does not match). Otherwise the cold path is the plain
  `--trail` argv plus a warning.
- **Membership states per task:**
  - `in` (≥1 trail; with a `partial` note when some trail/file could not be read);
  - `none` (complete scan, no trail);
  - `unknown(<reason>)` (export failed, or partial with no known trail, or
    `project.name` unset);
  - `looking` (no result yet);
  - `off` (no scanner configured: tests' default, no rows, key hidden).

  The key is visible only for `in`. A partial scan keeps the positive evidence: known
  trails are shown and usable, plus one disabled "some trails could not be read" row.
- **Details `z`:** acts on the highlighted trail row when the links list has one
  highlighted. Otherwise: 1 trail → open it, 2+ trails → the picker. On the main list:
  1 trail → open, 2+ → picker.
- **Rescans:** after the first load, on every store generation change (`_apply`), when a
  task item's details open, and every `TRAILS_RESCAN_INTERVAL` (60 s; confirmed by the
  pre-phase measurement). One scan runs at a time; a trigger during a scan sets a dirty
  flag that reruns it once. The action re-checks the cached membership. A trail that
  changed in between is reported by TrailsApp ("not in this trail any more"), which
  still opens the trail.

## Plan review (2026-11-09) — two blocking findings, both verified and fixed

- **Details selection identity.** Positional `trail:{i}` ids plus an id-based highlight
  restore re-select a *different* trail after [A,B,C]→[B,C]. The launch-time "handle
  still listed" check accepts it, so the check cannot protect the selection. Fixed in
  step 7: option ids are `trail:<handle>`, the restore is by id, a vanished handle
  clears the highlight (no positional fallback), and Enter passes the option's own
  handle. Removal / reorder / vanish tests with a pre-fix control are in step 9.
- **Deferred card focus.** The draft cleared `_pending_card` when it scheduled the focus.
  It also dropped the attempt after a bounded retry under a modal, and the resume hook
  only drained `_pending_trail_focus`. A modal opened after activation could lose the
  card. Fixed in step 3: the request stays pending until it succeeds, is reported,
  superseded, or another trail is activated. A modal never spends hops, and
  `_drain_trail_focus` re-schedules the pending card on resume. The post-activation-
  window test (modal held past the budget) with a pre-fix control and two negative
  controls is in step 9.
- **Tab cancellation paths (second review round).** The draft cancelled only in
  `_activate_trail`. Tab clicks, `[` / `]`, the numbered keys and `ctrl+w` call
  `_switch_trail_session` / `_close_trail_session` directly, and the focus callback only
  returned on a mismatch. So leaving and coming back kept an obsolete request that a
  later resume could re-apply over the user's saved card. Fixed in step 3:
  - the cancellation sits on the `_trail_active` assignment (a TrailsApp property),
    which all five transition sites write. An intended activation of the pending
    handle does not cancel, and a mismatch in the callback clears;
  - the step-9 control drives the real navigation routes in the delayed-attempt window,
    because those handlers refuse while a modal is up.

## Implementation steps

### Pre-phase (risk mitigations)

1. [characterize_trails_mailbox] Before editing `agent_launch_utils.py` / `trails_app.py`,
   run `tests/test_trails_focus_writer.py`, `tests/test_trails_app.py`,
   `tests/test_trails_focus_mailbox_live.py` and `tests/test_sitrep_tui_actions.py -k
   OpenInBoard`. Record the pass counts in the plan.
   - After the steps below, the same tests must pass with **no edits to their existing
     test bodies**; only new test classes/cases are added. The one exception is the
     `_PaneStore.patches` seam list, which gains the new capability functions.
   - Mutant, in an isolated scratch copy: make the writer send the task payload
     regardless of capability. The new old-receiver test must turn red. Record the result.
2. [tmux_seam_inventory] Before step 3, `grep -rn "mark_trails_receiver\|pane_on_gateway_server\|focus_pane" tests/`
   and list every test that boots a TrailsApp with a pane or patches its mailbox seams.
   - Each such seam gets patches for `mark_trails_card_focus` / `unmark_trails_card_focus`
     too. The production code calls them only after `pane_on_gateway_server` passed, so
     these are exactly the sites that could reach tmux.
   - After step 3, run `tests/test_trails_app.py` with `AITASKS_TMUX_SOCKET` pointed at a
     non-existent private socket (`TMUX_TMPDIR` under the scratchpad). It must pass, and
     the socket must never have been created (no server started, nothing written to a real
     one). Record the result.
3. [measure_membership_scan] Time `trail_links.py export` in this repo, cold and warm
   (`time ~/.aitask/venv/bin/python .aitask-scripts/lib/trail_links.py export`, cwd = repo
   root; it writes only `.aitask-cache/`).
   - Record both numbers in the plan.
   - Keep `TRAILS_RESCAN_INTERVAL = 60` if warm ≤ 2 s; otherwise raise it to 120 and
     note why.

**Pre-phase results (2026-11-09):**
- characterize_trails_mailbox:
  - before any edit: `test_trails_focus_writer.py` + `test_trails_app.py` +
    `test_trails_focus_mailbox_live.py` 134 passed; `OpenInBoard` 7 passed;
  - after the edits: the same 134 (+42 `test_trail_links.py`) passed with no
    existing test body edited;
  - mutant (capability ignored, `if True:` in the receiver branch) in a scratch copy →
    only `LaunchWithTaskTests::test_an_older_receiver_gets_the_bare_handle_and_a_warning`
    red (1 failed, 33 passed).
- tmux_seam_inventory:
  - the only seam is `_PaneStore.patches` in `tests/test_trails_app.py` (every
    `focus_pane=` test goes through it). It now patches both capability functions.
  - They log to a separate `cap_log` / `order`, because the existing tests pin the
    exact `log` verb lists (`["verify","read","mark"]`, last `"unmark"`).
  - Run under `AITASKS_TMUX_SOCKET=t2211seam` with a private `TMUX_TMPDIR` and a logging
    `tmux` shim first on PATH: 125 passed, **zero** tmux invocations, no socket
    created.
- measure_membership_scan: warm export 843 / 677 / 694 ms, uncached
  (`AIT_TRAIL_CACHE=0`) 3596 ms (18 trails, 0 unreadable) → interval kept at 60 s.

### 1. `lib/trail_links.py` — waves in the export, a public runner
- `build_export()`: each trail dict gains `"waves": {ref: [ordinal, ...]}`, built from
  `doc["waves"][*]["ordinal"]` over `entries[*]["task"]`. The change is additive:
  `EXPORT_FORMAT` stays 1 and `_valid_export` is unchanged, because the export always
  runs this checkout's code.
- Add `export_project(root: str) -> tuple` = `_collect_export("(this project)", root)`,
  documented as the one-root entry point (the sitrep TUI). No other behaviour change.

### 2. `lib/agent_launch_utils.py` — the task-carrying trails request
- `TRAILS_CARD_FOCUS_OPTION = "@aitask_trails_card_focus"`.
- `_TRAILS_TARGET_RE = ^(art:[a-z0-9][a-z0-9._-]{0,127})(?: ([0-9]+(?:_[0-9]+)?))?\Z`
  (the same handle grammar as `HANDLE_RE` and the same task grammar as
  `BOARD_TASK_ID_RE`; a test pins both equalities).
- `parse_trails_focus_target(value) -> None | (id, None) | (id, (handle, task | None))`
  goes through `parse_pane_request(value, _TRAILS_TARGET_RE)`, then splits the payload.
  `parse_trails_focus_request` is **unchanged** (the bare-handle grammar, pinned by
  `test_parse`).
- `mark_trails_card_focus(pane)` / `unmark_trails_card_focus(pane)` delegate to
  `mark_pane_receiver` / `unmark_pane_receiver` with the new option.
- `_trails_receiver_takes_task(pane) -> bool`: ONE `display-message -p -t <pane>
  "#{pane_id}\t#{@aitask_trails_app}\t#{@aitask_trails_card_focus}"`. True iff rc 0, the
  echoed pane matches, and both values are the same `_TRAILS_STAMP_RE` pid. Everything
  else is False.
- `trails_supports_task_focus(project_root) -> bool`: the `trails_supports_focus` text
  probe with the needle `'"--task"'`.
- `launch_or_focus_trails(session, project_root, handle, task_id=None)`:
  - validate the handle; with `task_id`, validate it with `BOARD_TASK_ID_RE`
    **before any tmux call** (`invalid task id`);
  - receiver branch: with `task_id` and a capable receiver → payload `f"{handle}
    {task_id}"`. With `task_id` and an incapable receiver → payload `handle`, and on
    success return `(True, "the running ait trails cannot focus a card — restart it to
    show t<id>")`;
  - cold branch: `--task <id>` appended when `trails_supports_task_focus`, else the plain
    argv and `(True, "this project's ait trails cannot focus a card — opened the trail
    only")`;
  - **without `task_id` every argv is byte-identical to today**, so the existing writer
    tests stay valid.
- All tmux goes through `_TMUX`.

### 3. `board/trails_app.py` — `--task`, the task-carrying mailbox, card focus
- `main()`: `--task ID` (accepts a `t` prefix, stored bare). `parser.error` when the ID is
  invalid or `--trail` is absent. Pass `initial_task=`.
- `TrailsApp.__init__(…, initial_task: str | None = None)`. `on_mount`:
  `_deliver_trail_focus(self._initial_trail, self._initial_task)`.
- Register worker: baseline read → `mark_trails_card_focus(pane)` → `mark_trails_receiver(pane)`.
  The capability is set first, so any writer that sees the stamp also sees it. A failed
  capability mark leaves an ordinary receiver. Unmount unmarks both.
- `_on_trail_focus_registered` / `_on_trail_focus_value` use `parse_trails_focus_target`.
  Malformed → the existing warning; `(handle, task)` → `_deliver_trail_focus(handle, task)`.
- `_pending_trail_focus` becomes `(seq, handle, task)`. `_deliver_trail_focus(handle,
  task=None)` / `_apply_trail_focus(seq, handle, task=None, *, announce)` carry it through
  the selector/modal deferral unchanged in shape. The final branch sets
  `self._pending_card = (seq, handle, task)` when `task`, else `None`, then calls
  `_open_trail_by_handle` as now.
- **The pending card request is resumable state, not a one-shot callback.**
  `_pending_card` is cleared ONLY when one of these happens:
  - (a) the card was focused;
  - (b) a definitive outcome was reported (trail failed to load / not a member / card
    never mounted after the hop budget — each with its toast);
  - (c) a newer request superseded it (`seq` no longer current);
  - (d) the active trail changed to a different handle. That is the user (or a later
    request) moving on.

  Scheduling an attempt never clears it, and a modal never consumes it.
- **Rule (d) lives at the one place every transition writes: `_trail_active`.**
  - Tab clicks (`_select_trail_tab`), `[` / `]` (`_step_trail_tab`), the numbered keys
    (`_goto_trail_tab`) and `ctrl+w` (`_close_trail_session`, which shows a neighbour or
    sets None) never pass through `_activate_trail`. The other writers are
    `_show_trail_session`, the `active_trail_handle` setter and the fresh-session branch
    of `_activate_trail`, five assignment sites in all.
  - So `TrailsApp` defines `_trail_active` as a **property** over a private slot
    (`self.__dict__["_trail_active_slot"]`). Its setter clears `_pending_card` when the
    new value's handle differs from the pending handle (None included), then stores the
    value.
  - The mixin's `_init_trail_state` assignment runs in `__init__` before `_pending_card`
    exists, so the setter reads it with `getattr(…, None)`.
  - An **intended** activation of the pending handle assigns that handle's session (a
    switch to its open tab, or a fresh session with the same handle), so it never
    cancels.
  - Closing a *different, inactive* tab writes nothing, so the request is kept, which is
    correct: the user has not left the requested trail.
- Override `_activate_trail(handle)`: call `super()`. Then, if `_pending_card` (still set,
  i.e. not cancelled by the transition) names this handle and its seq is current →
  `_schedule_card_focus()`. Every request-driven activation route (cached, rescan-then,
  already-open tab, other tab) passes through here.
- `_schedule_card_focus()` → `call_after_refresh(self._focus_trail_member, seq,
  self._MOUNT_HOPS)` for the current `_pending_card`. The `hops` budget counts only
  refreshes **without a modal**, waiting for the cards to mount.
- `_focus_trail_member(seq, hops)`, which re-reads `_pending_card` and acts only while it
  is still `(seq, …)`:
  - stale or cleared → return;
  - **a modal is active → return WITHOUT clearing and without spending hops**. The resume
    hook re-schedules (below), however long the modal stays open;
  - the active trail is not the pending handle → **clear** and return. Defensive: the
    `_trail_active` setter already cleared it on the transition, and an attempt is only
    ever scheduled while the pending handle is active, so a mismatch always means the
    user left;
  - active session error → toast "t<task> not shown: trail <h> did not load", clear;
  - not a member of `self._trail_doc` (by `trail_ref_to_local_id(ref,
    self._get_local_project())` over the waves' entries) → toast "t<task> is not in trail
    <h> (any more) — trail opened", clear;
  - else find the card with that local id among `self.query(TaskCard)` (via
    `trail_entry`). No card yet and hops > 0 → re-queue with `hops - 1`. Found →
    `card.focus()`, `card.scroll_visible()`, the active session's
    `focus_filename`/`focus_col_id` updated (so a tab switch back keeps it), clear.
    Hops exhausted → toast "t<task> is in trail <h> but its card is not visible", clear.
- Resume: `_drain_trail_focus` (already called by `TrailsScreen.on_screen_resume`) first
  applies a pending trail request as now. Otherwise, if `_pending_card` is set and names
  the active trail, it calls `_schedule_card_focus()` with a fresh hop budget. So a
  modal opened after activation, but before the card was focused, cannot lose the
  request.
- Module docstring: the `--task` flag and the capability stamp.

### 4. `sitrep_tui/sitrep_tui_widgets.py` (new, tiny)
- Move `SelectOnClickList` here unchanged. `sitrep_tui_app.py` re-imports it under the
  same name, so the tests' imports keep working.

### 5. `sitrep_tui/sitrep_tui_trails.py` (new) — membership model + picker
- Frozen dataclasses:
  - `TrailRef(handle, name, waves: tuple)` with `label()` → `"Sitrep follow-ups
    (art:trail-sitrep-followups) — wave 1"` (waves joined; no wave → no suffix) and
    `short()` → `"Sitrep follow-ups (w1)"`;
  - `TaskTrails(state, trails=(), reason="")`;
  - `Membership(ok, reason, partial, local_project, by_task)` with `lookup(task_id) ->
    TaskTrails`. States as pinned above.
- `membership_from_export(data, errors) -> Membership` (pure). The ownership rule is
  `parse_ref` and project == `data["local_project"]`. Trails with `load_error` contribute
  nothing and make it partial; a PARTIAL error detail becomes `partial`; no data →
  `ok=False`.
- `scan_membership(root) -> Membership`: blocking (thread workers only), never raises.
  It calls `trail_links.export_project(root)`; an exception becomes `ok=False,
  reason=<exc>`.
- `TrailPickerDialog(task_id, trails)` (`GuardedModalScreen`, `LabelFilterDialog`'s
  geometry rules):
  - title "Show t<id> in which trail?";
  - a `SelectOnClickList` of `Text(trail.label())` rows (click selects, Enter opens);
  - a docked Cancel button, `_fit_list` on mount/resize, the highlight kept in view;
  - `escape` cancels;
  - returns the handle or None.

### 6. `sitrep_tui/sitrep_tui_actions.py` — the action and the session jump
- `ACTION_BINDINGS += ("open_in_trails", "z", "Trails")`; `ITEM_ACTIONS` adds it;
  `_ACTION_LABEL["open_in_trails"] = "Show in trails"`.
- `_init_actions(…, trails_scan=None)`. The membership state is `self._trails:
  Membership | None`, plus `_trails_busy`, `_trails_dirty` and `_trails_gen`.
  - `trails_for(task_id) -> TaskTrails` returns `off` with no scanner, `looking` before
    the first result, else `lookup`.
  - `_kick_trails_scan()` starts `@work(thread=True, group="sitrep-trails",
    exit_on_error=False) _trails_worker` (or sets dirty).
  - The worker's callback `_on_trails_scanned(m)` stores the result, calls
    `refresh_bindings()`, then updates **only** the top screen when it is an
    `ItemDetailScreen`, `is_active_screen(top)`, and its task id resolves: it calls
    `top.set_trails(self.trails_for(tid))`. Then it reruns once if dirty.
  - `_start_actions` kicks the first scan and sets the interval (only with a scanner).
- `_item_action_ok("open_in_trails")`: `task_ref_id(item)` set and
  `trails_for(id).state == "in"`.
- `action_open_in_trails()`: `_resolve_action_item` (re-resolve, the moved-rev refresh,
  and the predicate on the current item), then the trail choice per the pinned
  details/main rule. The details' highlighted trail comes from
  `screen.highlighted_trail()`; a handle no longer in `trails_for` → refuse with a
  toast. The picker's callback re-resolves once more, like the pick dialog: same num,
  predicate ok, same task id, handle still listed. Otherwise "c<N> changed while the
  dialog was open — not shown".
- `open_trail_from_details(screen, handle)`: the details' Enter path. It runs the same
  re-resolve (`_resolve_action_item("open_in_trails")`, with `self.screen is screen`),
  checks the handle is still listed, then starts `_trails_jump_worker`.
- `_trails_jump_worker(handle, task_id)` (thread, exclusive group "sitrep-trails-jump")
  → `open_in_trails(root, handle, task_id)` notices.
- Refactor the session jump into `_jump_in_project_session(root, launch, texts)`, shared
  by `open_in_board` (**its messages byte-identical**, pinned by `OpenInBoardTests`) and
  the new `open_in_trails(root, handle, task_id, name="")`:
  - its cold hint is `./ait trails --trail <h> --task <id>`;
  - its success text is "Showing t<id> in trail <name>";
  - its failed-switch text is "ait trails opened in session '<dest>' but switching there
    failed — switch with: tmux switch-client -t =<dest>".
  - It calls `alu.launch_or_focus_trails(dest, project, handle, task_id)`. A returned
    warning becomes a warning notice when no switch happened.
- `NEXT_STEPS`: no change (trails are a launch, not a next step).

### 7. `sitrep_tui/sitrep_tui_app.py` — details rows, triggers, main
- `ItemDetailScreen(…, trails: "TaskTrails | None" = None)`; None for a non-task item.
  - Body: after the `Created` line, `_field("Trails", …)`:
    - `in` → the joined `short()` names;
    - `none` → "none";
    - `looking` → "looking…";
    - `unknown` → "unknown (<reason>)";
    - omitted for `off`/None. All values are plain `Content` parts.
  - Links: right after "Task description", one `Option(Text(trail.label()),
    id=f"trail:{trail.handle}")` per trail. **The option id is the row's stable identity,
    the handle, never its position.** Handles are unique per membership (discovery
    dedupes by handle) and option-id safe (`art:[a-z0-9._-]`; `partition(":")` keeps
    `art:…` whole as the arg). Partial → plus a disabled "Trails: some trails could not
    be read (<partial>)" row. `looking` → one disabled "Trails: looking…" row. `unknown`
    → one disabled "Trails: unknown (<reason>)" row and **no** trail rows. `none`/`off` →
    nothing.
  - `set_trails(tt)`: no-op when equal. Otherwise update `#sd-body` and rebuild
    `#sd-links` (`clear_options` + `add_options(self._link_options())`), then restore the
    highlight **by option id**:
    - the highlighted row's id still exists → re-highlight it. Since trail ids are
      handles, a trail that moved position (removal before it, reorder) stays selected;
    - **it vanished** (that trail no longer lists this task) → `highlighted = None`. No
      row is actionable, so Enter does nothing (`_link_ready` is False) and `z` takes its
      no-highlight path (1 trail → that trail, 2+ → the picker). The screen shows a
      toast: "<trail name> no longer lists t<id> — selection cleared".
    - Never fall back to a neighbouring position.
    - `on_screen_resume` re-pulls `app.trails_for(...)` through the same `set_trails`.
  - `highlighted_trail() -> str | None`: the handle from a highlighted `trail:` row's id.
  - `on_option_list_option_selected`: `kind == "trail"` →
    `app.open_trail_from_details(self, arg)`. `arg` is the handle taken from the selected
    option's id, never an index into the screen's current `_trails`. The app re-validates
    that handle against the current membership.
- `open_item`: pass `trails=self.trails_for(tid)` for a task item, and kick a rescan.
- `_apply`: kick a rescan (debounced) after the metas.
- `SitrepTuiApp.__init__(…, trails_scan=None)`; `main()` passes
  `sitrep_tui_trails.scan_membership`.
- `check_action`: `open_in_trails` is in `ITEM_ACTIONS`, so the main + details gating is
  already shared.
- Module docstrings: the `z` key and the trail rows.

### 8. Docs (framework only; user docs are t2211_6)
- `aidocs/framework/tmux_gateway.md`:
  - the `@aitask_trails_focus` row → payload `"<id> <art: handle>[ <task id>]"`, the task
    form only to a capable receiver;
  - a new `@aitask_trails_card_focus` row (set by the trails app to its pid before its
    receiver stamp; unset on exit; read by `launch_or_focus_trails`; meaning: this
    receiver accepts the task form; not a helper marker).
- `aidocs/framework/sitrep.md` "TUI's actions" paragraph: `z` / trail rows, the
  membership states and the partial rule.
- `aidocs/framework/tui_conventions.md`: add the two new sitrep_tui modules if the doc
  maps sitrep_tui modules (check). The board package map is unchanged (no new board
  module).

### 9. Tests
- `tests/test_trails_focus_writer.py`, new classes only:
  - `parse_trails_focus_target` table: old form, task form, `t12` refused, extra
    tokens, bad task, a bad id;
  - the grammar-equality pins vs `HANDLE_RE` / `BOARD_TASK_ID_RE`;
  - `_trails_receiver_takes_task` argv and answers (match, pid mismatch, empty, rc≠0,
    wrong echo);
  - `launch_or_focus_trails(..., task_id)`: a capable receiver gets `<h> <id>`; an
    incapable one gets `<h>` + the warning; cold argv with `--task` (support patched
    True) and without (+ warning); a malformed task id is refused with `calls == []`;
    `task_id=None` keeps today's calls exactly.
- `tests/test_trails_app.py`:
  - `_PaneStore` gains `mark_cap`/`unmark_cap` and patches for the two new names;
  - new `TrailCardFocusTests(TrailFocusTests)`, using a doc whose target is the
    **second** member, so the default first-card focus cannot pass by accident:
    - main: `--trail h --task 12` → `initial_task="12"`; `t12` → "12"; `--task`
      without `--trail` / invalid → SystemExit, app not built;
    - cold boot with `initial_task` focuses that card;
    - a mailbox `<h> <id>` focuses it, for a new trail, the already-active trail and
      another open tab;
    - a task not in the trail → toast + trail opened;
    - a request held by a modal → the card is focused after close;
    - **the post-activation window:** wrap `_focus_trail_member` so its first call
      pushes a modal (the trail summary / entry-detail modal) and then runs the original.
      The original sees the modal and defers. Keep the modal open across more than
      `_MOUNT_HOPS` forced refreshes (`_settle` several times), and assert
      `_pending_card` is still set and no card focus changed. Dismiss it → the
      **second** member's card is focused. Negative controls:
      - (1) a newer request (another task) sent while the modal is open supersedes:
        after dismissal the newer card is focused, never the old one;
      - (2) **real tab navigation cancels it.** The tab handlers refuse to act under a
        modal, so this control runs in the *delayed attempt* window instead:
        - deliver the request, open and dismiss the modal as above, but patch
          `_schedule_card_focus` to record the call instead of queueing it. `_pending_card`
          is then set, with no modal and the pending trail active;
        - leave through the **real** path, one subTest per route: `pilot.press("]")`, the
          numbered key `"2"`, a `pilot.click` on the other tab in `#trail_tabs`, and
          `ctrl+w` closing the pending trail's own tab;
        - assert `_pending_card is None` right after each route;
        - come back (`"["` / `"1"` / click; for `ctrl+w`, re-open nothing). Run the
          recorded stale attempt, then open and dismiss another modal (the resume drain);
        - assert the tab's own saved focus (the card the user had) is restored, never the
          requested second member.
        - Positive twin: closing a *different, inactive* tab with the pending trail
          active keeps `_pending_card`, and the next drain focuses the requested card;
      - (3) pre-fix control in an isolated scratch copy: a variant that clears
        `_pending_card` at scheduling time fails this test (record the result);
    - an old-form request still opens with the default focus;
    - a malformed task suffix → the warning, nothing opened, not retried;
    - the register log order is verify → read → mark_cap → mark; unmount unmarks both;
    - the focused card survives the drift re-render (settle, then assert).
- `tests/test_trails_focus_mailbox_live.py`, new tests on the same throwaway server:
  - a capable stamped pane (both options set to the live pid) receives `<h> <id>`;
  - a stamped pane without the capability receives `<h>` and the call returns the
    warning;
  - with no receiver and the `./ait` sleep stub, the new `trails` window's start command
    has `--task <id>` (via `list-panes -F '#{pane_start_command}'`; the
    `test_board_focus_mailbox_live.py` stub pattern).
- `tests/test_sitrep_tui_trails.py` (new):
  - `membership_from_export` table: 0/1/2 trails, waves, child ids, `#t` spelling,
    foreign/unparseable refs ignored, a failed blob (`load_error`) → the known task
    `in` + partial note and an unlisted task `unknown`, export failure → all `unknown`,
    empty `local_project` → `unknown`;
  - `scan_membership` exception → `unknown`, never raises;
  - one end-to-end `export_project` over a real fixture repo with two trails (the
    `tests/test_trail_links.py` real-repo helpers: `_repo` / `_task` / `_store_trail`,
    imported by name), asserting the waves key and a task in two trails;
  - picker: rows, a click only selects, Enter returns the handle, Esc → None, fit at
    short sizes with real `pilot.click`.
- `tests/test_sitrep_tui_actions.py`, new classes with a stub `trails_scan` (an Event
  can gate it):
  - bindings matrix: `z` × {in, none, unknown, looking, off} × {main, details, viewer,
    Q&A}, plus triage / non-task / xref items hidden;
  - main `z`: 1 trail → `open_in_trails` stub called (root, handle, task id); 2 →
    picker → Enter on the 2nd row → called with that handle; Esc → nothing;
  - details: the `Trails` body line and one links row per trail; Enter on a row →
    called with the row's handle + task id; a click only selects; `z` with a trail row
    highlighted → that handle; with none highlighted and 2 trails → picker;
  - **selection identity across a membership refresh.** Open the details with
    membership [A, B, C] and highlight B's row. Deliver a rescan result, then assert the
    highlighted option id and what Enter / `z` launch:
    - [B, C] (removal before it) → B still highlighted; Enter → the launcher called
      with B;
    - [C, B] (reorder) → B still highlighted; `z` → B;
    - [A, C] (B removed) → nothing highlighted; Enter launches nothing; `z` → the
      picker (2 trails), and the launcher is not called; the toast names B.
    - Pre-fix control in an isolated scratch copy: positional `trail:{i}` ids make the
      first case launch C (record the result);
  - "looking…" is replaced when the gated worker finishes. Its callback leaves alone a
    details screen that was closed or replaced (another item's details) meanwhile: no
    error, and the new screen's rows are unchanged;
  - a failed lookup → the disabled unknown row and no trail rows, `z` hidden;
  - partial → the known rows plus the disabled partial row, `z` shown;
  - a moved rev (an external `update`) → details refreshed, launcher not called, for both
    `z` and Enter on a row;
  - picker callback: the item changes while the dialog is open → not shown;
  - `OpenInTrailsTests`, the `OpenInBoardTests` cases for `open_in_trails` (own session,
    switch, failed switch names the session, not in tmux → cold hint, no longer owned,
    no session, the launcher warning).
- Existing suites stay green: `tests/test_trails_focus_writer.py`, `tests/test_trails_app.py`,
  `tests/test_trails_focus_mailbox_live.py`, `tests/test_trail_links.py`,
  `tests/test_sitrep_tui_app.py`, `tests/test_sitrep_tui_actions.py`,
  `tests/test_shortcut_scopes.py`.

### Post-phase (risk mitigations)
(none)

## Verification
- The tests above; `bash tests/run_all_python_tests.sh --test-dir tests` under `set -o
  pipefail` (read the last line); `bash tests/test_no_raw_tmux.sh`;
  `bash tests/test_no_lib_to_tui_import.sh`.
- Manual (t2211_7 owns the checklist), in a real sitrep window:
  - a task item's details list its trails;
  - Enter on a trail row opens it with the card focused;
  - `z` from the list, with trails running (handoff) and not running (new window), and
    from another session (client switch).
- After commit: `ait note` to t2211_6 (key `z`, the details rows, `--task`, the states)
  and t2211_7 (the manual checks above), hedged as tree-relative to the commit SHA.

## Risk

### Code-health risk: low
- The trails mailbox gains a second request grammar and a capability stamp, on a live, multi-process handoff path. A writer/receiver mismatch would silently stop `ait trails` focus requests, or show "malformed" toasts on older apps · severity: low (residual — addressed by inline pre-phase characterize_trails_mailbox) · → mitigation: inline pre-phase characterize_trails_mailbox
- New tmux-touching functions (`mark_/unmark_trails_card_focus`, `_trails_receiver_takes_task`) are called from TrailsApp's register worker. A test fixture that patches the old names but not the new ones would run real `tmux set-option` against the developer's server · severity: low (residual — addressed by inline pre-phase tmux_seam_inventory) · → mitigation: inline pre-phase tmux_seam_inventory
- The sitrep TUI grows another worker + interval and a rebuildable links list. The new module and the shared `_jump_in_project_session` keep the files bounded; `open_in_board`'s messages stay pinned by `OpenInBoardTests` · severity: low · → mitigation: none
- `trail_links` export gains an additive `waves` key. Its only other consumer (`scan_linked_trails`) ignores unknown keys · severity: low · → mitigation: none

### Goal-achievement risk: medium
- Card focus inside TrailsApp races its own activation refocus, the startup rescue (`apply_filter` focuses the first card), the tab-restore refocus and the drift re-render. A wrong order lands focus on the first card, and the feature looks done but is not. A modal opened after activation is handled by the resumable pending request (review fix) · severity: medium · → mitigation: none (covered by the second-member TrailCardFocusTests across all four activation routes and the post-activation modal window)
- The membership scan's cost (one `trail_links.py export` subprocess per trigger) is unmeasured, so the 60 s rescan interval is a guess · severity: low (residual — addressed by inline pre-phase measure_membership_scan) · → mitigation: inline pre-phase measure_membership_scan
- Repos without `project.name` match no member (the board's rule), so every task reads `unknown` there · severity: low · → mitigation: none

### Planned mitigations
- timing: pre-phase | name: characterize_trails_mailbox | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — trails mailbox grammar/capability mismatch | desc: trails writer/app/live suites + OpenInBoardTests green before and with unedited bodies after; one capability-bypass mutant must go red
- timing: pre-phase | name: tmux_seam_inventory | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — tests reaching a real tmux server | desc: patch the new capability functions in every TrailsApp mailbox seam; run test_trails_app.py against a non-existent private socket and prove it is never created
- timing: pre-phase | name: measure_membership_scan | type: performance | priority: low | effort: low | inline_risk: low | added_complexity: low | addresses: goal-achievement — unmeasured scan cost | desc: time trail_links.py export cold/warm in this repo and set TRAILS_RESCAN_INTERVAL from it

## Step 9
Commit `feature: … (t2211_10)` (code, named paths) and `ait: Update plan for t2211_10`,
then archive per the shared workflow.

## Post-Review Changes

### Change Request 1 (2026-11-10)
- **Requested by user:** `_focus_trail_member`'s verified-success branch (the target card already holds the focus) returned without revealing the card. With its column scrolled away, a request for that card cleared `_pending_card` and left the card off-screen. Reveal it in that branch and test viewport visibility, not only the focused filename.
- **Changes made:**
  - The success branch calls `card.scroll_visible(animate=False)`; the focus branch uses `animate=False` too.
  - New `TrailCardFocusTests::test_a_focused_card_scrolled_out_of_view_is_revealed_by_a_request`:
    - a tall wave puts the target last, after 20 ghost members;
    - the first request is asserted in the column viewport (`_in_view`: virtual offset vs `scroll_offset` and the scrollable height);
    - the user scrolls the column home with focus kept (precondition: out of view);
    - a second request for the same card → in view again, `_pending_card` cleared.
  - Pre-fix control in a scratch copy (no reveal in that branch): the test fails already at the FIRST request's viewport assertion. So the defect was wider than reported: on a fresh render `focus()` / `scroll_visible` run before the column's layout settles, and the verified branch is what really reveals a card far down a long wave.
- **Files affected:** `.aitask-scripts/board/trails_app.py`, `tests/test_trails_app.py`

## Final Implementation Notes
- **Actual work done:**
  - `lib/trail_links.py`: the export gains an additive per-trail `waves` (`{ref: [ordinal…]}`, `_member_waves`) and a public one-root runner `export_project(root)`.
  - `lib/agent_launch_utils.py`:
    - `TRAILS_CARD_FOCUS_OPTION` (`@aitask_trails_card_focus`) and the `_TRAILS_TARGET_RE` grammar;
    - `parse_trails_focus_target` (`parse_trails_focus_request` unchanged);
    - `mark_/unmark_trails_card_focus`, `_trails_receiver_takes_task` (one `display-message`, pid equality) and `trails_supports_task_focus`;
    - `launch_or_focus_trails(…, task_id=None)`: task form only to a capable receiver, bare handle + warning otherwise; `--task` on the cold path when supported. The argv without a task is unchanged.
  - `board/trails_app.py`:
    - `--task` (needs `--trail`, `t` prefix dropped) and `initial_task`;
    - the capability stamped before the receiver stamp and unmarked after it;
    - `_pending_trail_focus` carries the task; resumable `_pending_card`;
    - `_trail_active` is a property whose setter cancels the card request on any move to another trail;
    - `_activate_trail` override → `_schedule_card_focus`; `_drain_trail_focus` resumes a card a modal interrupted;
    - `_focus_trail_member` verifies focus on the next refresh and reveals the card (`scroll_visible(animate=False)`).
  - `sitrep_tui/sitrep_tui_widgets.py` (new, `SelectOnClickList` moved; re-exported from the app).
  - `sitrep_tui/sitrep_tui_trails.py` (new): `TrailRef` / `TaskTrails` / `Membership`, `membership_from_export`, `scan_membership`, `TrailPickerDialog`, `TRAILS_RESCAN_INTERVAL`.
  - `sitrep_tui_actions.py`:
    - `z` (`open_in_trails`) in `ACTION_BINDINGS` / `ITEM_ACTIONS`;
    - the scan worker (one at a time + dirty rerun; the callback writes only the active details screen);
    - `action_open_in_trails` (highlighted row / single trail / picker with a re-resolving callback), `open_trail_from_details`;
    - `_jump_in_project_session`, shared by `open_in_board` (messages unchanged) and the new `open_in_trails`.
  - `sitrep_tui_app.py`:
    - `ItemDetailScreen(trails=…)`: the `Trails` body line, handle-keyed rows (`trail:<handle>`), disabled looking / unknown / partial rows;
    - `set_trails` restores the highlight by id (cleared + toast when the trail vanished), plus `highlighted_trail` and `on_screen_resume`;
    - rescans on `_apply` and on opening a task item's details; `main()` passes `scan_membership`.
  - Docs: `tmux_gateway.md` (new `@aitask_trails_card_focus` row; the payload grammar in the `@aitask_trails_focus` row) and `sitrep.md` (show in trails + membership).
  - Tests:
    - new `tests/test_sitrep_tui_trails.py` (14) and `tests/test_sitrep_tui_trails_actions.py` (26);
    - `test_trails_focus_writer.py` +4 classes; `test_trails_app.py` `TrailCardFocusTests` (16) + the `_PaneStore` capability seam; `test_trails_focus_mailbox_live.py` +4 live tests.
- **Deviations from plan:**
  - (1) The details tests live in a new `tests/test_sitrep_tui_trails_actions.py` (it reuses `test_sitrep_tui_actions._Case`), because that file is already 1,500+ lines.
  - (2) `_focus_trail_member` treats `focus()` as unverified and checks on the next refresh. Right after an activation the found card may still be the outgoing render's (removal is asynchronous), and the startup rescue then focuses the first card. Found with instrumented logging; the "mailbox request" and "held by a modal" tests failed intermittently before this.
  - (3) Message templates in `_jump_in_project_session` are callables, not `str.format` templates: a trail name is untrusted text and may contain braces.
  - (4) `_TRAILS_TARGET_RE` ends in `\Z`, so it refuses a trailing newline that `HANDLE_RE`'s `$` accepts. This one difference is pinned in a test.
  - (5) No startup kick in `_start_actions`: the host's first `_apply` already kicks the scan.
- **Issues encountered:**
  - The full-suite run: 1 failure out of 11,855, `test_board_movement.py::BoardMovementBenchmarkTests::test_attribution_tier_localises_an_injected_cost`: "`render` absorbed 38.9 ms of a cost injected into `refocus` (bound 25.0 ms)".
    - It came during a load average of about 6 (parallel suites from other sessions);
    - it passed 3/3 in isolation and in the post-review run of the whole module (201 passed);
    - this task does not touch board rendering. Load-dependent timing, not caused by this change.
  - Mutants (isolated scratch copies), each red only on its target:
    - capability ignored → the older-receiver writer test;
    - bounded retry + drop under a modal → the post-activation-window test;
    - cancellation only in `_activate_trail` → `test_leaving_the_trail_by_any_route_cancels_the_card`;
    - positional `trail:{i}` ids → all 3 `SelectionIdentityTests` (at the highlighted-id assertion);
    - no reveal in the verified branch → the new viewport test (at its first request).
    - Also run: a one-shot (cleared at scheduling) variant → 7 failures, including the post-activation test.
- **Key decisions:**
  - Backward compatibility is by capability, not by grammar. An older TrailsApp must still open the trail, and its parser refuses any second token. So the writer reads the receiver's `@aitask_trails_card_focus` and sends the task form only when its pid equals the receiver stamp's.
  - Membership goes through the `trail_links` export subprocess (cwd = root), because trail discovery is cwd-relative and the TUI's root is an argument. The content-keyed discovery cache makes a warm scan cost about 0.7 s.
  - The details screen pins `z`: the highlighted trail row, else 1 trail → open, 2+ → the picker.
- **Upstream defects identified:**
  - `.aitask-scripts/lib/artifact_manifest.py:58` — `HANDLE_RE` ends in `$`, so it also matches a handle with a trailing newline (`"art:a\n"`). Its validators (`launch_or_focus_trails`, `trails_app.main --trail`) therefore accept a newline-terminated handle.
- **Notes for sibling tasks:**
  - **t2211_4 (agent requests):** `z` is taken. Item actions go in `actions.ITEM_ACTIONS` with a predicate in `_item_action_ok`, and `check_action` already gates main + details. For a list of choices, `trails_model.TrailPickerDialog` (a click selects, Enter opens) is the pattern. Details rows that follow background state are keyed by stable identity (`trail:<handle>`) and restored by id; see `ItemDetailScreen.set_trails`.
  - **t2211_6 (docs):**
    - key `z` "Trails" (main list + details);
    - the details `Trails` line and the "In trail: <name> (<handle>) — wave N" rows (Enter opens);
    - the picker for 2+ trails;
    - `ait trails --trail <h> --task <id>`;
    - the states (looking / unknown / partial);
    - a running trails too old for the task form still opens the trail and says so.
  - **t2211_7 (manual):** in a real sitrep window:
    - details list the trails;
    - Enter on a row opens `ait trails` with the card focused;
    - `z` with trails running (handoff), not running (new window), and from another session (client switch);
    - a long wave: the card is scrolled into view.
