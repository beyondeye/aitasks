---
Task: t339_5_document_agent_commit_coauthors.md
Parent Task: aitasks/t339_codex_contributor.md
Sibling Tasks: aitasks/t339/t339_1_*.md, aitasks/t339/t339_2_*.md, aitasks/t339/t339_3_*.md, aitasks/t339/t339_4_*.md, aitasks/t339/t339_6_*.md
Worktree: (current directory)
Branch: (current branch)
Base branch: main
---

# Implementation Plan: t339_5 — Documentation

## Overview

Document the configurable code-agent commit coauthor mechanism in setup/config and workflow docs.

## Steps

### 1. Document project config

Add website docs for the new `project_config.yaml` coauthor-domain field and explain how `ait setup` initializes it.

### 2. Document commit behavior

Explain how code commits can now include both imported contributor attribution and code-agent attribution.

### 3. Document Claude caveat

If Claude remains special or partially unsupported, document that explicitly instead of implying full parity.

## Verification

- website docs build successfully
- config/setup pages document the new field
- workflow docs match actual attribution behavior

## Step 9 Reference

Post-implementation: archive via task-workflow Step 9.

## Final Implementation Notes

- **Actual work done:** Added a dedicated `/aitask-pick` Commit Attribution page, linked it from the main `/aitask-pick` docs, expanded `setup-install.md` with `project_config.yaml` initialization details, and documented `ait codeagent coauthor` plus its relationship to `implemented_with`.
- **Actual work done:** Added a dedicated `/aitask-pick` Commit Attribution page, linked it from the main `/aitask-pick` docs, expanded `setup-install.md` with `project_config.yaml` initialization details, and documented `ait codeagent coauthor` plus its relationship to `implemented_with`. Follow-up wording now covers contributor metadata imported via both PRs and issues.
- **Deviations from plan:** The implementation also corrected two user-facing stale examples outside the website docs: `seed/project_config.yaml` and the Settings TUI project-config help text still described the old pre-Claude or model-in-email behavior.
- **Issues encountered:** The current repository worktree already reports broad untracked `aitasks/` and `aiplans/` directories, so I limited verification to content/build checks and did not attempt any task-workflow commit/archive steps.
- **Key decisions:** The new docs treat Claude Code as fully part of the shared resolver path, because sibling task `t339_6` established that the shared trailer safely replaces the old Claude-specific wording.
- **Notes for sibling tasks:** The canonical user-facing explanation of commit attribution now lives in `website/content/docs/skills/aitask-pick/commit-attribution.md`; future workflow-doc updates should keep that page aligned with `.claude/skills/task-workflow/procedures.md`.
