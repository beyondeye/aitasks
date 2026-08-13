---
Task: t1500_fix_codebrowser_non_git_focus_deadend.md
Worktree: (current branch — profile 'fast')
Branch: (current branch)
Base branch: main
Output branch: main
---

# t1500 — Fix the codebrowser non-git focus dead-end (+ board live-test flake)

## Context

t1495 removed the codebrowser's accidental startup auto-focus. Its Step 8b
review surfaced three pre-existing defects, all recorded in the task file. Two
live in `compose()`'s `RuntimeError` arm — the branch taken when `ait
codebrowser` is launched **outside a git repo**, where `get_project_root()`
raises and the sidebar becomes a bare `Container` holding one non-focusable
`Static`:

1. **Focus dead-end.** `action_toggle_focus` finds neither `#recent_files` nor
   `#file_tree`, falls through to `_focus_recent_or_tree(None, None,
   code_viewer)`, and re-focuses the viewer it started from
   (`codebrowser_app.py:1332-1345`). `#file_search_input` is mounted but
   unreachable by keyboard.
2. **Inert search box.** The box it strands could not work anyway: its file
   list is seeded from `ProjectFileTree._tracked_files` inside a `try` that
   queries `#file_tree` first (`:720-725`, same shape at `:1085-1090`), and
   opening a hit resolves against `self._project_root` — neither exists here.

The third is unrelated to the codebrowser and was observed while running the
suite for t1495:

3. **Board live-test flake.** `tests/test_board_startup_focus_live.py`'s
   `_launch_board` returns one 0.25s poll after the *filter row* (`Task
   filter`) appears — but that row is yielded by `BoardScreen.compose`, while
   the columns are mounted afterwards by `refresh_board`. **Measured live in a
   tmux pane on an idle box: the filter row lands at t=1.43s and the columns at
   t=1.53s.** Under load — the serial phase runs after a ~200s four-worker
   parallel phase — that gap outgrows the single extra poll, the capture is
   taken mid-mount, and the `CARD_TITLE` assertion fails (~2 of 4 full-suite
   runs; 3/3 alone).

**Intended outcome:** the non-git branch mounts nothing the keyboard cannot
reach, the search-index seeding is a single named helper that fails narrowly
and is pinned on both its callers, and the board live pin waits on markers that
actually prove the board finished painting.

## Findings that shaped the plan

Both established by probing the real classes, not by reading:

- **The git branch's boot seeding *does* work.** Despite the
  `_claim_startup_focus` comment about the sidebar's children mounting
  asynchronously, a headless probe shows `#file_tree` is queryable inside
  `on_mount` and `FileSearchWidget._all_files` holds 2 files on cycle 0. So
  defect 2 is confined to the non-git branch — this is not a silent
  fuzzy-search outage in normal use. No test covers this today.
- **`Backlog (0)` renders contiguously** in a 200×50 pane
  (`│ ▼           Backlog (0)            ✎ │`), so it is a usable wait marker.

## Approach (user-confirmed)

**Do not mount `FileSearchWidget` when there is no project root.** This kills
defects 1 and 2 structurally rather than patching each: with the box gone, the
non-git Tab cycle is `code_viewer → code_viewer`, which is *correct* (the
viewer is the sole focus target), and there is no widget left to seed. The
rejected alternative — keeping the box and giving the cycle a `search_input`
fallback — makes a permanently-empty box reachable and leaves the inert half of
the defect in place.

`_focus_recent_or_tree` and `action_toggle_focus` are therefore **not
modified**.

## Implementation

### Pre-phase (risk mitigations)

1. `[pin_search_index_seeding]` Add **both** new tests from step 3 —
   `test_the_git_branch_seeds_the_search_index_at_boot` and
   `test_a_tracked_file_refresh_reseeds_the_search_index` — to
   `tests/test_codebrowser_startup_focus.py` and run them against
   **unmodified** `codebrowser_app.py`. Both must pass before any source edit:
   that is what makes step 2 a refactor of covered code, and it covers each of
   `_seed_search_index`'s two callers, so a broken event delegation cannot slip
   through. If either fails here, the premise that the current seeding works is
   wrong and the plan needs re-verification before continuing.

### 1. `.aitask-scripts/codebrowser/codebrowser_app.py` — gate the search box

