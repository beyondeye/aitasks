---
Task: t2211_1_sitrep_tui_read_views_and_launcher.md
Parent Task: aitasks/t2211_sitrep_two_pane_window_with_sitrep_tui.md
Sibling Tasks: aitasks/t2211/t2211_2_*.md, aitasks/t2211/t2211_3_*.md, aitasks/t2211/t2211_4_*.md, aitasks/t2211/t2211_5_*.md, aitasks/t2211/t2211_6_*.md, aitasks/t2211/t2211_7_*.md
Archived Sibling Plans: aiplans/archived/p2211/p2211_*_*.md
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5_5 @ 2026-11-07 18:19
---

# t2211_1 — Sitrep TUI: read views + launcher (verified 2026-11-06)

## Context

`ait sitrep` opens only the `/aitask-sitrep` agent (+ minimonitor), so reading the
store goes through an LLM — slow and hard to scan. This child builds the
**read-only half** of a Python/Textual sitrep TUI plus its launcher
`ait sitrep tui [--root P]`. Placement in the `agent-sitrep` window (t2211_2),
actions (t2211_3), agent request delivery (t2211_4), skill slim (t2211_5) and
docs (t2211_6) are siblings. Parent plan:
`aiplans/p2211_sitrep_two_pane_window_with_sitrep_tui.md`.

## Verification findings (premises re-derived against HEAD)

- **Rebase check:** t2175_6 is landed. `git diff HEAD` is empty for
  `aitask_sitrep.sh`, `lib/sitrep_todo.py`, `lib/sitrep_cli.py`,
  `lib/sitrep_harvest.py`, `lib/shortcut_scopes.py`. Re-check right before the
  first edit (main advances mid-session).
