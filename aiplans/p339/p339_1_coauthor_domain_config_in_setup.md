---
Task: t339_1_coauthor_domain_config_in_setup.md
Parent Task: aitasks/t339_codex_contributor.md
Sibling Tasks: aitasks/t339/t339_2_*.md, aitasks/t339/t339_3_*.md, aitasks/t339/t339_4_*.md, aitasks/t339/t339_5_*.md, aitasks/t339/t339_6_*.md
Worktree: (current directory)
Branch: (current branch)
Base branch: main
---

# Implementation Plan: t339_1 — Coauthor Domain Config

## Overview

Add a project-scoped config field for the code-agent coauthor email domain and initialize it through `ait setup`.

## Steps

### 1. Extend project config

Add a documented field in `seed/project_config.yaml` for the coauthor email domain used by custom code-agent commit attribution.

### 2. Update setup flow

Update `.aitask-scripts/aitask_setup.sh` so new projects receive the field and reruns preserve an existing custom value.

### 3. Wire config consumption

Make the future coauthor resolver read the field from `aitasks/metadata/project_config.yaml`, with a documented default if absent.

### 4. Add tests

Cover setup/config creation and preservation behavior.

## Verification

- fresh setup creates the field
- rerun preserves a custom domain
- downstream resolver reads configured domain correctly

## Step 9 Reference

Post-implementation: archive via task-workflow Step 9.
