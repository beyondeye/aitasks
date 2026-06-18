---
priority: high
effort: low
depends: []
issue_type: bug
status: Ready
labels: [framework, syncer, desync, git]
created_at: 2026-06-18 12:40
updated_at: 2026-06-18 12:40
---

## Symptom

In a repo whose primary branch is `master` (e.g., `aitasks_mobile`), the
desync/syncer TUI status line shows `main: missing_remote` even when the
repo is fully in sync with its remote.

Reproduces by running:

```
python3 .aitask-scripts/lib/desync_state.py snapshot --format text
```

Expected: `main: up to date` (or behind/ahead counts).
Actual: `main: missing remote ref`.

## Root cause

`.aitask-scripts/lib/desync_state.py` hardcodes the primary branch name:

- `snapshot_ref()` at lines 103-107:
  ```python
  if name == "main":
      worktree = root
      worktree_label = "."
      local_ref = "main"
      remote_ref = "origin/main"
  ```
- `snapshot()` default list (line 157): `["main", "aitask-data"]`.
- argparse `--ref` choices (line 215): `["main", "aitask-data"]`.

In a `master`-default repo `origin/main` does not exist, so
`ref_exists(worktree, "origin/main")` returns false at line 139 and the
status falls through to `missing_remote`. The framework already exposes a
`base_branch` execution-profile key (see
`.aitask-scripts/lib/profile_editor.py:52,132`), but `desync_state.py`
ignores it.

## Proposed fix

Keep `"main"` as the **logical/user-facing** ref name (no CLI break) and
resolve the actual branch dynamically inside `snapshot_ref`:

1. Add `detect_primary_branch(worktree: Path) -> str` that tries, in order:
   - `git symbolic-ref --quiet --short refs/remotes/origin/HEAD` (strip
     `origin/` prefix);
   - the execution profile's `base_branch` key, if reachable from this
     scope (optional — symbolic-ref alone covers most cases);
   - candidate probe `main` → `master`;
   - fallback string `"main"`.
2. In `snapshot_ref` for `name == "main"`:
   `local_ref = detect_primary_branch(worktree); remote_ref = f"origin/{local_ref}"`.
3. Optionally update `_format_desync_lines` in
   `.aitask-scripts/lib/tui_switcher.py` so the rendered label reflects
   the actual branch (e.g., `master: up to date`) instead of the logical
   `main`. Keeping the logical label is also acceptable; pick one.
4. Add a test covering a `master`-default repo (e.g., a tmp-git fixture
   where `git symbolic-ref` resolves to `master`).

## Notes

- A local patch implementing step 1 + step 2 has already been applied in
  `aitasks_mobile` (vendored copy) to unblock work. The vendored file is
  byte-identical to the upstream, so the upstream fix supersedes it on
  next framework sync.
- The `aitask-data` ref path is unaffected — it has its own dedicated
  branch name.
