---
Task: t364_no_option_to_skip_reviewguide_install_in_ait_setup.md
Worktree: current
Branch: main
Base branch: main
---

# Implementation Plan - t364

Add an option to skip the installation of review guides in `ait setup`.

## Proposed Changes

### 1. `.aitask-scripts/aitask_setup.sh`

- In `setup_review_guides()`:
    - Add a `[Y/n]` prompt before the guide selection list (interactive mode only).
    - Add an explicit `>>> Skip review guide installation` option to the `fzf` list.
    - Handle the "Skip" option in the `fzf` selection processing.
    - Update the indexing loop to exclude the "SKIP" marker from file indices.

## Verification Steps

### Automated Tests
- Run `bash -n .aitask-scripts/aitask_setup.sh` (syntax check).
- Run `shellcheck --severity=error .aitask-scripts/aitask_setup.sh`.
- Run mock test script for non-interactive mode.

### Manual Verification
- Run `ait setup` (or `.aitask-scripts/aitask_setup.sh`) and verify:
    - The new "Install review guides? [Y/n]" prompt appears.
    - Choosing 'n' skips the installation.
    - Choosing 'Y' (or default) enters `fzf`.
    - In `fzf`, the `>>> Skip review guide installation` option appears at the end.
    - Selecting "Skip" in `fzf` skips the installation.
    - Selecting guides and pressing Enter installs only those guides.

## Final Implementation Notes
- **Actual work done:** Implemented both the Y/n prompt and the explicit Skip option in fzf.
- **Deviations from plan:** None.
- **Key decisions:** Placed the Skip option at the end of the fzf list to keep the indexing logic simple (preserving `i-1` for files).
