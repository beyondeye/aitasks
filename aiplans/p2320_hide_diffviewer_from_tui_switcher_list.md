---
Task: t2320_hide_diffviewer_from_tui_switcher_list.md
Base branch: main
Output branch: main
plan_verified: []
---

# t2320 — Drop Diff Viewer from the TUI switcher

## Context

The docs screenshot generator (t2278) captures the real TUI switcher (opened with `j`)
for the `tui_switcher_from_monitor` / `tui_switcher_from_minimonitor` scenes (and the
`tui_switcher_dialog` scene on `website/content/docs/tuis/_index.md`). The switcher lists
"Diff Viewer", because `.aitask-scripts/lib/tui_registry.py` registers
`("diffviewer", "Diff Viewer", "ait diffviewer", True)` and `lib/tui_switcher.py` builds
`KNOWN_TUIS = switcher_tuis()` from it. CLAUDE.md says diffviewer is transitional and must
stay out of user-facing lists, but it also says to keep it in `KNOWN_TUIS` "switchable via
`j`". Those two rules conflict.

Findings:
- `j` only opens the switcher. diffviewer has no shortcut key there (`_TUI_SHORTCUTS` has
  no entry and there is no `action_shortcut_diffviewer`), and `DiffViewerApp` does not mix
  in `TuiSwitcherMixin`. So "switchable via `j`" only ever meant "listed as a row".
- `website/content/docs/tuis/_index.md` ("Navigating between TUIs") already leaves Diff
  Viewer out of its list, so the documented list currently differs from the real one.
- `brainstorm` already pushes `DiffViewerScreen` for proposal diffs (t745_4). Only the
  standalone merge and plan-manager screens are not integrated yet (t417 / t423).

**User decision (planning):** drop it from the switcher (option 3) and update the
CLAUDE.md rule. `ait diffviewer` stays the way to launch it. Not showing a running
diffviewer window under "Other" is accepted: the window stays classified as a TUI, the
same way `minimonitor` and `scratchpad` are.

Base branch: main · Output branch: main · current-branch mode (profile `fast`).

## Implementation

1. **`.aitask-scripts/lib/tui_registry.py`** — change the diffviewer row to
   `("diffviewer", None, None, False)` and move it into the hidden block (after
   `syncer`, alongside `brainstorm` / `minimonitor` / `scratchpad`). It stays in
   `TUI_NAMES`, so monitor/minimonitor pane classification and minimonitor auto-spawn
   exclusion (`agent_launch_utils`) do not change. Add a short comment on the row:
   transitional, launched with `ait diffviewer`, hidden from the switcher until the
   brainstorm integration lands.
   - `_get_launch_command` falls back to `ait <name>` for unknown names, so nothing
     else in `tui_switcher.py` needs to change. Check that `switcher_tuis()`'s
     `l and c` filter still drops the row (it does: `in_sw=False`).

2. **`tests/test_git_tui_config.py`** (`TestTuiRegistry`) — add
   `test_diffviewer_classified_but_hidden_from_switcher`: `"diffviewer" in TUI_NAMES`
   and `"diffviewer" not in {n for n, _, _ in switcher_tuis()}`. Also assert it is not
   in `tui_switcher.KNOWN_TUIS` names, which pins the switcher-side list too. The
   existing `test_registry_contains_all_framework_tuis` already covers `TUI_NAMES`
   membership and stays as it is.

3. **`CLAUDE.md`** ("Project-Specific Notes", the diffviewer bullet) — replace
   "Keep `diffviewer` in `KNOWN_TUIS` … switchable via `j` until the brainstorm
   integration lands" with: diffviewer is registered in `TUI_REGISTRY` with
   `in_switcher=False`, so it classifies as a TUI window but is not listed in the `j`
   switcher. Launch it with `ait diffviewer` until the brainstorm integration lands.
   Keep the "omit it from user-facing website docs and lists-of-TUIs" sentence.

4. **`aidocs/framework/tui_conventions.md`** line ~632 — the registry-order example
   "App Linker sits after `stats` and before `diffviewer`" no longer names a
   switcher-visible neighbour. Change it to "before `chatlink`".

5. **Website** — no change. `docs/tuis/_index.md` already lists the switcher without
   Diff Viewer, and that now matches the code. No `website/content` page is edited, so
   `check_links.py` is not needed.

## Verification

- `python3 tests/test_git_tui_config.py` (or via the runner) — the new test passes.
- Switcher tests: `bash tests/run_all_python_tests.sh --test-dir` scoped to the switcher
  modules is awkward, so run them directly:
  `python3 -m pytest -q tests/test_tui_switcher_*.py tests/test_switcher_ring_dedupe.py tests/test_git_tui_config.py`
  (fall back to `python3 <file>` per module if pytest is unavailable), plus
  `bash tests/test_tui_switcher_brainstorm_session.sh tests/test_tui_switcher_multi_session.sh tests/test_tui_switcher_footer_fit.sh`
  (each run individually).
- `bash tests/test_shortcuts_registry_coverage.sh` (diffviewer_app is still a shortcut
  scope).
- Quick probe: `python3 -c` with `.aitask-scripts/lib` on `sys.path`, printing
  `[n for n,_,_ in switcher_tuis()]` (no diffviewer) and `'diffviewer' in TUI_NAMES`
  (True).

## Post-implementation

- Step 8e: send an `ait note` to t2278_5 saying the switcher no longer lists Diff Viewer,
  so the `tui_switcher_from_monitor` / `tui_switcher_from_minimonitor` scenes (and
  `tui_switcher_dialog`) can now be recorded.
- Step 9: commit (`enhancement: … (t2320)`) and archive per the shared workflow.

## Risk

### Code-health risk: low
- One registry tuple changes, plus a test and two doc lines. All consumers of `TUI_NAMES`
  (monitor classification, minimonitor auto-spawn exclusion) are unaffected, because
  the name stays in the classification set. · severity: low · → mitigation: none needed

### Goal-achievement risk: low
- A diffviewer window that is already open is no longer reachable from the `j`
  switcher. It is classified as a TUI, so it is also left out of "Other". The user
  accepted this when choosing option 3. · severity: low · → mitigation: none (accepted
  trade-off)
