---
Task: t1511_manual_verification_fix_codebrowser_non_git_focus_deadend_fo.md
Verifies: t1500
Worktree: (none — current-branch mode)
Branch: main
Base branch: main
Output branch: main
---

# Auto-Verification Execution Log — t1511

Autonomous whole-list auto-verification of the t1511 checklist, which verifies
t1500 (`bug: Stop mounting the codebrowser search box outside a git repo`).

## Harness

Live tmux, mirroring `tests/test_codebrowser_startup_focus_live.py`: a
throwaway per-run socket (`ait_t1511_verify`), an interactive shell in each
pane (200x50), and two standalone `ait` fixtures built as a copy of `ait`
beside a **symlink** to the real `.aitask-scripts` — so the panes ran the
working-tree code, not a stale snapshot.

- `fixtures/nogit` — plain directory, **no** `.git`, so `get_project_root()`
  raises and `compose()` takes the `RuntimeError` arm (items 1–3).
- `fixtures/withgit` — real repo, tracked `src/alpha.py` (8 lines),
  `src/beta.py`, `docs/zeppelin.md` (items 4–7).

Driver: `drive.py` in the session scratchpad (setup / launch / send / capture /
capture-ansi / cmd / waitshell / addfile / teardown). Both fixtures and the
tmux server were torn down at the end. Nothing under `aitasks/` or `aiplans/`
was touched by the harness.

Focus was never asserted from a headless replica — every stop is pinned by a
**behavioural probe in the real pane**, plus `capture-pane -e` colour evidence
where a probe would have mutated state.

## Execution Log

### Item 1 — non-git: error in sidebar, no search box
- Item text: Launch `ait codebrowser` from a directory that is NOT a git repo:
  the sidebar shows "Error: not inside a git repository" and NO "Search
  files..." box is drawn anywhere in the code pane.
- Approach: TUI interaction (live pane) + full-capture assertion.
- Action run: `drive.py launch nogit "not inside a git repository"`, then
  `grep` over the whole capture.
- Output (trimmed): sidebar renders `Error: not inside a git repository`; the
  code pane renders only `No file selected` / `Select a file to view` /
  `CodeViewer`. `grep "Search files"` over the entire 50-row capture: **no
  match**.
- Verdict: **pass**

### Item 2 — non-git: Tab is a degenerate cycle, nothing takes the keyboard
- Item text: press Tab several times: focus never leaves the code viewer and no
  hidden widget takes the keyboard (no cursor appears in a search field).
- Approach: TUI interaction with a positive control.
- Action run: 6x `Tab`, capture-diff against the pre-Tab capture, then a bare
  `?`.
- Output (trimmed): the capture after 6 Tabs is **byte-identical** to the
  pre-Tab capture except the header clock (`20:53:12` → `20:53:23`); still no
  search field. The bare `?` then opened the `Shortcuts — codebrowser` overlay
  — the keystroke reached an App binding, so no text input held the keyboard.
  (The positive control matters: "screen unchanged" alone would also be
  consistent with a dead app.)
- Verdict: **pass**

### Item 3 — non-git: a bare `q` quits
- Item text: press a bare `q`: the codebrowser exits back to the shell (the
  keystroke is not swallowed).
- Approach: TUI interaction, asserted on `#{pane_current_command}` rather than
  on pixels.
- Action run: `Escape` (dismiss the overlay), `q`, poll `pane_current_command`.
- Output (trimmed): `cmd before q: python` → `OK: pane back at shell (bash)
  after 0.3s`; the `not inside a git repository` marker is gone from the pane.
- Verdict: **pass**

### Item 4 — git repo: box present, results on the FIRST keystroke
- Item text: the "Search files..." box IS present, and typing a partial
  filename shows matching results immediately on the first keystroke (this
  proves the boot seeding reached the widget, not just its internal list).
- Approach: TUI interaction.
- Action run: `drive.py launch git "Recent Files"`; `Tab` `Tab` (recent →
  tree → search); send a **single** `z`.
