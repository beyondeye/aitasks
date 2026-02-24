---
priority: medium
effort: low
depends: [t228_3]
issue_type: feature
status: Implementing
labels: [aitask_board]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-02-24 09:14
updated_at: 2026-02-24 11:22
---

## Update board TUI to handle AUTOMERGED status

### Context

After t228_3 adds auto-merge support to `ait sync`, the board TUI needs to recognize the new `AUTOMERGED` batch output status and display appropriate notifications. The conflict dialog should only appear for truly unresolvable conflicts.

Part of t228 "Improved Task Merge for ait sync". Depends on t228_3.

### Key Files to Modify

- `aiscripts/board/aitask_board.py` — Update `_run_sync()` method and status handling

### Reference Files for Patterns

- `aiscripts/board/aitask_board.py` lines 2260-2299 — Current `_run_sync()` method
- `aiscripts/board/aitask_board.py` lines 2278-2297 — Current status line parsing
- `aiscripts/board/aitask_board.py` lines 1679-1710 — `SyncConflictScreen` class

### Implementation Plan

#### 1. Handle `AUTOMERGED` Status

In `_run_sync()`, add handling for the new status between the existing `CONFLICT:` and `NO_NETWORK` checks:

```python
elif status_line == "AUTOMERGED":
    if show_notification:
        self.notify("Sync: Auto-merged conflicts", severity="information")
```

This is treated the same as `SYNCED` — reload tasks and refresh board (which already happens at the end of the method).

#### 2. Update Conflict Dialog (Optional Enhancement)

If the sync output includes additional detail lines (e.g., which files were auto-merged vs which remain conflicted), parse and display them in `SyncConflictScreen`:

```python
# Parse additional lines after CONFLICT: for auto-merge details
automerged_files = [l.split(":", 1)[1] for l in output[1:] if l.startswith("AUTOMERGED_FILE:")]
```

This is a minor enhancement — the core functionality works without it since `CONFLICT:` output now only lists truly unresolvable files.

### Verification Steps

1. Run `./ait board`, trigger a sync (press `s`) when there are no conflicts — verify normal behavior
2. Create a conflict scenario where auto-merge resolves everything → board should show "Auto-merged conflicts" notification, no conflict dialog
3. Create a conflict scenario with unresolvable fields → board should show conflict dialog with only the unresolvable files listed
