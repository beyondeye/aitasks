---
Task: t85_8_github_actions_release.md
Parent Task: aitasks/t85_universal_install.md
Sibling Tasks: aitasks/t85/t85_9_*.md, aitasks/t85/t85_11_*.md
Archived Sibling Plans: aiplans/archived/p85/p85_*_*.md
Worktree: (none - working on current branch)
Branch: main
Base branch: main
---

# Plan: t85_8 - Create GitHub Actions Release Workflow

## Context

The aitasks framework needs an automated release process. When a version tag (e.g., `v0.1.0`) is pushed to the `beyondeye/aitasks` repo, a GitHub Actions workflow should automatically build a release tarball and create a GitHub Release with it attached. The `install.sh` script (completed in t85_7) downloads this tarball.

## File to Create

- `~/Work/aitasks/.github/workflows/release.yml`

The `.github/workflows/` directory already exists (empty).

## Implementation

Create the workflow YAML as specified in the task file:

1. **Trigger**: On push of tags matching `v*`
2. **Permissions**: `contents: write` (needed to create releases)
3. **Steps**:
   - Checkout code
   - Extract version from tag (strip `v` prefix)
   - Verify `VERSION` file matches tag — prevents mismatched releases
   - Create tarball containing: `ait`, `VERSION`, `aiscripts/`, `skills/` (flat, no parent dir)
   - Create GitHub Release using `softprops/action-gh-release@v2` with the tarball attached and auto-generated release notes

## Verification

1. Validate YAML syntax
2. After pushing to GitHub, verify the workflow appears in the Actions tab
3. Full test: push a `v0.1.0` tag and check the Releases page

## Final Implementation Notes
- **Actual work done:** Created `.github/workflows/release.yml` exactly as specified in the task file. No deviations needed.
- **Deviations from plan:** None — the task spec was complete and accurate.
- **Issues encountered:** None.
- **Key decisions:** Used the exact YAML from the task specification since it was well-designed.
- **Notes for sibling tasks:** The release workflow is ready but untested until a `v*` tag is pushed to the `beyondeye/aitasks` repo. The `install.sh` (t85_7) already references the GitHub Releases URL for downloading tarballs. To fully test the pipeline: update VERSION, commit, tag with `v0.1.0`, push with `--tags`.