- Output (trimmed): the box renders with placeholder `Search files...`; after
  the one keystroke the result list unhid with `docs/zeppelin.md`. A single
  character is what makes this discriminating — the `on_mount`
  `_seed_search_index` call must already have populated `_all_files`.
- Verdict: **pass**

### Item 5 — git repo: Enter opens the hit
- Item text: pick a search result with Enter: the file opens in the code viewer
  (the open path still resolves against the project root).
- Approach: TUI interaction.
- Action run: `Enter` on the highlighted result.
- Output (trimmed): info bar became `zeppelin.md — 1 lines | Annotations:
  2026-08-13 20:55:19`, the viewer rendered `1  # zeppelin`, the search box
  cleared back to its placeholder, and `docs/zeppelin.md` was pushed onto
  Recent Files. Resolving `docs/zeppelin.md` against `_project_root` is what
  produced a readable file.
- Verdict: **pass**

### Item 6 — git repo: `R` re-seeds the index end-to-end
- Item text: press `R` to refresh the file tree, then search for a file added
  since launch: it appears in the results (proves the TrackedFilesRefreshed
  path re-seeds the index end-to-end).
- Approach: TUI interaction **with a negative control**, driven through the
  real producer (`R` → `action_reset_file_tree` → `action_reset_tree` →
  `refresh_tracked_files` → `TrackedFilesRefreshed` → `_seed_search_index`).
- Action run: create + `git add src/gamma_newfile.py` in the live fixture;
  search `gamma` **before** `R`; `Escape`, `Tab` off the input, `R`; search
  `gamma` again.
- Output (trimmed): before `R` — `gamma` typed, result list stayed hidden (the
  boot-time index has no such path). After `R` — `src/gamma_newfile.py`
  listed. The file also appeared in the Project Files tree. The negative
  control is what makes this a real transition rather than a list that
  happened to contain the file.
- Verdict: **pass**

### Item 7 — git repo: the full Tab cycle is unchanged
- Item text: Tab from the recent-files row: focus goes recent_files →
  file_tree → search box → code viewer, i.e. the full cycle is unchanged by
  this task.
- Approach: TUI interaction; one decisive probe per stop, so no stop is
  inferred from another.
- Action run / output per stop:
  - **Stop 0 — recent_files.** `capture-pane -e` row 3: `RecentFilesList`
    border-left in `$accent` (`38;2;254;166;43`) and the `src/alpha.py` row
    carrying `48;2;74;57;32` = `$accent 20%` over the surface — i.e.
    `RecentFileItem:focus`.
  - **Stop 1 — file_tree.** `Down` moved the tree cursor highlight
    (`48;2;1;120;212`) from `src/beta.py` to `src/gamma_newfile.py`, while the
    info bar gained **no** `Line N/M` — so the code viewer did not receive the
    key.
  - **Stop 2 — search box.** Typing `beta` filtered to `src/beta.py`.
  - **Stop 3 — code viewer.** Two `Down`s set the info bar to
    `alpha.py — 8 lines | Line 3/8` — `CodeViewer.action_cursor_down` ran.
  - **Stop 4 — back to recent_files.** Row 3 again shows the accent border-left
    and the `$accent 20%` row background; the cycle closed.
- Verdict: **pass**

## Result

`TOTAL:7 PENDING:0 PASS:7 FAIL:0 SKIP:0 DEFER:0` — no follow-up bug tasks
created, no carry-over needed.

## Notes

- `Annotations: error ('NoneType' object is not iterable)` shows in the git
  fixture's info bar. It is a property of the throwaway fixture (a bare repo
  with no `.aitask-explain` cache and no task history to annotate against),
  not of the code under verification, and it is outside this checklist's
  scope. Not recorded as an upstream defect on that basis; worth a look if it
  ever reproduces in a real project.

## Cleanup

- `fixtures/nogit`, `fixtures/withgit` — removed (`drive.py teardown`).
- tmux server on socket `ait_t1511_verify` — killed (`drive.py teardown`).
- No scratch state left inside the repository.
