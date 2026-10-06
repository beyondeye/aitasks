---
Task: t1895_trails_tabbed_multi_trail_sessions.md
Base branch: main
Output branch: main
---

# t1895 — `ait trails`: tabbed multi-trail sessions

## Context

`ait trails` shows one trail at a time. `s` always re-runs discovery (one
`ait artifact get` subprocess per trail, 15s timeout each) and `_activate_trail`
throws away the previous trail's doc, drift verdict, focus and any pending
agent-refresh watch. The goal: keep several **explicitly opened** trails in
memory, one tab each, with instant in-memory switching, while the board's
embedded `z` view stays single-trail and does not regress.

Design follows the task's Option B, with one deliberate deviation: the tab strip
is a small custom `Static` (`TrailTabStrip`) instead of Textual's `Tabs`.
`Tabs.add_tab` / `remove_tab` are asynchronous and post their own
`TabActivated` / `Cleared` messages (auto-activating the first tab, re-activating
a neighbour on removal), which would make the widget a second source of truth
racing the session model. A synchronous strip rendered from the sessions has no
such feedback loop; clicks are resolved from recorded cell spans.

## Design summary

- **`TrailSession` dataclass** (in `board_trail_screen.py`, no new module):
  `handle, doc, error, versions_fallback, drift, owner_id, owner_archived,
  reload_gen, drift_gen, focus_filename, focus_col_id, updated, read_seq`.
- **Mixin state:** `_trail_sessions: dict[str, TrailSession]` (insertion order
  = tab order) + `_trail_active: TrailSession | None`. The old scalars
  (`active_trail_handle`, `_trail_doc`, `_trail_error`, `_trail_versions_fallback`,
  `_trail_drift`, `_trail_owner_id`, `_trail_owner_archived`) become
  **properties delegating to the active session**, so the board and the ~40 test
  references keep working.
- **Host policy flag** `_TRAIL_TABBED: ClassVar[bool] = False` on the mixin;
  `TrailsApp` sets `True`. Tabbed ⇒ multi-session + cache-first `s`. Board ⇒ one
  session, `s` still rescans (explicit decision, pinned by a test).
- **Tokens split.** `_trail_gen` stays the monotonic counter; consumers compare
  against *stamps*: `_trail_discovery_gen` (stamped by `_open_trail_select`) and
  per-session `reload_gen` / `drift_gen` (see below). The board's view
  enter/leave calls `_supersede_trail_workers()`, which bumps and restamps both,
  preserving today's "leaving/entering the view retires everything".
- **Callbacks keyed by handle**: drift / reload / watch look up
  `_trail_sessions[handle]`, validate against that session's `gen`, write into
  that session, re-render only when it is active, otherwise set `updated` (`•`)
  and refresh the strip.
- **Cache-first `s`, never a dead end.** In the tabbed host `s` serves the
  cached list only when it is non-empty; a missing (`None`) **or empty** cache
  re-scans. Otherwise a successful zero-trail scan would pin `[]` forever (the
  existing `_open_trail_select_from_cache` returns without opening the modal on
  an empty list, so its `r` rescan key would be unreachable).
- **Newest content wins, whatever the completion order — by a sequence that
  provably follows fetch order.** Discovery and a background reload can now run
  concurrently and read the same handle. A request-time stamp cannot order them:
  `load_trail_blob` resolves the stored version inside its subprocess, so an
  earlier-requested read can stall and sample a later revision. Instead, every
  in-process read of trail content goes through
  `trail_discovery.sequenced_trail_read(handle, loader)`: it holds a **per-handle
  lock** around the whole read and takes the next value of a process-wide counter
  **inside that lock, after the loader returns**. Same-handle reads are therefore
  serialized, and since each one samples within its own critical section,
  `read_seq` order **is** sampling order. Because the artifact store only moves
  forward, a larger `read_seq` means content at least as new. Discovery (inside
  `discover_trails`) and the reload worker are the only two readers; both use it.
- **One reconciliation rule for cache and session.** `_newest_trail_content`
  picks, per handle, the candidate with the largest `read_seq` among {the
  incoming result, the cache entry, the open session}. Both callbacks write the
  winner to **both** the cache entry and the open session, so neither can be left
  on an older revision. That holds whichever callback lands first: an older
  reload landing first and a newer scan landing second still updates the
  session. A content update arriving from discovery restarts drift for that
  session. Identical content only advances `read_seq`: no re-render and no drift
  subprocess, so a plain rescan does not churn every open tab.
