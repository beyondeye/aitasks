---
Task: t1427_2_picker_reject_tristate.md
Parent Task: aitasks/t1427_reject_shadow_concerns_suppress_next_round.md
Sibling Tasks: aitasks/t1427/t1427_1_rejection_store_helper.md, aitasks/t1427/t1427_3_producer_suppression_rule.md, aitasks/t1427/t1427_4_rejection_docs.md
Archived Sibling Plans: aiplans/archived/p1427/p1427_*_*.md
Worktree: . (current directory — profile 'fast', no worktree)
Branch: main (current branch)
Base branch: main
Output branch: main
---

# p1427_2 — Picker reject tri-state, dismiss contract, persistence wiring

Adds the per-row reject action to `ConcernPickerModal`, persists rejections
through the t1427_1 helper, adds the rejected-store view with un-reject, and
changes the modal's dismiss contract. Depends on t1427_1 (helper landed —
consult its archived plan `aiplans/archived/p1427/p1427_1_*.md` for the final
machine-line protocol before wiring subprocess calls).

**Binding user decisions:** `a`/`A` bulk shortcuts are REMOVED ENTIRELY
(per-row actions only — rejection state must never be bulk-overridden);
un-reject is TUI-only; NO stale-data conflict handling or refresh behavior for
pre-fetched store entries (concurrent cross-session editing out of scope).

Line numbers below are from exploration at planning time — re-read the files
from HEAD before editing.

## Steps

1. **`concern_parser.py` — extract the canonical marker renderer.** New
   `concern_marker_line(c: Concern) -> str` returning
   `f"- [{c.priority} | {c.region}] {c.body}"` (uses `.body`, the canonical
   FORWARD role — never `display_body()`). Rewrite
   `build_clipboard_payload` (~:539-553) to use it. Keep
   `tests/test_concern_body_display_contract.py` green (it freezes the
   DISPLAY/FORWARD role split).

2. **`monitor_shared.py` — `_ConcernRow` tri-state** (~:1218-1353):
   - Replace `_selected: bool` with `_state` in `{"none","forward","rejected"}`
     (string or small enum). Keep a `selected`-equivalent accessor only if it
     reads clearer at call sites; update `toggle()` / `set_selected()` into
     `set_state()` / `toggle_forward()` / `toggle_reject()` (mutually
     exclusive: setting one clears the other; refresh only on change).
   - `render()` mark: `☐` none, `[bold yellow]☑[/]` forward, `[red]✗[/]`
     rejected — all single-width, so `_NARROW_PREFIX_COLS = 8` (~:1215) is
     untouched.
   - CSS: add `.rejected { color: $text-muted; }` (dim; combined with the red
     ✗ mark this reads as struck without relying on terminal strike support).
   - `on_key` (~:1327-1339): `space` → toggle forward; new `r` → toggle
     reject; both `prevent_default()` + `stop()`.

3. **`monitor_shared.py` — remove bulk actions:** delete the `a`
   (`action_toggle_all`, ~:1686-1698) and `A` (`action_copy_all`, ~:1703-1706)
   BINDINGS (~:1488-1496) and methods; scrub them from `_CONCERN_HELP_FULL` /
   `_CONCERN_HELP_COMPACT` (~:1384-1393).

4. **`monitor_shared.py` — `ConcernPickResult` + dismiss contract:**
   ```python
   class ConcernPickResult(NamedTuple):
       forwarded: list[Concern]
       rejected: list[Concern]
       unrejected: tuple[str, ...]   # store entry ids, e.g. ("r1", "r3")
   ```
   Modal dismisses with `ConcernPickResult | None` (None on Esc/Cancel).
   Update the class docstring (~:1460-1486 — it states the old contract
   verbatim), `action_confirm`, `action_dismiss_dialog`, `on_button_pressed`.
   `_selected_concerns()` becomes two collectors (forwarded/rejected), both
   sorted by `original_index` (the stable selection identity — never by
   value/DOM). `_context_line()` (~:1574-1582) wording gains reject.

5. **`monitor_shared.py` — `RejectedStoreModal` (new):** modeled on
   `ConcernBlockInspectModal` (~:1396-1456). Input: the pre-fetched store
   entries `list[RejectedEntry]` where `RejectedEntry = NamedTuple(id, ts,
   producer, marker_line)`. Rows show the marker line (escape markup; muted
   when untogglable); per-row toggle key (`space`) marks an entry for
   un-reject; `enter` dismisses with the toggled id tuple, `escape` with `()`.
   Picker binding `R` (`action_show_rejected`): pushes the modal on
   `self.app` (pattern of `action_inspect_unrecovered` ~:1657-1670 — picker
   NOT dismissed) with a callback accumulating into the picker's
   `_unreject_ids`. When the picker was constructed with no entries AND a
   `store_unavailable` flag (no task id), `R` shows a notify/static notice
   "no task id — rejection store unavailable" instead. Empty store with a
   valid task id → notice "no rejected concerns".
   No refresh: the entries passed at construction are the session's view
   (out-of-scope decision).

