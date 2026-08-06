---
Task: t1427_2_picker_reject_tristate.md
Parent Task: aitasks/t1427_reject_shadow_concerns_suppress_next_round.md
Sibling Tasks: aitasks/t1427/t1427_1_rejection_store_helper.md, aitasks/t1427/t1427_3_producer_suppression_rule.md, aitasks/t1427/t1427_4_rejection_docs.md
Archived Sibling Plans: aiplans/archived/p1427/p1427_*_*.md
Worktree: . (current directory — profile 'fast', no worktree)
Branch: main (current branch)
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5 @ 2026-08-06 00:08
---

# p1427_2 — Picker reject tri-state, dismiss contract, persistence wiring

Adds the per-row reject action to `ConcernPickerModal`, persists rejections
through the t1427_1 helper, adds the rejected-store view with un-reject, and
changes the modal's dismiss contract. t1427_1 has landed — its archived plan
`aiplans/archived/p1427/p1427_1_rejection_store_helper.md` carries the final
machine-line protocol and the exit-code contract this plan consumes.

**Binding user decisions:** `a`/`A` bulk shortcuts are REMOVED ENTIRELY
(per-row actions only — rejection state must never be bulk-overridden);
un-reject is TUI-only; NO stale-data conflict handling or refresh behavior for
pre-fetched store entries (concurrent cross-session editing out of scope).

## Verification pass (2026-08-05) — what changed from the original plan

The plan was written while t1293 was still uncommitted and was never verified.
Re-reading the sources at HEAD (t1293 landed as `e2db6e3f6`, shifting
`monitor_shared.py` by ~+250 lines) surfaced six corrections, all folded into
the steps below. **Line numbers below are re-derived from HEAD.**

1. **The plan had no `## Risk` section**, but t1427_2 is risk-gated
   (`active_gates: [risk_evaluated]`; `aitask_gate.sh active 1427_2
   risk_evaluated` exits 0). The `RISK_MISSING` guard in `planning.md` would
   have refused it. Authored below, with the inline mitigations moved into a
   proper `### Pre-phase (risk mitigations)` block at the head of the steps
   (they were previously buried inside step 9).

2. **`EXPECTED_ACCESSES` is FROZEN and must gain a row.**
   `tests/test_concern_body_display_contract.py:107-114` is an AST guard keyed
   on `(file, function, receiver)`; the row
   `("concern_parser.py", "build_clipboard_payload", "c"): (FORWARD, {"body"})`
   describes a `.body` read *inside* `build_clipboard_payload`. Extracting
   `concern_marker_line` **moves** that read, and the table's own comment is
   explicit: "A new or moved Concern-body read must consciously add a row here,
   WITH a role. A silent pass after a refactor is a bug in this table." The
   original plan only said "keep it green". Step 1 now specifies the exact
   table edit.

3. **The dismiss callback cannot resolve the task id.** Textual invokes
   `callback(result)` with nothing else, so `_on_concerns_picked` has no pane
   and no snapshot. `get_task_id_for_pane` takes a `TmuxPaneInfo`
   (`monitor_core.py:3013`), which is only reachable at `action_pick_concerns`
   time. The id (and the `store_unavailable` flag) must be **stashed on `self`
   at pick time** and read by the callback. The original plan said "resolve
   `task_id = …`" in the callback, which is not implementable.

4. **`_on_concerns_picked` is synchronous**, so the helper call cannot be
   awaited there. The repo's own idiom for exactly this is
   `minimonitor_app.py:1480-1484` — "The seam is a subprocess and this is a
   synchronous `push_screen` callback, so the work has to move onto a worker" —
   i.e. `run_worker`. Specified in steps 7/8.

5. **The helper seam is shared, not per-app.** `AgentMarksMixin._run_marks_cmd`
   (`monitor_shared.py:279-323`) is the established shape: an overridable
   `async` method with a **total** contract (never raises, always terminates;
   `OSError` and timeout both normalised to `(rc, "ERROR:…")`), which is also
   precisely the "monkeypatch the helper-invocation seam — do not execute bash"
   the test section asks for. Adding one shared `_run_rejected_cmd` beside it
   beats two open-coded subprocess blocks. It needs **stdin** (`add` reads
   markers from stdin), which `_run_marks_cmd` does not have.