- **Two tokens per session**: `reload_gen` (latest reload request — a superseded
  reload result is discarded) and `drift_gen` (latest drift request; also bumped
  whenever the session's content changes from any source, so a verdict computed
  for older content can never land on newer content). A discovery-driven content
  update bumps `drift_gen` only: an in-flight reload stays valid and is
  reconciled by `read_seq` when it lands.
- **Deferred focus restores are owned by the render that queued them.**
  `TrailsApp` keeps `_render_seq`, bumped on every lane re-mount
  (`refresh_board`, and a `_rerender_trail` override); `_queue_refocus` captures
  it and `_refocus` (including its retry hops) drops itself when the sequence
  moved on. This closes the A→B→A case, where a session-keyed guard would accept
  a restore queued for A's *first* visit.
- **Watch stays a single global watch keyed by `_trail_watch_handle`** (all
  existing watch tests keep their meaning), but it is stopped by *closing that
  handle's tab* (or, on the board, by replacing the session / leaving the view),
  not by switching tabs. A version change reloads the watched handle's session,
  active or background. Limitation kept as today: arming `R` on a second trail
  replaces the first watch.

## Implementation steps

### Pre-phase (risk mitigations)

1. [baseline_trail_suites] Before any edit, run on the untouched tree
   `~/.aitask/venv/bin/python -m pytest -q -p no:randomly tests/test_trails_app.py
   tests/test_board_bytrail_view.py tests/test_board_trail_view.py
   tests/test_trail_screen_host_protocol.py tests/test_board_keymap_characterization.py
   tests/test_shortcut_scopes.py tests/test_shortcut_editor_modal.py` plus
   `bash tests/test_shortcuts_registry_coverage.sh` and
   `bash tests/test_keybinding_registry.sh`; save the per-module pass/fail result
   to the scratchpad. A module already failing there is pre-existing and is
   reported as such, never "fixed" silently as part of this task.

### 1. `.aitask-scripts/board/board_trail_screen.py` — state refactor

1. Add `from dataclasses import dataclass, field` and
   ```python
   @dataclass(eq=False)
   class TrailSession:
       """One opened trail's in-memory state (session-only, never persisted)."""
       handle: str
       doc: dict | None = None
       error: str = ""
       versions_fallback: list = field(default_factory=list)
       drift: tuple | None = None
       owner_id: str = ""
       owner_archived: bool = False
       reload_gen: int = 0        # stamp of the latest reload request
       drift_gen: int = 0         # stamp of the latest drift request / content change
       focus_filename: str = ""   # last focused card, restored on tab switch
       focus_col_id: str = ""
       updated: bool = False      # background change not yet seen (tab's •)
       read_seq: int = 0          # fetch-order sequence of `doc` (0 = unknown)
   ```
   (`eq=False`: identity comparison — `s is self._trail_active` checks.)
2. `TrailScreenMixin._TRAIL_TABBED: ClassVar[bool] = False` with a comment
   stating what it switches (multi-session tabs + cache-first selector).
3. `_init_trail_state`: replace the seven scalar assignments with
   `self._trail_sessions = {}`, `self._trail_active = None`,
   `self._trail_discovery_gen = 0`. Keep `_trail_infos`, `_trail_gen`,
   `_local_project`, all `_trail_watch_*`, `_trail_launch_pending`. Update the
   comment on `_trail_gen` (counter; stamps are compared).
4. Properties (getter + setter each):
   - `active_trail_handle`: get → `s.handle if s else None`. Set `None` →
     `_trail_active = None`. Set `h` → existing session for `h` becomes active,
     else a new `TrailSession(h, reload_gen=self._trail_gen,
     drift_gen=self._trail_gen)` is inserted (non-tabbed:
     `_trail_sessions` cleared first, so the board always holds ≤1 session).
   - `_trail_doc`, `_trail_error`, `_trail_versions_fallback`, `_trail_drift`,
     `_trail_owner_id`, `_trail_owner_archived`: get → active session's field or
     the old default (`None`, `""`, `[]`, `None`, `""`, `False`); set → write the
     active session's field, `RuntimeError("no active trail session")` when none
     (fail loud; every production writer already sets the handle first).
