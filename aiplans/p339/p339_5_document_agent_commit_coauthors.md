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
