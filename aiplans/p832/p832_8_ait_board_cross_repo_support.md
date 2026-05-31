---
Task: t832_8_ait_board_cross_repo_support.md
Parent Task: aitasks/t832_brainstorm_cross_repo_skills_retrieval_xdeps_parallel_planni.md
Sibling Tasks: aitasks/t832/t832_*_*.md
Archived Sibling Plans: aiplans/archived/p832/p832_*_*.md
Worktree: aiwork/t832_8_ait_board_cross_repo_support
Branch: aitask/t832_8_ait_board_cross_repo_support
Base branch: main
plan_verified:
  - claudecode/opus4_8 @ 2026-05-31 08:19
---

# Plan: ait board cross-repo support

See parent plan §t832_8. Depends on t832_3 (parser), t832_4 (blocking
signal), and t832_1 (cross-repo `task-status` probe) — **all three have
landed and are archived.**

## Context

The `ait board` Textual TUI (`.aitask-scripts/board/aitask_board.py`) is
currently blind to cross-repo dependencies. The framework now supports
`xdeps:` (list of cross-repo task IDs) + `xdeprepo:` (scalar project name)
frontmatter (t832_3), blocking on unmet cross-repo deps in `aitask_ls.sh`
(t832_4), and a `task-status --project` probe (t832_1). The board should
surface these so cross-repo work is navigable from the kanban view. Three
bundled concerns (kept together — TUI changes are coupled):

1. Card display of `xdeps:` / `xdeprepo:`.
2. "Blocked by cross-repo" indicator with live cross-repo status.
3. Cross-repo `<project>#<id>` notation parser + read-only navigation popup.

## Plan verification (2026-05-30)

Verified against current `main` (deps t832_1/_3/_4 landed). Corrections
applied to the original draft:

- **Blocked status is computed in Python, not parsed from `aitask_ls.sh`.**
  The board builds `unresolved_deps` itself in `TaskCard.compose()`
  (`aitask_board.py:751-782`) by looping `meta.get('depends')` and checking
  each dep's `status != 'Done'`. The board does **not** consume
  `aitask_ls.sh`'s `blocking_info`. → Step 3 below extends the *Python*
  blocking loop rather than pattern-matching shell output.
- **`task_yaml.py` does NOT normalize `xdeps`.** `parse_frontmatter`
  (`task_yaml.py:85-88`) normalizes only `depends`/`children_to_implement`/
  `folded_tasks`. `xdeps` passes through raw (YAML may yield `1`, `'2_3'`),
  so the card layer must format IDs itself (strip any `t`/quotes for the
  canonical `<repo>#<id>` display).
- **`--project` precedes the subcommand:** `aitask_query_files.sh --project
  <name> task-status <id>` (cross-repo re-exec strips `--project <name>`
  before dispatch — `lib/cross_repo_reexec.sh:44-71`). Emits
  `STATUS:<value>` (one of Ready/Editing/Implementing/Postponed/Done/Folded/
  NOT_FOUND).
- **Parser test is Python, not bash.** New `.aitask-scripts/lib/*.py` modules
  are unit-tested via `tests/test_*.py` (e.g. `test_config_utils.py`,
  `test_launch_modes.py`) run by `tests/run_all_python_tests.sh`. → Test file
  is `tests/test_cross_repo_notation.py`, not `.sh`.
- **No real parser overlap with t832_2.** t832_2 shipped a bash *file-path*
  classifier (`aitask_explain_context.sh:80-87`, regex `^([a-z0-9_-]+)#(.+)$`)
  for `<repo>#<path>` pairs — not task-ID notation. The new Python task-ID
  parser is genuinely needed; no duplication.
- Confirmed unchanged: `aitask_project_resolve.sh` emits `RESOLVED:<path>` /
  `NOT_FOUND:<name>` / `STALE:<name>:<path>`; `aitask_ls.sh` blocking display
  uses `<repo>#<id>` (t-prefix stripped, ` (UNREACHABLE)` suffix) as the
  canonical format to mirror.