5. Helpers:
   - `_bump_trail_gen() -> int`.
   - `_supersede_trail_workers()`: bump; stamp `_trail_discovery_gen` and every
     session's `reload_gen` and `drift_gen` with the new value.
   - `_newest_trail_content(handle, incoming)` → the winning
     `(doc, error, versions, read_seq)` among the incoming tuple, the cache
     entry for `handle` and its open session — largest `read_seq`; ties keep the
     incoming result. The **only** place `read_seq` is compared.
   - `_apply_trail_content(s, content, *, from_discovery)`: write the content
     into session `s`; when `doc`/`error` actually changed, bump
     `s.drift_gen`, clear `s.drift`, and (active) re-render + subtitle, or
     (background) set `updated` + refresh tabs, then start drift if the doc is
     loadable. When unchanged, only `read_seq` advances — no re-render, no
     drift. (`from_discovery=False` — the reload path — always restarts drift,
     because the reload request cleared the verdict.)
   - `_store_trail_info_content(handle, content)`: replace the cache entry's
     `doc` / `load_error` / `versions` / `read_seq` in place
     (`dataclasses.replace`), keeping its owner fields; no-op when the handle is
     not cached.
   - `_trail_session(handle) -> TrailSession | None`.
   - `_refresh_trail_tabs()`: no-op hook (tabbed hosts override).
   - `_store_trail_focus()`: copy `_focused_card()`'s filename / column id into
     the active session.
   - `_switch_trail_session(handle)`: no-op if unknown or already active; store
     focus, `self.screen.set_focus(None)` (so `_rerender_trail` captures no
     outgoing column), activate, clear `updated`, `self._rerender_trail()`,
     `self._queue_refocus(s.focus_filename, s.focus_col_id)`,
     `self._refresh_trail_tabs()`, `self.refresh_bindings()`. **No subprocess,
     no `load_tasks`, no drift re-run.**
   - `_close_trail_session(handle)`: remove; if `_trail_watch_handle == handle`
     → `_stop_trail_watch()`; if it was active, activate the right-hand
     neighbour (else left) via the switch body, or set `_trail_active = None` and
     `_rerender_trail()` (empty-state hint) when none remain; refresh tabs +
     bindings.
6. `_activate_trail(handle)`:
   - tabbed and already open → `_switch_trail_session(handle)`; return.
   - `self.manager.load_tasks()` (t1365 reason unchanged).
   - non-tabbed: `_stop_trail_watch()` + `_trail_sessions.clear()` (today's
     "a watch belongs to the trail it was installed for"); tabbed:
     `_store_trail_focus()` (outgoing tab keeps its focus; its watch survives).
   - build `TrailSession` from the cached `TrailInfo` (same field mapping as
     today, plus `read_seq=info.read_seq`) with both tokens set to
     `self._bump_trail_gen()`; insert; make active;
     `refresh_board()`; drift if doc ok; subtitle; `_refresh_trail_tabs()`;
     `refresh_bindings()`.
7. Drift: `_start_trail_drift()` keeps its zero-arg signature (tests stub it as
   `lambda: None`) and delegates to new `_start_session_drift(s)`
   (`s.doc is None` → return; `s.drift = None`;
   `s.drift_gen = _bump_trail_gen()`; worker `(s.drift_gen, s.handle)` — only
   the latest drift request for a session is accepted).
   `_on_trail_drift(gen, handle, …)`: `s = _trail_session(handle)`; discard if
   `None`, `gen != s.drift_gen` or not By-Trail; set `s.drift`; active → today's
   re-render + subtitle; background → `s.updated = True`, `_refresh_trail_tabs()`.