- **`ait` is NOT edited.** It carries another session's uncommitted hunks
  (`relations` verb). The edit is unnecessary anyway: `sitrep` was never in the
  update-check skip list, the notice is printed only from a fresh cache, and the
  TUI takes the alternate screen right after. (Shared-file gate: don't edit.)
- **No `TUI_REGISTRY` row.** `TUI_NAMES` is a *window-name* registry, and its
  consumers would mis-treat a pane-only TUI: `monitor_core.spawn_tui` /
  `applink/router.py` allow-list it and run `new-window -n <name> "ait <name>"`
  (a broken launch for `sitrep_tui`), `get_missing_tuis` would report it
  missing, and `framework_version.detect_target_activity` would count a window of
  that name as busy. The sitrep TUI never owns a window (it is a pane in
  `agent-sitrep`), so the row would add no value and some hazards. Recorded in
  the Final Implementation Notes for t2211_6 (docs list TUIs by hand).
- **Store location = `<canonical root>/.aitask-sitrep`**, not
  `$AITASK_SITREP_DIR`. That is what every read-side consumer uses
  (`sitrep_cli` triage, `sitrep_close.SitrepNowCounter`, harvest, refresh);
  only the writer honours the variable. Tests therefore build the store with the
  real writer run with `cwd=<tmp root>` and `AITASK_SITREP_DIR` removed from env.
- **"case/raw pointers" are `capture:` pointers.** t2175_6 records review cases
  as `sources/<hex>.txt` copies whose byte-identical `cases/<hex>.txt` twin
  makes them trusted. Labelling logic already exists in `sitrep_cli`
  (`_capture_kind`, `_review_case`, `_trusted_text`); the raw input of a trusted
  origin comes from `sitrep_todo.case_origin_input` + `raw_input_ok`. Reuse, do
  not re-implement.
- `file:` pointers may carry a `#L<a>[-L<b>]` fragment (golden fixture:
  `aidocs/framework/shadow_agent.md#L10`). `trail:` handles are `art:trail-<id>`
  in production; the fixture also has bare values.
- Textual 8.2.7: `OptionList` skips `disabled=True` options on keyboard nav
  (probed), so group headings are disabled options in one list. An `async`
  `set_interval` callback is awaited by the timer, so reload ticks never overlap
  and need no worker. `TextArea(read_only=True, show_line_numbers=True,
  line_number_start=…)` exists.

## Implementation steps

1. **Rebase re-check.** `git diff HEAD --stat --` on every file below must be
   empty; stop and report if not.

2. **`lib/sitrep_todo.py`** — add public `load_qa_for_read(store_dir) -> QaLog`
   mirroring `load_todo_for_read` (missing `qa.md`: `_require_not_damaged(store,
   "qa")` then `QaLog()`; else `load_qa`). The model (step 4) calls the two
   `*_for_read` functions only for a **missing** file; present files are parsed
   from the bytes it hashed.

3. **`lib/sitrep_cli.py`** — public names for the TUI, no behaviour change:
   ```python
   #: Public names (t2211_1): the sitrep TUI labels the same capture pointers.
   capture_kind = _capture_kind
   review_case = _review_case
   ```

4. **NEW `.aitask-scripts/sitrep_tui/sitrep_tui_model.py`** (stdlib + lib only,
   no Textual — unit-testable):
   - `Snapshot(digest, store: TodoStore|None, qa: QaLog|None, todo_error: str,
     qa_error: str)`.
   - `read_digest_and_bytes(store_dir)` → per file `(state, sha256, bytes)` where
     state is `ok|missing|error:<msg>`; `load_snapshot(store_dir, prev_digest=None)`
     returns `None` when the digest equals `prev_digest` (no parse), else parses
     **the same bytes it hashed** (`parse_todo(data.decode("utf-8"), path)`,
     `parse_qa(...)`; a missing file follows the `*_for_read` semantics; any
     `FormatError` / `UnicodeDecodeError` / `OSError` becomes the error string).
   - `group_items(store, show_closed) -> [(slot, heading, [Item])]` from
     `st.SLOTS` + `st._slot_of`; done/dismissed only when `show_closed`.
   - `resolve_now() -> datetime`: `st.now_ts()` (honours `AITASK_SITREP_NOW`)
     parsed with `strptime`; a `RequestError` **or** a `ValueError` (the seam
     matches `TS_RE` but is no calendar date, e.g. `2026-02-31T12:00:00Z` —
     `now_ts` checks syntax only) falls back to real UTC now. Never raises.
   - `age_text(checked_at, now: datetime)` → `never` | `just now` | `5m ago` |
     `3h ago` | `2d ago`. A `checked_at` that passes the store grammar but is no
     calendar date (`normalize_ts` accepts `2026-02-31T12:00:00Z`; the writer is
     **not** changed here) → `at <raw> (invalid date)`; a future time → `in the
     future`. Never raises — it runs at render time, after `load_snapshot`'s
     error handling.
   - `row_text(item, now)` → `c<N>  kind  state  title  — outcome (age)`.
   - `qa_newest_first(qa)`, `qa_backlinks(qa, num)`, `referenced_by(store, num)`.
   - `PointerView(title, text, error, first_line=1, focus_line=None)` and
     `follow_pointer(root, store_dir, stype, ptr, timeout=20) -> PointerView`
     that **never raises** (catch-all → `error`):
     - `task` / `plan` / `file`: `safe_repo_path(root, ptr)` — strip and parse
       `#L<a>[-L<b>]`; refuse empty, `/`, `~`, `\`, control chars, a `..`
       segment; `realpath(join(root, rel))` must equal or be under
       `realpath(root)` (symlink escape refused: "points outside the
       repository"); must be a regular file. Read ≤256 KiB (`errors="replace"`,
       note when truncated); `focus_line=a`.
     - `capture`: `st.CAPTURE_RE`; `<store>/sources/<hex>.txt` must be a regular
       non-symlink file under the store; show lines a..b (`first_line=a`,
       note when past EOF). Title carries the label
       `sitrep_cli.capture_kind(...)` (CAPTURE/BANNER/KEY/CASE/ANALYSIS/REVIEW).
     - `commit`: `st.COMMIT_RE`, then `git -C <root> show --stat --no-color
       --format=fuller <sha> --`.
     - `trail`: refuse a value starting with `-` or with whitespace; a value not
       starting with `art:` must also pass `safe_repo_path` (it reaches
       `trail_gather` as a path). Run `aitask_trail_gather.sh drift --trail <v>`
       (cwd=root) and `aitask_artifact.sh get <v>` (art: handles) or read the
       file (paths); show the drift verdict lines above the content.
     - `artifact`: same `-`/whitespace refusal; `aitask_artifact.sh get <v>`.
     - `url`: text only, never opened.
     - unknown type: error.
     - every subprocess: argv list, `cwd=root`, `capture_output`, `timeout`,
       non-zero rc → error with the stderr tail.
   - `case_extras(store_dir, ptr)` → for a trusted CASE pointer, the raw input
     `(rel, sha, ok)` from `case_origin_input` + `raw_input_ok`;
     `follow_raw(store_dir, rel, sha)` shows the first 256 KiB of a verified raw
     input (sha mismatch → error). `review_case(store_dir, captures[1:])` gives
     the "review case <hex> (<codes>) — `ait sitrep case show <hex>`" line.

5. **NEW `.aitask-scripts/sitrep_tui/sitrep_tui_app.py`** — sys.path bootstrap
   as `frozenagent_app.py`; all store strings rendered through `rich.text.Text`
   (OptionList prompts) / `Static(Content(text))`; `notify(..., markup=False)`.
   - `SitrepTuiApp(TuiSwitcherMixin, ShortcutsMixin, App)`,
     `_shortcuts_scope="sitrep_tui"`, `current_tui_name="sitrep_tui"`,
     `__init__(root, store_dir, reload_interval=2.0)` (absolute paths, never
     chdir — tests share a process).
   - Compose: `#st-header` Static (root, store state: `N items · M open now` /
     `no store yet` / last-reload time), `#st-banner` Static (hidden unless an
     error: "Store unusable: <err> — showing the last good view" / "restore with
     `aitask_sitrep_todo.sh restore todo|qa`"), `#st-situation` VerticalScroll
     (`max-height: 6`, one `#### theme` block per theme, hidden by `s`), `#st-list`
     OptionList (disabled heading options `Pick now (3)` etc., item options
     `id=c<N>`), `MultiRowFooter(hint_action="open_shortcuts_editor")`.
     Sized for the ~40%-height pane t2211_2 gives it.
   - Startup focus: default screen `_SitrepScreen(Screen)` with `AUTO_FOCUS=""`,
     `on_mount` → `call_after_refresh(self._claim_startup_focus)` (focus list).
   - Bindings (footer-visible): `q` Quit, `enter` Details, `d` Done/dismissed
     toggle, `l` Q&A log, `s` Situation toggle, plus `SWITCHER_BINDINGS` and
     `SHORTCUTS_MIXIN_BINDINGS`. `check_action` hides `enter` when no item is
     highlighted (hook t2211_3 extends; actions re-check).
   - Reload: `set_interval(reload_interval, self._poll_store)`;
     `async _poll_store()` = `await asyncio.to_thread(load_snapshot, store_dir,
     self._digest)` inside try/except (a failing tick never reaches
     `_handle_exception`). Changed → `_apply_snapshot`: a todo error keeps the
     last good store and shows the banner; otherwise rebuild the list.
     **Unchanged → `_refresh_ages()`** on the same tick: recompute the visible
     rows' text from the cached store and `replace_option_prompt` only the rows
     whose label changed (no reparse, no rebuild, highlight untouched); every
     `ItemDetailScreen` on the stack re-renders its `checked_at` age line the
     same way (`refresh_ages()` hook).
     `_rebuild_list()` keeps the highlighted cid; if it vanished (or got hidden
     by the toggle) it highlights the item at the same position among item rows,
     clamped to the last. Initial load is synchronous in `on_mount` (one small
     read).
   - **Detail / Q&A-entry layout (keyboard-scrollable, both halves reachable):**
     a focusable `VerticalScroll` text pane (`height: 1fr`, holding the
     Static(Content)) above the link `OptionList` (`height: auto; max-height:
     50%`), each in its own region so focusing one never scrolls the other away.
     Footer-visible `tab` / `shift+tab` "Text/links" (`focus_next` /
     `focus_previous`). The links list has focus on open. The text pane, when
     focused, scrolls with up/down/PageUp/PageDown/Home/End (probed at 100×16:
     End reaches the bottom and the list keeps its own Home/End).
   - `ItemDetailScreen(ShortcutsMixin, GuardedDismissMixin, Screen)`,
     scope `sitrep_tui.detail`: text pane with fields (cid, rev, kind,
     state, group, ref, derived, outcome + `checked_at` age, title), context
     (background, origin `k=v`, theme), the review-case line; then one
     OptionList "Sources & links": `src:<i>` (`capture [CASE]: …`), `raw:<i>`
     (verified raw input of a trusted case origin), `rel:<n>` (related; a cid
     not in the store is a disabled `c9 (not in store)`), `ref:<n>`
     (referenced by), `qa:<i>` ("asked about in <ts>"). Enter: sources/raw run
     `follow_pointer` in a `run_worker(..., group="pointer", exclusive=True)`
     coroutine (`asyncio.to_thread`), then push `PointerViewerScreen` if this
     screen is still active; rel/ref push another `ItemDetailScreen` from the
     app's current snapshot; qa pushes `QaEntryScreen`. Escape closes
     (`self.dismiss()`). Details show the snapshot taken when opened.
   - `PointerViewerScreen` (scope `sitrep_tui.viewer`): title + error Static
     (Content), `TextArea(read_only=True, show_line_numbers=True,
     line_number_start=first_line)`, cursor moved to `focus_line`; Escape closes.
   - `QaLogScreen` (scope `sitrep_tui.qa`): OptionList of entries newest first
     (`<ts>  items: c1,c3 — <first body line>`); Enter → `QaEntryScreen`.
     `QaEntryScreen` (same scope): the split layout above — body in the text
     pane, OptionList of item links below (Enter → `ItemDetailScreen`; missing
     cid disabled). qa_error → message instead.
   - `main(argv)`: argparse (`allow_abbrev=False`, `--root` default `.`,
     `type=sitrep_cli.root_arg` → exit 2), `sh.canonical_root(abspath)`;
     `HarvestFailure` → `ROOT_FAILED:<why>` on stderr, exit 1; `os.chdir(root)`
     (so ShortcutsMixin/config reads are project-relative), store =
     `join(root, sh.STORE_NAME)`, run the app, return 0.

6. **NEW `.aitask-scripts/aitask_sitrep_tui.sh`** — clone of
   `aitask_frozenagent.sh`: `require_ait_python`, textual/pyyaml check (`die`),
   `ait_warn_if_incapable_terminal`, `exec "$PYTHON"
   "$SCRIPT_DIR/sitrep_tui/sitrep_tui_app.py" "$@"`. `chmod +x`.

7. **`.aitask-scripts/aitask_sitrep.sh`** — `tui) shift; exec
   "$SCRIPT_DIR/aitask_sitrep_tui.sh" "$@" ;;` in the verb `case` (beside
   `case)`); header usage block gains `ait sitrep tui [--root <path>]` with one
   line of description; `usage()` gains the line. `open` stays the default;
   exit codes unchanged.

8. **`lib/shortcut_scopes.py`** — `KNOWN_BINDING_SOURCES` entry
   `("sitrep_tui_app", "sitrep_tui/sitrep_tui_app.py", ("sitrep_tui",
   "sitrep_tui.detail", "sitrep_tui.viewer", "sitrep_tui.qa"))`.

9. **NEW `tests/test_sitrep_tui_app.py`** (unittest; `IsolatedAsyncioTestCase`
   for `run_test`). Fixture: tmp root (git-inited for the commit case), store
   built through the REAL `aitask_sitrep_todo.sh` (`cwd=root`, env without
   `AITASK_SITREP_DIR`, `AITASK_SITREP_NOW` pinned): `add` items across
   now/next/waiting + one `set-state done` + one `dismiss`; `retain` a passage;
   `upsert-context` with every pointer kind (task/plan/file#L2 files created in
   root, capture, commit of a real commit, url, a `file:` symlink to a file
   outside root); `situation` for two themes; two `qa --items` entries; a
   trusted case via `retain-case` + `retain` of the same record bytes +
   `retain-raw` of its input.
   - Model (pure): `group_items` with/without closed slots; `age_text` table
     incl. `never`, a future time and the impossible date `2026-02-31T12:00:00Z`
     (→ `at … (invalid date)`, no exception); `resolve_now` with
     `AITASK_SITREP_NOW=2026-02-31T12:00:00Z` and with a malformed value (→ real
     UTC now, no exception);
     `load_snapshot` returns `None` on an unchanged digest and parses on change;
     `safe_repo_path` refuses `..`, absolute, `~`, backslash, symlink escape and
     accepts a normal path + fragment; `follow_pointer` for each kind (capture
     slice + label, commit `--stat` text, url text-only, missing file → error,
     a `-`-leading trail/artifact refused, artifact/trail with a fake script
     dir or the real CLI's error surfaced, never raised); `case_extras` +
     `follow_raw` (sha ok / tampered raw → error).
   - **Negative control:** with `safe_repo_path`'s realpath containment patched
     out, the symlink-escape test must fail (asserted in-test via a
     subTest/`assertRaises(AssertionError)` wrapper, naming the guard).
   - App (`run_test(size=(100, 16))` — the short pane): headings + rows per
     group; `d` reveals Recently done / Dismissed; Enter opens details with
     fields, outcome age, context and the source options; a source option
     opens the viewer (drive the worker, then `await
     app.workers.wait_for_complete()` — `follow_pointer` never raises); the
     symlink pointer shows the refusal in the viewer; related → details of the
     related item; `l` → Q&A newest first → entry → item link → details; item
     details list the "asked about in" back-link; reload: highlight c3, add an
     item through the writer, `await app._poll_store()` → new row present and
     c3 still highlighted; dismiss the highlighted item (closed hidden) →
     highlight moves to the nearest row; a real short-interval timer tick picks
     up a change (wiring proof); a hostile title `[bold]x[/] $x [link=y]z`
     renders literally in the list and details (no MarkupError);
     **impossible date**: an item set through the writer with `set-state …
     --checked-at 2026-02-31T12:00:00Z` (the writer accepts it) renders
     `(invalid date)` in its row and details and the app keeps running;
     **ages refresh without reparse**: pin `AITASK_SITREP_NOW`, mount, advance
     the seam by 2h with the files untouched, `await app._poll_store()` → the
     row label changes to `2h ago`, the highlight is unchanged, and a counting
     wrapper around `sitrep_todo.parse_todo` shows zero new parses (an open
     details screen's age line changes too);
     **keyboard scrolling at 100×16**: an item whose context fills the 2000-byte
     cap with many sources, and a Q&A entry with a long multi-line body — using
     keys only, `tab` to the text pane + `end` reaches `max_scroll_y > 0`, then
     `shift+tab`/`tab` back to the list + `end` highlights the last link and
     Enter opens it; overwrite
     `todo.md` with garbage → banner shown and the last good rows kept; a store
     corrupted before start → banner, empty list. Assert `app.workers` empty at
     block exit.
   - Launcher: `aitask_sitrep.sh tui --root ''` exits 2; `--root
     /nonexistent/x` exits 1 with `ROOT_FAILED:`; `tui --help` exits 0 (all
     without a TTY — argparse runs before Textual starts).

### Post-implementation (Step 9)
Commit `feature: Add the sitrep TUI read views and launcher (t2211_1)`; archive
via the normal Step 9 flow. Final Implementation Notes must record for
t2211_2..6: the store-location rule, no registry row (docs list it by hand),
`ait` untouched, the `check_action`/`_selected_item()` hooks for t2211_3, and
that details screens are snapshots (t2211_3 may refresh them after writes).

## Verification

- `~/.aitask/venv/bin/python -m pytest tests/test_sitrep_tui_app.py
  tests/test_shortcut_scopes.py tests/test_sitrep_corpus.py` (or unittest).
- `bash tests/run_all_python_tests.sh` — read the last line only.
- `shellcheck .aitask-scripts/aitask_sitrep.sh .aitask-scripts/aitask_sitrep_tui.sh`.
- `bash tests/test_sitrep_window_live.sh` / `tests/test_sitrep_skill_contract.sh`
  still pass (the `open` path is unchanged).
- Manual: `./ait sitrep tui` in this repo shows the real store's groups,
  details, pointers and Q&A.

## Risk

### Code-health risk: low
- Pointer following reads paths and runs CLIs with values taken from the store
  (agent-written text): traversal, symlink escape or option injection would
  read outside the repo · severity: low · → mitigation: none (design
  requirement: `safe_repo_path` realpath containment, `-`-leading refusal, argv
  only, fixed `--`; refusal tests + a negative control for the containment)
- Workers/timers in `run_test` can fail an unrelated test if left in flight ·
  severity: low · → mitigation: none (reload is an awaited timer callback, not a
  worker; pointer workers never raise and are drained; `app.workers` asserted
  empty)

### Goal-achievement risk: low
- Three deliberate deviations from the task text (store dir, no registry row,
  `ait` untouched) could surprise the siblings · severity: low · → mitigation:
  none (each justified above and recorded in Final Implementation Notes)
- The TUI will live in a ~40%-height pane; an unbounded situation header could
  push the list off-screen, and long detail / Q&A text could hide its links ·
  severity: low · → mitigation: none (capped `max-height`, `s` toggle, split
  text/links layout with `tab`, key-only reachability tests at 100×16)
- Render-time values the parser accepts but `datetime` rejects (impossible
  calendar dates in `checked_at` or the clock seam) and age labels that go stale
  on an idle store · severity: low · → mitigation: none (never-raising
  `age_text` / `resolve_now`, per-tick age refresh without reparse, tests)