## Implementation steps

### 1. Notation parser (shared lib)

New file: `.aitask-scripts/lib/cross_repo_notation.py`. Minimal, dependency-
free, one public function:

```python
import re

# Canonical regex from aidocs/cross_repo_references.md (unanchored for
# in-text scanning; the `t` prefix is tolerated).
_NOTATION_RE = re.compile(r"([a-z0-9_-]+)#t?(\d+(?:_\d+)?)")

def parse(text):
    """Find all <project>#<id> / <project>#t<id> references in text.
    Returns list of (project_name, task_id) tuples; task_id has no `t`
    prefix (canonical form). Empty list when none match."""
    return [(m.group(1), m.group(2)) for m in _NOTATION_RE.finditer(text)]
```

Keep the API to a single `parse(text)` so future consumers (`ait monitor`
cross-repo surfacing, deferred) reuse it without reinvention.

### 2. Card display: xdeps / xdeprepo line

`aitask_board.py`, `TaskCard.compose()` (after the `depends` block at
`:751-782`):

- Read `xdeps = meta.get('xdeps', [])` and `xdeprepo = meta.get('xdeprepo')`.
- Format each id to canonical `<repo>#<id>` (strip leading `t`, coerce to
  str — values are raw per the verification note). Build e.g.
  `↗ aitasks_mobile#42, aitasks_mobile#16_2`.
- Render as a distinct `Label(..., classes="task-info")` with a glyph (`↗`)
  that visually separates it from the local-deps `🔗` line (`:782`). Only
  emit when both `xdeps` and `xdeprepo` are present (both-or-neither
  invariant from t832_3).

### 3. Blocked-status surfacing (extend the Python loop)

Extend the existing Python blocking computation in `TaskCard.compose()`
(`:751-782`) — do **not** parse `aitask_ls.sh` output:

- After the local `depends` loop builds `unresolved_deps`, add a cross-repo
  loop over `xdeps` (when `xdeprepo` is set). For each id, shell out:
  ```
  ./.aitask-scripts/aitask_query_files.sh --project <xdeprepo> task-status <id>
  ```
  Parse `STATUS:<value>`. `Done` → satisfied; any other value → blocked;
  empty stdout / `STATUS:NOT_FOUND` → blocked + UNREACHABLE.
- Collect unmet cross-repo deps as canonical `<repo>#<id>` strings (with
  ` (UNREACHABLE)` suffix when applicable), mirroring `aitask_ls.sh`'s
  display format.
- Render a **distinct** "blocked by cross-repo" indicator (separate glyph/
  color from the local `🚫 blocked` at `:774`), e.g. `🌐 blocked` plus a
  `↗ aitasks_mobile#42 [Implementing]` detail line showing the live status.
- **Caching:** the `task-status` subprocess must not fire per redraw. Cache
  results on the `TaskManager` (alongside `lock_map` / `modified_files`,
  `aitask_board.py:393-414`) keyed by `(repo, id)`, populated once per
  refresh cycle. Follow the existing subprocess pattern (`subprocess.run`
  with `timeout`, try/except `TimeoutExpired`/`FileNotFoundError`); use the
  `@work(thread=True)` + `call_from_thread` pattern (`:2547-2564`) if the
  probe is done off the render path. Graceful fallback to UNREACHABLE on any
  failure — never crash the board.

### 4. Notation parser + read-only navigation popup

- **Detect links:** when a task detail view is opened (`TaskDetailScreen`,
  `aitask_board.py:2101+`, which already renders body via `VerticalScroll +
  Markdown` at `:2300-2301`), run `cross_repo_notation.parse()` on the task
  body to find `<repo>#<id>` references.