8. Reload: `_reload_active_trail()` (zero-arg, stubbed by tests) delegates to new
   `_reload_trail_session(s)`: `g = _bump_trail_gen()`; `s.reload_gen =
   s.drift_gen = g` (as today, a reload also retires an in-flight verdict);
   `s.drift = None`; subtitle (active) or tabs (background); worker.
   `_trail_reload_worker(gen, handle)` reads through
   `sequenced_trail_read(handle, load_trail_blob)` (`load_trail_blob` still
   looked up in **this** module's namespace, so existing patch targets keep
   working) and passes `read_seq` on.
   `_on_trail_reload(gen, handle, doc, error, versions, read_seq=0)` (the tests'
   5-arg calls get `0`, which still wins a tie against an unknown-sequence
   session): session lookup; discard if `gen != s.reload_gen` or not By-Trail;
   `best = _newest_trail_content(handle, incoming)`; `_apply_trail_content(s,
   best, from_discovery=False)`; `_store_trail_info_content(handle, best)` —
   replacing the old `_trail_infos = None`, so a later `s` cannot resurrect a
   superseded document and neither can an older reload win over a scan that
   fetched later.
9. Discovery: `_open_trail_select` stamps `_trail_discovery_gen` after its bump;
   `_on_trail_discovery` compares against `_trail_discovery_gen` (so a
   background reload/activation no longer discards an in-flight scan).
   Reconcile before assigning `_trail_infos = infos`: for every returned info,
   `best = _newest_trail_content(info.handle, info's content)`; write `best`
   into the new info (owner fields from the scan); and when the handle has an
   open session, `_apply_trail_content(s, best, from_discovery=True)` — the
   session moves to the newer revision as well (an older reload that landed
   first cannot leave the session behind the cache). Unchanged content is a
   no-op beyond `read_seq`.
   `action_trail_select` → `_open_trail_select(rescan=not self._TRAIL_TABBED
   or not self._trail_infos)` — empty or missing cache re-scans.
   `_open_trail_select_from_cache` passes
   `open_handles=set(self._trail_sessions) if tabbed else ()` and
   `allow_rescan=self._TRAIL_TABBED` to `TrailSelectScreen`; `on_select`:
   `None` → return; `TRAIL_SELECT_RESCAN` → `_open_trail_select(rescan=True)`;
   else `_activate_trail(handle)`.
10. Watch: `_trail_watch_tick` / `_on_trail_watch` replace
    `handle != self.active_trail_handle` with "`handle` has no open session".
    On a version change: stop, notify, then `_reload_active_trail()` when the
    handle is active (stub-compatible) else `_reload_trail_session(s)`.
11. `_finish_trail_launch` calls `_after_trail_launch(handle=watch_handle)`;
    `_after_trail_launch(reload=True, handle="")`: with a handle, reload *that*
    session (no-op if its tab was closed meanwhile); without one, today's
    behaviour.
12. Docstrings: module header / `TrailHost` mention `_TRAIL_TABBED`,
    `_refresh_trail_tabs` (optional override), and the stamp scheme.

### 1b. `.aitask-scripts/lib/trail_discovery.py`

- `TrailInfo.read_seq: int = 0` (in-memory only; fetch-order sequence of
  `doc`, 0 = unknown). Keyword construction everywhere keeps working.
- `sequenced_trail_read(handle, loader) -> (result, read_seq)`: a module-level
  `threading.Lock` per handle (created under one guard lock) held around
  `loader(handle)`; `read_seq = next(_TRAIL_READ_SEQ)` taken **inside the lock
  after the loader returns**. Docstring states the invariant (same-handle reads
  are serialized and each samples inside its critical section, so `read_seq`
  order is sampling order; the store only moves forward) and the cost (a stalled
  read delays other reads of the *same* handle, bounded by the 15s subprocess
  timeouts; different handles never wait on each other; no nested locking).
- `discover_trails` loads each blob through
  `sequenced_trail_read(info.handle, load_trail_blob)` and sets
  `info.read_seq`.

### 2. `.aitask-scripts/board/aitask_board.py`

- `_set_base_filter`: replace `self._trail_gen += 1` with
  `self._supersede_trail_workers()` (comment updated). Nothing else changes —
  the board stays non-tabbed.

### 3. `.aitask-scripts/board/board_trail_view.py`

- `TRAIL_SELECT_RESCAN = "\x00rescan"` sentinel (module constant).
- `TrailSelectItem(info, overlap_notes, is_open=False)`: append `  ● open`
  (accent style) after the title when open.
