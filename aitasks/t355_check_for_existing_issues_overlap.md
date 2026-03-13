---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Ready
labels: [aitask_contribute]
children_to_implement: [t355_7]
implemented_with: claudecode/opus4_6
created_at: 2026-03-09 23:12
updated_at: 2026-03-11 15:13
boardidx: 60
---

## Problem

When creating contribution issues with aitask-contribute, there is no check for whether the same fix/change was already proposed in another contribution issue. The repo maintainer must manually import and inspect each issue one by one. Additionally, multiple related issues can't be merged into a single imported task.

Prompt injection in imported issues is out of scope (must be handled on reviewer side — follow-up task).

## Design: Three-Layer, Platform-Agnostic Architecture

### Layer 1: Contributor side (aitask-contribute skill)
Embed a composite fingerprint AND auto-label suggestions in the issue metadata comment. No label application or overlap checking during issue creation — keep contributor flow fast.

Fingerprint fields added to `<!-- aitask-contribute-metadata -->`:
```
fingerprint_version: 1
areas: scripts,claude-skills
file_paths: .aitask-scripts/foo.sh,.aitask-scripts/bar.sh
file_dirs: .aitask-scripts
change_type: enhancement
auto_labels: area:scripts,scope:enhancement
```

### Layer 2: Receiving repo side (core script + CI/CD wrappers)
A portable bash script (`aitask_contribution_check.sh`) with encapsulated platform-specific code (same dispatch pattern as `aitask_contribute.sh`). Platform-specific API access: CLI-first with curl fallback for CI/CD (GitHub Actions pre-installs `gh`; GitLab/Bitbucket CI runners use curl + REST API).

Thin CI/CD wrappers call the core script:
- **GitHub Actions**: event-driven (`issues.opened`/`issues.labeled`)
- **GitLab CI**: webhook-triggered pipeline or scheduled scan
- **Bitbucket Pipelines**: scheduled scan

`ait setup` auto-detects the git remote, creates the `contribution` label (GitHub: `gh label create`, GitLab: `glab label create`, Bitbucket: skip), and installs the appropriate CI/CD wrapper.

The script posts a comment on each contribution issue with:
- Top 5 overlapping issues (scores + links + overlap details)
- Label suggestions (apply existing auto_labels, suggest creating missing ones)
- Machine-readable `<!-- overlap-results -->` block for downstream consumption

Overlap scoring: file path intersection × 3, directory intersection × 2, area intersection × 2, change type match × 1. Thresholds: ≥ 4 "likely", ≥ 7 "high".

### Layer 3: Reviewer side (new AI skill + merge import)
New `aitask-contribution-review` skill. Input: single issue number. Gathers related issues from platform-linked issues AND fingerprint overlap results (from the bot comment). AI analyzes actual code diffs across candidates. Proposes ONE task group (or single import). Uses `aitask_issue_import.sh --merge-issues` (new capability) to import.

Multi-contributor attribution for merged issues: primary contributor (largest diff) gets `Co-Authored-By` trailer; others listed in commit body text. New `contributors:` YAML list field in frontmatter for secondary contributors.

## Child Tasks

See child task files in `aitasks/t355/` for detailed implementation specs.
