---
Task: t832_8_ait_board_cross_repo_support.md
Parent Task: aitasks/t832_brainstorm_cross_repo_skills_retrieval_xdeps_parallel_planni.md
Sibling Tasks: aitasks/t832/t832_*_*.md
Archived Sibling Plans: aiplans/archived/p832/p832_*_*.md (none yet)
Worktree: aiwork/t832_8_ait_board_cross_repo_support
Branch: aitask/t832_8_ait_board_cross_repo_support
Base branch: main
---

# Plan: ait board cross-repo support

See parent plan §t832_8. Depends on t832_3 (parser) and t832_4 (blocking
signal).

## Goal

Three bundled concerns (kept together — TUI changes are coupled):
1. Card display of `xdeps:` / `xdeprepo:`.
2. "Blocked by cross-repo" indicator with live cross-repo status.
3. Cross-repo notation parser + read-only navigation popup.

## Implementation steps

### 1. Notation parser (shared lib)

New file: `.aitask-scripts/lib/cross_repo_notation.py`.

```python
import re
_NOTATION_RE = re.compile(r"([a-z0-9_-]+)#t?(\d+(?:_\d+)?)")

def parse(text: str) -> list[tuple[str, str]]:
    """Find all <name>#<id> or <name>#t<id> references in text.
    Returns list of (project_name, task_id) tuples."""
    return [(m.group(1), m.group(2)) for m in _NOTATION_RE.finditer(text)]
```

Coordinate with t832_2 — if that task already shipped a bash parser for
the same regex, fine; they're parallel implementations for different
runtimes.

### 2. Card display: xdeps / xdeprepo line

- `.aitask-scripts/board/aitask_board.py`: extend task-card rendering
  to inspect `task.xdeps` / `task.xdeprepo` (added to the in-memory
  Task model via `task_yaml.py` after t832_3 lands).
- Render line in the form `xdeps: aitasks_mobile#42, aitasks_mobile#16_2`.
- Visual distinction: prefix with a glyph (e.g., `↗`) or use a distinct
  color/style. Match patterns from the existing depends line; the goal
  is "at-a-glance these are not local deps".

### 3. Blocked-status surfacing

- After t832_4 lands, `aitask_ls.sh`'s `blocking_info` may contain
  `<repo>#<id>` entries (possibly with ` (UNREACHABLE)` suffix).
- In the board widget: when rendering blocked status, parse
  `blocking_info` for `#` substrings; if present, render the "blocked by
  cross-repo" indicator (distinct color/glyph from "blocked by local").
- Optionally fetch live cross-repo status via subprocess call to
  `aitask_query_files.sh task-status --project <name> <id>` (from
  t832_1). Show inline (e.g., `aitasks_mobile#42 [Implementing]`).
- Cache the fetched status per render cycle so the call doesn't fire
  per redraw.

### 4. Notation parser + navigation popup

- On task-card open / detail-view: run `cross_repo_notation.parse()`
  on task body + plan body text. Render matched substrings as
  activatable links (Textual `RichLog` or `Markdown` widget with
  custom action handlers).
- New key handler: when the user activates a cross-repo link,
  resolve the project name via `aitask_project_resolve.sh` (subprocess
  call), read the cross-repo task file read-only (NO lock acquisition,
  NO `aitask_pick_own.sh`), and push a modal popup widget displaying
  its content.
- ESC closes the popup; board state is unchanged.
- Stale-link handling: if `aitask_project_resolve.sh` returns
  `STALE:` or `NOT_FOUND:`, the popup displays the error message
  (do NOT crash the board).

## Tests

- `tests/test_cross_repo_notation.sh` — Python unit tests for the parser:
  ```python
  parse("see aitasks#42 and aitasks_mobile#t16_2") == [
      ("aitasks", "42"), ("aitasks_mobile", "16_2")
  ]
  parse("no refs here") == []
  parse("malformed#") == []
  ```
- TUI display verification is by manual run (interactive). Document
  the manual checklist in this plan's "Verification (manual)" section
  below.

## Verification (automated)

- `bash tests/test_cross_repo_notation.sh` passes (or equivalent
  `python -m pytest` invocation if the test is Python).
- `./.aitask-scripts/aitask_skill_verify.sh` passes (no skill changes,
  but board launch via skills should not regress).
- `shellcheck` clean if any new bash wrappers are introduced.

## Verification (manual)

Set up two fake projects with the registry pointing at both.

- [ ] Launch `ait board` in project A. A task with `xdeps: [1]`
      `xdeprepo: b` shows a distinct cross-repo dep line on its card.
- [ ] That same task shows "blocked by cross-repo" indicator (assuming
      B/t1 is not Done).
- [ ] When B/t1's status changes to Done (out-of-band) and the board
      refreshes, the task becomes unblocked.
- [ ] Stale-registry case: edit `~/.config/aitasks/projects.yaml` to point
      B at a non-existent path. Refresh board. Task shows
      `aitasks_mobile#1 (UNREACHABLE)` blocked state without crashing.
- [ ] Restore registry.
- [ ] Open a task whose body contains `aitasks#42`. Activate the link.
      A read-only popup shows the cross-repo task content. ESC closes.
- [ ] Activate a link to a non-registered project. The popup shows the
      error message instead of crashing.

## Coordination with sibling tasks

- **Manual-verification aggregate sibling:** the parent's child-task
  checkpoint should offer a manual-verification sibling scoped to
  `[832_8]` because this is the only TUI-touching child in t832. Accept
  the offer; the manual checklist above seeds the sibling's content.
- **`lib/cross_repo_notation.py`** will likely be reused by future `ait
  monitor` cross-repo support (deferred follow-up). Keep the API tight
  (one `parse(text)` function returning the simplest possible shape).

## Out of scope

- **`ait monitor` cross-repo surfacing** — separate follow-up.
- **Board project-switch** (full re-mount with different `TASK_DIR`) —
  defer; read-only popup is the minimum viable navigation.
- **In-board editing of cross-repo tasks** — scripts (t832_7) handle
  this; the TUI doesn't call them directly until UX is settled.

## Final Implementation Notes

(To be filled by the implementing agent during/after execution.)