- `TrailSelectScreen(infos, overlaps, open_handles=(), allow_rescan=False)`:
  title hint gains `r rescan` when allowed; `Binding("r", "rescan", …,
  show=False)`; `action_rescan` dismisses `TRAIL_SELECT_RESCAN` only when
  `allow_rescan` (board: inert).

### 4. `.aitask-scripts/board/trails_app.py`

1. `TrailsApp._TRAIL_TABBED = True`; module docstring updated (tabs, cache-first
   selector, new keys).
2. `TrailTabStrip(Static)` (id `trail_tabs`, `markup=False`, `can_focus=False`,
   height 1, hidden when no tabs): `set_tabs(rows)` renders
   ` 1 title ✓ │ 2 title ⟳ • │ …` as a `Text` (active tab bold/reverse), records
   `(start, end, handle)` cell spans; `on_click` maps `event.x` to a handle and
   calls `app._select_trail_tab(handle)`.
3. Label: index, title (`doc.title` or handle, truncated to 24 cells with `…`),
   glyph — `⟳` drift pending, `✓` CURRENT, `⚠` STALE, `?` drift unavailable,
   `✗` load error — plus ` •` when `updated`.
4. `compose`: strip between `Header` and `#board_container`. CSS rule for
   `#trail_tabs`.
5. `_refresh_trail_tabs()` override builds the rows; `_refresh_subtitle`
   override calls it first (keeps the active tab's glyph in step with the
   banner).
6. Bindings — trails-only rows, a module-level list spliced into `BINDINGS`:
   ```python
   TRAIL_TAB_BINDINGS = [
       Binding("[", "trail_tab_prev", "Prev Tab"),
       Binding("]", "trail_tab_next", "Next Tab"),
       Binding("ctrl+w", "trail_tab_close", "Close Tab"),
       *(Binding(str(n), f"trail_tab_{n}", f"Tab {n}", show=False)
         for n in range(1, 10)),
   ]
   ```
   Digits hidden in the footer (the tab labels carry the index — the
   discoverability surface); `[`, `]`, `^w` footer-visible.
7. Actions `action_trail_tab_prev/next` (wrap-around), `action_trail_tab_close`,
   `action_trail_tab_1` … `_9` → `_goto_trail_tab(n)`; each guards
   `_modal_is_active()` and the tab count. `_select_trail_tab(handle)` (click
   path) → `_switch_trail_session`.
8. `check_action`: prev/next need ≥2 tabs, close ≥1, `trail_tab_<n>` needs
   `n ≤ len(tabs)`; otherwise `False` (hidden + non-dispatching).
