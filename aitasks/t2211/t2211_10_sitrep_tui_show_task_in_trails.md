---
priority: medium
effort: high
depends: []
issue_type: feature
status: Implementing
labels: [sitrep, tui, trails]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 2175
created_at: 2026-11-09 10:11
updated_at: 2026-11-09 17:45
---

## Context

Child of t2211 (sitrep two-pane window with the sitrep TUI). Split out of t2211_9 at the user's request, because it is more than a UI tweak.

In the sitrep TUI (`ait sitrep tui`), a task item names a local task (`kind=task`, ref `t<N>[_<M>]`; `sitrep_tui_model.task_ref_id`). When that task is a member of one or more implementation trails, the TUI should offer a shortcut that shows the task in the `ait trails` TUI: the trail opened, and the task's card focused within it.

## What exists today (verified 2026-11-09)

- **Finding the trails of a task:** `lib/trail_discovery.py`.
  - `discover_trails()` returns `(infos, unreadable)`, with `TrailInfo.handle` / `.doc` / `.load_error`. It is subprocess-heavy: call it from a thread worker only.
  - `trail_entry_refs(doc)` returns the member task refs, project-qualified (`aitasks#2211_3`).
  - Do NOT read codebrowser or board internals for this.
  - Mind fail-closed rules: a trail whose blob failed to load (`load_error`), or an `unreadable` scan, means "unknown", never "not in any trail".
- **Opening a trail:** `lib/agent_launch_utils.launch_or_focus_trails(session, root, handle)`.
  - It writes the pane mailbox `@aitask_trails_focus "<32-hex id> <art: handle>"` to the first live `@aitask_trails_app` receiver, else starts a `trails` window with `./ait trails --trail <handle>`.
  - Since t2211_3 it is built on the generalized pane mailbox: `read_pane_request` / `parse_pane_request(value, payload_re)` / `_deliver_pane_request`. The board twin, `launch_or_focus_board` + `board/board_focus_request.py`, focuses a CARD.
  - **Missing:** focusing a task card INSIDE the opened trail. `board/trails_app.py` `TrailsApp` handles `initial_trail` and `_deliver_trail_focus(handle)` / `_apply_trail_focus(seq, handle)` (handle only).
- **Moving to the TUI's session:** `sitrep_tui_actions.open_in_board()` (t2211_3) shows the destination-session rule:
  - own session if attributed to the root, else `live_project_session`;
  - re-check `session_owned_by` before launching;
  - `switch_client_to` when the destination differs, reporting a failed switch with the session name.
  Reuse that shape.
- **The sitrep TUI's action layer:** `sitrep_tui_actions.py`.
  - `ACTION_BINDINGS`, `ITEM_ACTIONS`, `_item_action_ok`, `_resolve_action_item` (re-resolve against the current store; a moved rev refreshes the details and runs nothing).
  - Thread workers via `@work(thread=True)`.
  - `TaskMeta` lookup in `sitrep_tui_model` (t2211_3); t2211_9 extends it.

## Required behaviour

1. **Membership lookup, off the event loop and cached.** Compute which trails contain each task item's task (match `aitasks#<id>` and the bare local form the trail docs use; confirm against real trail docs, e.g. `art:trail-sitrep-followups`).
   - Do it in a worker after load, and again when trails change.
   - Key any cache on content, not stat freshness (memory: cache keys cover every consumed input). The discovery cache (`trail_discovery_cache`) already exists; prefer reusing it.
   - States: in N trails, in none, unknown (scan failed). Do not block the UI.
2. **A shortcut, shown only where it applies.**
   - A key (pick one free of `q enter d l s j ? r x R A p b P` and whatever t2211_9 adds) on the main list and on item details. It is visible only for a task item whose task is known to be in >= 1 trail (`check_action`), and the action re-checks.
   - In 2+ trails → a small picker (a `SelectOnClickList`: click selects, Enter opens) listing the trail names and handles.
3. **Trail membership in the task item's details (user-requested, 2026-11-09).**
   - `ItemDetailScreen` shows the membership, so the user sees it without pressing anything:
     - in the body: a labelled line `Trails` listing each trail's name (plus its wave, e.g. `w1`, when the trail doc gives one);
     - in the links list (`#sd-links`, a `SelectOnClickList`): one row per trail, e.g. `In trail: Sitrep follow-ups (art:trail-sitrep-followups) — wave 1`.
   - **Selecting a trail row and pressing Enter opens that trail in `ait trails` with this task's card focused**, through the same path as the shortcut (requirement 4, and the session handling in requirement 5).
     - It goes through the screen's existing `OptionSelected` handler (`_OpenLinkMixin` / `_OPEN_BINDING`; a click only selects).
     - It re-resolves the item against the current store first, like every item action (`_resolve_action_item`): a moved rev refreshes the details and runs nothing.
   - States, rendered plainly (store and trail text is untrusted: plain `Content`/`Text`, never markup):
     - in no trail → no rows;
     - the lookup is still running → one disabled row "Trails: looking…", replaced when the worker finishes. Details are snapshots, so the update must come from a worker callback that checks the screen is still the active one for that item;
     - the lookup failed or a trail blob was unreadable → one disabled row "Trails: unknown (<reason>)", never shown as "in no trail".
   - With the trail rows in the details, the shortcut from requirement 2 stays for the main list. On the details screen it may simply act on the highlighted trail row, or open the picker when no trail row is highlighted. Decide and pin which.