6. **Exit codes 2 / 3 / 4 must be discriminated.** t1427_1's Final
   Implementation Notes state this as a requirement on *this* task: `3` =
   LOCK_BUSY (transient), `4` = store unusable (never retry — it will not fix
   itself), `2` = caller bug. The original plan handled only `3`.

**One claimed hazard was checked and is NOT real.** `monitor_app.py` binds `r`
→ `refresh` (:480) and `R` → `restart_task` (:489) at App level, which looks
like a fall-through risk for the new keys. It is not: Textual does **not**
dispatch App-level `BINDINGS` while a `ModalScreen` is active. That is measured,
not assumed — `tests/test_monitor_modal_space_dispatch.py` pins it with a
negative control and its module docstring says so explicitly. No guard,
re-binding, or key change is needed; do not add one.

## Steps

### Pre-phase (risk mitigations)

These land in the test files of step 9 and are name-labeled so the `## Risk`
cross-references resolve regardless of later reordering.

1. **[rejections_only_result_negative_control]** In BOTH callback suites
   (`tests/test_monitor_concern_action.py`,
   `tests/test_minimonitor_concern_action.py`): invoke the callback with
   `ConcernPickResult(forwarded=[], rejected=[c], unrejected=())` and assert the
   persistence seam fired and no early return swallowed it. This is the pin
   against a truthiness (`if not result:`) regression — both callbacks are
   `if not selected:` today (`monitor_app.py:2949`,
   `minimonitor_app.py:1921`), and a rejections-only result is falsy under the
   *old* shape only if the new NamedTuple is empty, so the switch to
   `is None` must be explicit. Prove each new test can fail by temporarily
   reintroducing the truthiness check; do not commit the flip.

2. **[exit_code_discrimination]** Assert the three helper outcomes produce
   three *different* user-visible results, in both suites: rc 3 → "busy, try
   again" (transient wording, nothing written); rc 4 → a distinct
   never-retry message naming the store; rc 2 → an error message. A single
   "rejection failed" catch-all passes a weaker test and is what this pins
   against — t1427_1 records that conflating 3 and 4 turns a permanent
   misconfiguration into an infinite retry.

3. **[body_role_registry_row]** After adding the `concern_marker_line` row to
   `EXPECTED_ACCESSES`, prove the guard is not vacuously satisfied: delete the
   new row locally and confirm
   `tests/test_concern_body_display_contract.py` **fails** with an
   unclassified-read finding naming `concern_marker_line`; restore it. Record
   the observed failure text in the Final Implementation Notes. Without this
   the row could be wrong (or the guard blind to the new function) and nothing
   would say so.

4. **[task_id_refusal_is_visible]** In both suites, drive the no-task-id path
   (`get_task_id_for_pane` → `None`) with a non-empty `rejected` list and
   assert (a) a **warning-severity** notify whose text names the missing task
   id, and (b) the persistence seam was **not** invoked. The task file requires
   an unresolvable task id be "A VISIBLE REFUSAL, never silent"; asserting only
   "nothing was written" would pass for a silent no-op too.

### Main implementation