9. Render-owned focus restore: `self._render_seq = 0` in `__init__`;
   `refresh_board` bumps it before re-mounting; override
   `_rerender_trail(self, refocus_filename="")` → bump, then `super()`.
   `_queue_refocus` queues `_refocus(filename, col_id, _MOUNT_HOPS,
   self._render_seq)`; `_refocus(filename, col_id, hops=_MOUNT_HOPS,
   seq=None)` returns at once when `seq is not None and seq != self._render_seq`,
   and passes `seq` through its retry hop. (The `apply_filter` rescue stays
   unguarded: it only acts when no attached card is focused and targets the
   current DOM's first card.)

### 5. Tests

**Existing suites** — expected edits only:
- `tests/test_board_bytrail_view.py` `test_real_reload_worker_replaces_the_document`:
  seed `_trail_infos` with the handle's `TrailInfo` and assert the cached entry's
  `doc` was replaced in place (was: cache dropped to `None`).
- `tests/test_trails_app.py` `test_every_trails_row_has_an_identical_board_twin`:
  exempt `TRAIL_TAB_BINDINGS` actions (trails-only rows), plus the new
  ownership test below.

**New, in `tests/test_trails_app.py`** (`TabbedSessionTests`, patches serving two
trails A/B with distinct titles/summaries and *counting* `discover_trails`,
`load_trail_blob`, `run_trail_drift`):
- open A (boot selector) then B via `s`: `discover_trails` called once (cache
  hit on the second `s`); the second selector shows `● open` on A; two sessions,
  B active.
- switch with `[`, `]` (wrap), `2`: zero new subprocess-seam calls; subtitle and
  summary pane follow the active tab; focus restored to the card last focused in
  that tab (move down in A, switch to B and back).
- choosing the already-open A from the selector switches, no duplicate tab.
- background drift: `_on_trail_drift(sB.drift_gen, B, "STALE", …)` while A active →
  B's session updated, A's TaskCard widget ids unchanged (no re-render), strip
  shows `•` for B; switching to B clears it.
- watch: armed on A survives a switch to B (tick still spawns a worker for A);
  a version change for background A reloads A's session (not B); closing A's tab
  stops the watch.
- closing the last tab (`ctrl+w`) → empty-state hint, subtitle
  `no trail selected — press s`, tab actions hidden by `check_action`.
- selector `r` re-runs discovery and reopens the selector.
- **empty-cache recovery**: `discover_trails` (patched over a mutable list)
  first returns `([], [])` → boot scan finds nothing; the list then gains
  trail A; pressing `s` re-scans (call count 2), the selector lists A, `enter`
  opens it as a tab.
- **discovery/reload reconciliation, both completion orders**: the two
  results are produced by real `sequenced_trail_read` runs over a fake store
  (rev1 → rev2), never by hand-assigned sequence numbers. Each completion order
  is checked with each of {reload fetched rev2, discovery fetched rev2}:
  reload-then-discovery and discovery-then-reload must both leave the open
  session **and** the cache entry on rev2. This includes the reported case: an
  older reload lands first, a newer scan lands second, and the open (active)
  session re-renders onto rev2. Then closing A and reopening it through the
  cache-first selector shows rev2 (summary pane / `_trail_doc`). Unchanged
  content (both rev2) triggers no re-render and no drift call.

**New, `tests/test_trail_discovery_sequencing.py`** (pure lib, real threads,
`threading.Event` schedules, bounded `join` timeouts):
- **request order ≠ sampling order, stall before sampling**: T1 (discovery) is
  requested first but blocks before its read; T2 (reload) reads rev1; the store
  advances to rev2; T1 resumes and reads rev2. Assert T1's `read_seq` > T2's,
  so the rev2 result wins.
- **stall after sampling, before return**: T1 enters, samples rev1 and blocks
  before returning; T2 is requested, the store advances to rev2, then T1 is
  released. Assert T2 waited on the lock (it had not sampled while T1 held it),
  sampled rev2, and holds the larger `read_seq`.
- **negative control**: the second schedule with the per-handle lock patched to
  a no-op context assigns rev1 the larger sequence. This proves the lock is
  load-bearing and the test can fail.
- different handles do not block each other (T1 blocked on handle A, T2 on
  handle B completes).
- **overlapping switches with a delayed stale restore**: trails A and B share a
  member file X in different waves; in B the saved focus is X, in A it is Y.
  Capture the queued `_refocus` calls (wrap `call_after_refresh` so `_refocus`
  is recorded, not run) while pressing `]` then `[` back-to-back without
  settling (A→B→A); after A's cards mount, run the captured calls oldest first.
  The stale one (B's restore, X) must not move focus; the focused card is A's Y.
  Negative control: the same sequence with the `seq` check disabled (patch
  `_render_seq` comparison out) lands on A's X, proving the test can fail.
- tab rows are trails-only: the board declares none of their actions, and none
  of their keys is bound by any board row.
- tab click: `pilot.click("#trail_tabs", offset=…)` on the second label switches.

**New board pins** (in `tests/test_board_bytrail_view.py`):
- board `s` still rescans (`_open_trail_select` receives `rescan=True`), the
  board has no `#trail_tabs`, and activating a second trail leaves exactly one
  session (watch stopped as before).
- supersession split: an in-flight drift for the active trail is **not**
  discarded by opening the selector, and a reload does not discard an in-flight
  discovery (`_trail_discovery_gen`).

### 6. Docs (`website/content/docs/tuis/trails/`)

- `reference.md`: keys table (`[`/`]`, `1`–`9`, `Ctrl+W`, `s` = open from the
  cached list, `r` inside the selector re-scans); "What each refresh reads" row
  for `s` / selector `r`; the "Separate selection" bullet → open tabs are
  session-only and independent of the board.
- `how-to.md`: rewrite "How to Switch to Another Trail" (tabs, `● open`, switching
  keys, closing) and the refresh guidance that says `s` re-scans (now: `s`, then
  `r` in the selector).
- Run `python3 check_links.py --build` in `website/`.

### 7. Step 9 (Post-Implementation)

Commit code + docs (`feature: … (t1895)`), plan via
`aitask_task_commit.sh`, archive per task-workflow Step 9.

## Verification

```bash
bash tests/run_all_python_tests.sh --test-dir tests   # or targeted runs:
~/.aitask/venv/bin/python -m pytest -q tests/test_trails_app.py \
  tests/test_trail_discovery_sequencing.py \
  tests/test_board_bytrail_view.py tests/test_board_trail_view.py \
  tests/test_trail_screen_host_protocol.py \
  tests/test_board_keymap_characterization.py tests/test_shortcut_scopes.py \
  tests/test_shortcut_editor_modal.py
bash tests/test_shortcuts_registry_coverage.sh
bash tests/test_keybinding_registry.sh
cd website && python3 check_links.py --build
```
Plus a real-terminal smoke: `ait trails` in a scratch tmux window, open two
trails, switch with `[`/`]`/digits and a mouse click, `ctrl+w` to close.

## Risk

### Code-health risk: medium
- The shared mixin's scalar state becomes active-session properties and the supersession token is split into stamps, which also changes the board `z` view's semantics (opening the selector no longer retires an in-flight drift/reload; a reload no longer retires an in-flight discovery) · severity: medium · → mitigation: inline pre-phase baseline_trail_suites
- Property setters raise when no session is active — a writer that sets trail state before the handle would now fail loud instead of storing silently · severity: low · → mitigation: none
- Tab switching re-renders the lanes asynchronously; focus restore could hit the detached-focus class of bugs (t1839) in `TrailsApp` · severity: medium · → mitigation: manual_verification_trail_tabs
- Same-handle reads are now serialized by a per-handle lock: a stalled `artifact get` delays a concurrent reload/scan of the *same* trail (bounded by the 15s subprocess timeouts; other handles unaffected). The ordering guarantee holds only for readers that go through `sequenced_trail_read` — a future in-process reader that bypasses it would reintroduce the race · severity: low · → mitigation: none (docstring states the invariant; discovery and reload are the only readers)

### Goal-achievement risk: low
- Custom `TrailTabStrip` instead of the draft's Textual `Tabs` (deliberate, see Context); many tabs on a narrow terminal clip labels · severity: low · → mitigation: manual_verification_trail_tabs
- The agent-refresh watch stays single and global: arming `R` on a second tab replaces the first tab's watch (unchanged from today's install-replaces contract) · severity: low · → mitigation: none

### Planned mitigations
- timing: pre-phase | name: baseline_trail_suites | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: shared-mixin refactor / token split regressions on the board z view | desc: Run the trail + shortcut suites on the untouched tree first and record per-module results so later failures are attributable
- timing: after | name: manual_verification_trail_tabs | type: manual_verification | priority: medium | effort: low | inline_risk: low | added_complexity: medium | addresses: focus restore across async re-render; tab-strip clipping/click on real terminals | desc: Real-terminal check of ait trails tabs: open 2+ trails, switch with [ ] digits and mouse click, ctrl+w, focus restore, narrow-width label clipping

## Post-Review Changes

### Change Request 1 (2026-10-06 09:40)
- **Requested by user:** (1) `TrailSelectScreen.action_rescan` dismissed through a bare `ModalScreen`: a stale `r` after the selector closed raised `ScreenStackError` or popped the replacement screen — use `GuardedModalScreen` (tui_conventions "Modal dismissal"). (2) A tab switch re-projects the trail, and a member that is not a live task goes through `find_task_including_archived`; opening another trail runs `load_tasks`, which clears the manager's archived-task cache, so switching back read the archive (`zstd -dc`) on the UI thread — contradicting the memory-only switch.
- **Changes made:** (1) `TrailSelectScreen` now derives from `GuardedModalScreen`. (2) New mixin `_load_trail_tasks()` replaces the direct `manager.load_tasks()` calls in `_activate_trail`, `action_trail_refresh_local` and `TrailsApp._after_dialog_command`; in a tabbed host it re-resolves every open trail's members (`_resolve_trail_members`, which runs the same `build_trail_lanes` projection a render runs, warming the manager's archive cache). A background tab whose document changes is resolved at that moment too. `_build_active_trail_lanes` shares the new `_live_tasks_by_id()`. Tests: the switch test now also asserts zero `_load_archived_task` calls and zero `Popen` spawns during switches, with trail A carrying a ghost member B does not have; a direct pin that opening B leaves A's ghost in the archive cache; a stale-selector test (`r`/`Esc` after close, with the base screen and with a replacement modal on top). Mutants: disabling the pre-resolution fails both archive tests; restoring the unguarded `dismiss` fails the stale-selector test.
- **Files affected:** `.aitask-scripts/board/board_trail_view.py`, `.aitask-scripts/board/board_trail_screen.py`, `.aitask-scripts/board/trails_app.py`, `tests/test_trails_app.py`