In `compose()` (`:744-759`), track whether the project arm succeeded and gate
the `yield`:

```python
def compose(self) -> ComposeResult:
    yield Header(show_clock=True)
    has_project = False
    with Horizontal():
        try:
            self._project_root = get_project_root()
            self.explain_manager = ExplainManager(self._project_root)
            has_project = True
            yield LeftSidebar(self._project_root, id="left_sidebar")
        except RuntimeError:
            self._project_root = None
            with Container(id="left_sidebar"):
                yield Static("Error: not inside a git repository")
        with Container(id="code_pane"):
            # Fuzzy search is fed from the tree's git-tracked file list and
            # resolves a hit against `_project_root`; without a repository it
            # has neither, so mounting it would only add an unreachable,
            # permanently-empty focus target (t1500).
            if has_project:
                yield FileSearchWidget(id="file_search")
            yield Static("No file selected", id="file_info_bar")
            yield CodeViewer(id="code_viewer")
        yield DetailPane(id="detail_pane", classes="hidden")
    yield ContextualFooter()
```

`has_project` is a local flag rather than an `is not None` test on
`_project_root`, because `ExplainManager(...)` can raise *after* the field is
assigned; the explicit `self._project_root = None` in the `except` arm keeps
the field consistent with the branch that was actually composed.

### 2. Same file — one named seeding helper

Replace the duplicated blocks at `:720-725` (`on_mount`) and `:1085-1090`
(`on_tracked_files_refreshed`) with a single helper both call:

```python
def _seed_search_index(self) -> None:
    """Feed the fuzzy-search box the tree's git-tracked file list.

    Both widgets exist only in the project branch of `compose()`, so a missing
    one is a normal outcome here, not an error — but only the *lookup* may go
    missing. `set_files` runs outside the guard so a real failure surfaces
    instead of being swallowed alongside it (t1500).
    """
    try:
        tree = self.query_one("#file_tree", ProjectFileTree)
        search = self.query_one("#file_search", FileSearchWidget)
    except NoMatches:
        return
    search.set_files(sorted(tree._tracked_files))
```

Add `from textual.css.query import NoMatches` to the textual imports
(`:47-53`). `on_mount` keeps its call in the same position (after the
`set_interval`); `on_tracked_files_refreshed` becomes a one-line delegation.

### 3. `tests/test_codebrowser_startup_focus.py` — update the pins t1495 left

The module deliberately pinned the status quo; the repair must update it
deliberately.

- `test_the_non_git_branch_mounts_no_sidebar_focus_target` — flip
  `len(app.query("#file_search_input"))` from `1` to `0` and rewrite the
  message: the box used to be the first focusable widget here, and is now not
  mounted at all.
- `test_tab_is_a_self_loop_without_a_sidebar` — keep the name (the cycle *is*
  still a self-loop) but rewrite the docstring: it is now correct by
  construction rather than a recorded dead-end. Replace the
  `query_one("#file_search_input")` line (which would now raise `NoMatches`)
  with an assertion that nothing else is mounted to reach.
- `test_the_search_input_never_holds_focus_during_boot` — behaviour unchanged,
  but note in the docstring that the non-git leg is now vacuous by
  construction and the git leg carries the contract.
- **Module docstring** — the lines describing the Input as the non-git
  branch's first focusable widget are t1495 history; mark them as the
  *pre-t1500* shape so the file does not read as describing current source.
- **Two new tests — one per caller of `_seed_search_index`.** The helper serves
  *both* the boot path and the `TrackedFilesRefreshed` handler, so one test
  covering boot would let a mistaken one-line event delegation — or a refresh
  that leaves `_all_files` stale — pass every other check in this plan. Both
  paths get their own pin:

  - `test_the_git_branch_seeds_the_search_index_at_boot` — boot the git fixture
    and assert `app.query_one("#file_search", FileSearchWidget)._all_files ==
    ["src/alpha.py", "src/beta.py"]`. The exact list, not "non-empty", so a
    wrong source can still fail it.
  - `test_a_tracked_file_refresh_reseeds_the_search_index` — driven through the
    **real producer**, not a hand-posted message: `git add` a new `src/gamma.py`
    into the tree, call
    `app.query_one("#file_tree", ProjectFileTree).refresh_tracked_files()`
    (which re-runs `git ls-files` and posts the real `TrackedFilesRefreshed`),
    pause, and assert `_all_files == ["src/alpha.py", "src/beta.py",
    "src/gamma.py"]`. Verified against current source: the boot list is exactly
    the first two, and the third appears after a single `pilot.pause()`, so the
    assertion discriminates rather than passing vacuously. `git ls-files`
    reports staged paths, so no commit is needed.

    **This test must build its own fixture tree** (`_build_tree(…,
    want_git=True)` into a per-test `TemporaryDirectory` with `addCleanup`) —
    it mutates the repository, and `cls.git_tree` is class-scoped and shared
    with every other test in the module.