6. **`monitor_shared.py` — picker `__init__`:** new keyword-only params
   `rejected_entries: Sequence[RejectedEntry] = ()` and
   `store_unavailable: bool = False`. Help strings gain `r` and `R`; re-tune
   `_CONCERN_HELP_COMPACT` to stay readable at 24 cols (dropping `a`/`A` buys
   the room; the width test `test_keys_stay_readable_at_every_supported_width`
   pins it).

7. **App wiring — `monitor_app.py`** (`action_pick_concerns` ~:2830-2934,
   `_on_concerns_picked` ~:2936-2953):
   - Resolve `task_id = self._task_cache.get_task_id_for_pane(<followed pane>)`
     (idiom at ~:1272 etc.; the followed pane is the snapshot pane the shadow
     shadows, not the shadow pane). Fetch store entries via the helper
     `list --machine <task_id>` in the existing async/executor style
     (`asyncio.to_thread` / worker — match how capture subprocesses are run in
     this file). Parse `REJECTED:` lines with `split("|", 3)`;
     `NO_REJECTIONS` → empty. No task id → `store_unavailable=True`.
   - Pass `rejected_entries` / `store_unavailable` into `ConcernPickerModal`.
   - `_on_concerns_picked(result: ConcernPickResult | None)`: explicit
     `if result is None:` (release busy guard, return). Forwarded non-empty →
     `copy_to_system_clipboard(self, build_clipboard_payload(result.forwarded))`
     + notify (unchanged; never `app.copy_to_clipboard` —
     `tests/test_tui_clipboard_seam.sh`). Rejected non-empty → if task id
     resolved: helper `add <task_id> --producer picker` with
     `concern_marker_line(c)` per concern on stdin (subprocess off the event
     loop); notify "N concern(s) rejected — suppressed next round". If no
     task id: notify "Rejections not persisted — no task id for this pane"
     (visible refusal, never silent). Unrejected non-empty → helper
     `remove <task_id> <ids...>`; notify count. Helper exit 3 (LOCK_BUSY) →
     notify the busy outcome; nothing written.
   - Keep the `_concern_pick_busy` guard release semantics intact
     (`PickReentrancyTests` pins them).

8. **App wiring — `minimonitor_app.py`** (`action_pick_concerns`
   ~:1677-1742, `_on_concerns_picked` ~:1745-1756): same changes;
   `task_id = self._task_cache.get_task_id_for_pane(snap.pane)` where
   `snap = self._find_own_agent_snapshot()` (same expression the shadow
   launcher uses at ~:1514). `narrow=True` path unchanged. The auto-offer
   dedup (`_last_concern_block_payload`, ~:1819-1822) keys on the block
   payload and is unaffected.

9. **Tests:**
   - `tests/test_concern_picker_modal.py`: dismiss-contract tests (~:187-227)
     now assert `ConcernPickResult` fields (forwarded order still by
     `original_index`); DELETE `test_copy_all_dismisses_with_every_concern`
     and the toggle-all tests; add: `r` toggles ✗ glyph and `.rejected` class;
     forward↔reject mutual exclusion; reject survives partition reorder
     (duplicate-valued concerns stay positionally distinct); `R` view happy
     path + un-reject ids in the result + no-task-id notice; width-tier suite
     re-tuned for the new help strings.
   - `tests/test_monitor_concern_action.py` /
     `tests/test_minimonitor_concern_action.py`: callbacks invoked with
     `ConcernPickResult`; persistence subprocess spied (monkeypatch the
     helper-invocation seam — do not execute bash); task-id-refusal notice
     asserted; LOCK_BUSY notify path.

   ### Pre-phase (risk mitigations)
   1. **[rejections_only_result_negative_control]** In BOTH callback suites:
      invoke the callback with
      `ConcernPickResult(forwarded=[], rejected=[c], unrejected=())` and
      assert the persistence spy fired and no early return swallowed it —
      this is the pin against a truthiness (`if not result`) regression.
      Prove each new test can fail (temporarily reintroduce a truthiness
      check during development; do not commit it).

## Verification

- `bash tests/run_all_python_tests.sh --test-dir tests` — verdict from the
  last stderr line; check `${PIPESTATUS[0]}` if piping.
- Live (tmux): open minimonitor against a followed agent with an active
  shadow and a concern block; press `c`, mark one concern with `r`, confirm →
  `.aitask-shadow/<task_id>/rejected.md` gains the entry; re-open picker,
  press `R`, un-reject it, confirm → entry removed. Repeat in full monitor.

Post-implementation cleanup, archival, and merge follow **Step 9
(Post-Implementation)** of the task workflow.