### Change Request 2 (2026-10-06 10:05)
- **Requested by user:** (1) `_apply_trail_content` compared only `doc`/`error`, so a newer failing revision with the same error but new recorded versions left the open session listing the old versions while `read_seq` advanced. (2) `_reconcile_discovered_trails` never copied a scan's `owner_id` / `owner_archived` into an already-open session (the banner stayed on the old owner). (3) Follow-up: `_load_trail_tasks` rebuilt the live task map once per open tab.
- **Changes made:** (1) the versions list is part of the change test, so the error card is redrawn. (2) new `_apply_trail_owner`: ownership (task frontmatter, not the artifact) is adopted from every accepted scan, independent of `read_seq`; active tab → subtitle, background tab → `•`. (3) the live task map is built once per reload and passed to `_resolve_trail_members`. Tests: a failing-revision test (reload, then a newer scan, each with new versions; card and cache asserted) and an owner-move test with an unchanged document and an equal sequence. Both killed by their mutants.
- **Files affected:** `.aitask-scripts/board/board_trail_screen.py`, `tests/test_trails_app.py`

## Final Implementation Notes
- **Actual work done:** As planned. `TrailSession` + session-delegating properties in `TrailScreenMixin`; `_TRAIL_TABBED` host flag (TrailsApp true, board false); split supersession stamps (`_trail_discovery_gen`, per-session `reload_gen` / `drift_gen`); handle-keyed drift / reload / watch callbacks with background `•`; `trail_discovery.sequenced_trail_read` (per-handle lock, sequence drawn after the read) + `TrailInfo.read_seq`; one reconciliation rule (`_newest_trail_content`) applied to both the cache and the open session; cache-first `s` that re-scans an empty/missing cache; selector `● open` marker and `r` re-scan; `TrailTabStrip` + tab keys (`[` `]` `1`–`9` `ctrl+w`, trails-only `board`-scope rows); render-owned deferred refocus (`_render_seq`). Docs: trails `_index` / how-to / reference, board reference, implementation-trails workflow, TUI index.
- **Deviations from plan:** `_apply_trail_content(..., restart_drift=)` instead of `from_discovery=`; discovery moves an open session only on a strictly newer `read_seq` (equal = both unknown is no evidence); `TRAIL_SELECT_RESCAN` added to the board's re-export list and `VIEW_ONLY_NAMES` (single-home contract in `test_board_trail_view.py`). Review rounds added: guarded selector modal, archive pre-resolution on every task reload (`_load_trail_tasks` / `_resolve_trail_members`), versions as content, scan-driven owner updates, one live-task map per reload.
- **Issues encountered:** `test_real_reload_worker_replaces_the_document`'s `assertIsNone(_trail_infos)` kept passing vacuously after the change (the board's view entry resets the cache) — rewritten to seed a cached entry and assert the in-place update. The first archive-read switch test was non-discriminating because trail B shared A's ghost member and refilled the cache; A now has its own ghost (`99997`), and the mutant is killed.
- **Key decisions:** custom synchronous tab strip rather than Textual `Tabs` (no second source of truth); one global agent-refresh watch kept (closing its trail's tab stops it; a second `R` replaces it — documented); board `s` keeps re-scanning (pinned by `BoardSingleSessionTests`). Every new behaviour test was checked against an in-process mutant (reconcile, newest-wins, empty-cache, pre-resolution ×2, guarded dismiss, versions, owner — all killed) and the A→B→A refocus test carries its own negative control.
- **Upstream defects identified:** None
