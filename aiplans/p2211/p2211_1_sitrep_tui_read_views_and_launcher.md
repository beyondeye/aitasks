---
Task: t2211_1_sitrep_tui_read_views_and_launcher.md
Parent Task: aitasks/t2211_sitrep_two_pane_window_with_sitrep_tui.md
Sibling Tasks: aitasks/t2211/t2211_2_*.md, aitasks/t2211/t2211_3_*.md, aitasks/t2211/t2211_4_*.md, aitasks/t2211/t2211_5_*.md, aitasks/t2211/t2211_6_*.md
Archived Sibling Plans: aiplans/archived/p2211/p2211_*_*.md
Base branch: main
Output branch: main
---

# t2211_1 — Sitrep TUI: read views + launcher

Parent plan: `aiplans/p2211_sitrep_two_pane_window_with_sitrep_tui.md`. The task file
carries the full context, the reference line numbers and the patterns.

## Steps

1. **Rebase check.**
   - Re-read the landed t2175_6 surface (`6fc7b3972`): `lib/sitrep_todo.py` (raw/cases
     dirs, case-origin pointers, review items), `lib/sitrep_cli.py`, `aitask_sitrep.sh`
     (`case` verb), and `aidocs/framework/sitrep.md` "The store" + "Unparsed output".
   - `git diff HEAD -- <files>` must be empty for every file edited below.
2. **Launcher.**
   - New `.aitask-scripts/aitask_sitrep_tui.sh`, a copy of the `aitask_frozenagent.sh` shape:
     `require_ait_python`, the missing-dependency check, `ait_warn_if_incapable_terminal`,
     then `exec "$PYTHON" .aitask-scripts/sitrep_tui/sitrep_tui_app.py "$@"`.
   - `aitask_sitrep.sh`: a `tui)` arm in the verb dispatch that execs the launcher with
     the remaining args. Update the header usage text.
   - `ait`: route `sitrep tui` past the update check if `sitrep` is not already skipped
     (~L200).
3. **Registration.**
   - `lib/shortcut_scopes.py` `KNOWN_BINDING_SOURCES`: add `sitrep_tui/sitrep_tui_app.py`.
   - `lib/tui_registry.py`: add a row (`window="sitrep-tui"` label "Sitrep TUI",
     `in_switcher=False`). Then verify with `TUI_NAMES` that `maybe_spawn_minimonitor`'s
     name gate is unaffected for `agent-sitrep`.
   - If the row adds no value beyond the docs, skip it and record the decision in the
     Final Implementation Notes.
4. **App** `sitrep_tui/sitrep_tui_app.py`.
   - `SitrepTuiApp(TuiSwitcherMixin, ShortcutsMixin, App)`, `current_tui_name="sitrep_tui"`,
     `_shortcuts_scope="sitrep_tui"`. Use `MultiRowFooter`, `AUTO_FOCUS=""` +
     `_claim_startup_focus`.
   - `main(argv)` takes `--root`: it resolves `canonical_root` via `sitrep_cli.root_arg`,
     `chdir`s there, and uses store_dir = `$AITASK_SITREP_DIR` or `.aitask-sitrep`.
   - Model: a `load()` function that returns `(TodoStore|None, QaLog|None, error|None)` from
     `load_todo_for_read` + `parse_qa`. It is pure and testable.
   - Main screen:
     - header `Static`: root, store state, situation lines per theme (`Content(text)`);
     - one section per slot in `SLOTS` order. Done and dismissed are hidden behind the `d`
       toggle;
     - rows: `c<N>  kind  state  title  outcome  (age)`, where the age is computed from
       `checked_at` (`never` literal).
   - Details screen (a pushed `Screen`):
     - fields, then the context: background, origin pairs, theme, sources, related;
     - a sources `ListView`; Enter follows a pointer into a viewer `RichLog(markup=False)`
       / `TextArea(read_only=True)`.
   - Pointer followers (one function each, workers, 10 s timeout, errors shown):
     - `task:` / `plan:` / `file:`: re-validate repo-relative, no `..`, not absolute,
       `realpath` inside the root;
     - `capture:`: parse `sources/<16hex>.txt#La[-Lb]` and slice the lines;
     - `commit:`: `git show --stat --no-color <sha>`;
     - `trail:` / `artifact:`: `aitask_artifact.sh get <h>` and `aitask_trail_gather.sh
       drift --trail art:<h>` (or the path);
     - `url:`: display only;
     - the t2175_6 case/raw pointers via its landed reader (`read_case_record` /
       `case_origin_input`, or whatever landed).
   - Q&A screen (`q`): entries newest first. Enter on an item reference opens that item's
     details; item details list "asked about in <ts>" back-links.
   - Reload:
     - `set_interval(2.0)` drives a worker that runs `asyncio.to_thread(digest)` over
       `todo.md` and `qa.md`;
     - on a change it reloads, re-renders and restores the selection by cid;
     - a parse failure keeps the last good view and shows the banner.
5. **Tests** `tests/test_sitrep_tui_app.py`.
   - Fixture store in a tmp dir (`AITASK_SITREP_DIR` absolute) built with the real
     `aitask_sitrep_todo.sh` verbs: add, upsert-context with every pointer kind, situation,
     qa.
   - `run_test` cases: groups, the toggle, details per pointer, the refusal of `..` /
     absolute / symlink-escape, Q&A links both ways, a digest change triggering a reload
     with the selection kept, a hostile-markup title rendered literally, a corrupted
     `todo.md` showing the banner.
   - Await or cancel the workers before block exit (`testing_conventions.md`).

## Verification

- `python -m pytest tests/test_sitrep_tui_app.py tests/test_shortcut_scopes.py` under the
  ait venv, and `bash tests/run_all_python_tests.sh` (read the last line).
- `shellcheck .aitask-scripts/aitask_sitrep.sh .aitask-scripts/aitask_sitrep_tui.sh`.
- Manual: `./ait sitrep tui` shows the real store's groups, details, pointers and Q&A.

## Step 9

Commit with `feature: … (t2211_1)` and archive via the normal post-implementation flow.
