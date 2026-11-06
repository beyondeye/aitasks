---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Implementing
labels: [sitrep, tui]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 2175
created_at: 2026-11-05 15:35
updated_at: 2026-11-06 11:16
---

## Context

Child 1 of t2211 (sitrep window: agent + sitrep TUI + minimonitor). Today `ait sitrep`
opens only the `/aitask-sitrep` code agent (+ minimonitor). Showing the list goes through
the agent, which is slow and hard to scan. This child builds the **read-only half** of a new
Python/Textual sitrep TUI and its launcher (`ait sitrep tui`). Window placement and role
identity are child t2211_2. Actions (harvest/refresh, dismiss, restore, respawn, launches)
are t2211_3. Agent request delivery is t2211_4. The parent plan
`aiplans/p2211_sitrep_two_pane_window_with_sitrep_tui.md` holds every cross-child decision.

User-confirmed decisions that apply here:
- The TUI pane sits below the agent in the `agent-sitrep` window (t2211_2 places it). This
  child only needs `ait sitrep tui [--root P]` to run stand-alone.
- The TUI, not the skill, owns harvest + refresh at startup (wired in t2211_3). This child
  only reads.

## First step: rebase check

t2175_6 (harvest fallback + review corpus) landed in `6fc7b3972` during parent planning. It
added review items, `raw/` + `cases/` store dirs, case-origin pointers and the
`aitask_sitrep.sh case` verb. Re-read the landed `lib/sitrep_todo.py`, `lib/sitrep_cli.py`,
`aitask_sitrep.sh`, `aitask_sitrep_todo.sh` and `aidocs/framework/sitrep.md` ("The store",
"Unparsed output: the review corpus"), and render whatever pointer/item shapes they define.
Confirm `git diff HEAD -- <files you edit>` is empty before the first edit.

## Key files to modify / create

- NEW `.aitask-scripts/sitrep_tui/sitrep_tui_app.py`, `SitrepTuiApp(TuiSwitcherMixin,
  ShortcutsMixin, App)`, `_shortcuts_scope = "sitrep_tui"`, `main(argv)`.
- NEW `.aitask-scripts/aitask_sitrep_tui.sh`: launcher (`require_ait_python`, dependency
  check, `ait_warn_if_incapable_terminal`, `exec`), modelled on `aitask_frozenagent.sh`.
- `.aitask-scripts/aitask_sitrep.sh`: add a `tui` verb that execs the launcher (keep `open`
  as the default verb). Exit codes stay 0/1/2/4.
- `ait`: add `sitrep tui` (or the verb route) to the update-check skip list (~L200) if
  needed.
- `.aitask-scripts/lib/shortcut_scopes.py`: add the module to `KNOWN_BINDING_SOURCES` (~L47).
  `tests/test_shortcut_scopes.py` fails otherwise.
- `.aitask-scripts/lib/tui_registry.py`: a `TUI_REGISTRY` row with `in_switcher=False`. It
  lets the TUI be known to `TUI_NAMES` and the docs, while the switcher's `S` keeps opening
  the sitrep window. **Check** that `maybe_spawn_minimonitor` still accepts the
  `agent-sitrep` window: the TUI name gate (`tui_names`) is keyed by WINDOW name, so the row's
  window name must not be `agent-sitrep`. If the row would collide, drop it and document why.

## Reference files for patterns

- Template TUI: `.aitask-scripts/frozenagent/frozenagent_app.py` (~L1156 `main`),
  `aitask_frozenagent.sh`, `ait:220`, `tests/test_frozenagent_app.py`.
- Store reads: `lib/sitrep_todo.py`:
  - `load_todo_for_read(store_dir)` (~L1394) → `TodoStore(situations, items, contexts,
    format)`;
  - `Item` (~L214: num, rev, kind, state, group, checked_at, ref, derived, outcome, title;
    `.cid`);
  - `ContextEntry` (~L243: background, origin, theme, sources, related);
  - `SLOTS` (~L118) / `_slot_of` (~L287) for grouping (Pick now / Next / Waiting / Recently
    done / Dismissed);
  - `parse_qa(text)` (~L525) → `QaLog.entries` of `QaEntry(ts, items, body)`;
  - `_check_pointer` (~L666) gives the pointer validation rules;
  - `FormatError` means the store is unusable.

  The store is `${AITASK_SITREP_DIR:-.aitask-sitrep}` relative to cwd: run with cwd =
  canonical root (`sitrep_cli.root_arg`, `sitrep_harvest.canonical_root`).