### 4. `tests/test_board_startup_focus_live.py` — wait for a full paint

Readiness must be **both** markers — the cards *and* the last column. The
column header alone would prove `refresh_board` reached the last column, but
not that the `TaskCard` children painted; under a slow mount the header could
satisfy the wait while `CARD_TITLE` is still absent one 250 ms beat later,
which is the exact failure being fixed.

Add two module constants next to `CARD_TITLE`:

```python
_LAST_COLUMN = _COLUMNS[-1]
#: The last configured column's header. Paired with `CARD_TITLE` as the
#: readiness condition: `CARD_TITLE` proves cards painted, this proves the
#: board is *complete* rather than half-mounted (columns mount in
#: `column_order`, so the last one's header is the tail of that sequence).
#: Derived from the fixture so a backlog task added to `_TASKS` cannot silently
#: desync the count.
COLUMNS_MOUNTED_MARKER = (
    f"{_LAST_COLUMN['title']} "
    f"({sum(1 for _id, col, _idx, _slug in _TASKS if col == _LAST_COLUMN['id'])})"
)
#: Already asserted on below; named here so the readiness loop can recognise a
#: definitive negative instead of spinning to the deadline.
FILTERED_MARKER = "(hidden by filter)"
```

Rewrite `_launch_board`'s loop to return only when
`CARD_TITLE in capture and COLUMNS_MOUNTED_MARKER in capture`, keeping the
existing extra `POLL_INTERVAL_S` beat and final re-capture. Two further
requirements:

- **Break early on a definitive negative.** If the columns are mounted *and*
  `FILTERED_MARKER` is on screen, the cards are filtered away rather than
  slow — stop immediately instead of burning the full 45 s.
- **Make the timeout discriminate.** Report each marker separately —
  `filter row: <bool>, columns mounted: <bool>, cards drawn: <bool>` — plus the
  capture. This is what preserves the diagnostic the old `assertIn(CARD_TITLE,
  …)` used to give: a board that never paints its cards still FAILS, and the
  message now says whether it never booted, never mounted, or mounted without
  cards.

Keep the body's `assertIn(CARD_TITLE, …)` / `(empty)` / `(hidden by filter)`
assertions. They are not redundant: `_launch_board` returns a **re-capture**
taken after the settling beat, so they still catch a board that repainted
(e.g. filtered itself) between satisfying the wait and being read.

Why `"Task filter"` is dropped as the trigger: it is yielded by
`BoardScreen.compose` and paints ~100 ms before the first column exists
(measured live — filter row 1.43 s, columns 1.53 s; the gap widens under load),
so it was never evidence of a rendered board.

### 5. `tests/test_codebrowser_startup_focus_live.py` — re-anchor one assertion