1. **`concern_parser.py` — extract the canonical marker renderer.** New
   module-level `concern_marker_line(c: Concern) -> str` returning
   `f"- [{c.priority} | {c.region}] {c.body}"` — `.body`, the canonical FORWARD
   role, never `display_body()`. Rewrite `build_clipboard_payload` (:539-553,
   which inlines the f-string at :552) to call it. Carry the existing
   `.body`-not-`display_body()` comment onto the new function; it is now the
   site that holds the rule.

   **Required table edit** (correction 2) — in
   `tests/test_concern_body_display_contract.py:107-114`, replace the
   `build_clipboard_payload` row with:
   ```python
   ("concern_parser.py", "concern_marker_line", "c"): (
       FORWARD, frozenset({"body"})),
   ```
   `build_clipboard_payload` no longer reads a Concern body directly, so its
   row must go — a stale row for a function that no longer performs the read is
   exactly the "silent pass after a refactor" the table's comment forbids.
   Re-check `tests/test_concern_body_display_contract.py:564-571`, which
   asserts against the `build_clipboard_payload` key by name (AC #2) and must
   be retargeted to the new key.

2. **`monitor_shared.py` — `_ConcernRow` tri-state** (:1476-1611):
   - Replace `_selected: bool` (:1530) with `_state` in
     `{"none","forward","rejected"}`. `selected` (:1550-1552) stays as a
     `_state == "forward"` property if call sites read better for it; `toggle()`
     / `set_selected()` (:1554-1560) become `set_state()` /
     `toggle_forward()` / `toggle_reject()` — mutually exclusive (setting one
     clears the other), refreshing only on an actual change.
   - `render()` mark (:1572): `☐` none, `[bold yellow]☑[/]` forward,
     `[red]✗[/]` rejected. All single-width, so `_NARROW_PREFIX_COLS = 8`
     (:1473) is untouched and the narrow budget arithmetic at :1581 is
     unchanged.
   - CSS (:1497-1516): add `_ConcernRow.rejected { color: $text-muted; }` —
     dim, which combined with the red ✗ reads as struck without depending on
     terminal strike support. Note `.informational` already sets the same
     colour; a rejected informational row is simply dim, which is correct.
   - `on_key` (:1585-1597): `space` → `toggle_forward()`; new `r` →
     `toggle_reject()`; both `prevent_default()` + `stop()`, matching the
     existing space arm.
   - Update the class docstring (:1477-1493), which says "a ``selected`` flag"
     and "``space`` toggles the selection".

3. **`monitor_shared.py` — remove bulk actions:** delete the `a`
   (`action_toggle_all`, :1944-1956) and `A` (`action_copy_all`, :1961-1964)
   methods and their `BINDINGS` entries (:1749-1750). Scrub `a`/`A` from
   `_CONCERN_HELP_FULL` (:1642-1645) and `_CONCERN_HELP_COMPACT` (:1649-1651).
   **Two prose sites also name them and are easy to miss:** the
   `ConcernPickerModal` docstring's t1274 paragraph (:1724-1729, "``a`` (select
   all) skips them") and the `xnarrow` CSS comment (:1794-1798, "the only place
   `u` / `a` / `A` are named"). Both must be rewritten, not left describing
   removed keys.

4. **`monitor_shared.py` — `ConcernPickResult` + dismiss contract:**
   ```python
   class ConcernPickResult(NamedTuple):
       forwarded: list[Concern]
       rejected: list[Concern]
       unrejected: tuple[str, ...]   # store entry ids, e.g. ("r1", "r3")
   ```
   Ids carry the `r` prefix — that is exactly what `list --machine` emits
   (`aitask_shadow_rejected.sh:339` prints `REJECTED:r%s|…`), and `remove`
   accepts them with or without it.

   The modal dismisses with `ConcernPickResult | None` (`None` on Esc /
   Cancel). Update **every** dismiss site: `action_confirm` (:1958-1959),
   `action_dismiss_dialog` (:1966-1967), `on_button_pressed` (:1969-1973), and
   the now-deleted `action_copy_all`. `_selected_concerns()` (:1933-1942)
   becomes two collectors, both keeping the `sorted(…, key=original_index)`
   rule and its rationale (partitioning reorders the DOM; equal `Concern`
   tuples are indistinguishable by value). Rewrite the **Dismiss contract**
   paragraph of the class docstring (:1737-1743) — it states the old contract
   verbatim, including the `A` copy-all clause. `_context_line()` (:1832-1840)
   currently ends "select to forward" in both branches; widen the wording to
   cover reject.

5. **`monitor_shared.py` — `RejectedStoreModal` (new):** modeled on
   `ConcernBlockInspectModal` (:1654-1714). Input: the pre-fetched entries as
   `RejectedEntry = NamedTuple(id: str, ts: str, producer: str,
   marker_line: str)`. Rows render the marker line with **`markup=False`** —
   a marker is literally `- [high | region]`, which Rich would eat, and this is
   the same reason `ConcernBlockInspectModal` sets it (:1665-1667). Per-row
   `space` toggles an entry for un-reject; `enter` dismisses with the toggled
   id tuple, `escape` with `()`.

   Picker binding `R` → `action_show_rejected`, pushed on `self.app` following
   `action_inspect_unrecovered` (:1915-1928) — the picker is **not** dismissed,
   so returning lands on an intact selection. Its callback accumulates into the
   picker's `_unreject_ids`, which the final result carries. Notices, not a
   modal, for the two empty cases: `store_unavailable` → "no task id —
   rejection store unavailable"; valid task id but no entries → "no rejected
   concerns". No refresh — the entries passed at construction are the session's
   view (binding out-of-scope decision).