- Off-loop sha256 reload: `SitrepNowCounter` in `monitor/sitrep_close.py` (~L286) and its
  call via `asyncio.to_thread` in `monitor/monitor_app.py` (~L1174).
- Markup safety (t2017): `Static(Content(text))` (`sitrep_close.py` ~L404),
  `Content.from_markup("$x", x=...)`, `monitor_shared.markup_literal`,
  `notify(..., markup=False)`.
- Modals: `lib/guarded_dismiss.py` `GuardedModalScreen` (mandatory, never a bare
  ModalScreen). Details dialog shape: `monitor_shared.TaskDetailDialog`.
- Footer/focus conventions: `aidocs/framework/tui_conventions.md` (`MultiRowFooter`,
  `AUTO_FOCUS=""` + `_claim_startup_focus`, priority bindings scoped to `self.screen`).
- Pointer CLIs:
  - `aitask_artifact.sh get <handle>` writes the bytes to stdout;
  - `aitask_trail_gather.sh drift --trail <path|art:handle>` prints `CURRENT` / `STALE` +
    `DRIFT:code|task|detail` / `ERROR:kind:id`, always exit 0 except 2/3, with cwd = root.

## Implementation plan

1. Rebase check (above).
2. Launcher + `tui` verb + registry/scope registration.
3. App skeleton:
   - header: root, store state, situation text per theme;
   - grouped `ListView`/`DataTable` sections (Pick now / Next / Waiting; Recently done +
     Dismissed behind a toggle key). Each row shows `c<N>`, kind, state, title, outcome and
     the `checked_at` age (`never` shown as such);
   - a "store unusable" banner on `FormatError` (restore comes in t2211_3).
4. Details screen for the selected item:
   - fields, outcome with age, the context map;
   - a source list with **read-only** pointer following into a viewer: `task:` / `plan:` /
     `file:` (re-validate repo-relative, no `..`, no absolute paths, no symlink escape out of
     the root), `capture:` (lines `#La[-Lb]` from `sources/<hex>.txt`), `commit:`
     (`git show --stat <sha>`), `trail:` / `artifact:` (artifact get + trail drift), `url:`
     (display only), plus the t2175_6 case/raw pointers;
   - every subprocess runs in a worker with a timeout, and failures are shown, never
     raised;
   - related items link to their details.
5. Q&A browser screen: entries newest first, each linking to its items; item details show
   "asked about in" back-links.
6. Auto-reload:
   - an interval timer hashes `todo.md` + `qa.md` in `asyncio.to_thread`;
   - only on a digest change does it reparse and re-render;
   - the selection is kept by cid, and a selected item that vanished goes to the nearest
     row;
   - a parse failure keeps the last good view plus the banner.
7. Tests (`tests/test_sitrep_tui_app.py`, `App.run_test`, a fixture store built through the
   REAL writer verbs `aitask_sitrep_todo.sh add/upsert-context/situation/qa` in a scratch
   dir):
   - groups and toggles;
   - details for each pointer kind (incl. a `..` / absolute / symlink-escape pointer being
     refused);
   - Q&A links;
   - a digest change triggers a reload and the selection is kept;
   - a hostile-markup title (`[bold]`, `[/]`, `$x`) renders literally;
   - `FormatError` gives the banner.

   Mind `@work` workers in flight at block exit (`aidocs/framework/testing_conventions.md`).

## Verification

- `bash tests/run_all_python_tests.sh --test-dir tests` (or a narrowed subset), and
  `python -m pytest tests/test_sitrep_tui_app.py tests/test_shortcut_scopes.py` under the ait
  venv.
- `shellcheck .aitask-scripts/aitask_sitrep.sh .aitask-scripts/aitask_sitrep_tui.sh`.
- Manual: `./ait sitrep tui` in this repo shows the real store.