- **New key handler:** add a `Binding` (footer-visible per
  `aidocs/tui_conventions.md`) + `action_*` method that, when a cross-repo
  reference is active, resolves the project and opens the popup. Follow the
  binding/action pattern at `:3325-3370` / `:4024-4128`.
- **Resolve + read read-only:** subprocess `aitask_project_resolve.sh
  <repo>`; on `RESOLVED:<root>` read the cross-repo task file **read-only**
  (NO lock, NO `aitask_pick_own.sh`); on `STALE:`/`NOT_FOUND:` show the
  error in the popup instead of crashing.
- **Popup widget:** new `ModalScreen` displaying the cross-repo task content
  via the read-only `VerticalScroll + Markdown` pattern (mirror
  `TaskDetailScreen` read-only / `lib/section_viewer.py`). It MUST carry its
  own `DEFAULT_CSS` (lib/board modals don't inherit App CSS — see
  `lib/shortcut_editor_modal.py`, `lib/stale_entry_modal.py`). `Binding(
  "escape", "close", ...)` → `dismiss()`; board state unchanged on close.

## Tests

- **`tests/test_cross_repo_notation.py`** — Python unittest (pattern of
  `tests/test_config_utils.py`: `sys.path.insert(0, …/.aitask-scripts/lib)`
  then `from cross_repo_notation import parse`). Cases:
  ```python
  parse("see aitasks#42 and aitasks_mobile#t16_2") == [
      ("aitasks", "42"), ("aitasks_mobile", "16_2")]
  parse("no refs here") == []
  parse("malformed#") == []
  ```
  Run via `bash tests/run_all_python_tests.sh` (pytest or unittest discovery).
- TUI display/blocking/popup behavior is verified by manual run (interactive)
  — see "Verification (manual)".

## Verification (automated)

- `bash tests/run_all_python_tests.sh` passes (includes the new parser test).
- `./.aitask-scripts/aitask_skill_verify.sh` passes (no skill changes, but
  board launch via skills must not regress).
- `python3 -c "import ast; ast.parse(open('.aitask-scripts/board/aitask_board.py').read())"`
  (or board import smoke-test) clean; `shellcheck` clean if any new bash
  wrapper is introduced (none expected — board calls existing helpers).

## Verification (manual)

Set up two fake registered projects (registry points at both).

- [ ] Launch `ait board` in project A. A task with `xdeps: [1]`
      `xdeprepo: b` shows a distinct `↗` cross-repo dep line on its card.
- [ ] That task shows the distinct "blocked by cross-repo" indicator
      (assuming B/t1 is not Done), with B/t1's live status inline.
- [ ] When B/t1 → Done (out-of-band) and the board refreshes, the task
      becomes unblocked.
- [ ] Stale-registry case: point B at a non-existent path; refresh. Task
      shows `b#1 (UNREACHABLE)` blocked state without crashing. Restore.
- [ ] Open a task whose body contains `aitasks#42`. Activate the reference.
      A read-only popup shows the cross-repo task content. ESC closes; board
      unchanged.
- [ ] Activate a reference to a non-registered project. The popup shows the
      error message instead of crashing.

## Coordination with sibling tasks

- **Manual-verification aggregate sibling (t832_9):** the parent already
  carries `t832_9_manual_verification_cross_repo`; this task's manual
  checklist above seeds/overlaps that sibling. No new sibling created here.
- **`lib/cross_repo_notation.py`** will likely be reused by future `ait
  monitor` cross-repo support (deferred). Keep the API to one `parse(text)`.

## Out of scope

- **`ait monitor` cross-repo surfacing** — separate follow-up.
- **Board project-switch** (full re-mount with a different `TASK_DIR`) —
  defer; the read-only popup is the minimum viable navigation.
- **In-board editing of cross-repo tasks** — scripts (`aitask_update.sh
  --project`, t832_7) own this; the TUI does not call them until UX settles.

## Final Implementation Notes

(To be filled by the implementing agent during/after execution.)
