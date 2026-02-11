---
priority: high
effort: low
depends: [t85_1]
issue_type: feature
status: Done
labels: [bash, aitasks]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-02-11 10:00
updated_at: 2026-02-11 12:37
completed_at: 2026-02-11 12:37
---

## Context

This is child task 3 of parent task t85 (Cross-Platform aitask Framework Distribution). The aitask bash scripts have been moved from the project root into `aiscripts/`. Some scripts call other scripts using hardcoded `./aitask_ls.sh` paths, which now break because the scripts are no longer at `./` (the project root). These references must be updated to use `$SCRIPT_DIR` (the directory containing the calling script).

All work is in the `beyondeye/aitasks` repo at `~/Work/aitasks/aiscripts/`.

## What to Do

### Files that need `SCRIPT_DIR` added

These scripts call other scripts but don't define `SCRIPT_DIR`:

**File: `aiscripts/aitask_create.sh`**

Add near the top (after `set -e` or `set -euo pipefail`, before `TASK_DIR="aitasks"`):
```bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
```

**File: `aiscripts/aitask_update.sh`**

Add near the top (same position):
```bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
```

### Cross-reference fixes

**File: `aiscripts/aitask_create.sh`**

1. Around line 214 — change:
   ```bash
   tasks=$(./aitask_ls.sh -v -s all 99 2>/dev/null || echo "")
   ```
   to:
   ```bash
   tasks=$("$SCRIPT_DIR/aitask_ls.sh" -v -s all 99 2>/dev/null || echo "")
   ```

2. Around line 536 — same change:
   ```bash
   tasks=$(./aitask_ls.sh -v -s all 99 2>/dev/null || echo "")
   ```
   to:
   ```bash
   tasks=$("$SCRIPT_DIR/aitask_ls.sh" -v -s all 99 2>/dev/null || echo "")
   ```

3. Around lines 268-269 — change:
   ```bash
   if [[ -x "./aitask_update.sh" ]]; then
       ./aitask_update.sh --batch "$parent_num" --add-child "$child_id" 2>/dev/null || {
   ```
   to:
   ```bash
   if [[ -x "$SCRIPT_DIR/aitask_update.sh" ]]; then
       "$SCRIPT_DIR/aitask_update.sh" --batch "$parent_num" --add-child "$child_id" 2>/dev/null || {
   ```

**File: `aiscripts/aitask_update.sh`**

1. Around line 657 — change:
   ```bash
   tasks=$(./aitask_ls.sh -v -s all 99 2>/dev/null || echo "")
   ```
   to:
   ```bash
   tasks=$("$SCRIPT_DIR/aitask_ls.sh" -v -s all 99 2>/dev/null || echo "")
   ```

2. Around line 726 — same change:
   ```bash
   tasks=$(./aitask_ls.sh -v -s all 99 2>/dev/null || echo "")
   ```
   to:
   ```bash
   tasks=$("$SCRIPT_DIR/aitask_ls.sh" -v -s all 99 2>/dev/null || echo "")
   ```

**File: `aiscripts/aitask_board.sh`**

Change line 35:
```bash
exec $PYTHON "$SCRIPT_DIR/aitask_board/aitask_board.py" "$@"
```
to:
```bash
exec $PYTHON "$SCRIPT_DIR/board/aitask_board.py" "$@"
```

(This fixes the path after the Python TUI code was moved from `aitask_board/` to `aiscripts/board/`.)

### Files that are already correct (NO changes needed)

- **`aitask_import.sh`** — already uses `$SCRIPT_DIR/aitask_create.sh` (lines 325, 567)
- **`aitask_issue_update.sh`** — has `SCRIPT_DIR` defined but doesn't call other scripts
- **`aitask_ls.sh`** — standalone, no cross-script calls
- **`aitask_stats.sh`** — standalone, no cross-script calls
- **`aitask_clear_old.sh`** — standalone, no cross-script calls

### Important: `TASK_DIR` references are fine

All scripts define `TASK_DIR="aitasks"` as a relative path. This works correctly because the `ait` dispatcher (created in t85_2) `cd`s to the project root before calling any script. Do NOT change these.

### Commit

```bash
cd ~/Work/aitasks
git add aiscripts/aitask_create.sh aiscripts/aitask_update.sh aiscripts/aitask_board.sh
git commit -m "Fix cross-references in scripts for aiscripts/ directory layout"
```

## Verification

1. `grep -n 'SCRIPT_DIR' ~/Work/aitasks/aiscripts/aitask_create.sh` shows the new SCRIPT_DIR definition
2. `grep -n '\./aitask_' ~/Work/aitasks/aiscripts/aitask_create.sh` returns NO matches (all `./aitask_` references should be gone)
3. `grep -n '\./aitask_' ~/Work/aitasks/aiscripts/aitask_update.sh` returns NO matches
4. `grep 'board/aitask_board.py' ~/Work/aitasks/aiscripts/aitask_board.sh` shows the corrected path
