---
Task: t2166_fix_switcher_brainstorm_window_listed_twice.md
Base branch: main
Output branch: main
---

# Plan: t2166 — Switcher lists a running `brainstorm-<n>` window twice

## Context

`TuiSwitcherOverlay._populate_list_for` (`.aitask-scripts/lib/tui_switcher.py:950-960`)
adds every `brainstorm-<n>` (on-disk sessions + running windows) to the TUIs group
as a "Brainstorm (t<n>)" entry. The non-TUI classification loop that follows only
skips names in `_TUI_NAMES`, which holds the bare `brainstorm` but not
`brainstorm-<n>`. `_classify_window` returns `"tui"` for the prefixed name, and the
loop's split is `cat == "agent"` vs everything else — so the window also lands in
`others` and renders under "Other". Result with running `stats`, `brainstorm-7`,
`agent-pick-7`: `TUIs … Brainstorm (t7)` / `Code Agents: agent-pick-7` /
`Other: brainstorm-7`.

## Change

### 1. `.aitask-scripts/lib/tui_switcher.py` — non-TUI loop

Replace the `_TUI_NAMES` membership skip with a classification-based skip, so the
loop's skip rule is the classifier's own definition of "tui":

```python
for win_idx, win_name in running_windows:
    cat = _classify_window(win_name)
    if cat == "tui":
        continue  # already rendered in the TUIs group (incl. brainstorm-<n>)
    if cat == "agent":
        agents.append((win_idx, win_name))
    else:
        others.append((win_idx, win_name))
```

Equivalence check: `_classify_window` returns `"tui"` for exactly
`name in _TUI_NAMES` or `name.startswith(_BRAINSTORM_PREFIX)`. The first set is
what is skipped today; the second set is exactly the running windows the
brainstorm block above already adds to the TUIs group (it iterates
`self._running_names` with the same prefix test). So no window disappears from
the list — only the duplicate row goes.

### 2. Regression test — `tests/test_tui_switcher_brainstorm_session.sh`

Add a section to the existing python heredoc (same mocking pattern as the current
`_populate_list_for` block): patch `get_tmux_windows` to return
`[("1","stats"),("2","brainstorm-7"),("3","agent-pick-7")]`, patch
`_build_tui_list` → `[]`, `_discover_brainstorm_sessions` → `[]`, and replace
`_GroupHeader`, `_TuiListItem`, `_WindowListItem` with recorders that return
tagged tuples; capture `list_view.append` calls from the mocked `query_one`.
Emit:

- `DUP_BRAINSTORM_ROWS:<count of rows naming brainstorm-7>` → assert `1`
- `DUP_HEADERS:<comma list of group headers>` → assert `TUIs,Code Agents`
  (no "Other" group, since `stats` is in `_TUI_NAMES` and `brainstorm-7` is now
  skipped)
- `DUP_AGENT_ROWS:agent-pick-7` → agent still listed

Red proof: run the new asserts against the unpatched code first (expect the
count `2` and an `Other` header), then apply the fix.

Update the file's header comment "Covers:" list with the new case.

## Out of scope / notes

- aitasks_go's Go port (`app/switcher/testdata/gen_switcher_fixture.py`) pins the
  old behaviour; regenerating its fixture will show drift. That is expected and
  belongs to that repo — offer an `/aitask-note` at Step 8e if a live owning task
  exists there.

## Verification

```bash
bash tests/test_tui_switcher_brainstorm_session.sh
bash tests/test_tui_switcher_multi_session.sh
bash tests/run_all_python_tests.sh --test-dir tests   # switcher python tests
shellcheck tests/test_tui_switcher_brainstorm_session.sh
```

## Step 9 (Post-Implementation)

Current-branch mode on `main`: commit code (`bug: … (t2166)`) and plan separately,
then archive via `./.aitask-scripts/aitask_archive.sh 2166` and `./ait git push`.

## Risk

### Code-health risk: low
None identified.

### Goal-achievement risk: low
None identified.
