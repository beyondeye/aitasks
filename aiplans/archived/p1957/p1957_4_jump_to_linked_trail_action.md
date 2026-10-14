---
Task: t1957_4_jump_to_linked_trail_action.md
Parent Task: aitasks/t1957_trail_cross_repo_blockers_and_linked_trails.md
Sibling Tasks: aitasks/t1957/t1957_1_*.md, aitasks/t1957/t1957_2_*.md, aitasks/t1957/t1957_3_*.md, aitasks/t1957/t1957_5_*.md
Archived Sibling Plans: aiplans/archived/p1957/p1957_*_*.md
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5_5 @ 2026-10-14 00:28
---

# t1957_4 — `L` Linked Trails: list linked trails in other repos and jump to one

## Context

Part of t1957 (parent plan `aiplans/p1957_trail_cross_repo_blockers_and_linked_trails.md`).
t1957_2 shipped `ait trails --trail <h>` plus the pane-addressed focus mailbox and
`launch_or_focus_trails(session, root, handle) -> (ok, err)`, which does not
switch the client. t1957_3 shipped
`trail_links.scan_linked_trails(doc) -> LinkScan(links, errors, complete)`.
This child adds the user-facing action. From the active trail in By-Trail
(board `z` view, or stand-alone `ait trails`), `L` searches the other projects
and lists the linked trails. Picking one switches the tmux client to that
project's session, with that trail open in its `ait trails`. If the project has
no running session, one is started first (user decision).

## Verification findings (plan vs. current code, 2026-10-13)

Line anchors still hold: `TRAIL_BINDINGS` ~101, `_supersede_trail_workers` ~349,
`_switch_trail_session` ~491, `_close_trail_session` ~499, `_open_trail_select`
~968, `_activate_trail` ~1132, `owned_lookup_session` ~548,
`launch_or_focus_trails` ~2684, `_ensure_session_live` ~639. `L` is unbound at
App level on both hosts. The board's `L` = `lock` sits on `TaskDetailScreen`,
and its `l` = `view_locked` is a different action, so the uppercase-sibling
rule does not apply. Refinements:

