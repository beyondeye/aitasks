---
priority: medium
effort: low
depends: []
issue_type: chore
status: Done
labels: [task-archive, archiveformat]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_6
created_at: 2026-03-27 13:10
updated_at: 2026-03-29 11:12
completed_at: 2026-03-29 11:12
---

Add zstd to the list of CLI tools that ait setup installs across all supported platforms.

## Context

The tar.zst archive format requires the zstd command-line tool. ait setup already installs fzf, jq, and git — zstd needs to be added to the same installation flow for all OS detection paths.

## Key Files to Modify

### `.aitask-scripts/aitask_setup.sh`
- Find the tool installation section (each OS case: macOS/brew, Debian/apt, Fedora/dnf, Arch/pacman)
- Add `zstd` to the package lists for each OS
- The package name is `zstd` across all package managers (brew, apt, dnf, pacman)
- Add `zstd` to the tool check that verifies installation succeeded

## Implementation Plan
1. Read `aitask_setup.sh` to find the exact tool installation sections
2. Add `zstd` to each OS package list
3. Verify the tool check section includes zstd
4. Test: `bash .aitask-scripts/aitask_setup.sh --help` (syntax check)

## Verification
- `shellcheck .aitask-scripts/aitask_setup.sh`
- Verify `which zstd` works on the current system
