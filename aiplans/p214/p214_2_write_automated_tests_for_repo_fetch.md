---
Task: t214_2_write_automated_tests_for_repo_fetch.md
Parent Task: aitasks/t214_multi_platform_reviewguide_import_and_setup_dedup.md
Sibling Tasks: aitasks/t214/t214_1_*.md, aitasks/t214/t214_3_*.md, aitasks/t214/t214_4_*.md
Worktree: (none — working on current branch)
Branch: (current)
Base branch: main
---

## Implementation Plan

### Step 1: Create test file structure

Create `tests/test_repo_fetch.sh` following existing test conventions. Look at `tests/test_detect_env.sh` or `tests/test_claim_id.sh` for the assert helpers pattern.

### Step 2: Add test helpers

```bash
#!/usr/bin/env bash
set -euo pipefail

PASS=0; FAIL=0
assert_eq() { ... }
assert_contains() { ... }
```

### Step 3: Source the library

```bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$SCRIPT_DIR/aiscripts/lib/repo_fetch.sh"
```

### Step 4: Implement offline tests (URL parsing/detection)

Tests 1-11 from the task description. These don't need network access:
- Platform detection for each URL type
- URL parsing for GitHub/GitLab/Bitbucket file and directory URLs
- Nested path parsing
- Unknown URL handling

### Step 5: Implement network tests (gated by SKIP_NETWORK)

Tests 12-17 from the task description. Each checks for `SKIP_NETWORK=1` before running:
- File fetching from each platform (assert content contains expected strings)
- Directory listing from each platform (assert non-empty, contains expected files)

### Step 6: Add summary output

```bash
echo "===================="
echo "PASS: $PASS  FAIL: $FAIL"
[[ $FAIL -eq 0 ]] && echo "All tests passed!" || exit 1
```

### Step 7: Run and validate

```bash
bash tests/test_repo_fetch.sh                    # full run
SKIP_NETWORK=1 bash tests/test_repo_fetch.sh     # offline only
shellcheck tests/test_repo_fetch.sh
```

## Post-Implementation (Step 9)
Archive task and plan. Push changes.
