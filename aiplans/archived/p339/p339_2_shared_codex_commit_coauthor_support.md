---
Task: t339_2_shared_codex_commit_coauthor_support.md
Parent Task: aitasks/t339_codex_contributor.md
Sibling Tasks: aitasks/t339/t339_1_*.md, aitasks/t339/t339_3_*.md, aitasks/t339/t339_4_*.md, aitasks/t339/t339_5_*.md, aitasks/t339/t339_6_*.md
Worktree: (current directory)
Branch: (current branch)
Base branch: main
---

# Implementation Plan: t339_2 — Shared Resolver and Codex Support

## Overview

Introduce the reusable commit-attribution resolver and shared workflow procedure, then prove it with Codex.

## Steps

### 1. Add resolver output

Extend `.aitask-scripts/aitask_codeagent.sh` or a shared helper to emit:
- resolved agent string
- coauthor display name
- coauthor email
- full `Co-authored-by:` trailer

### 2. Update workflow procedures

Add a code-agent commit attribution procedure in `.claude/skills/task-workflow/procedures.md` and update Step 8 text in `.claude/skills/task-workflow/SKILL.md`.

### 3. Align direct commit skills

Keep `.claude/skills/aitask-pickrem/SKILL.md`, `.claude/skills/aitask-pickweb/SKILL.md`, and `.claude/skills/aitask-wrap/SKILL.md` consistent with the shared procedure.

### 4. Add Codex tests

Extend `tests/test_codeagent.sh` to cover at least one Codex agent string and final trailer composition.

## Verification

- resolver emits correct Codex coauthor data
- shared workflow docs describe contributor + agent trailer composition
- Codex tests pass

## Final Implementation Notes

- **Actual work done:** Added `ait codeagent coauthor <agent-string>` with machine-readable `AGENT_COAUTHOR_*` output, Codex-specific coauthor naming/email/trailer generation, and help text updates. Updated the shared task-workflow procedures and Step 8 instructions so contributor attribution and code-agent attribution compose into one commit message. Aligned `aitask-pickrem`, `aitask-pickweb`, and `aitask-wrap` with the shared commit-composition flow. Extended `tests/test_codeagent.sh` to cover Codex resolver output, custom-domain handling, unknown-model fallback, unsupported-agent failure, and help text.
- **Deviations from plan:** The implementation kept the resolver scope intentionally narrow: Codex is the only supported coauthor agent in this child, and unsupported agents fail explicitly so later sibling tasks can add their own mappings without changing the interface.
- **Issues encountered:** The main repo checkout reports `aitasks/` and `aiplans/` as untracked directories, so task metadata archival/commit workflow was not safe to run as part of this implementation pass.
- **Key decisions:** The coauthor trailer uses `Co-Authored-By:` casing to match existing repository history. Codex coauthor display names include the agent plus a readable model label derived from the model config `cli_id` when known, falling back to the raw agent-string model token when unknown. Agent-attribution resolution failures are documented as non-blocking so imported contributor trailers remain intact.
- **Notes for sibling tasks:** The `coauthor` subcommand interface is now stable for follow-up children: `AGENT_STRING`, `AGENT_COAUTHOR_NAME`, `AGENT_COAUTHOR_EMAIL`, and `AGENT_COAUTHOR_TRAILER`. Gemini CLI and OpenCode children can extend the same helper with their own display-name/email rules. The Claude redesign child should decide whether to migrate Claude’s existing trailer format into this shared resolver or keep Claude special-cased.

## Step 9 Reference

Post-implementation: archive via task-workflow Step 9.