4. **Show the task in `ait trails`.**
   - Extend the trails focus request so it can carry the task, e.g. payload `<handle> <task id>`. Keep the old `<handle>` payload valid (backward compatible: an older running TrailsApp must still open the trail and ignore what it does not understand, never crash).
   - Extend the cold path: `./ait trails --trail <handle> --task <id>`.
   - `TrailsApp` opens the trail, then focuses that member's card. A task not in the trail (any more) → toast, trail still opened.
   - Update `parse_trails_focus_request` and its tests. The request stays untrusted input: validate the task id with the same grammar as `BOARD_TASK_ID_RE`.
   - Respect `trails_supports_focus(root)`-style probing if an older `ait trails` without `--task` could be launched.
5. **Session handling** exactly as `open_in_board`: own session vs. the project's live session, re-check ownership, switch the client when needed, report a failed switch.

## Key files

- `.aitask-scripts/sitrep_tui/sitrep_tui_actions.py`, `sitrep_tui_app.py`, `sitrep_tui_model.py`
- `.aitask-scripts/lib/agent_launch_utils.py` (`launch_or_focus_trails`, the trails mailbox parse)
- `.aitask-scripts/board/trails_app.py` (`main()` argv, `_deliver_trail_focus` / `_apply_trail_focus`, card focus within a trail)
- `.aitask-scripts/lib/trail_discovery.py` (read-only use)
- Docs: `aidocs/framework/tmux_gateway.md` (`@aitask_trails_focus` row: the payload grammar), `aidocs/framework/tui_conventions.md` if the trails module map changes

## Tests

- Membership: fixture trails (see how `tests/test_trails_app.py` / `tests/lib/board_fixture.py` stage trail blobs), a task in 0 / 1 / 2 trails, a failed blob → unknown (key hidden, never "none").
- The key shown only where it applies (bindings matrix incl. details; triage / non-task items hidden).
- The picker for 2+ trails.
- Details membership: the `Trails` body line and one links row per trail. Enter on a trail row opens that trail (stubbed launcher called with the row's handle and the task id); a click only selects. The "looking…" row is replaced when the worker finishes, and its callback does not touch a details screen that was closed or replaced meanwhile. A failed lookup shows the disabled "unknown" row and no trail rows. A moved rev refreshes the details and launches nothing.
- Writer argv: the extended request, plus backward compatibility. An old-style `<handle>` request still parses; a new request to a TrailsApp ignores an unknown suffix safely; a malformed task id is refused before tmux.
- TrailsApp: `--trail h --task id` focuses the card; a mailbox request with a task focuses it; a task absent from the trail gives a toast.
- Session switch cases as in `tests/test_sitrep_tui_actions.py::OpenInBoardTests`.
- A live tmux check in the style of `tests/test_trails_focus_mailbox_live.py` for the new payload.
- Existing suites stay green: `tests/test_trails_focus_writer.py`, `tests/test_trails_app.py`, `tests/test_trails_focus_mailbox_live.py`.

## Verification

- The tests above. `bash tests/run_all_python_tests.sh --test-dir tests` (last line); `bash tests/test_no_raw_tmux.sh`.
- Manual check in a real sitrep window: the details of a task item list its trails, and Enter on a trail row opens it with the card focused.
- Manual check in a real sitrep window: a task item in a trail → the key opens `ait trails` on that trail with the card focused, both with trails running (handoff) and not running (new window), and from another session (client switch).
- Send t2211_6 (docs) and t2211_7 (manual checklist) an `ait note` with the new key and behaviour.

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t2211_9** id=2026-11-09T15:27:03Z.572ed66768978c1ece0c0e40 from=t2211_9 from_verified=yes at=2026-11-09T15:27:03Z base=6d44bd275b3df9d0dea78d4137a12f305584d5c1 base_branch=main dirty=yes host=omg16
>
> | Advisory (claim, from t2211_9; code commit 6d44bd275, tree-relative). For your key choice and patterns:
> | 
> | - `f` (filter_labels) and `F` (clear_label_filter) are now taken on the sitrep TUI main list. Keys in use are now: q enter d l s j ? r x R A p b P f F. t2211_4 plans t w T.
> | - Main-screen-only actions go in `_MAIN_ACTIONS` (sitrep_tui_app.py) with a `check_action` gate, and the action re-checks.
> | - A footer label that follows state: use `SitrepTuiApp._set_binding_label(action, text)`. It replaces the live keymap entry with a NEW list per key. Never edit a keymap list in place: BindingsMap.copy() is shallow, and an in-place edit leaks into later instances (t2014).
> | - A modal listing items: copy `LabelFilterDialog` (sitrep_tui_actions.py). Its buttons are docked at the bottom, `_fit_list` sizes the list to the remaining height (on mount and resize), and the highlight is scrolled back into view after a resize. Test with real `pilot.click` at short sizes, not Button.press().

> **👁 note:read** id=2026-11-09T15:44:28Z.333f530ee12401d07dd74b16 by=t2211_10 at=2026-11-09T15:44:28Z mode=explicit ids=2026-11-09T15:27:03Z.572ed66768978c1ece0c0e40
