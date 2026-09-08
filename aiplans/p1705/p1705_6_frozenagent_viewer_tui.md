---
Task: t1705_6_frozenagent_viewer_tui.md
Parent Task: aitasks/t1705_frozen_codeagents_session_store_and_viewer_tui.md
Sibling Tasks: aitasks/t1705/t1705_10_freeze_restore_workflow_docs.md, aitasks/t1705/t1705_11_manual_verification_frozen_codeagents_session_store_and_view.md, aitasks/t1705/t1705_7_monitor_minimonitor_frozen_rows.md, aitasks/t1705/t1705_8_frozen_agents_acceptance_test.md, aitasks/t1705/t1705_9_frozenagent_tui_docs.md
Archived Sibling Plans: aiplans/archived/p1705/p1705_1_spike_freeze_standin_and_session_id_capture.md, aiplans/archived/p1705/p1705_2_framework_session_store.md, aiplans/archived/p1705/p1705_3_session_id_capture_hooks.md, aiplans/archived/p1705/p1705_4_freeze_engine.md, aiplans/archived/p1705/p1705_5_restore_and_repick_flows.md
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5 @ 2026-09-08 18:10
---

# t1705_6 — `ait frozenagent` viewer TUI

*Re-verified 2026-09-08 against the shipped tree (t1705_5 landed at `c4499ed7c`).
Findings are listed in `## Re-verification findings` at the bottom; the steps
below already incorporate them.*

## Context

Sixth child of t1705 (frozen code agents). t1705_1..t1705_5 shipped the session
store, the session-id hooks, the freeze engine and the restore coordinator. What
is missing is the thing the user actually looks at: when an agent is frozen, its
pane is respawned into `ait frozenagent --record <id>` — a **stand-in viewer**
that renders the agent's persisted terminal output in place and offers the way
back (restore / re-pick / drop).

Nothing renders those captures today. `lib/agent_sessions.standin_command()`
already returns `ait frozenagent --record <id>`, and live freeze tests run
against `tests/lib/fake_standin.sh`, a placeholder that only reproduces the
self-stamp. Until this task lands, freezing an agent leaves a pane running a
stub, and `t1705_7` (monitor/minimonitor frozen rows) is blocked on it.

Name `frozenagent` and switcher key `f` are **PINNED** user decisions. Two rules
from the parent plan's §B/§D are this child's own responsibility:

