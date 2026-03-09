---
Task: t339_1_coauthor_domain_config_in_setup.md
Parent Task: aitasks/t339_codex_contributor.md
Sibling Tasks: aitasks/t339/t339_2_*.md, aitasks/t339/t339_3_*.md, aitasks/t339/t339_4_*.md, aitasks/t339/t339_5_*.md, aitasks/t339/t339_6_*.md, aitasks/t339/t339_7_*.md
Worktree: (current directory)
Branch: (current branch)
Base branch: main
---

# Implementation Plan: t339_1 — Coauthor Domain Config

## Overview

Add a project-scoped config field for the code-agent coauthor email domain and initialize it through `ait setup`.

## Steps

### 1. Extend project config

Add a documented field named `codeagent_coauthor_domain` in `seed/project_config.yaml` and in the tracked `aitasks/metadata/project_config.yaml`. The default/example value is `aitasks.io`.

### 2. Update setup flow

Update `.aitask-scripts/aitask_setup.sh` so new projects receive the field and reruns preserve an existing custom value. If an existing project config is missing the key, add it without clobbering other values.

### 3. Wire config consumption

Add a small reusable helper in `.aitask-scripts/aitask_codeagent.sh` that reads `codeagent_coauthor_domain` from `aitasks/metadata/project_config.yaml` and falls back to `aitasks.io` when absent or empty. Do not implement the full coauthor trailer resolver in this child.

### 4. Add tests

Cover setup/config creation and preservation behavior, plus helper resolution and fallback behavior.

## Verification

- fresh setup creates the field
- rerun preserves a custom domain
- helper reads the configured domain
- helper falls back to `aitasks.io` when the key is missing or empty

## Final Implementation Notes

- **Actual work done:** Added `codeagent_coauthor_domain` with default `aitasks.io` to the seed and tracked project config, taught `ait setup` to ensure the key exists without overwriting an existing value, added `ait codeagent coauthor-domain` for machine-readable domain resolution, and expanded shell tests for setup and resolver behavior.
- **Deviations from plan:** In addition to the planned `t339_1` work, part of the intended `t339_7` scope was implemented here: YAML helpers, an editable Project Config tab in `ait settings`, and the corresponding Settings docs updates.
- **Issues encountered:** The first setup regression failed because the fresh-setup test fixture did not copy `seed/project_config.yaml`; the fixture was fixed instead of weakening the assertion.
- **Key decisions:** The default domain was finalized as `aitasks.io`, and the code-agent domain reader was exposed as a small dedicated subcommand so later children can consume it without duplicating YAML parsing.
- **Notes for sibling tasks:** `t339_7` should now be treated as follow-up work for cleanup or further refinement, not a greenfield implementation. The initial Project Config tab already edits `codeagent_coauthor_domain` and `verify_build`, and the Settings docs already mention the new surface.

## Step 9 Reference

Post-implementation: archive via task-workflow Step 9.
