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

- **Actual work done:**
  - New `.aitask-scripts/lib/cross_repo_notation.py` — single `parse(text)`
    using the unanchored canonical regex `([a-z0-9_-]+)#t?(\d+(?:_\d+)?)`;
    returns `(project, id)` tuples with the `t` prefix stripped.
  - `.aitask-scripts/board/aitask_board.py`:
    - Import `parse as parse_cross_repo_notation`.
    - `TaskManager.__init__`: new `xdep_status_cache: dict[(repo,id)] -> str`.
    - `TaskManager.get_xdep_status(repo, id)`: subprocess
      `aitask_query_files.sh --project <repo> task-status <id>`, parses
      `STATUS:<value>`; returns `""`/`NOT_FOUND` → UNREACHABLE; cached.
    - `refresh_board()` clears `xdep_status_cache` each full refresh cycle.
    - `TaskCard.compose()`: renders the `↗ repo#id [status]` cross-repo dep
      line (distinct from the local `🔗` line) and a `🌐 blocked
      (cross-repo)` status chip when any xdep is unmet, with live status /
      `(UNREACHABLE)` inline.
    - New `#` board binding → `action_open_cross_repo` (footer-gated via
      `check_action` to tasks that actually have cross-repo refs).
      `_gather_cross_repo_refs` merges xdeps frontmatter + body notation;
      one ref opens directly, several show `CrossRepoRefPickerScreen`.
    - New module helper `_resolve_cross_repo_task(repo, id)` →
      `(title, content, is_error)`: resolves via `aitask_project_resolve.sh`
      (`RESOLVED:`/`STALE:`/`NOT_FOUND:`), reads the task file **read-only**
      (no lock, no pick flow), graceful error messages on every failure.
    - New `CrossRepoTaskScreen` (read-only `VerticalScroll + Markdown`
      popup, self-contained `DEFAULT_CSS`, ESC/`c` to close) and
      `CrossRepoRefItem` / `CrossRepoRefPickerScreen`.
  - New `tests/test_cross_repo_notation.py` — 9 parser unit tests (basic,
    `t`-prefix strip, child `N_M`, empty/None, dash/underscore project,
    multi-in-prose, uppercase-leading-char partial match).
- **Deviations from plan:**
  - **Blocked status computed in Python, not parsed from `aitask_ls.sh`.**
    Verified during planning: the board builds `unresolved_deps` itself in
    `TaskCard.compose()`. Implemented cross-repo blocking by extending that
    Python loop (per-xdep `get_xdep_status` probe), not by pattern-matching
    `aitask_ls.sh`'s `blocking_info`. `<repo>#<id>` remains the mirrored
    display format.
  - **Navigation is a focused-card `#` binding + picker, not inline
    clickable Markdown links.** The plan floated "render matched substrings
    as activatable links". Activating arbitrary inline Markdown spans is
    fragile in Textual; a board-level binding that gathers refs (xdeps +
    body notation) and offers a picker mirrors the existing dependency-
    navigation UX (`DependencyPickerScreen`) and is far more robust. Body
    notation is still parsed via `cross_repo_notation.parse()`.
  - **`task-status` flag order** is `--project <repo> task-status <id>`
    (flag precedes subcommand — the cross-repo re-exec strips it first).
  - **Parser test is Python** (`tests/test_cross_repo_notation.py`), not the
    `tests/test_cross_repo_notation.sh` the draft named — new `lib/*.py`
    modules are unit-tested in Python.
- **Issues encountered:**
  - The board could not be import-smoke-tested directly because the local
    (gitignored) `aitasks/metadata/userconfig.yaml` is malformed and the
    keybinding registry's `load_user_overrides()` lets the resulting
    `yaml.ParserError` propagate, crashing every TUI import. Worked around
    by temporarily moving the file aside (loader falls back to `{}` when
    absent) for the smoke test and the full-suite run, restoring it after.
    See "Upstream defects identified".
- **Key decisions:**
  - **Lazy-populate + clear-on-refresh cache** for cross-repo status rather
    than a threaded pre-scan: keeps the change small, satisfies "no
    per-redraw subprocess", and matches the board's existing
    `lock_map`/`modified_files` refresh model. Probe `timeout=10`, all
    failures squashed to UNREACHABLE — never crashes the board.
  - **Read-only popup reads the task file directly** under the resolved
    root (active tasks only) instead of routing through a pick/query that
    might lock; guarantees the "no lock acquisition" requirement.
  - **`#` binding key** — the cross-repo notation separator; punctuation
    bindings are proven to work here (`shortcuts_mixin` binds `?`).
- **Upstream defects identified:**
  - `.aitask-scripts/lib/keybinding_registry.py:50-52 — load_user_overrides() calls yaml.safe_load without catching yaml.YAMLError; a malformed (gitignored) aitasks/metadata/userconfig.yaml therefore propagates a ParserError that crashes every board/TUI at import. Should fall back to {} (and warn) on parse failure, matching the existing missing-file fallback.`
- **Notes for sibling tasks:**
  - `cross_repo_notation.parse(text)` is the shared task-ID notation parser
    (distinct from `aitask_explain_context.sh`'s bash file-path classifier).
    Future `ait monitor` cross-repo surfacing should reuse it.
  - `TaskManager.get_xdep_status(repo, id)` returns the live cross-repo
    status (`""`/`NOT_FOUND` ⇒ UNREACHABLE), cached per refresh — reuse it
    rather than re-shelling `task-status`.
  - Cross-repo TUI behavior (card line, blocked chip, popup, UNREACHABLE
    fallback) is interactive-only; the manual checklist above seeds the
    t832_9 manual-verification sibling.