6. **`monitor_shared.py` — picker `__init__`** (:1803-1816): new keyword-only
   `rejected_entries: Sequence[RejectedEntry] = ()` and
   `store_unavailable: bool = False`. Help strings gain `r` and `R`; re-tune
   `_CONCERN_HELP_COMPACT` to stay readable at 24 cols — dropping `a`/`A` buys
   the room, and `test_keys_stay_readable_at_every_supported_width`
   (`tests/test_concern_picker_modal.py:520`) pins it.

7. **`monitor_shared.py` — the shared helper seam** (correction 5). Beside
   `_MARKS_SH` (:188) add `_REJECTED_SH = _SCRIPT_DIR /
   "aitask_shadow_rejected.sh"` and a timeout constant above the helper's own
   `MUTATE_LOCK_TIMEOUT=10` (mirroring the `_MARKS_CMD_TIMEOUT = 20.0`
   rationale at :299-301 — a slow-but-working writer must be allowed to report
   `LOCK_BUSY` itself). Add:

   ```python
   async def _run_rejected_cmd(
       self, args: list[str], stdin_text: str = ""
   ) -> tuple[int, str]:
   ```

   modeled directly on `_run_marks_cmd` (:279-323) and keeping its **total**
   contract verbatim — never raises, always terminates, `OSError` and
   `asyncio.TimeoutError` both normalised to `(rc, "ERROR:…")`, child killed
   *and reaped* on timeout. The one addition is `stdin=asyncio.subprocess.PIPE`
   with `communicate(stdin_text.encode())`, since `add` takes markers on stdin.
   Tests override this method — that is the spy seam, so no bash ever runs in
   the suites. Put it on `AgentMarksMixin` or a small sibling mixin both apps
   already inherit; do not duplicate it per app.

   Outcome mapping, used by both callbacks (correction 6):
   | rc / first line | user-visible result |
   |---|---|
   | 0, `ADDED:<n>` / `REMOVED:<csv>` | success notify with the count |
   | 3 or `LOCK_BUSY` | warning: "rejection store busy — try again"; nothing written |
   | 4 | error: store unusable, naming the store; **do not retry** |
   | 2 | error: bad request (a bug in the caller) |
   | other / `ERROR:` | error with the raw first line |

