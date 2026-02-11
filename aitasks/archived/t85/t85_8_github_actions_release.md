---
priority: medium
effort: low
depends: [t85_1]
issue_type: feature
status: Done
labels: [bash, aitasks]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-02-11 10:00
updated_at: 2026-02-11 13:37
completed_at: 2026-02-11 13:37
---

## Context

This is child task 8 of parent task t85 (Cross-Platform aitask Framework Distribution). A GitHub Actions workflow needs to be created that automatically builds a release tarball when a version tag is pushed. The `install.sh` script (t85_7) downloads this tarball to install aitasks into projects.

**File to create**: `~/Work/aitasks/.github/workflows/release.yml`

## What to Do

### Create the release workflow

```yaml
name: Release

on:
  push:
    tags:
      - 'v*'

permissions:
  contents: write

jobs:
  release:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Extract version from tag
        id: version
        run: echo "version=${GITHUB_REF_NAME#v}" >> $GITHUB_OUTPUT

      - name: Verify VERSION file matches tag
        run: |
          file_version=$(cat VERSION)
          tag_version="${GITHUB_REF_NAME#v}"
          if [ "$file_version" != "$tag_version" ]; then
            echo "ERROR: VERSION file ($file_version) does not match tag ($tag_version)"
            exit 1
          fi

      - name: Create release tarball
        run: |
          tar -czf aitasks-${{ github.ref_name }}.tar.gz \
            ait \
            VERSION \
            aiscripts/ \
            skills/

      - name: Create GitHub Release
        uses: softprops/action-gh-release@v2
        with:
          files: aitasks-${{ github.ref_name }}.tar.gz
          generate_release_notes: true
```

### Key design decisions

**Tarball structure**: The tarball contains files at the top level (no parent directory wrapper). When extracted with `tar -xzf`, it creates:
- `ait` (file)
- `VERSION` (file)
- `aiscripts/` (directory with all scripts + `board/`)
- `skills/` (directory with all SKILL.md files)

This is important because `install.sh` extracts directly into the project root.

**What's NOT in the tarball** (repo-only files):
- `install.sh` — fetched raw from GitHub main branch, not from the release
- `README.md` — documentation, not needed in projects
- `LICENSE` — repo-level file
- `.github/` — CI configuration
- `templates/` — if added later

**Version verification step**: Ensures the `VERSION` file content matches the git tag (e.g., tag `v0.1.0` must have `0.1.0` in VERSION file). This prevents mismatched versions.

**`softprops/action-gh-release@v2`**: This is the standard, well-maintained GitHub Action for creating releases. It:
- Creates the release with the tag name as title
- Attaches the tarball as a release asset
- Auto-generates release notes from commit messages since last release

### Release process (for the developer)

To create a release:
```bash
# 1. Update VERSION file
echo "0.2.0" > VERSION
git add VERSION
git commit -m "Bump version to 0.2.0"

# 2. Tag and push
git tag v0.2.0
git push origin main --tags
```

The GitHub Action will automatically:
1. Verify VERSION matches the tag
2. Create `aitasks-v0.2.0.tar.gz`
3. Create a GitHub Release with the tarball attached

### Commit

```bash
cd ~/Work/aitasks
mkdir -p .github/workflows
git add .github/workflows/release.yml
git commit -m "Add GitHub Actions release workflow"
```

## Verification

1. File exists at `.github/workflows/release.yml` with valid YAML
2. After pushing to GitHub, the Actions tab shows the workflow (it won't trigger until a tag is pushed)
3. To fully test: create a tag `v0.1.0` and push it, then check the Releases page for the created release with tarball