`test_bare_q_quits_a_codebrowser_launched_outside_a_git_repo` ends with
`assertNotIn(f"{SEARCH_PLACEHOLDER}\n", final, ...)` — with the box gone from
this branch that assertion can no longer fail, i.e. it silently stops checking
that the app left the screen. Re-anchor it on `BOOT_MARKER` ("not inside a git
repository"), which is what this branch actually renders, and update
`SEARCH_PLACEHOLDER`'s comment plus the module docstring's account of the
pre-fix focus target. `_search_region` already falls back to the `BOOT_MARKER`
anchor, so its diagnostics keep working.

### 6. `aidocs/framework/tui_conventions.md` — refresh the audit row

The t1495 audit table (`:178`) records `codebrowser (non-git) | Input#file_search_input`.
Keep the historical "picked at compose" reading but append that t1500 removed
the widget from this branch, so the only focusable target left is the code
viewer.

### Post-phase (risk mitigations)

1. `[full_suite_flake_rerun]` Run `bash tests/run_all_python_tests.sh` in full,
   **twice**, and read only the last line of each
   (`PYTHON SUITE: PASSED|FAILED (runner=…, exit=N)`). The standalone module
   passes 3/3 even with the defect present; only the whole-suite shape — the
   serial carve-out following the ~200s four-worker parallel phase — reproduces
   the flake. Two clean full runs is the acceptance signal for step 4.

## Verification

1. `python3 -m pytest tests/test_codebrowser_startup_focus.py -v` — all pins,
   including the two new seeding tests.
2. **Negative controls, one mutation each, each naming the test it must fail:**
   - make `_seed_search_index` return before `set_files` →
     `test_the_git_branch_seeds_the_search_index_at_boot` must fail;
   - make `on_tracked_files_refreshed` a bare `pass` (delegation dropped) →
     `test_a_tracked_file_refresh_reseeds_the_search_index` must fail, and the
     boot test must still **pass** (that asymmetry is what proves the two pins
     cover different callers).

   Revert each mutation before the next.
3. `python3 -m pytest tests/test_codebrowser_startup_focus_live.py -v` — the
   live non-git quit pin under a real pty.
4. `python3 -m pytest tests/test_board_startup_focus_live.py -v` — the board
   pin, standalone. Also confirm the derived `COLUMNS_MOUNTED_MARKER` evaluates
   to the string the pane really renders (`Backlog (0)`, observed contiguous in
   a 200×50 capture) — a marker that never appears would turn every run into a
   45 s timeout.
5. Manual, in a scratch non-git directory: `ait codebrowser` renders no search
   box, `Tab` keeps focus on the code viewer, and a bare `q` quits.
6. `bash tests/run_all_python_tests.sh` — read only the last line
   (`PYTHON SUITE: …`); use `set -o pipefail` if piping.

## Risk

### Code-health risk: low

- Narrowing the boot-path guard from `except Exception` to `except NoMatches`
  means a query failure of any *other* kind would now propagate out of
  `App.on_mount` and take the TUI down at boot instead of being swallowed.
  Bounded: the only statements left inside the guard are the two `query_one`
  calls, and `_tracked_files` is populated in `ProjectFileTree.__init__`, so
  the realistic failure set is exactly `NoMatches`. · severity: low ·
  → mitigation: none needed
- The `_seed_search_index` extraction refactors a path with **no test coverage
  at all** today, and it has **two** callers — boot and the
  `TrackedFilesRefreshed` handler. A mistaken one-line delegation in the
  handler, or a refresh that leaves `_all_files` stale, would pass every other
  check in this plan. · severity: medium ·
  → mitigation: inline pre-phase pin_search_index_seeding
- Removing the search box makes the non-git leg of
  `test_the_search_input_never_holds_focus_during_boot` vacuous, and would
  likewise hollow out the live test's post-quit assertion if it were left
  anchored on the placeholder. · severity: low · → mitigation: none needed
  (steps 3 and 5 re-anchor both assertions)

### Goal-achievement risk: low

- The board flake reproduces only ~2 of 4 *full-suite* runs, where the serial
  phase follows a ~200s four-worker parallel phase. A green standalone run of
  the module therefore proves nothing about the fix. · severity: medium ·
  → mitigation: inline post-phase full_suite_flake_rerun
- Residual, accepted: requiring `CARD_TITLE` in the readiness condition means a
  board that genuinely renders no cards now fails at the wait rather than at
  the assertion. The signal is preserved (the timeout is an explicit
  `self.fail` naming which of the three markers was missing, and the
  filtered-away case breaks out early), but the failure arrives up to
  `BOOT_TIMEOUT_S` later than it used to. · severity: low ·
  → mitigation: none needed

### Planned mitigations
- timing: pre-phase | name: pin_search_index_seeding | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — the `_seed_search_index` extraction refactors an untested path with two callers | desc: write and green both the boot-seeding and the tracked-file-refresh tests against unmodified source before extracting the helper
- timing: post-phase | name: full_suite_flake_rerun | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: goal-achievement — a standalone module run cannot show the board flake is gone | desc: verify the board live-pin fix with two full `run_all_python_tests.sh` runs, the only shape that reproduces the flake