8. **App wiring — `monitor_app.py`** (`action_pick_concerns` :2830-2934,
   `_on_concerns_picked` :2936-2955):
   - The followed agent's pane is `self._snapshots[pane_id].pane` (`pane_id =
     self._focused_pane_id`, :2845-2846) — the snapshot the shadow shadows, not
     the shadow pane. Resolve
     `task_id = self._task_cache.get_task_id_for_pane(self._snapshots[pane_id].pane)`
     (the `get_task_id_for_pane(snap.pane)` idiom appears ~11× in this file,
     e.g. :2735, :2764). Fetch entries with
     `await self._run_rejected_cmd(["list", task_id, "--machine"])`. Parse
     `REJECTED:` lines with `split("|", 3)` — the marker line is **last**
     because it contains `|`. A lone `NO_REJECTIONS` line → empty; branch on
     that sentinel, never on the exit status (`list` exits 0 for every
     resolution outcome). No task id → `store_unavailable=True`, no fetch.
   - **Stash for the callback** (correction 3): set
     `self._concern_pick_task_id = task_id` right beside the existing
     `self._concern_pick_busy = True` (:2856), so the sync callback can read
     it. Clear it wherever the guard is cleared.
   - Pass `rejected_entries` / `store_unavailable` into `ConcernPickerModal`
     (:2921-2930).
   - `_on_concerns_picked(result: ConcernPickResult | None)`: release the guard
     first (unchanged, :2948 — `PickReentrancyTests` pins the release on every
     path), then **`if result is None: return`**, explicitly, not `if not
     result`. `result.forwarded` non-empty →
     `copy_to_system_clipboard(self, build_clipboard_payload(result.forwarded))`
     + notify, unchanged; never `app.copy_to_clipboard`
     (`tests/test_tui_clipboard_seam.sh` enforces it, :2951-2954).
     `result.rejected` non-empty → with a task id, dispatch `add <task_id>
     --producer picker` with one `concern_marker_line(c)` per concern on stdin
     via `run_worker` (correction 4); without one, the visible refusal notify.
     `result.unrejected` non-empty → `remove <task_id> <ids…>` the same way.

9. **App wiring — `minimonitor_app.py`** (`action_pick_concerns` :1846-1912,
   `_on_concerns_picked` :1914-1925): the same changes, with
   `snap = self._find_own_agent_snapshot()` (:1855) already in hand, so
   `task_id = self._task_cache.get_task_id_for_pane(snap.pane)` (the idiom at
   :1186, :1226, :1419). `narrow=True` (:1906) is unchanged. This callback has
   no busy guard, so it starts directly with the `is None` check.
   `_maybe_offer_concerns`'s dedup (:1988-1991) calls
   `build_clipboard_payload(concerns)` purely as a **dedup key** on the whole
   block — not a forward path, and unaffected by every change here.

10. **Tests:**
    - `tests/test_concern_picker_modal.py`: retarget the dismiss-contract test
      `test_ok_dismisses_with_selected_in_order` (:187) onto
      `ConcernPickResult` (forwarded order still by `original_index`) and
      `test_escape_dismisses_with_none` (:218) onto `None`. **Delete exactly
      three tests** — `test_select_all_toggles_every_row` (:170),
      `test_copy_all_dismisses_with_every_concern` (:204) and
      `test_select_all_skips_informational_but_copy_all_includes_it` (:310);
      the third lives in the *partition* suite rather than with the other bulk
      tests, which is why it is easy to leave behind as a dangling reference to
      two deleted actions. Informational dimming stays covered by
      `test_informational_row_carries_the_dim_class` (:296).
      Add: `r` toggles the ✗ glyph and the `.rejected` class;
      forward↔reject mutual exclusion; reject survives the partition reorder
      (duplicate-valued concerns stay positionally distinct — mirror
      `test_duplicate_valued_concerns_are_selected_positionally`, :364);
      `R` view happy path, un-reject ids in the result, and both empty-case
      notices. Re-tune the width-tier suite (:587) for the new help strings.
      Assert glyphs at render level (`render().plain` / row state), per the TUI
      conventions.
    - `tests/test_monitor_concern_action.py` (:259, :276) /
      `tests/test_minimonitor_concern_action.py` (:154, :173): callbacks
      invoked with `ConcernPickResult`; `_run_rejected_cmd` overridden as a
      spy recording `(args, stdin_text)` — no bash executed; plus the four
      pre-phase mitigation cases above.

## Verification

- `bash tests/run_all_python_tests.sh --test-dir tests` — read the **last
  stderr line** for the verdict (`PYTHON SUITE: PASSED|FAILED (runner=…,
  exit=N)`); if piping, check `${PIPESTATUS[0]}` or `set -o pipefail`.
- `bash tests/test_concern_body_display_contract.py` specifically green after
  the `EXPECTED_ACCESSES` edit, and proven able to fail per
  `[body_role_registry_row]`.
- `bash tests/test_monitor_modal_space_dispatch.py` — unchanged and green; it
  is what licenses leaving `r`/`R` unguarded against the App bindings.
- Live (tmux): open minimonitor against a followed agent with an active shadow
  and a concern block; press `c`, mark one concern with `r`, confirm →
  `.aitask-shadow/<task_id>/rejected.md` gains the entry; re-open the picker,
  press `R`, un-reject it, confirm → the entry is removed. Repeat in the full
  monitor. Confirm `git status --porcelain` stays clean throughout
  (`.aitask-shadow/` is gitignored).

## Risk

### Code-health risk: medium

- The dismiss contract changes shape across 2 apps, 1 shared modal and 4 dismiss
  sites; a missed site returns a bare `list` and the callback then reads
  `.forwarded` off it · severity: medium · → mitigation: inline pre-phase
  rejections_only_result_negative_control
- Extracting `concern_marker_line` **moves** a tracked `.body` read, and
  `EXPECTED_ACCESSES` is a FROZEN table whose whole purpose is to refuse a
  silent post-refactor pass · severity: medium · → mitigation: inline pre-phase
  body_role_registry_row
- A new subprocess seam reached from a **synchronous** dismiss callback: an
  unhandled `OSError` or a child that never exits would propagate out of, or
  wedge, the picker path · severity: medium · → mitigation: reuse
  `_run_marks_cmd`'s total contract verbatim (step 7) — pinned by the seam
  override in both suites
- Removing `a`/`A` leaves residual references in two prose sites (class
  docstring, xnarrow CSS comment) and two help strings; a missed one documents
  a key that no longer exists · severity: low · → mitigation: enumerated
  explicitly in step 3

### Goal-achievement risk: medium

- An unresolvable task id could silently drop rejections — the task file names
  this as the one thing that must never be silent · severity: high ·
  → mitigation: inline pre-phase task_id_refusal_is_visible
- Conflating helper exit 3 (busy, transient) with exit 4 (store unusable,
  permanent) turns a misconfiguration into an endless retry; t1427_1 recorded
  this as a requirement on this task · severity: medium · → mitigation: inline
  pre-phase exit_code_discrimination
- Un-reject acts on ids pre-fetched at picker-open time and staleness handling
  is descoped by decision; bounded only because t1427_1 made entry ids stable
  and never reused · severity: low · → mitigation: none — accepted, and the
  id-stability property it rests on is pinned by t1427_1's `entry_id_no_reuse`

### Planned mitigations
- timing: pre-phase | name: rejections_only_result_negative_control | type: test | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: a truthiness check swallowing a rejections-only result | desc: both callback suites assert a result with empty forwarded and non-empty rejected still triggers persistence, proven able to fail by reintroducing the truthiness check
- timing: pre-phase | name: task_id_refusal_is_visible | type: test | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: silently dropped rejections when the task id is unresolvable | desc: drive the no-task-id path with a non-empty rejected list and assert a warning-severity notify naming the missing task id AND that the seam was never invoked
- timing: pre-phase | name: exit_code_discrimination | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: conflating LOCK_BUSY with an unusable store | desc: assert helper rc 3, 4 and 2 produce three distinct user-visible outcomes rather than one catch-all failure message
- timing: pre-phase | name: body_role_registry_row | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: the frozen Concern-body role table silently passing after the marker-renderer extraction | desc: delete the new concern_marker_line row locally, confirm the guard fails with an unclassified-read finding naming it, restore, and record the observed failure text

## Final Implementation Notes

- **Actual work done:** All ten planned steps landed as specified, across 8
  files (+1256/−140). `concern_parser.concern_marker_line()` is now the single
  renderer of the canonical marker grammar. `_ConcernRow` carries a
  mutually-exclusive `_state` (`none`/`forward`/`rejected`) with a
  `_CONCERN_MARKS` glyph table; `a`/`A` are gone along with their bindings,
  methods, help entries and the two prose sites that named them.
  `ConcernPickResult` / `RejectedEntry` / `parse_rejected_machine_lines` and the
  new `RejectedStoreModal` (+`_RejectedRow`) live in `monitor_shared.py`, as
  does a new `ShadowRejectionsMixin` both apps inherit. Tests:
  `test_concern_picker_modal.py` 41→47, `test_monitor_concern_action.py` 64→71,
  `test_minimonitor_concern_action.py` 38→45.

- **Deviations from plan:**
  1. **The `rejections_only_result_negative_control` mitigation was re-targeted,
     because the mutation the plan specified is unreachable.** The plan (and the
     task file) called for pinning against an `if not result:` truthiness
     regression. That mutation was applied and **the whole suite still passed**:
     a `NamedTuple` with fields is *always* truthy, so `not result` is `True`
     only for `None` and the mutation is a structural no-op. A passing negative
     control means the control is wrong, so the test was re-aimed at the
     regression that **is** reachable — carrying the old "nothing selected,
     nothing to do" shortcut across as `if not result.forwarded: return`. Under
     that mutation both suites fail (4 tests each, including "the rejection was
     swallowed"). The always-truthy property is now stated in the
     `ConcernPickResult` docstring so the next reader does not re-add the
     unreachable guard.
  2. **The callback body is shared, not duplicated.** The plan specified
     equivalent edits to `_on_concerns_picked` in both apps; the logic was
     identical, so it became `ShadowRejectionsMixin.apply_concern_pick_result()`
     plus a `_persist_concern_dispositions()` worker. Each app's callback is now
     3 lines: the monitor releases its pick guard, the minimonitor has none.
  3. **`_fetch_rejected_entries` and `rejection_outcome_message` were added
     beside the planned `_run_rejected_cmd`.** The plan named one seam; the
     parse-and-branch and the exit-code vocabulary are equally shared, and
     leaving them at the call sites would have duplicated the `NO_REJECTIONS`
     check and the 2/3/4 discrimination in two apps.
  4. **`_writes()` test helper.** The picker pre-fetches with `list`, so the raw
     spy could not distinguish "wrote nothing" from "never read the store" —
     several assertions turn on exactly that difference.

- **Issues encountered:**
  - `EXPECTED_ACCESSES` in `test_concern_body_display_contract.py` is a FROZEN
    table and the extraction **moved** a tracked `.body` read. Adding the
    `concern_marker_line` row and deleting the stale `build_clipboard_payload`
    one was mandatory, and `test_guard_fails_when_the_clipboard_path_strips_the_trailer`
    (AC #2) had to be retargeted to the new key.
  - A hazard that looked real and is not: `monitor_app` binds `r`→`refresh` and
    `R`→`restart_task` at App level. Textual does **not** dispatch App-level
    `BINDINGS` under a `ModalScreen` — measured and pinned by
    `tests/test_monitor_modal_space_dispatch.py`. No guard was added; a future
    reader should not add one either.

- **Key decisions:**
  - **One shared, overridable subprocess seam.** `_run_rejected_cmd` copies
    `_run_marks_cmd`'s total contract (never raises, always terminates, timeout
    above the helper's own 10s lock timeout so a healthy contended writer
    reports `LOCK_BUSY` itself) and adds stdin, which `add` needs. It is also
    the test seam: no bash executes in any suite.
  - **Exit codes 2 / 3 / 4 stay distinct**, per t1427_1's note that conflating
    3 (busy) with 4 (unusable) turns a permanent misconfiguration into an
    endless retry.
  - **The no-task-id refusal is visible twice** — `R` says the store is
    unavailable *before* confirming, and the confirm path warns that rejections
    were not persisted.
  - **`RejectedStoreModal` accumulates across visits** rather than replacing, so
    reopening the view before confirming cannot discard earlier choices.

- **Verification evidence.** Full suite: `PYTHON SUITE: PASSED (runner=pytest,
  exit=0)`. `tests/test_tui_clipboard_seam.sh` 5/5. **Four negative controls**,
  each a single mutation, each restored byte-identically from a scratchpad
  backup (never `git checkout` — two other sessions were writing this tree):
  M1 forwarded-early-return → 8 failures across both suites ·
  M2 collapse rc 3/4 → both `test_exit_codes_are_discriminated` ·
  M3 silent no-task-id → both `test_no_task_id_is_a_visible_refusal` ·
  M4 drop the registry row → 3 failures naming `concern_marker_line`.
  Plus an **end-to-end probe against the real `aitask_shadow_rejected.sh`**
  (not the spy): `add --producer picker` → `ADDED:2`, `list --machine`
  round-tripped a body containing `|` byte-identically, `remove r1` →
  `REMOVED:r1` leaving `r2`, and an invalid id → rc 2 mapped to the
  bad-request message.

- **Upstream defects identified:** None.

- **Notes for sibling tasks:**
  - **t1427_3 (producers):** the store is written with `--producer picker` for
    picker-originated rejections, so `list`'s producer column distinguishes
    them from anything a producer writes itself. Entry ids are `r`-prefixed on
    the wire (`REJECTED:r1|…`) and `parse_rejected_machine_lines()` in
    `monitor_shared.py` is the ready-made parser if a Python consumer needs one.
  - **t1427_4 (docs):** the user-visible key map changed — `Space` forwards,
    `r` rejects, `R` opens the rejected list, `u` inspects unparsed; **`a` and
    `A` no longer exist**. Both help strings (`_CONCERN_HELP_FULL` /
    `_CONCERN_HELP_COMPACT`) are the canonical wording and stay readable to 24
    columns. The doc surfaces listed in the parent task all still name `a`/`A`.
  - **Cross-agent skills:** nothing in `.claude/skills/` changed here, so no
    Codex/OpenCode port is implied by this child.

Post-implementation cleanup, archival, and merge follow **Step 9
(Post-Implementation)** of the task workflow.