1. **Seven error kinds**, not four (note from t1957_3): stale, not_found,
   export_failed, timeout, partial (that project's links ARE still returned),
   registry_unreadable (`project` = the registry path) and local_unreadable (a
   member of THIS trail). Each kind gets its own wording.
2. **No count in the "Searching…" notice.** The candidate set is built inside
   the scan, from the registry plus the trail's direct references, so N is not
   known on the UI thread. The notice therefore says "Searching for linked
   trails in other projects…". Measured scan time is about 1.5s, so the notice
   is enough feedback.
3. **A trail that has not loaded must not be scanned.** A doc that is `{}` or
   `None` has no members. The scan would then come back `complete=True` with no
   links, which is the definitive "no linked trails" for a trail whose members
   are unknown. The `L` key (`check_action`) and the action both require a
   loaded doc with no load error (`_trail_link_ready()`).
4. **Finding the target session.** `owned_lookup_session(root)` only considers
   two sessions: the caller's own session (which belongs to this project, X)
   and Y's configured `default_session`. A Y session running under another name
   (`ait ide --session foo`) would be missed, and the bootstrap would then start
   a second session for Y. The new `live_project_session(root)` walks all live
   sessions with the same attribution rule the switcher's discovery uses
   (`_collect_live_roots`), and prefers the `default_session` name when several
   sessions match.
5. **Checks happen in the jump worker, at execution time.** The worker re-checks
   that the root still holds `aitasks/metadata/project_config.yaml`. The scan
   proved the link by its realpath root, and resolving the project name again
   could land in a different repo.
6. **"Not in tmux" covers two cases:** not in tmux at all, and in a different
   tmux server. `current_tmux_session()` returns None for both, and
   `switch-client` through the gateway could not reach this client in either
   case. The worker then notifies the manual command
   `ait projects exec <Y> -- ./ait trails --trail <h>` and starts, launches and
   switches nothing.
7. **Version skew skips the launch.** `launch_or_focus_trails`'s cold path would
   run `./ait trails --trail <h>` in a repo whose `trails_app.py` has no
   `--trail`. argparse would reject it and the window would die. In that case
   the worker skips the launch, warns ("<Y> runs an older aitasks… `ait
   upgrade`"), and still switches to the session (parent risk record).
8. **No modal on top of another modal.** Pushing `LinkedTrailsScreen` above a
   `LoadingOverlay` (the board's sync) would strand the overlay, because its pop
   checks `self.screen is overlay`. A result that arrives while a modal is up is
   dropped, and the user is told to press `L` again (`_modal_is_active`).
9. **Text from other repos is untrusted.** Project names, handles and error
   details come from other repos' exports. Modal rows use `rich.Text`, never
   markup, and every notice that carries them passes `markup=False`.
10. **Pinned surfaces that change deliberately:**
    - `TRAIL_BINDINGS` count 9 → 10 (`tests/test_trail_screen_host_protocol.py`);
    - the board keymap golden (`tests/test_board_keymap_characterization.py`)
      gains an `L` row, and `trail_linked` joins every "hidden" set (no trail
      is active in that fixture);
    - the new `board_trail_view` top-level names join `VIEW_ONLY_NAMES`
      (`tests/test_board_trail_view.py`), and `aitask_board.py` imports them
      back (single-home contract).
11. **The bootstrap extraction keeps the switcher's tests valid.** Those tests
    patch the global `subprocess.run`, so they exercise the moved helper
    unchanged. That includes the `argv[1].endswith("tmux_bootstrap.sh")` check:
    the helper lives in `lib/` too, so the script path is identical.
12. **Source revision (review).** Generation, view and session identity are not
    enough. `_apply_trail_content` (~401) replaces `session.doc` /
    `session.error` on the SAME `TrailSession`, both when a reload lands and
    when a discovery result is reconciled. A search started on revision 1 would
    therefore display links, or a definitive empty result, for revision 2's
    members or load error.
    - **Fix:** at press, take a `copy.deepcopy` snapshot of the doc and capture
      the error string. The worker scans the SNAPSHOT, so the thread never
      reads the live doc. At delivery, require `origin.doc == snapshot and
      origin.error == source_error`.
    - The check is by **equality, not identity** (review, round 2).
      `_on_trail_reload` passes `restart_drift=True`, and `_apply_trail_content`
      then assigns `session.doc = doc` even when the content is equal. An
      identity check would discard a valid search after an ordinary unchanged
      reload. Equality against a private snapshot also survives a doc mutated
      in place.
    - The user is still waiting on the same trail, so this drop says why
      ("…changed during the search — press L again"). A user who moved away
      (switch / close / leave) is dropped silently.
13. **Warnings must be read before the switch (review).** After a successful
    `switch-client` the source App sits in the session the user just left, so
    any notice it shows there is never seen. That affects the version-skew
    warning (the trail is deliberately not opened) and the bootstrap's
    fallback-session warning.
    - **Fix:** split the jump into *prepare* and *finish*.
      - Prepare covers the checks, the session lookup / bootstrap and the skew
        probe. It has no client effect.
      - Finish covers the launch, then the switch.
    - When prepare produced warnings, a confirm dialog shows them in the source
      App BEFORE anything switches, with "Switch to <session>" / "Stay here".
      Without warnings, finish runs immediately.
    - **Invariant:** the source App only shows notices on a path where the
      client did NOT switch, and a successful finish returns no notices.
14. **Finish re-checks the destination (review, round 2).** The confirm dialog
    can stay open for any length of time. Meanwhile Y's session may stop and
    its name may be reused by another project. `launch_or_focus_trails`
    trusts the session it is given, so a stale name would send the handle to
    that other project's `TrailsApp` and teleport the client there.
    - **Fix:** `finish` first re-checks the project marker and that THIS exact
      session is still attributed to `link.root`. A new public
      `session_owned_by(session, root)` wraps the existing
      `_sessions_owned_by(root, {session})`, which attributes only that
      candidate.
    - Either check failing → the error "The tmux session for <p> changed
      before the jump — press L to try again", with no launch and no switch.
    - It runs on every finish, not only after a dialog. This is the
      execution-boundary rule, and it costs one `list-sessions`.
15. **No warning dialog over another modal (review, round 2).** Picking a
    link and then pressing `s` while `prepare` runs opens discovery's
    `LoadingOverlay`. A warning dialog pushed on top would strand that
    overlay, the same hazard as finding 8.
    - **Fix:** when `prepare` returns warnings while `_modal_is_active()`, the
      callback pushes nothing, clears busy, and notifies "Jump to <h> paused —
      a dialog was open. Press L to try again". An error notice and a
      warning-free finish push nothing, so they are unaffected.

## Implementation

### 1. `lib/agent_launch_utils.py` — session helpers (next to `launch_or_focus_trails`)

- `@dataclass(frozen=True) class BootstrapResult: ok: bool; error: str = "";
  stale: bool = False; default_session_problem: str | None = None`.
- `bootstrap_project_session(project_root: Path, timeout: float = 15) -> BootstrapResult`.
  This is the subprocess call lifted out of `_ensure_session_live`:
  `subprocess.run(["bash", <lib>/tmux_bootstrap.sh, str(root)], capture_output=True, text=True, timeout=timeout)`.
  - `TimeoutExpired` / `FileNotFoundError` / `OSError` → `ok=False, error=str(exc)`.
  - A non-zero exit → `ok=False`, with `error` = the last stripped stderr line,
    or `"unknown error"` when stderr is empty. `stale` is set when stderr
    contains `"BOOTSTRAP_FAILED:stale_path"`.
  - Exit 0 → `ok=True` and
    `default_session_problem=parse_default_session_unreadable(stderr)`.
- `live_project_session(project_root: Path) -> str | None`. It walks every
  live session with
  `_collect_live_roots(_TMUX.run, _read_registry_entry)` and keeps those whose
  `_root_key(root)` equals `_root_key(project_root)`. If the root's
  `load_tmux_defaults(root)["default_session"]` is among them, that session is
  returned; otherwise the alphabetically first one; otherwise None.
- `trails_supports_focus(project_root: Path) -> bool`. It returns True only
  when `<root>/.aitask-scripts/board/trails_app.py` is readable and contains
  `"--trail"`. When the file cannot be read (`OSError`) or is missing, it
  returns False: support cannot be proven, so the caller does not launch.
- `switch_client_to(session: str) -> bool`, which runs
  `_TMUX.run(["switch-client", "-t", tmux_session_target(session)])` and
  returns `rc == 0`.
- `session_owned_by(session: str, project_root: Path) -> bool`, which returns
  `bool(session) and session in _sessions_owned_by(project_root, {session})`.
  It uses the canonical attribution rule and attributes only that candidate
  (finding 14).

### 2. `lib/tui_switcher.py` — `_ensure_session_live` uses the helper

The method keeps everything except the subprocess call itself:

- the early `entry is None or entry.is_live` return;
- every user-facing message, word for word;
- the STALE modal on `result.stale`;
- the default-session warning
  (`entry.default_session_problem or result.default_session_problem`);
- the `dataclasses.replace(is_live=True)` flip.

The subprocess call becomes `result = bootstrap_project_session(entry.project_root)`.
`subprocess` stays imported, because other call sites still use it.

### 3. `board/board_trail_view.py` — the modal

- `linked_scan_error_text(err) -> str` gives one line per kind:
  - stale → `"<p>: could not search — stale path (<detail>)"`;
  - not_found → `"…not registered"`;
  - export_failed → `"…export failed: <detail>"`;
  - timeout → `"…timed out"`;
  - partial → `"<p>: searched in part — <detail>"`;
  - registry_unreadable → `"project registry <p> could not be read — <detail>"`;
  - local_unreadable → `"this trail (<p>): member(s) could not be read — <detail>"`;
  - an unknown kind → `"<p>: <kind> — <detail>"`.

  Details longer than 200 chars are cut with `…`.
- `LinkedTrailItem(PickerItem)` builds a `Text` row:
  `project` in bold, then ` · handle · name`. It adds up to 3 dim
  `└ <reason>` sub-lines and a `(+N more)` line beyond that. Enter or a click
  calls `self.screen.dismiss(self.link)`.
- `LinkedTrailsScreen(GuardedModalScreen)`:
  - built from `(title, links, errors, complete)`;
  - its `DEFAULT_CSS` mirrors `TrailSelectScreen` (`#dep_picker_dialog`,
    `.picker-dialog`, `PickerItem` rules), plus `.linked-trail-error { color:
    $warning; }`;
  - the title Label is fixed markup: `Linked trails — <dim>↑/↓ move · Enter
    jump · Esc cancel</dim>`;
  - with links present but the scan incomplete, a `Static(Text(...))` line
    reads "Some projects could not be fully searched — the list may be
    incomplete:";
  - with no links and an incomplete scan, the line reads instead "No linked
    trails found — the search was incomplete:". The definitive message never
    appears here;
  - error rows are non-focusable `Static(Text(linked_scan_error_text(e)),
    classes="linked-trail-error")`;
  - a Cancel button; `escape` → `dismiss(None)`; `on_mount` focuses the first
    item.
- `TrailJumpConfirmScreen(GuardedModalScreen)`, built from `(session,
  warnings)`:
  - a bold `Text` header "Before switching to tmux session '<session>':";
  - one `Static(Text("• " + w))` per warning;
  - buttons `Switch` (`#btn_jump_switch`, focused on mount) and `Stay here`
    (`#btn_jump_stay`);
  - `escape` → `dismiss(False)`, Switch → `dismiss(True)`;
  - its `DEFAULT_CSS` mirrors `TrailSummaryScreen`'s dialog box (own ids).

### 4. `board/board_trail_screen.py` — binding, scan, jump

- Add `Binding("L", "trail_linked", "Linked Trails")` to `TRAIL_BINDINGS`,
  after `v`. No capability entry is needed, because the mixin implements the
  action on both hosts.
- Imports:
  - `from trail_links import scan_linked_trails`;
  - `import copy`;
  - from `agent_launch_utils`: `DEFAULT_TMUX_SESSION`,
    `bootstrap_project_session`, `current_tmux_session`,
    `launch_or_focus_trails`, `live_project_session`, `session_owned_by`,
    `switch_client_to`, `trails_supports_focus`;
  - from `board_trail_view`: `LinkedTrailsScreen`, `TrailJumpConfirmScreen`.

  The tests patch these names on this module (the module docstring's
  patch-target list gains them).
- `_init_trail_state` gains `self._trail_link_gen = 0` and
  `self._trail_jump_busy = False`.
- Invalidation:
  - `_supersede_trail_workers` sets `self._trail_link_gen = gen`;
  - a new `_drop_trail_link_scan()` (`self._trail_link_gen =
    self._bump_trail_gen()`) is called first thing in `_switch_trail_session`
    (after its no-op guard), in `_close_trail_session` (after its None guard)
    and in `_activate_trail`.
- `_trail_link_ready()` returns `bool(self.active_trail_handle and
  self._trail_doc and not self._trail_error)`.
- `action_trail_linked()`:
  - guards in order: `_modal_is_active()` → return; `base_filter !=
    "bytrail"` → return; not ready → notify "Trail not loaded — nothing to
    search from" (warning) and return;
  - then sets `origin = self._trail_active` and `source =
    (copy.deepcopy(origin.doc), origin.error)`. This is the source revision: a
    private snapshot (finding 12).
  - Then `gen = self._trail_link_gen = self._bump_trail_gen()`, the notice
    "Searching for linked trails in other projects…", and
    `self._trail_link_worker(gen, origin, source)`.
- `@work(thread=True) _trail_link_worker(gen, origin, source)`:
  - in a `try` it calls `scan = scan_linked_trails(source[0])`, scanning the
    snapshot and never the live doc;
  - on `Exception as exc` it sets `scan = None, error = str(exc)`;
  - it always posts `call_from_thread(self._on_trail_links, gen, origin,
    source, scan, error)`.
- `_on_trail_links(gen, origin, source, scan, error)` drops the result
  silently unless all of these hold: `gen == self._trail_link_gen`,
  `base_filter == "bytrail"`, `self._trail_active is origin`, and
  `self._trail_session(origin.handle) is origin`. Then:
  1. When `origin.doc != source[0] or origin.error != source[1]` (finding 12;
     equality, not identity), it notifies "Trail <h> changed during the linked-trail search —
     press L to search again" (`markup=False`) and returns.
  2. With an error, it notifies "Linked-trail search failed: <error>" (error,
     `markup=False`).
  3. When a modal is active, it notifies "Linked-trail search finished while a
     dialog was open — press L again".
  4. With no links and `scan.complete`, it notifies "No linked trails in other
     projects".
  5. Otherwise it pushes
     `LinkedTrailsScreen(title, scan.links, scan.errors, scan.complete)` with
     the callback `_on_linked_trail_chosen`.
- **The jump runs in two phases** (finding 13).
  - Module-level `@dataclass(frozen=True) class TrailJump`, with fields
    `link`, `session: str = ""`, `launch: bool = False`, `warnings: tuple =
    ()` and `error: str = ""`.
  - `error` is terminal: nothing switches and the source App shows it.
  - `warnings` must be confirmed before the switch.
- `prepare_linked_trail_jump(link) -> TrailJump` is module-level. It runs on a
  thread, has NO client effect, and may start the target session. Steps, in
  order:
  1. `current_tmux_session() is None` → `error` = the manual-command message
     (`ait projects exec <project> -- ./ait trails --trail <handle>`).
  2. The root lacks the project marker → `error` "<p>: <root> is no longer an
     aitasks project — press L to search again".
  3. `session = live_project_session(root)`. If it is None:
     - call `bootstrap_project_session(root)`; a failure sets `error` "Could
       not start a tmux session for <p>: <err>";
     - if the result carries a `default_session_problem`, add the warning
       "<p>: tmux.default_session is unusable (<shape>); started session
       '<DEFAULT_TMUX_SESSION>'";
     - re-run `live_project_session(root)`; if it is still None, set
       `error`.
  4. `launch = trails_supports_focus(root)`. When it is false, add the skew
     warning: "<p> runs an older aitasks without trail jumps — run `ait
     upgrade` there; you will land in its session without <h> opened".
- `finish_linked_trail_jump(jump) -> list[tuple[str, str]]` is module-level and
  runs on a thread.
  0. Destination re-check (finding 14). If the root has lost its project
     marker, or `session_owned_by(jump.session, root)` is false, it returns
     `[("The tmux session for <p> changed before the jump — press L to try
     again", "error")]` and launches and switches nothing.
  1. With `jump.launch`, it calls `ok, err = launch_or_focus_trails(session,
     root, handle)`. When that fails, it returns `[("Could not open <h> in <p>:
     <err>", "error")]` WITHOUT switching.
  2. `switch_client_to(session)`. When it fails, it returns `[("Could not
     switch to tmux session '<s>' — <manual command>", "error")]`.
  3. Otherwise it returns `[]`. A successful switch emits nothing, because the
     source App is no longer visible.
- `_on_linked_trail_chosen(link)`:
  - a None link → return;
  - `_trail_jump_busy` set → notify "A jump is already in progress" and
    return;
  - otherwise set busy and call `self._trail_jump_prepare_worker(link)`.
- `@work(thread=True) _trail_jump_prepare_worker(link)`:
  - `try: jump = prepare_linked_trail_jump(link)`;
  - on `Exception as exc` it sets `jump = TrailJump(link, error=f"Jump to
    {link.handle} failed: {exc}")`;
  - `finally` posts `call_from_thread(self._on_trail_jump_prepared, jump)`.
- `_on_trail_jump_prepared(jump)`:
  - with `jump.error` → clear busy and notify the error (`markup=False`,
    `timeout=12`);
  - with `jump.warnings` and `_modal_is_active()` → push nothing, clear busy,
    and notify "Jump to <h> paused — a dialog was open. Press L to try again"
    (finding 15);
  - with `jump.warnings` and no modal → push
    `TrailJumpConfirmScreen(jump.session, jump.warnings)`. The callback calls
    `_trail_jump_finish_worker(jump)` on True; on False/None it clears busy
    and runs nothing. A session the bootstrap already started stays, and that
    is harmless;
  - otherwise → `self._trail_jump_finish_worker(jump)`.
- `@work(thread=True) _trail_jump_finish_worker(jump)`:
  - `try: notices = finish_linked_trail_jump(jump)`;
  - on an exception the notice is `[("Jump to <h> failed: <exc>", "error")]`;
  - `finally` posts `call_from_thread(self._on_trail_jump_done, notices)`.
- `_on_trail_jump_done(notices)` clears busy, then notifies each `(msg, sev)`
  with `markup=False` and `timeout=12`. By construction it only receives
  notices from a path that did not switch.

### 5. Hosts

- `board/aitask_board.py`:
  - place `TRAIL_BINDING["trail_linked"]` right after
    `TRAIL_BINDING["trail_summary_expand"]`, with a comment saying it is live
    only in By-Trail with a loaded trail;
  - in `check_action`, add `elif action == "trail_linked": if self.base_filter
    != "bytrail" or not self._trail_link_ready(): return False`;
  - add `LinkedTrailItem, LinkedTrailsScreen, TrailJumpConfirmScreen,
    linked_scan_error_text` to the `from board_trail_view import (...)`
    re-export list.
- `board/trails_app.py`:
  - `*TRAIL_BINDINGS` already carries the binding;
  - in `check_action`, add `elif action == "trail_linked": if not
    self._trail_link_ready(): return False`.

### 6. Tests

- `tests/test_trail_screen_host_protocol.py`: binding count 10.
- `tests/test_board_keymap_characterization.py`:
  - add the row `("L", "trail_linked", "Linked Trails", True, False)` after `v`;
  - add `"trail_linked"` to every hidden set, in sorted position;
  - update the docstring note naming this task as a deliberate change.
- `tests/test_board_trail_view.py`: add the four new names to
  `VIEW_ONLY_NAMES`.
- `tests/test_trails_app.py`:
  - the identity test already covers `L`;
  - add `LinkedTrailsTabTests`, with `scan_linked_trails` patched on
    `board_trail_screen` and gated on a `threading.Event`. Each case lets the
    scan finish only after the test's move:
    - search on tab A, switch to tab B → no modal;
    - search on A, close A → no modal;
    - A→B→A before the result lands → dropped;
    - two `L` presses whose scans finish in either order → exactly one modal,
      the newest;
    - the result lands under a modal → no push, plus the "press L again"
      notice;
    - `L` hidden and inert with no trail, or with a load error;
    - **source revision (finding 12), through the REAL reload path:**
      - Setup: start `_reload_active_trail()` with `_trail_reload_worker`
        patched to capture its gen, then call
        `app._on_trail_reload(gen, handle, doc, error, versions, seq)`.
      - Before the scan is released, deliver a doc with changed members, and
        separately a load error. Expect no modal, and the "changed during the
        search" notice.
      - Control: deliver a DISTINCT but EQUAL doc object the same way. First
        assert `session.doc is not` the original, so the identity churn of
        `restart_drift=True` really happened. Then release the scan: the modal
        still shows. This proves the guard is keyed on content, not identity
        and not "any reload".
      - Discovery reconciliation with changed content
        (`_reconcile_discovered_trails` with a newer `read_seq`) → also
        dropped with the notice.
- `tests/test_board_bytrail_view.py`, new `LinkedTrailsTests`:
  - `L` shown in By-Trail with a loaded synthetic trail and hidden otherwise;
    the action is a no-op outside By-Trail (palette route);
  - leaving By-Trail before the result lands → dropped;
  - modal rendering, through `_dialog_text`:
    - link rows with reasons;
    - every one of the seven error kinds' wording;
    - the incomplete-with-links line;
    - empty plus incomplete shows "No linked trails found — the search was
      incomplete", never the definitive message;
    - empty plus complete gives the notify and no modal;
  - the jump UI, with `prepare_linked_trail_jump` / `finish_linked_trail_jump`
    patched:
    - choosing a row runs prepare once;
    - no warnings → finish runs with no dialog;
    - warnings → `TrailJumpConfirmScreen` shows them in the source App, and
      finish has NOT run yet;
    - Switch → finish runs;
    - Stay here / Esc → finish never runs, and busy clears;
    - an error → notify, and finish never runs;
    - a second pick while busy is refused;
    - busy clears after either worker raises;
    - **modal opened while prepare runs (finding 15):** gate `prepare` on an
      Event. Pick a link, then press `s` with `discover_trails` itself gated,
      so its `LoadingOverlay` is on top. Release `prepare` with warnings:
      - no `TrailJumpConfirmScreen` is pushed, the "paused — press L" notice
        appears, busy is cleared, and finish never ran;
      - then release discovery: its overlay pops itself, and the screen stack
        is back to the base screen;
      - a new `L` → pick → prepare (no modal now) shows the dialog, proving
        busy recovered.
- New `tests/test_linked_trail_jump.py` (`bf.FixtureBoardTestBase` for the
  module handle; helpers patched on `board_trail_screen`; real tmp roots with
  and without the marker).
  - `prepare_linked_trail_jump`:
    - live session → `TrailJump(session, launch=True)`, no warnings, and NO
      launch or switch call (prepare has no client effect);
    - no session → bootstrap → re-lookup;
    - bootstrap failure → `error`;
    - bootstrap success but no session found → `error`;
    - a fallback-name problem → a warning;
    - not on the gateway → only the manual-command `error`, with no bootstrap
      call;
    - version skew → `launch=False` plus the skew warning;
    - the root lost its marker → `error` before any tmux call.
  - `finish_linked_trail_jump`:
    - **destination re-check (finding 14).** Prepare against a live owned
      session, then before finish:
      - (i) `session_owned_by` → False (the session was stopped, or its name
        was reused by another root) → the error "changed before the jump",
        with NO launch and NO switch call;
      - (ii) the root's marker removed → the same error, and no tmux call;
      - (iii) control: still owned → launch and switch proceed.
    - launch then switch → `[]` (the invariant: a successful switch returns
      nothing);
    - `launch=False` → no launch call, but the switch happens;
    - launch failure → error, and no switch;
    - switch failure → an error carrying the manual command.
- New `tests/test_linked_trail_jump.py`, `agent_launch_utils` unit tests:
  - `bootstrap_project_session` with a stubbed `subprocess.run`: success, the
    sentinel on stderr → problem, a non-zero exit (last line), `stale_path` →
    `stale`, an exception → error;
  - `live_project_session` with a stubbed `_TMUX.run`:
    - a stamped default session;
    - a non-default-named session for the root;
    - two sessions where the default wins;
    - another root's session ignored;
    - none → None;
  - `trails_supports_focus`: with `--trail`, without it, file missing;
  - `switch_client_to` argv (`=<session>`) and rc;
  - `session_owned_by`, with a stubbed `_TMUX.run`:
    - the session stamped with the root → True;
    - stamped with another root → False;
    - absent → False;
    - an empty name → False with no tmux call.
- The existing switcher suites (`test_tui_switcher_default_session_notify.py`,
  `test_tui_group_nav.py`, `test_tui_switcher_agent_launch.py`) run unchanged
  as the extraction regression.
- Event-gated scans: every test releases its gates and drains
  `app.workers.wait_for_complete()` before the `run_test` block exits.
  `aidocs/framework/testing_conventions.md` requires this, because a worker
  still in flight fails the enclosing test.

### Post-phase (risk mitigations)

1. [live_jump_bootstrap_path] Add `tests/test_linked_trail_jump_live.sh`, a
   bash test with Python cases, modeled on
   `tests/test_restore_session_bootstrap_live.sh`.
   - Isolation and fixtures:
     - `require_isolated_tmux`, `assert_counters_init`, and
       `assert_counters_load` before the footer guard;
     - our own `TMUX_TMPDIR`, `AIT_NO_SYSTEMD_RUN=1`, and a fixture
       `AITASKS_PROJECTS_INDEX`;
     - a stub `ait` on PATH and as `./ait` in each fixture root. The stub
       records its argv to a file and stays alive (`exec sleep`).
   - Fixture projects:
     - X, the caller: a plain dir;
     - Y, the target: `aitasks/metadata/project_config.yaml` with
       `tmux.default_session: ait_jump_y_$$`, plus
       `.aitask-scripts/board/trails_app.py` containing `--trail`.
   - Cases. Each runs the real `board_trail_screen.prepare_linked_trail_jump`,
     then `finish_linked_trail_jump`, in Python under `require_ait_python`.
     Only `current_tmux_session` (→ `"x"`) and `switch_client_to` (→ True,
     records its session) are patched.
     - **(a) No Y session.** Prepare returns no error and no warnings, and
       starts session `ait_jump_y_$$` on the isolated server, stamped with Y's
       root. No `trails` window exists yet: prepare has no client effect.
       Finish returns `[]`, `switch_client_to` got that session name, and a
       `trails` window now exists there whose stub argv file reads `trails
       --trail art:trail-y` (bounded wait).
     - **(b) A second jump.** No second Y session is created (the session count
       is unchanged), and `switch_client_to` gets the same name.
     - **(c) Control.** With Y's `trails_app.py` lacking `--trail`, prepare
       returns `launch=False` plus the skew warning. Finish creates no
       `trails` window and still switches. This proves the window assertion
       in (a) can fail.
     - **(d) Destination gone (finding 14, real tmux).** Prepare against Y's
       live session, then `kill-session` it and create a session with the
       SAME name rooted in a third fixture project Z. Finish returns the
       "changed before the jump" error, `switch_client_to` was never called,
       and Z's session has no `trails` window.

   Skip with `SKIP` when tmux is absent. Run it 3× to check for flakiness.

## Verification

- `~/.aitask/venv/bin/python -m pytest tests/test_board_bytrail_view.py tests/test_trails_app.py tests/test_trail_screen_host_protocol.py tests/test_board_keymap_characterization.py tests/test_board_trail_view.py tests/test_linked_trail_jump.py tests/test_trails_focus_writer.py tests/test_tui_switcher_default_session_notify.py tests/test_tui_group_nav.py tests/test_tui_switcher_agent_launch.py -q`
- `bash tests/test_no_raw_tmux.sh`
- `bash tests/test_linked_trail_jump_live.sh`, run 3 times. Also
  `shellcheck tests/test_linked_trail_jump_live.sh`; no framework shell
  script changes.
- `bash tests/run_all_python_tests.sh`; read the last line for the verdict.
- Manual check, offered at Step 8c as a manual-verification follow-up:
  - from `ait trails` here, `L` lists the `aitasks_mobile` linked trail
    (expect error rows for thinking_app / thinking_backend, see t1978);
  - Enter switches to that session with the trail focused;
  - with that session stopped, the jump starts it first;
  - **warning visibility on a successful version-skew jump:** register a
    scratch copy of an aitasks project whose
    `.aitask-scripts/board/trails_app.py` lacks `--trail`, with a trail linked
    to the current one. Pressing `L` and picking it must show the upgrade
    warning in a dialog in THIS TUI before anything switches. Stay here must
    leave the client in place. Switch must land in that project's session with
    no trail opened, the warning already read. Afterwards unregister the copy
    with `ait projects remove`.

## Step 9 reference

After review, follow Step 9: commit on main and archive this child. The parent
t1957 is archived together with its last child (t1957_5 docs still pending).

## Risk

### Code-health risk: medium
- A third worker family (the linked-trail scan) joins the shared `TrailScreenMixin`, with stamp-based supersession across two hosts. A slip would show the modal for the wrong trail, for an older revision of the same trail, or after the user has left By-Trail · severity: medium · → mitigation: none. Addressed in-plan: four invalidation points, an origin-identity check, a source-revision check by equality against a snapshot (finding 12), and supersession / out-of-order / under-modal / content-change tests on both hosts. The equal-content control goes through the real reload path.
- The jump becomes a two-phase flow (prepare → optional confirm → finish) with its own busy flag across two workers and a dialog · severity: low · → mitigation: none. Addressed in-plan: finish re-checks the destination (finding 14), the dialog never stacks on a modal (finding 15), and busy is cleared on every route (error, paused, Stay here / Esc, finish, either worker raising). Each route is tested.
- The bootstrap subprocess is extracted out of the tested `TuiSwitcherOverlay._ensure_session_live` · severity: low · → mitigation: none. The messages and STALE handling stay in the switcher, and the existing suites, which patch the global `subprocess.run`, run unchanged.
- `L` joins the shared `board` shortcut scope, so the keymap golden and the binding count change · severity: low · → mitigation: none. The golden is updated deliberately with the change named, and the identity tests run on both hosts.
- `live_project_session` walks every live session (one `list-panes` per unstamped session) · severity: low · → mitigation: none. It runs on the jump's thread worker only, and it is the same walk the switcher's discovery runs.

### Goal-achievement risk: low
- The jump's tmux path is exercised only against a stubbed gateway: the bootstrap, then finding the session it created by root, then the cold `new-window` launch inside that session. If the session the bootstrap creates and the one `live_project_session` finds disagree (stamp vs realpath, fallback name), every jump into a stopped project would fail with "could not find it" · severity: low (residual — addressed by inline post-phase live_jump_bootstrap_path) · → mitigation: inline post-phase live_jump_bootstrap_path
- `switch-client` relies on tmux finding the caller's client through the TUI process's `$TMUX`. That cannot be tested headless, because there is no attached client · severity: low · → mitigation: none. The TUI switcher's teleport uses the same mechanism, and the Step 8c manual check covers it.
- Version skew is detected by a text probe (`--trail` in the target's `trails_app.py`) · severity: low · → mitigation: none. A wrong answer fails toward skipping the launch, warning, and still switching.
- Success-path warnings (version skew, fallback session name) would be shown in the session the user just left · severity: low · → mitigation: none. Addressed in-plan (finding 13): warnings are confirmed in a dialog before the switch, a successful finish returns no notices, and the Step 8c manual check covers a skew jump.
- Real scans on this host are incomplete today (t1978), so users will always see error rows · severity: low · → mitigation: none. Accepted: each row names the project and the cause.

### Planned mitigations
- timing: post-phase | name: live_jump_bootstrap_path | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: goal-achievement — jump tmux path exercised only against a stubbed gateway | desc: live isolated-tmux test running the real prepare_linked_trail_jump + finish_linked_trail_jump: start the target session → find it by root → trails window with --trail; no duplicate session on a second jump; version-skew control

## Post-Review Changes

### Change Request 1 (2026-10-14 11:20)
- **Requested by user:** Three review findings.
  1. A warning paused under another dialog was lost on retry: the fallback-session warning exists only on the prepare that STARTED the session.
  2. The manual `ait projects exec …` command was not quoted, so a registry name holding spaces broke.
  3. Overlapping `L` searches multiply export work. This one was marked as a follow-up.
- **Changes made:**
  1. Paused warnings are kept per target root (`_trail_jump_unread`) and merged into the retry's dialog.
  2. `_manual_trail_command` uses `shlex.join`.
  3. Follow-up task t1979 (`coalesce_linked_trail_scans`, anchored to t1957_4) was created; the code is unchanged.

  Tests added: `test_a_paused_warning_is_shown_on_the_retry`,
  `test_the_manual_command_survives_shell_parsing`, and a quoted-name switch
  failure. Each fails with its fix reverted.
- **Files affected:** `.aitask-scripts/board/board_trail_screen.py`, `tests/test_board_bytrail_view.py`, `tests/test_linked_trail_jump.py`

### Change Request 2 (2026-10-14 11:50)
- **Requested by user:** Change Request 1 replayed EVERY cached message. A compatibility warning ("older aitasks") was therefore shown after the target had been upgraded. It also could carry a previous handle's text into another jump.
- **Changes made:** `TrailJump` now has two message kinds, and `to_confirm` = notices + warnings is what the dialog shows.
  - `notices` are one-time events of this prepare (the bootstrap's fallback session name).
  - `warnings` describe the target's current state (version skew).

  Only `notices` are kept across a pause. Warnings are re-derived by every prepare.

  Tests: `test_a_retry_rederives_compatibility_and_keeps_only_notices` and
  `test_a_paused_compatibility_warning_alone_is_not_replayed`. Both fail under
  the keep-everything behaviour. The unit test for the fallback case now
  asserts `notices`.
- **Files affected:** `.aitask-scripts/board/board_trail_screen.py`, `tests/test_board_bytrail_view.py`, `tests/test_linked_trail_jump.py`

## Final Implementation Notes

- **Actual work done:** All plan steps, findings 1–15, and the
  `live_jump_bootstrap_path` post-phase.
  - `lib/agent_launch_utils.py`:
    - `BootstrapResult` and `bootstrap_project_session` (the subprocess call
      lifted out of the switcher);
    - `live_project_session`, `session_owned_by`, `is_aitasks_project`,
      `trails_supports_focus`, `switch_client_to`.
  - `lib/tui_switcher.py`: `_ensure_session_live` calls the helper. Its
    messages and STALE handling are unchanged.
  - `board/board_trail_view.py`: `linked_scan_error_text` (seven kinds),
    `LinkedTrailItem`, `LinkedTrailsScreen`, `TrailJumpConfirmScreen`.
  - `board/board_trail_screen.py`:
    - the `L` binding in `TRAIL_BINDINGS`;
    - `_trail_link_gen` / `_drop_trail_link_scan` invalidation (supersede,
      switch, close, activate);
    - `action_trail_linked`, which scans a deepcopy snapshot;
    - `_on_trail_links`, with the gen / view / origin-identity / source-revision
      (equality) / under-modal guards;
    - the two-phase jump: `TrailJump`, `prepare_linked_trail_jump`,
      `finish_linked_trail_jump`, the confirm dialog, the busy flag, and the
      carried one-time notices.
  - Both hosts gate `trail_linked` in `check_action`; the board re-exports the
    new view names.
- **Deviations from plan:**
  - The "Searching…" notice has no project count (finding 2).
  - The fallback-session message names the session actually found, not
    `DEFAULT_TMUX_SESSION`.
  - The project-marker check moved into the lib helper `is_aitasks_project`.
    Both changes were forced by `test_board_fixture_harness.py::FreshLoadC2Tests`:
    it flags any `board/` module-level value equal to `"aitasks"` or starting
    with `aitasks/`, imported names included. That covers the imported
    `DEFAULT_TMUX_SESSION` and a module-level `Path("aitasks")/…` marker. Both
    are false positives (a session name and a project marker), but routing
    them through lib keeps the contract simple.
  - Error rows render below the link rows, under the incomplete-search note.
  - The keymap golden's docstring was not edited, following the existing
    style; this plan names the change.
- **Issues encountered:**
  - The first live run of case D failed on `tmux set-option -t '=<s>'`, which
    is "no such session". `set-option` resolves a WINDOW-typed target, so it
    needs `=<s>:` (the bootstrap's own form). This was test-only.
  - The pre-tool hook rightly refused an ad-hoc `TMUX_TMPDIR=… tmux` probe;
    `-L <throwaway>` was used instead.
  - The first full-suite run caught the C2 false positives above. The
    re-run passed: `PYTHON SUITE: PASSED (runner=pytest, exit=0)`, 8903
    passed, 2 skipped.
- **Key decisions:**
  - `live_project_session` attributes EVERY live session, not just
    `owned_lookup_session`'s two candidates. This finds a target running under
    a non-default name, so the jump does not start a duplicate.
  - `finish` re-checks the marker and `session_owned_by` on every run (the
    execution boundary).
  - The source App only shows notices on paths where the client did not
    switch.
  - Mutants confirmed each guard is test-pinned:
    - no revision check;
    - no drop on tab switch;
    - warnings stacked on a modal;
    - no ownership re-check (unit and live D);
    - no carry;
    - unquoted command;
    - carry-everything.
  - Live test: 25/25 on 3 consecutive runs. `shellcheck -x -P SCRIPTDIR` is
    clean.
- **Upstream defects identified:** None
- **Notes for sibling tasks:** For t1957_5 (docs):
  - Key: `L` "Linked Trails". It is live only in By-Trail with a loaded trail,
    on both the board and `ait trails`.
  - Messages, verbatim:
    - "Searching for linked trails in other projects…"
    - "No linked trails in other projects" (a complete, empty search)
    - dialog note "No linked trails found — the search was incomplete:" or
      "Some projects could not be fully searched — the list may be
      incomplete:"
  - Error rows: `<p>: could not search — stale path|not registered|export
    failed|timed out (<detail>)`, `<p>: searched in part (<detail>)`, `project
    registry <path> could not be read (<detail>)`, `this trail (<p>):
    member(s) could not be read (<detail>)`.
  - Picking a trail:
    - it starts the target's tmux session when none runs (tmux_bootstrap.sh);
    - it opens the trail in that project's `ait trails` (the running instance
      via the pane mailbox, else a new `trails` window);
    - then it switches the client.
  - A target on an older aitasks (no `--trail`) gets a confirm dialog naming
    `ait upgrade`; the user still lands in its session, without the trail
    opened.
  - Outside the aitasks tmux server the user gets the manual
    `ait projects exec <p> -- ./ait trails --trail <h>`.
  - `website/content/docs/tuis/board/reference.md` lists the trail keys and
    needs `L`.