- the viewer stamps `@aitask_standin_ready=<record-id>` **on its own pane, after
  mount and only then** (the `mark_monitor_pane` rule — an app stamps its own
  pane, never another's);
- the viewer **never mutates the store and never respawns anything itself**.
  Restore / re-pick / drop shell out to `aitask_frozen.sh` via
  `tmux run-shell -b`, because the coordinator replaces this very pane and a
  child of it would be killed mid-transaction.

Build against the **amended** four-outcome restore contract (parent plan
amendments B1–B4): a `liveness` confirm is a **success that keeps the captures**,
and a codex record can only ever reach `liveness` — the UI must not present that
as an error.

## Files

- **New** `.aitask-scripts/frozenagent/__init__.py`,
  `.aitask-scripts/frozenagent/frozenagent_app.py`,
  `.aitask-scripts/frozenagent/capture_log.py`,
  `.aitask-scripts/aitask_frozenagent.sh`
- **Edit** `ait` — usage `TUI:` block (`:27-38`), update-check bypass alternation
  (`:190`), dispatcher case beside `diffviewer` (`:208`)
- **Edit** `.aitask-scripts/lib/tui_registry.py` (`TUI_REGISTRY`, `:18-29`),
  `.aitask-scripts/lib/tui_switcher.py` (`_TUI_SHORTCUTS` `:216-226`,
  `_HINT_ITEMS` `:244-256`, `_QUICK_JUMP_BINDINGS` `:393-407`,
  `action_shortcut_frozenagent` beside `:1086-1128`),
  `.aitask-scripts/lib/shortcut_scopes.py` (`KNOWN_BINDING_SOURCES` `:47-64`)
- **Edit** `.aitask-scripts/lib/agent_freeze.py` (new `drop` verb),
  `.aitask-scripts/aitask_frozen.sh` (its usage + dispatch),
  `.aitask-scripts/lib/agent_sessions.py` (`drop --nonce`; new `lease-release`
  verb), `.aitask-scripts/aitask_agent_sessions.sh` (`cmd_drop` forwards its
  flags; `lease-release` case + usage),
  `.aitask-scripts/lib/agent_frozen_ops.py` (`AITASKS_DROP_FAIL_AT` seam,
  `drop_pre_store` pause stage),
  `.aitask-scripts/monitor/monitor_core.py` (extract
  `FROZEN_AWARE_PANE_FORMAT` + `classify_window_panes`; reorder
  `kill_agent_pane_smart`'s frozen branch to kill-then-drop)
- **Edit** `tests/test_no_lib_to_tui_import.sh` (`TUI_PACKAGES` `:46-49`),
  `tests/test_shortcuts_registry_coverage.sh` (`TUIS` `:54`),
  `tests/test_textual_markup_structure.py` (header-escaping pin),
  `tests/test_agent_freeze.py` (the `drop` verb), `tests/test_kill_agent_pane_smart.sh`
  and `tests/test_cleanup_rule_parity.sh` (the reordered frozen branch),
  `tests/test_agent_sessions_lease.py` (`lease-release`),
  `tests/test_agent_sessions_transitions.py` (`drop --nonce`)
- **New tests** `tests/test_frozenagent_app.py`,
  `tests/test_frozenagent_standin_stamp.sh`,
  `tests/data/frozen_capture/sample.ansi` + `sample.txt`

## Implementation steps

### Pre-phase (risk mitigations)

1. `[verify_standin_respawn_argv]` **Before writing the app**, prove the
   respawn contract the whole stand-in design rests on. Land the first half of
   `tests/test_frozenagent_standin_stamp.sh` against a minimal
   `frozenagent_app.py` that does nothing but mount and stamp: on an isolated
   tmux server (`tests/lib/tmux_isolation.sh` → `require_isolated_tmux`), stamp
   a pane `@aitask_frozen=<id>` and
   `respawn-pane -k -t <pane> "$(standin_command <id>)"`, then assert
   `#{@aitask_standin_ready} == <id>` on **that** pane within 5 s and empty on a
   sibling. This proves (a) the `ait frozenagent --record <id>` argv survives
   `respawn-pane`'s single-string quoting, (b) `ait` resolves on the respawned
   pane's PATH, and (c) the self-stamp lands on the right pane. If any of the
   three fails, the fix belongs in `standin_command` / the launcher — not in
   1000 lines of already-written app.

### Main implementation

1. **Launcher + dispatcher.** `aitask_frozenagent.sh` is a verbatim clone of
   `aitask_diffviewer.sh` (`aitask_path.sh` / `python_resolve.sh` /
   `terminal_compat.sh` sourcing, `require_ait_python`, the textual+yaml probe,
   `ait_warn_if_incapable_terminal`, then
   `exec "$PYTHON" "$SCRIPT_DIR/frozenagent/frozenagent_app.py" "$@"`). CPython,
   not PyPy — only `ait board` is routed through the fast path
   (`aidocs/framework/python_tui_performance.md`).

   `ait`: add `frozenagent    Launch the frozen-agent viewer TUI` to the `TUI:`
   usage block (alphabetical, after `diffviewer`);
   `frozenagent)  shift; exec "$SCRIPTS_DIR/aitask_frozenagent.sh" "$@" ;;`
   beside the `diffviewer` case; and add `frozenagent` to the update-check
   bypass alternation at `:190` — a stand-in respawned by the freeze engine must
   never stall on a version check.

2. **`CaptureLog(RichLog)`** (`frozenagent/capture_log.py`) — RichLog with the
   three selection overrides Textual's own `Log` has and `RichLog` does not (see
   finding **V1**). Mirror `textual/widgets/_log.py:265-345`:

   ```python
   class CaptureLog(RichLog):
       """RichLog + the native-selection support RichLog lacks (t1705_6, V1)."""

       def __init__(self, *args, **kwargs):
           super().__init__(*args, **kwargs)
           self._plain: list[str] = []      # ANSI-stripped, one per source line

       def get_selection(self, selection: Selection) -> tuple[str, str] | None:
           return selection.extract("\n".join(self._plain)), "\n"

       def selection_updated(self, selection: Selection | None) -> None:
           self._line_cache.clear()
           self.refresh()

       def render_line(self, y: int) -> Strip:
           scroll_x, scroll_y = self.scroll_offset
           strip = self._render_line(scroll_y + y, scroll_x,
                                     self.scrollable_content_region.width)
           strip = strip.apply_style(self.rich_style)
           strip = strip.apply_offsets(scroll_x, scroll_y + y)
           selection = self.text_selection
           if selection is not None:
               span = selection.get_span(scroll_y + y)
               if span is not None:
                   strip = self._paint_span(strip, span)
           return strip
   ```

   `_paint_span` uses `Strip.divide([start, end])` → restyle the middle strip
   with the selection style → `Strip.join`; `end == -1` means "to end of line".
   `apply_offsets` is what lets the compositor map a mouse position back to a
   text offset — without it a drag selects nothing, which is precisely the
   defect V1 records. `_plain` is set alongside every `write()` so extraction
   always matches what is on screen.

3. **App skeleton** (`frozenagent/frozenagent_app.py`). Module-level import must
   be side-effect free — `lib/shortcut_scopes.py` imports it to sweep bindings.

   ```python
   class FrozenAgentApp(TuiSwitcherMixin, ShortcutsMixin, App):
       _shortcuts_scope = "frozenagent"
       TITLE = "ait frozenagent"
       BINDINGS = [
           *TuiSwitcherMixin.SWITCHER_BINDINGS,
           *ShortcutsMixin.SHORTCUTS_MIXIN_BINDINGS,
           Binding("q", "quit", "Quit"),
           Binding("r", "toggle_plain", "Plain/ANSI"),
           Binding("m", "markdown", "Markdown"),
           Binding("slash", "search", "Search"),
           Binding("n", "search_next", "Next", show=False),
           Binding("escape", "cancel", "Cancel", show=False),
           Binding("shift+up", "select_up", "", show=False),
           Binding("shift+down", "select_down", "", show=False),
           Binding("y", "copy", "Copy"),
           Binding("g", "scroll_top", "", show=False),
           Binding("G", "scroll_bottom", "", show=False),
           Binding("R", "restore", "Restore"),
           Binding("p", "repick", "Re-pick"),
           Binding("k", "drop", "Drop"),
       ]

       def __init__(self, record_id: str | None = None) -> None:
           super().__init__()
           self.current_tui_name = "frozenagent"
           self._record_id = record_id
           self._view = SessionsView()
   ```

   `main()` parses `--record <id>`; absent → list mode. `--record` resolves via
   `SessionsView().by_id(id)` (the lock-free reader); unknown id → print
   `frozenagent: unknown record <id>` to stderr and exit 2.

4. **Viewer screen.** `compose`: `Static(id="fa-header", markup=True)`,
   `CaptureLog(highlight=False, markup=False, wrap=False, id="fa-log")`,
   `Input(id="fa-search", classes="hidden")`, `Footer()`.

   `on_mount`, in this order:
   - `self.query_one("#fa-log", CaptureLog).focus()` **first, on every path
     including the missing-capture early return** — Textual otherwise focuses
     the hidden search `Input`, which swallows every binding key (t1486; the
     exact trap `logview_app.py:88-99` documents).
   - load: `capture.ansi` bytes → `Text.from_ansi(decoded)` into the log,
     `capture.txt` lines into `self._lines` (search + keyboard selection) and
     into `log._plain` (native extraction).
   - header from the record + task title.
   - **then and only then** stamp:
     `TmuxClient().run(["set-option", "-p", "-t", os.environ["TMUX_PANE"], STANDIN_READY_OPTION, record_id])`,
     guarded on `TMUX_PANE` being set (outside tmux: no call at all, log a
     debug line). `STANDIN_READY_OPTION` comes from
     `monitor.monitor_core` — a TUI package importing `monitor` is established
     (`applink/server.py:25`), and `test_no_lib_to_tui_import.sh` only guards
     `lib/` → TUI.

   Header line:
   `<project> · <window> · t<task_id> <title> · <agent_string> · frozen <frozen_at> · <capture_lines> lines · <state>`
   — `<project>` via `agent_launch_utils.compact_root(Path(rec.root))`, `<title>`
   via `TaskInfoCache(project_root=Path(rec.root)).get_task_info(rec.task_id)`
   (`monitor_core.py:3970`; `""` when the record is unbound). **Escape every
   interpolated field with `rich.markup.escape`** — a window name containing
   `[x]` is read as an unknown tag and silently vanishes (t1486; pin it in
   `tests/test_textual_markup_structure.py`).

   Missing capture file → header says `capture missing`, the log shows one dim
   line, and `R` / `p` / `k` stay bound (the record is still restorable).

5. **Plain / markdown.** `r` re-renders from `capture.txt` (`Text(decoded)`) and
   back to `Text.from_ansi`; the header shows an escaped `\[plain]`. `m` pushes a
   `ModalScreen` containing `VerticalScroll > Markdown` over the keyboard-selected
   range if one is active, else the whole `.txt`; `escape` closes. Use plain
   `textual.widgets.Markdown` — **not** `lib/section_viewer.SectionAwareMarkdown`,
   which is a minimap/section-navigation widget (finding **V7**).

6. **Search.** Port `logview_app.py:173-205` onto `self._lines`
   (case-insensitive substring): `/` reveals the `Input`, `n` advances,
   `escape` cancels and returns focus to the log. Wrap with a
   `Search wrapped to top` notify and a `Not found: <term>` warning. Add what
   logview lacks: highlight the current match by restyling that line with
   `reverse`, remembering the previous index so it can be restored.

7. **Keyboard range selection + copy.** Port the model from
   `codebrowser/code_viewer.py:381-452` onto the `self._lines` index —
   `_selection_start` / `_selection_end` / `_selection_active`,
   `extend_selection(±1)`, `clear_selection()`, `get_selected_range()`
   (1-indexed) — and render it by restyling the affected log lines.
   `action_copy` resolves in this order: an active keyboard range →
   `"\n".join(self._lines[a-1:b])`; else `log.text_selection` →
   `log.get_selection(sel)` (the mouse path, working because of step 2); else
   `notify("Nothing selected")`. The copy goes through
   `lib/tui_clipboard.copy_to_system_clipboard(self, text)` and **nothing else**
   — `tests/test_tui_clipboard_seam.sh` fails any direct
   `app.copy_to_clipboard(` call anywhere under `.aitask-scripts/`.

8. **Actions (both modes, on the current record).** All three dispatch the same
   way and **never** block the event loop:

   ```python
   def _run_frozen(self, argv: list[str]) -> None:
       self._tmux.run(["run-shell", "-b",
                       shlex.join([str(FROZEN_SH), *argv])])
   ```

   Never `subprocess` — the coordinator replaces this pane and must outlive it.
   `run-shell -b` only *schedules* the job: it returns immediately, returns
   nothing, and the coordinator may not have started when the first poll fires.
   Both outcome paths below are built around that fact (findings **V10**,
   **V11**).

   - `R` → restore; `p` → re-pick (`notify("This record has no task id — restore
     instead", severity="warning")` and do nothing when `rec.task_id == ""`);
     `k` → drop, behind a confirm modal ("Remove the frozen record and its
     capture? This cannot be undone.") shaped like
     `monitor_shared.KillConfirmDialog:2019` (copy the shape, do **not** import
     that module).

   **Single-flight, per record (finding V13).** All three dispatch detached
   coordinators, and the store's `drop` is legal from **any** state and takes no
   nonce — so it is not refused by the lease that `restore-begin` mints. Nothing
   otherwise stops a user pressing `R` and then `k` before `restore-begin` runs,
   at which point the drop coordinator deletes the record and the only capture
   out from under an in-flight restore.

   Hold `self._pending: dict[str, str]` — record id → the action in flight —
   set at dispatch and cleared on **every** terminal outcome, including both
   grace expiries. Keyed per record, not globally, so list mode can legitimately
   have several in flight (`restore --all` does exactly that). While a record is
   pending, `check_action` returns `False` for `restore` / `repick` / `drop` on
   it, so Textual greys the key in the footer rather than silently swallowing
   the press, and an attempt notifies
   `"<action> already in flight for t<id>"`. A second `R` is refused here rather
   than left to the store, where it would surface as an opaque
   `TRANSITION_REFUSED`.

   The in-app guard covers one viewer; the coordinator's own in-flight refusal
   (step 9.0) is what covers two — a list-mode viewer in another window and the
   stand-in can both reach the same record.

   **`R` / `p` — the restore outcome path.** Before dispatch, snapshot
   `pre = (state, restore_attempts, op_nonce)` from the current record. Header
   goes to `dispatching…` — *not* `restoring…`, which would be a claim the
   viewer has no evidence for yet. Then `set_interval(1.0, self._poll_restore)`
   (`self._view.invalidate()` each tick):

   - **Pre-begin gate.** Until `rec.restore_attempts > pre.restore_attempts`
     (the only field `restore_begin` bumps monotonically — `agent_sessions.py:989`),
     the coordinator has not started. **Ignore `last_error` entirely** in this
     window: on a record whose previous restore failed it still holds that
     older attempt's `<old-nonce>:<reason>`, and reading it here would report
     the *new* restore as failed before it began. Keep showing `dispatching…`.
   - If the gate never opens within `DISPATCH_GRACE = 10 s`, stop polling and
     show `restore did not start — run 'ait frozenagent' or reconcile` (covers a
     `run-shell` job that never ran: missing binary, un-resolvable `ait`).
   - Once the gate opens, bind `nonce = rec.op_nonce` and interpret only against
     it. `last_error` counts **only** when it starts with `f"{nonce}:"` — the
     store's documented `"<nonce>:<reason>"` shape (`agent_sessions.py:786`),
     and the exact prefix test the coordinator itself uses
     (`agent_restore.py:519`):
     - back to `frozen` with a matching `last_error` → header
       `restore failed: <reason> — capture kept`; stop polling.
     - `live` → the pane is about to be replaced; do nothing. If it is not
       replaced within `frozen_ops.restore_ack_grace() + 5` s, show
       `restored elsewhere`.
     - `ack == "liveness"` → `restored, unverified — capture kept`. **This is a
       success, not a failure** (amendment B4), and it is the *only* outcome a
       codex record can reach — style it neutrally, never as an error.

   **`k` — its own completion path, never the restore interpreter.** A dropped
   record does not pass through `restoring` or `live`; it *disappears*. Routing
   `k` into `_poll_restore` would leave the app stuck on a state it can never
   observe. So: header → `dropping…`, then `set_interval(1.0, self._poll_drop)`:
   - `self._view.by_id(rid) is None` → **success**: `dropped — capture removed`;
     stop polling. In viewer mode the pane is about to be killed anyway; in list
     mode drop the row and return focus to the table.
   - record still present after `DROP_GRACE = 10 s` → `drop failed — record kept`
     (warning); stop polling. The coordinator's `DROP_FAILED:` line goes to a
     `run-shell` job whose stdout the viewer cannot read, so the record's
     continued existence is the observable.

   Stop every timer in `on_unmount` — a live `set_interval` at
   `App.run_test` exit fails the enclosing test
   (`aidocs/framework/testing_conventions.md`).

9. **`drop` verb** (`aitask_frozen.sh` + `lib/agent_freeze.py`), **kill-first
   and fail-closed**. The verb does not exist today (finding **V2**).

   **Ordering is the whole design here (finding V9).** The store's `drop`
   (`agent_sessions.py:1116`) removes the record *and its capture files* — the
   only copy of that session's output. Sequence it so the irreversible step is
   last and every intermediate state is one `reconcile` already repairs:

   **`drop` becomes a leased verb — an atomic claim, not a value comparison
   (finding V14).** Two weaker designs were considered and rejected:

   - *Pre-checking with `show`* is unsound: `show` is explicitly lock-free
     (`aitask_agent_sessions.sh:265-270`), so a `restore-begin` can land between
     the read and the delete.
   - *Comparing a snapshotted `(state, op_nonce)` under the lock* is **ABA-
     vulnerable**: `standin_respawned` from `aborting` calls `_set_state(FROZEN)`
     **and** `_clear_lease()` (`agent_sessions.py:1090-1094`), which zeroes
     `op_nonce`. So `(frozen, "")` → `(restoring, n)` → `(aborting, n)` →
     `(frozen, "")` restores the identical pair — and that final transition is
     precisely the one that records a **newly respawned stand-in viewer**.
     Comparing values would accept the stale delete and leave a live stamped
     viewer whose record and capture are gone: the exact V9 state this whole
     protocol exists to prevent.

   The store already has the right primitive, and the plan's §A contract already
   states the rule — *"every verb that mutates a record holding a lease requires
   `--nonce`"*. `drop` is the sole exception. Close it:

   - `drop <id>` — **unchanged**: any state, no nonce. This is
     `kill_agent_pane_smart`'s contract, where the user has explicitly killed
     the pane and it is going away regardless.
   - `drop <id> --nonce <n>` — `_require_nonce` (`agent_sessions.py:648`) inside
     the existing write lock; a mismatch prints `NONCE_MISMATCH:<id>` and exits
     **6**, the code the store already uses for exactly this. No new exit code,
     no new comparison semantics.
   - `lease-release <id> --nonce <n>` → `RELEASED:<id>` — the missing
     counterpart to `lease-take` (`_require_nonce` + `_clear_lease`). Without it
     an aborted drop leaves the record leased until the 60 s grace expires,
     making an immediate retry impossible.

   `cmd_drop` must forward its extra arguments; it currently discards them.

   0. **Claim the record.** `lease-take <id>`, which is atomic under the write
      lock and already encapsulates the staleness rule — it refuses with
      `LEASE_HELD:<id>` (exit 8) while a live or fresh lease exists, and takes
      over a stale one whose owner is gone, so a crashed coordinator can never
      make a record permanently undroppable. On `LEASE_HELD` print
      `DROP_REFUSED:<id>|in_flight`, exit non-zero, **kill nothing**. Otherwise
      bind the returned `nonce` and read `show <id>` for the pane inventory
      below.

      This replaces the earlier advisory `show`-based fast-fail entirely, and
      with it the promotion of `_lease_stale` / `_stale_op_grace` and the
      derived `lease_in_flight:` field — `lease-take` *is* that check, done
      atomically and in one place.

   1. **Preflight the pane inventory** — one `list-panes` over the record's
      window, which is also what the kill rule needs. Resolve the target
      (finding **V12**):
      - `pane_id == ""` (the gone-pane commit) → **gone**;
      - `pane_id` absent from the listing → **gone**. This is *not* an edge
        case: `_reconcile_frozen` (`agent_freeze.py:688-695`) returns
        `KEEP:<id>|pane_gone` and writes nothing, so a frozen record keeps its
        original nonempty `pane_id` indefinitely after a tmux server restart.
        Treating that as a kill failure would make exactly the records a user
        most wants to remove undroppable;
      - `pane_id` present but its `@aitask_frozen` is not this record id →
        **not ours** (a recycled `%N`). Treat as gone and **never kill it** —
        pane options die with the pane, so a recycled pane cannot carry our
        stamp, which is what makes the stamp the authoritative identity join
        (parent plan §B);
      - `pane_id` present and stamped ours → **kill it**, whether `pane_dead`
        is `0` or `1`. A dead pane is still a real pane object holding the
        window open under `remain-on-exit`; skipping it would leave the
        stand-in's corpse behind.

   2. **Kill**, by the shared rule (below). Pane user options are pane-scoped
      and die with the pane, so this also retires `@aitask_frozen` /
      `@aitask_record` / `@aitask_standin_ready` — there is no unstamp step to
      fail. If the kill fails: print `DROP_FAILED:<id>|kill:<reason>`, exit
      non-zero, **change nothing**. The user still has a working viewer and an
      intact capture.

   3. Only after the target is **verified gone** — either the preflight said so,
      or a re-read of the pane list shows the id absent — proceed.

   4. **The leased delete.** `frozen_ops.pause_at("drop_pre_store")`, then
      `aitask_agent_sessions.sh drop <id> --nonce <n>` with the nonce claimed in
      step 0.
      - success → `DROPPED:<id>`;
      - `NONCE_MISMATCH:<id>` (exit 6) → someone minted a new lease over ours
        while we were killing the pane. Print `DROP_ABORTED:<id>|raced`, exit
        non-zero. **The record and the capture survive** — this is the whole
        point, and unlike a value comparison it cannot be fooled by an
        ABA cycle, because any intervening transition mints or clears a nonce
        and our specific `<n>` never comes back;
      - any other failure → `lease-release <id> --nonce <n>`, then report. The
        record stays `frozen` with its pane gone, which is reconcile's benign
        `frozen | pane gone | keep (restorable into a new window)` row.
        Re-running `drop` converges immediately, because the lease was released.

   5. **Release on every abort path** after step 0 (`lease-release <id>
      --nonce <n>`, best-effort). A leaked lease is self-healing — it goes stale
      once our pid exits — but only after the 60 s grace, which would make a
      user's retry appear to hang.

   **Two residuals, accepted and documented in the verb's docstring** so nobody
   "fixes" them by reordering:

   - **Holding the lease detects a concurrent restore; it does not prevent one.**
     `restore_begin` (`agent_sessions.py:970-996`) checks only the state and
     mints its lease unconditionally — it does not consult an existing one. That
     asymmetry is pre-existing store behaviour (t1705_2/_5 territory) and is
     deliberately not changed here: reconcile's takeover flows depend on the
     current semantics. It is sufficient for this protocol, because the
     requirement is that `drop` never deletes under an in-flight operation, and
     a stolen lease makes our `--nonce` fail closed. Against **reconcile**
     specifically the lease *is* true mutual exclusion — it honours
     `LEASE_HELD`.
   - **The pane kill in step 2 cannot be made conditional.** If a restore begins
     between the kill and the delete, the user loses the *stand-in pane* — never
     the record and never the capture. The record remains restorable into a
     fresh window (`_reconcile_frozen`'s `KEEP:<id>|pane_gone`). Losing a
     replaceable viewer is the correct trade against losing the only copy of a
     session's output.

   The reverse order — the one **shipped** in `kill_agent_pane_smart`
   (`monitor_core.py:3419-3427`) — produces the one unrecoverable state: a live
   pane still stamped with an id whose record and capture are gone. `reconcile`
   iterates *records*, so it cannot see that pane at all. Flip that branch to
   kill-then-drop in the same commit and correct its comment; two opposite
   orderings for one operation is precisely the drift
   `tests/test_cleanup_rule_parity.sh` exists to prevent. Send `./ait note
   1705_7 --from 1705_6` recording the reorder, since t1705_7 owns the monitor
   keys that reach this path.

   **The kill rule is reused, not reimplemented (finding V9b).** There are
   already three implementations of "does this window still hold a real agent?"
   (`aitask_companion_cleanup.sh`, `kill_agent_pane_smart`, and the parity
   fixture); a fourth is the wrong answer. The rule is already decomposed:
   `count_other_real_agents` (`monitor_core.py:928`) is pure and import-free,
   and `is_shadow_target` / `is_live_companion_marker` / `_is_companion_process`
   are module-level. Extract only the two pieces still trapped inside
   `kill_agent_pane_smart` — the 5-field `list-panes` format and the `is_helper`
   composition (frozen checked **first**, so a stale companion marker cannot
   override it) — into module-level `FROZEN_AWARE_PANE_FORMAT` and
   `classify_window_panes(stdout) -> list[tuple[str, bool]]` in `monitor_core`,
   and have `kill_agent_pane_smart` call them. The coordinator then calls the
   same two functions plus `count_other_real_agents`: one rule, two Python call
   sites, **zero** new implementations. `agent_frozen_ops` already imports
   `monitor.monitor_core`, so the arrow stays one-way.

   Wire-up: add `drop <id>` to `aitask_frozen.sh`'s header comment, `usage()`
   and its `case` (dispatching to `FREEZE_PY` — the coordinator module must not
   depend on `agent_restore`), and to `agent_freeze.main()`'s verb table. Add
   the failure-injection seam `AITASKS_DROP_FAIL_AT=kill|verify|store` via the
   existing `frozen_ops.make_fail_at` (honoured only under `AITASKS_TEST_MODE=1`)
   so a test can fire between every irreversible step. Route every tmux call
   through `agent_frozen_ops` (`run` / `set_option` / `unset_option`) so
   `tests/test_no_raw_tmux.sh` stays green.

10. **List mode.** Bare `ait frozenagent` → a `DataTable` over
    `SessionsView().frozen()`, one row per record
    (`compact_root(rec.root)`, `rec.window`, `t<task_id>`, `rec.agent_string`,
    `rec.frozen_at`, `rec.capture_lines`). `enter` pushes the viewer screen for
    the highlighted id; `R` / `p` / `k` act on the highlighted row through the
    same `_run_frozen`; `q` quits. **List mode never stamps** — it is not a
    stand-in. This is the mode the switcher launches.

11. **Registration — the four-part atomic change**
    (`aidocs/framework/tui_conventions.md:583-602`), plus three test lists:
    - `tui_registry.py`: `("frozenagent", "Frozen Agent", "ait frozenagent", True)`
      positioned **after `monitor`** (grouped by function, not alphabetically).
    - `tui_switcher.py`: `_TUI_SHORTCUTS["frozenagent"] = "f"`;
      `Binding("f", "shortcut_frozenagent", "Frozen Agent", show=False)` in
      `_QUICK_JUMP_BINDINGS`;
      `def action_shortcut_frozenagent(self): self._shortcut_switch("frozenagent")`.
      `f` is free — the taken set is `a l b m c s t y r x X g n e` (finding
      **V3**) — and these bindings live on `TuiSwitcherOverlay`, not on the host
      App, so `f` cannot collide with a per-TUI `f`.
    - `_HINT_ITEMS`: add `("shortcut_frozenagent", "frozen", "f")` **only if**
      `tests/test_tui_switcher_footer_fit.sh` stays green with 13 items; drop it
      otherwise (the registry row and the key still work without a hint).
    - `shortcut_scopes.py`: `("frozenagent_app", "frozenagent/frozenagent_app.py", ("frozenagent",))`.
    - `tests/test_no_lib_to_tui_import.sh` `TUI_PACKAGES` += `frozenagent`;
      `tests/test_shortcuts_registry_coverage.sh` `TUIS` += the app with
      `lambda C: C()`.

### Post-phase (risk mitigations)

1. `[pin_textual_selection_internals]` Add an upgrade guard to
   `tests/test_frozenagent_app.py`: assert that `Strip.apply_offsets`,
   `Selection.get_span`, `Strip.divide`, `Strip.join` and `RichLog._line_cache`
   all still exist, and that `"get_selection" not in RichLog.__dict__` (the
   premise `CaptureLog` exists for). `CaptureLog` reaches into Textual internals
   that carry no compatibility promise; without this, a Textual upgrade breaks
   mouse selection **silently** — the drag still runs, it just copies nothing.
   The guard turns that into a named test failure.

2. `[cover_drop_destructive_path]` Cover the new `drop` verb end to end, driving
   `AITASKS_DROP_FAIL_AT` between **every** irreversible step. In
   `tests/test_agent_freeze.py` (fake tmux + temp store):
   - happy path: pane killed, verified gone, *then* record and capture directory
     removed — assert the order, not just the end state;
   - `AITASKS_DROP_FAIL_AT=kill` → `DROP_FAILED:<id>|kill:…`, non-zero exit, and
     **the record, the captures and the pane options are all still there**. This
     is the assertion that pins the whole fail-closed protocol;
   - `AITASKS_DROP_FAIL_AT=verify` → the kill was issued but not confirmed:
     nothing is dropped;
   - `AITASKS_DROP_FAIL_AT=store` → pane gone, record still `frozen`; re-running
     `drop` converges, and `reconcile` leaves it alone (its
     `frozen | pane gone | keep` row);
   - **preflight (V12)**, three rows: `pane_id == ""` → no kill, dropped;
     `pane_id` **nonempty but absent from the listing** → no kill, dropped
     *successfully* (the post-server-restart record — assert it is not reported
     as a kill failure); `pane_id` present but stamped with a **different**
     record id → no kill (assert no kill argv was issued at all) and the record
     dropped. Plus `pane_dead=1` on our own stamped pane → it **is** killed;
   - **claim refusal (V13)**: a record in `restoring` with a fresh lease →
     `lease-take` returns `LEASE_HELD` → `DROP_REFUSED:<id>|in_flight`, non-zero
     exit, **no kill argv issued**, record and capture untouched. The same
     record with a stale lease (grace elapsed via `AITASKS_STALE_OP_GRACE` under
     `AITASKS_TEST_MODE=1`, owner pid dead) → claimed and dropped;
   - **the ABA race (V14) — the test the whole design exists for.** Drive the
     exact interleaving with the existing SIGSTOP seam: run the drop coordinator
     with `AITASKS_FROZEN_PAUSE_AT=drop_pre_store` so it stops *after* the kill
     and *before* the store call. While it is stopped, run a **complete
     restore-and-recovery cycle** back to the starting values —
     `restore-begin` → `restore-abort` → `standin-respawned`, which returns the
     record to `frozen` with `op_nonce` cleared *and registers a new stand-in
     viewer*. `SIGCONT`. Assert `DROP_ABORTED:<id>|raced`, a non-zero exit, and
     that **the record and every capture file still exist**. This is the case a
     `(state, op_nonce)` comparison would have accepted;
   - the simpler races too: `lease-take` alone during the pause (state
     unchanged, nonce replaced), and `restore-begin` alone (both changed);
   - store-level unit tests in `tests/test_agent_sessions_transitions.py`:
     `drop --nonce` with the held nonce → deleted; with any other nonce →
     `NONCE_MISMATCH`, exit 6, nothing written; against a record with **no**
     lease → `NONCE_MISMATCH` (an empty stored nonce must never match);
     plain `drop <id>` with no flags → unchanged any-state behaviour (the
     `kill_agent_pane_smart` contract). Plus `lease-release`: correct nonce →
     `RELEASED` and the record is immediately `lease-take`-able; wrong nonce →
     `NONCE_MISMATCH`, lease intact.

   In `tests/test_frozenagent_standin_stamp.sh` (isolated server): the stand-in
   pane is actually killed, and the companion minimonitor **survives** when a
   real agent sibling remains in the window. Add a parity row to
   `tests/test_cleanup_rule_parity.sh` covering the coordinator's call site, so
   the third and fourth users of the rule cannot drift.

   Also assert the abort paths **release the claim**, so a retry is immediate
   rather than waiting out the 60 s lease grace.

   `drop` deletes the only copy of a frozen agent's output and kills a pane; it
   is the one irreversible thing this task adds.

## Tests

`tests/test_frozenagent_app.py` — `App.run_test`, headless, fake `TmuxClient`
recording argv, temp store via `AITASKS_AGENT_SESSIONS_FILE` + `AITASKS_FROZEN_DIR`,
fixture capture in `tests/data/frozen_capture/`:

- ANSI render vs `r` plain render (assert rendered plain text, never `.spans`);
- search: hit, wrap, not-found, and the current-match highlight;
- keyboard range: `shift+down` ×2 then `y` copies exactly those three lines
  (monkeypatch `copy_to_system_clipboard`, assert the text);
- native mouse path: `log.get_selection(Selection(...))` returns the expected
  text — the direct regression pin for finding **V1** — plus `apply_offsets` is
  applied and a covered line is painted;
- markdown modal renders the selected range;
- header escapes `[x]` in a window name; startup focus is the log on **both**
  the happy and the missing-capture paths;
- `R` / `p` / `k` produce the exact `run-shell -b` argv, and `p` is refused with
  a notify when `task_id == ""`;
- **restore correlation (V11):** with the record pre-seeded `frozen` and
  carrying a **stale** `last_error` from an earlier attempt, dispatch `R` and
  tick the poll *before* the coordinator runs — the header must read
  `dispatching…`, **not** `restore failed`. Then bump `restore_attempts` with a
  fresh `op_nonce` and only then does the interpreter engage; an error carrying
  the *old* nonce is still ignored, one carrying the new nonce is reported. Also
  test the `DISPATCH_GRACE` expiry (`restore did not start`);
- a store change to `frozen` + a new-nonce `last_error` flips the header to
  `restore failed: …`, and `ack=liveness` renders as a **success** line;
- **drop completion (V10):** `k` → confirm → the record vanishes from the store
  → header reads `dropped — capture removed` and the timer is stopped; the
  restore interpreter is never entered. Separately, a record that is still there
  after `DROP_GRACE` yields `drop failed — record kept`;
- **single-flight (V13):** dispatch `R`, then press `k` before the gate opens —
  **no** `drop` argv is issued, the user is notified, and `check_action` reports
  the drop binding as unavailable. Repeated `R` likewise issues exactly one
  `run-shell` argv. Then reach a terminal outcome and confirm the bindings are
  live again. In list mode, an action on a *different* record is **not**
  blocked;
- list-mode rows and `enter`;
- the `pin_textual_selection_internals` upgrade guard.

Beware the `@work`-worker rule: a worker still in flight at
`async with app.run_test()` exit fails the *enclosing* test
(`aidocs/framework/testing_conventions.md`) — the poll uses `set_interval`, so
stop the timer in `on_unmount`.

`tests/test_frozenagent_standin_stamp.sh` — isolated tmux server
(`tests/lib/tmux_isolation.sh`). Grown from the pre-phase smoke: the respawn
argv round-trips; `@aitask_standin_ready == <id>` lands on **that** pane within
5 s and on no sibling; with `TMUX_PANE` unset no `set-option` is attempted
(assert via a logging `tmux` shim on `PATH`); list mode stamps nothing.

Existing guards that must stay green: `test_tui_clipboard_seam.sh`,
`test_no_raw_tmux.sh`, `test_shortcut_scopes.py`,
`test_shortcuts_registry_coverage.sh`, `test_no_lib_to_tui_import.sh`,
`test_tui_switcher_hint_text.py`, `test_tui_switcher_footer_fit.sh`,
`test_textual_markup_structure.py`, `test_agent_freeze.py`,
`test_agent_frozen_ops.py`, `test_cleanup_rule_parity.sh`,
`test_kill_agent_pane_smart.sh`.

## Verification

```bash
bash tests/run_all_python_tests.sh                 # read the LAST line only
bash tests/test_frozenagent_standin_stamp.sh       # isolated tmux server
bash tests/test_cleanup_rule_parity.sh             # the reordered frozen branch
bash tests/test_kill_agent_pane_smart.sh
# test_agent_sessions_lease.py / test_agent_freeze.py / test_frozenagent_app.py
# run inside the python suite above.
bash tests/test_tui_clipboard_seam.sh
bash tests/test_no_raw_tmux.sh
bash tests/test_shortcuts_registry_coverage.sh
bash tests/test_no_lib_to_tui_import.sh
bash tests/test_tui_switcher_footer_fit.sh
shellcheck .aitask-scripts/aitask_frozenagent.sh .aitask-scripts/aitask_frozen.sh
./ait frozenagent                                  # list mode, manual look
./ait frozenagent --record <id-from-a-test-store>  # viewer mode, manual look
```

Not a tmux-stress task (the viewer only reads and self-stamps), but the stamp
test runs on an isolated server regardless.

Post-implementation cleanup, archival and merge follow **Step 9
(Post-Implementation)** of the task workflow.

## Re-verification findings (2026-09-08)

**V1 — `RichLog` has no native text selection. The PINNED premise is wrong.**
The parent plan §Viewer and this plan's original step 6 both state
"Textual 8.2.7 native mouse selection (`ALLOW_SELECT`, `get_selection` —
`Log`/`RichLog` implement it)". Only `Log`, `Markdown` and `Digits` override
`get_selection` in Textual 8.2.7. `RichLog` inherits `Widget.get_selection`
(`textual/widget.py:4213`), which calls `self._render()` — a no-op for a
ScrollView — so it returns `None`; measured headlessly:
`RichLog.get_selection(Selection(Offset(0,0), Offset(5,1))) -> None`.
`RichLog.render_line` (`_rich_log.py:301`) also never calls
`Strip.apply_offsets` and never paints a selection span, so a mouse drag
neither highlights nor extracts. **Resolution (user-confirmed):** ship
`CaptureLog(RichLog)` with the three overrides `Log` uses (step 2), and pin the
premise with a test. *Rejected alternative:* a `Static` in a scroll container
gets selection free — verified working, extraction plus automatic highlight via
`Visual.to_strips(apply_selection=True)` — but `DEFAULT_CAPTURE_MAX_LINES` is
**50000** (`lib/agent_freeze.py:108`) and one 50k-line `Static` renders every
line on each layout; `RichLog` is O(visible rows).

**V2 — `aitask_frozen.sh` has no `drop` verb**, confirmed against its `usage()`
(freeze / restore / reconcile only). The plan already scoped adding it here;
re-verification adds *what it must do beyond the store call*: `agent_sessions.drop()`
removes the record and captures but touches no pane options, so the coordinator
must also unstamp the three pane options and kill the stand-in pane — and must
run detached, exactly like restore, because it kills the viewer's own pane
(step 9).

**V3 — `f` is free.** `_TUI_SHORTCUTS` holds `b m c s t y g a l`;
`_QUICK_JUMP_BINDINGS` adds `r x X n e`. The quick-jumps are declared on
`TuiSwitcherOverlay.BINDINGS`, not on the host App, so `f` cannot collide with
any per-TUI `f`.

**V4 — every line number in the original plan's `## Files` still resolves**
(`tui_registry` rows 18-29, `_TUI_SHORTCUTS` 216-226, `_QUICK_JUMP_BINDINGS`
393-407, `_HINT_ITEMS` 244-256, `action_shortcut_*` 1086-1128; `ait` usage
27-38, bypass 190, diffviewer case 208). `_HINT_ITEMS` is 244-256, one line
later than the plan's `242-255`.

**V5 — the store side is ready.** `standin_command()`
(`lib/agent_sessions.py:265`) already returns `ait frozenagent --record <id>`;
`SessionsView.frozen()` / `.by_id()` exist (`:1287`, `:1290`).
`tests/lib/fake_standin.sh` is the current placeholder and reads its id from
`@aitask_frozen`; the real viewer takes it from `--record`, which is what
`standin_command` passes.

**V6 — reuse `TaskInfoCache`, do not hand-roll a title reader.**
`monitor/monitor_core.py:3970`, and importing that module costs 45 ms measured.
A TUI package importing `monitor` is established precedent
(`applink/server.py:25`, `applink/pusher.py:47`), and
`test_no_lib_to_tui_import.sh` only guards `lib/` → TUI.

**V7 — `SectionAwareMarkdown` is the wrong tool for `m`.**
`lib/section_viewer.py:357` is a minimap/section-navigation widget with a TOC
correlation pipeline; the deliverable needs "render this text as markdown".
Use a plain `ModalScreen` + `VerticalScroll > Markdown`.

**V8 — `DataTable.ALLOW_SELECT = False`** in Textual 8.2.7, so list mode is
unaffected by V1.

**V9 — the shipped frozen-drop ordering has an unrecoverable failure mode.**
`kill_agent_pane_smart` (`monitor_core.py:3419-3427`) calls
`_drop_session_record` **before** the kill, and its comment argues that ordering
leaves "the pane (and its record) intact" on failure. That does not hold:
`_drop_session_record` is best-effort and the kill runs regardless, so a *kill*
failure leaves a live pane still stamped `@aitask_frozen=<id>` whose record and
capture files are gone. `reconcile` iterates **records**, so it cannot see that
pane — nothing repairs it. The docstring's own rationale ("reconcile's
`capture_missing` / `dead_pane` rules retire the record later") in fact argues
for the opposite order: *record without pane* is the state reconcile handles
(`frozen | pane gone | keep`), *pane without record* is the state it cannot.
Hence the kill-first, fail-closed protocol in step 9, and the matching reorder
of that branch.

**V9b — the kill rule must be reused, not reimplemented.** "Does this window
still hold a real agent?" already exists three times
(`aitask_companion_cleanup.sh`, `kill_agent_pane_smart`, and the fixture in
`tests/test_cleanup_rule_parity.sh`, which exists *because* of that
duplication). A coordinator-side fourth copy is the wrong answer. It is not
needed: `count_other_real_agents` (`monitor_core.py:928`) is deliberately pure
and import-free, and the three helper predicates are module-level
(`:315`, `:341`, `:435`). Only the `list-panes` format and the `is_helper`
composition are still trapped inside the method — extract those two, and the
coordinator becomes a second *call site*, not a second implementation.

**V10 — `drop` has no terminal state in the restore poll.** `drop` removes the
record outright; it never enters `restoring` or `live`. A shared post-action
poll would therefore never reach a terminal branch after `k`, leaving the header
stuck on `restoring…` — reporting the wrong outcome for the one action that
succeeded. `drop` needs its own completion path keyed on record *disappearance*
(step 8).

**V11 — `run-shell -b` gives the viewer no nonce, and a pre-begin poll reads a
stale error.** The viewer cannot know the new attempt's nonce: `run-shell -b`
only schedules the coordinator and returns nothing. Meanwhile `restore_begin`
(`agent_sessions.py:970-996`) is what bumps `restore_attempts` and clears
`last_error` — so between dispatch and that call, a record whose *previous*
restore failed still carries `<old-nonce>:<reason>`. A poll in that window would
label the new restore as failed before it started. The fix is a
snapshot-and-gate on `restore_attempts` (the only monotonically bumped field),
then nonce-prefix matching on `last_error` — the same `f"{nonce}:"` test the
coordinator already uses at `agent_restore.py:519`.

**V12 — a frozen record keeps a stale *nonempty* `pane_id` forever.**
`_reconcile_frozen` (`agent_freeze.py:688-695`) returns `KEEP:<id>|pane_gone`
and writes nothing when the pane is not observed, so `pane_id` is never cleared
on this path — only `freeze-commit --pane "" --pane-pid 0` (the `freezing`
gone-pane row) ever empties it. After a tmux server restart every retained
frozen record therefore carries a `%N` that no longer exists. A drop protocol
that keys "nothing to kill" on `pane_id == ""` would treat those as kill
failures and, being fail-closed, make them permanently undroppable — the
records users most want to remove. The preflight must resolve the target
against the live pane inventory, and must also reject a **recycled** `%N` whose
`@aitask_frozen` is not this record's id.

**V13 — `drop` bypasses the lease, so concurrent actions can race.** Unlike
`freeze-begin` / `restore-begin` / `standin-respawned`, the store's `drop`
(`agent_sessions.py:1116`) is legal from **any** state and requires **no
nonce** — it is the one verb that does not consult `op_nonce` at all. A `drop`
dispatched while a restore coordinator is mid-transaction removes the record and
the capture the restore's abort path depends on. Two independent guards are
needed because they cover different scopes: a per-record single-flight gate in
the app (one viewer, immediate feedback) and an in-flight refusal in the
coordinator keyed on a non-stale lease (any number of viewers, and the durable
one). `kill_agent_pane_smart`'s direct store call is deliberately left
unguarded — there the user has explicitly killed the pane and it is going away
regardless; the guard belongs on the `aitask_frozen.sh drop` path that both
TUIs' `k` routes through.

**V14 — `drop` must be a leased verb; no pre-check and no value comparison is
sound.** Three designs were evaluated, and only the third survives:

1. *Pre-checking with `show`.* Unsound — both V13 guards are reads. The app's
   `_pending` map is process-local, and `show` is explicitly lock-free
   (`aitask_agent_sessions.sh:265-270`, "NO LOCK for the two read verbs"), so a
   `restore-begin` can land between the read and the delete.
2. *Comparing a snapshotted `(state, op_nonce)` inside the write lock.* Atomic,
   but **ABA-vulnerable**. `standin_respawned` from `aborting` performs
   `_set_state(FROZEN)` **and** `_clear_lease()` (`agent_sessions.py:1090-1094`),
   and `_clear_lease` zeroes `op_nonce` (`:675-678`). A full
   `frozen → restoring → aborting → frozen` cycle therefore restores the exact
   pair, and that closing transition is the one that registers a **newly
   respawned stand-in viewer**. The comparison would accept the stale delete and
   leave a live stamped viewer whose record and capture are gone — the V9 state
   the protocol exists to prevent, reached by a different route.
3. *An atomic claim.* `lease-take` is already the store's admission primitive:
   it is evaluated under the write lock, encapsulates the two-term staleness
   rule, and refuses with `LEASE_HELD` (exit 8). Pairing it with
   `drop <id> --nonce <n>` makes `drop` obey the rule the §A contract already
   states for every other mutating verb — *"every verb that mutates a record
   holding a lease requires `--nonce`"* — of which `drop` is currently the sole
   exception. A nonce is a fresh 8-hex token per claim (`_mint_nonce`), so
   unlike a value comparison it cannot recur; ABA is structurally impossible.
   It also needs no new exit code, and it retires the `_lease_stale` promotion
   and the derived `lease_in_flight:` field the previous design required.

The one gap it does **not** close is that `restore_begin` mints its lease
without consulting an existing one (`:970-996`) — so the claim *detects* a
concurrent restore rather than preventing it. That is sufficient here (we fail
closed) and is pre-existing store behaviour that reconcile's takeover flows
depend on; changing it belongs to t1705_2/_5, not here.

## Risk

### Code-health risk: medium

- The change edits four pieces of **shared TUI infrastructure**
  (`tui_registry.py`, `tui_switcher.py`, `shortcut_scopes.py`, `ait`) that every
  other TUI reads; a mistake in the four-part registration is felt outside this
  task · severity: medium · → mitigation: covered by the existing guards
  (`test_shortcuts_registry_coverage.sh`, `test_no_lib_to_tui_import.sh`,
  `test_tui_switcher_footer_fit.sh`, `test_shortcut_scopes.py`)
- `CaptureLog` depends on Textual internals with no compatibility promise
  (`RichLog._line_cache`, `Strip.apply_offsets`, `Selection.get_span`,
  `Strip.divide`/`join`). A Textual upgrade can break mouse selection
  **silently** — the drag still runs, it just copies nothing · severity: medium
  · → mitigation: inline post-phase `pin_textual_selection_internals`
- The new `drop` verb is **pane-destructive and capture-destructive**: it
  deletes the only copy of a frozen agent's output and kills a pane. It lands in
  `agent_freeze.py`, a module whose reconcile path must keep working with no
  coordinator present · severity: **high** (raised from medium: finding **V9**
  showed the shipped ordering already reaches an unrecoverable state, so this is
  a demonstrated defect class, not a hypothetical one) · → mitigation: inline
  post-phase `cover_drop_destructive_path`
- The task reorders a **shipped** branch of `kill_agent_pane_smart` and extracts
  two helpers from it — code owned by t1705_4 and exercised by t1705_7's keys.
  A mistake there is destructive (a window holding a live agent, or a frozen
  stand-in, gets killed) · severity: medium · → mitigation: covered by
  `tests/test_cleanup_rule_parity.sh` (extended with the coordinator call site)
  and `tests/test_kill_agent_pane_smart.sh`, plus an `ait note` to t1705_7

### Goal-achievement risk: medium

- The deliverable is wide (two modes, search, two selection models, a markdown
  modal, three store-mutating actions with outcome polling, an engine verb, and
  the four-part registration). Partial delivery is the most likely failure mode
  · severity: medium · → mitigation: none — the step order front-loads the
  contract-critical work, and each numbered step is independently verifiable
- The stand-in contract — `respawn-pane -k` into `ait frozenagent --record <id>`
  round-tripping through tmux's single-string quoting, `ait` resolving on the
  respawned pane's PATH, and the self-stamp landing on the right pane — is
  provable **only live**. It is also the one assumption that would invalidate
  the whole design rather than a detail of it · severity: high
  · → mitigation: inline pre-phase `verify_standin_respawn_argv`
- Restore-outcome surfacing must follow the *amended* four-outcome contract
  (B1–B4). Presenting `ack=liveness` as an error would mislabel the only outcome
  a codex record can ever reach · severity: medium · → mitigation: covered by
  the `ack=liveness` renders-as-success assertion in `tests/test_frozenagent_app.py`
- The viewer reports an outcome it observes only indirectly, through a store the
  detached coordinator writes asynchronously. Three ways to report or do the
  wrong thing were found in the original design: a stale `last_error` read
  before `restore-begin` (**V11**), a `drop` that never reaches a terminal state
  (**V10**), and concurrent actions racing because `drop` bypasses the lease
  (**V13**) · severity: medium · → mitigation: covered by the
  restore-correlation, drop-completion and single-flight tests in
  `tests/test_frozenagent_app.py`, plus the coordinator's claim refusal and the
  `drop_pre_store` ABA-race test in `tests/test_agent_freeze.py`
- The task makes `drop` a **leased verb** and adds `lease-release` — changes to
  the one module every frozen-agent path writes through, whose plain `drop`
  must keep its any-state contract for `kill_agent_pane_smart` · severity:
  medium · → mitigation: covered by the store-level `drop --nonce` and
  `lease-release` unit tests in `tests/test_agent_sessions_transitions.py` and
  `tests/test_agent_sessions_lease.py`, including an explicit
  unchanged-plain-`drop` case
- A frozen record's `pane_id` is durable but not authoritative: it survives the
  pane it names (**V12**). Any pane-targeting logic that trusts it without
  checking the live inventory either kills the wrong pane or refuses to act on
  a perfectly valid record · severity: medium · → mitigation: the preflight in
  step 9.1 and its three test rows in `cover_drop_destructive_path`

### Planned mitigations
- timing: pre-phase | name: verify_standin_respawn_argv | type: test | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: goal-achievement — the stand-in respawn/PATH/self-stamp contract is provable only live | desc: land the isolated-tmux stamp smoke against a mount-and-stamp-only app before building the rest of the viewer
- timing: post-phase | name: pin_textual_selection_internals | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — CaptureLog reaches into Textual internals with no compatibility promise | desc: assert Strip.apply_offsets / Selection.get_span / Strip.divide / Strip.join / RichLog._line_cache still exist and RichLog still lacks get_selection
- timing: post-phase | name: cover_drop_destructive_path | type: test | priority: high | effort: medium | inline_risk: low | added_complexity: low | addresses: code-health — the new drop verb deletes the only capture and kills a pane, and the shipped ordering (V9) already reaches an unrecoverable state | desc: drive AITASKS_DROP_FAIL_AT between every irreversible step (kill / verify / store), assert the fail-closed protocol keeps record+capture+options intact on a kill failure, cover the three preflight target-resolution rows (V12) and the in-flight refusal (V13), plus the live companion-survival case and a coordinator parity row

### Reassessment after inlining

Re-run of the two-dimension assessment against the augmented plan (the three
mitigations are now steps of it, not deferred work, and the plan has since
absorbed findings V9–V11):

- **Code-health risk: medium** — held, but for a different reason than before.
  It rose on substance: V9 turned the destructive-verb bullet from a
  hypothetical into a demonstrated defect class, and the plan now also edits
  shipped `monitor_core` code. It came back down on coverage: the drop protocol
  is now fail-closed by construction (nothing irreversible happens until the
  target is *verified gone*), every irreversible step has an injectable failure,
  concurrency is closed by an **atomic claim** rather than by pre-checks or a
  value comparison (V14), and both the kill rule and the admission primitive are
  reused rather than reimplemented — no fourth copy of the kill rule, no second
  copy of the staleness rule. The genuine increase is surface: the plan now
  modifies `agent_sessions.py` and its shell wrapper — the store every
  frozen-agent path writes through — to make `drop` a leased verb and to add
  `lease-release`. That is a smaller change than the design it replaced, and it
  moves `drop` *toward* the store's stated §A contract rather than adding a
  bespoke mechanism beside it.
- **Goal-achievement risk: medium** — down from the pre-inlining reading. The
  `high`-severity bullet was the only one carrying the level upward, and moving
  its proof to a **pre-phase** means an invalid stand-in contract now surfaces
  before the app is written rather than after. V10/V11 added a second
  goal-achievement bullet, but both are now closed by named tests. What keeps it
  at medium is breadth, not soundness.
