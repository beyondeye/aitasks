---
title: "Releases Workflow"
linkTitle: "Releases"
weight: 80
description: "Automated changelog generation and release pipeline from task data"
---

Documenting what changed in a new release is one of the most tedious tasks in software development. The aitasks framework solves this by turning your regular development work into the raw material for release notes. Every commit message carries a task ID `(tNN)`, and every completed task has an archived plan file with "Final Implementation Notes." The [`/aitask-changelog`](../../skills/aitask-changelog/) skill harvests this data and uses AI to generate user-facing release notes automatically.

**The key insight:** doing your regular development work with [`/aitask-pick`](../../skills/aitask-pick/) automatically creates the raw material for release notes. No extra documentation effort is needed at release time.

## The Release Pipeline

1. **Generate changelog** — Run [`/aitask-changelog`](../../skills/aitask-changelog/) in Claude Code to gather commit and plan data, then generate a categorized changelog entry
2. **Create release** — Run `./create_new_release.sh` to bump the version, create a git tag, and push
3. **Publish** — GitHub Actions automatically builds a release tarball and publishes release notes extracted from the changelog

## Walkthrough: Releasing v0.4.0

This example shows the three steps using the aitasks project's own v0.4.0 release.

### 1. Generate the changelog

Run the skill in Claude Code:

```
/aitask-changelog
```

The skill runs [`ait changelog --gather`](../../commands/issue-integration/#ait-changelog) behind the scenes, which:

- Finds the latest release tag (`v0.3.0`) and collects all commits since then
- Extracts task IDs from commit messages — the `(tNN)` pattern that [`/aitask-pick`](../../skills/aitask-pick/) uses in its commit convention
- For each task, reads the archived plan file to get the "Final Implementation Notes" section

Claude then generates concise, user-facing summaries for each task and groups them by issue type. You review the draft, pick a version number (the skill suggests next patch and minor versions), and the entry is written to `CHANGELOG.md`:

```markdown
## v0.4.0

### Features

- **Auto-bootstrap new projects** (t127): Running `ait setup` in a directory
  without aitasks now automatically bootstraps the framework, eliminating the
  need to manually download and run the installer.
- **Interactive codebase exploration** (t129_2): Added `/aitask-explore` skill
  for investigating problems, exploring code areas, and scoping ideas — with
  guided follow-up questions and automatic task creation.

### Bug Fixes

- **Missing changelog in help** (t104): Added the `changelog` command to the
  `ait` help text.
- **Exit trap corrupting exit codes** (t150): Fixed an EXIT trap in bash scripts
  that was overwriting the intended exit code.

### Documentation

- **Windows/WSL install notes** (t106): Added inline Windows/WSL guidance and
  authentication cross-references to the install documentation.
```

The skill handles overlap detection (if some tasks were already documented), version validation (ensures strict semver ordering), and supports iterative editing before writing.

### 2. Create the release

```bash
./create_new_release.sh
```

The script validates that `CHANGELOG.md` has an entry for the new version before proceeding. If the entry is missing, it warns and recommends running `/aitask-changelog` first:

```
Current version: 0.3.0
New version (without 'v' prefix): 0.4.0
CHANGELOG.md has entry for v0.4.0. Will be used as release notes.

Will update VERSION 0.3.0 -> 0.4.0
Will create tag v0.4.0 and push to trigger release workflow.
Continue? [y/N] y

Done! Release workflow triggered for v0.4.0.
```

Behind the scenes, the script writes the new version to `aiscripts/VERSION`, creates git tag `v0.4.0`, and pushes to origin — triggering the GitHub Actions workflows.

### 3. GitHub Actions publish

Two workflows run automatically:

**Release workflow** (`.github/workflows/release.yml`) — triggers on tag push:
- Verifies `aiscripts/VERSION` matches the tag (safety check)
- Builds a distributable tarball containing `ait`, `CHANGELOG.md`, `aiscripts/`, `skills/`, and `seed/`
- Extracts the v0.4.0 changelog section from `CHANGELOG.md` and uses it as the GitHub Release notes
- If no changelog section is found, falls back to GitHub's auto-generated release notes

**Documentation workflow** (`.github/workflows/hugo.yml`) — triggers after the Release workflow completes:
- Rebuilds and deploys the project documentation website to GitHub Pages

## Where the Data Comes From

The release pipeline works because regular development with aitasks already produces structured data:

```
Commit messages with task IDs          Archived plan files
  "feature: Add bootstrap (t127)"       "Final Implementation Notes" section
               ↓                                    ↓
         ait changelog --gather (combines both sources)
               ↓
         /aitask-changelog (AI summarization)
               ↓
           CHANGELOG.md
               ↓
       create_new_release.sh (version bump + tag + push)
               ↓
       GitHub Actions (release tarball + docs deploy)
```

Each component feeds the next: [`/aitask-pick`](../../skills/aitask-pick/) enforces the commit message convention (`<issue_type>: <description> (tNN)`), the archival step saves plan files with implementation notes, and [`ait changelog --gather`](../../commands/issue-integration/#ait-changelog) harvests both to produce the raw material for release notes.

## Tips

- **Run changelog before release** — The release script validates changelog completeness and warns if the entry is missing. Generate the changelog first so release notes are ready when the tag is pushed
- **Review AI summaries** — The skill shows the draft before writing. Check that summaries focus on user-facing changes rather than internal implementation details
- **Post-release cleanup** — After releasing, run `ait zip-old` to archive completed task and plan files, keeping the working directories clean for the next development cycle. See the [Release Process](../../development/#release-process) in the Development Guide
