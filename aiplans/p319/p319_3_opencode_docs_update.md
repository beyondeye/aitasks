---
Task: t319_3_opencode_docs_update.md
Parent Task: aitasks/t319_opencode_support.md
Sibling Tasks: aitasks/t319/t319_1_opencode_skill_wrappers.md, aitasks/t319/t319_2_opencode_setup_install.md, aitasks/t319/t319_4_opencode_model_discovery.md
Archived Sibling Plans: (check aiplans/archived/p319/ at implementation time)
Worktree: (none - working on current branch)
Branch: (current branch)
Base branch: main
---

# Plan: Update Website Documentation for OpenCode Support

## Overview

Update the live website entry pages so OpenCode is documented alongside the existing code-agent integrations, while keeping the invocation model accurate: Claude Code, Gemini CLI, and OpenCode use `/aitask-*`; Codex CLI uses `$aitask-*`.

## Step 1: Use the Codex docs update plan as reference

Read `aiplans/archived/p130/p130_3_codex_docs_update.md` to reuse the cross-agent documentation pattern, but adapt it to the current wrapper layout:

- `.agents/skills/` is the shared wrapper location for Codex CLI and Gemini CLI
- `.opencode/skills/` is the wrapper location for OpenCode
- Codex keeps the plan-mode caveat; OpenCode does not

## Step 2: Update skills page

**File:** `website/content/docs/skills/_index.md`

- Update the intro line and multi-agent callout to reflect the real invocation split:
  - `/aitask-*` for Claude Code, Gemini CLI, and OpenCode
  - `$aitask-*` for Codex CLI
- Document wrapper locations accurately:
  - `.agents/skills/` for Codex CLI and Gemini CLI
  - `.opencode/skills/` for OpenCode
- Keep the plan-mode warning scoped to Codex only
- Add the OpenCode note only where useful: native `skill` + native `ask`

## Step 3: Update home page

**File:** `website/content/_index.md`

- Update only the "Code Agent Integration" feature card
- Fix the missing Codex mention there
- Mention OpenCode there as part of the same invocation split
- Do not add a separate homepage release note or modify the release list

## Step 4: Update getting started page

**File:** `website/content/docs/getting-started.md`

- Expand the opening sentence to include OpenCode (and reflect the current multi-agent set)
- In the "Pick and Implement a Task" section, explain that `/aitask-pick` works in Claude Code, Gemini CLI, and OpenCode
- Keep the Codex-specific `$aitask-pick` example and plan-mode warning
- Update the skills cross-reference wording so it matches the invocation split used on the skills page

## Step 5: Verify website builds

```bash
cd website && hugo build --gc --minify
```

## Step 6: Commit

```bash
git add website/
git commit -m "documentation: Add OpenCode support to website docs (t319_3)"
```

## Verification

- [x] Website builds without errors
- [x] OpenCode mentioned on skills page (`website/content/docs/skills/_index.md`)
- [x] OpenCode mentioned in the homepage code-agent integration card (`website/content/_index.md`)
- [x] Correct invocation split documented (`/aitask-*` for Claude/Gemini/OpenCode, `$aitask-*` for Codex)
- [x] Wrapper locations documented correctly (`.agents/skills/` for Gemini/Codex, `.opencode/skills/` for OpenCode)

## Final Implementation Notes

- **Actual work done:** Updated the skills overview, getting started guide, and homepage feature card to document the current invocation split and wrapper layout for Claude Code, Gemini CLI, Codex CLI, and OpenCode. Also corrected the homepage code-agent card so Codex is explicitly mentioned there.
- **Deviations from plan:** Did not add a separate homepage release note. The final agreed scope kept homepage agent references confined to the `Code Agent Integration` feature card only. The docs wording was also broadened slightly to mention Gemini CLI where needed so the shared `.agents/skills/` directory and slash-command behavior are described accurately.
- **Issues encountered:** No content or build issues. `hugo build --gc --minify` passed after the edits. One shell verification command needed to be rerun because backticks in the search pattern were interpreted by the shell; this did not affect the docs changes.
- **Key decisions:** Treated `/aitask-*` as the default skill syntax for all code agents except Codex, which keeps `$aitask-*`. Documented `.agents/skills/` as the unified wrapper location for Codex CLI and Gemini CLI, and `.opencode/skills/` as the OpenCode-specific wrapper location. Kept the plan-mode caveat explicitly Codex-only and noted that OpenCode uses native `skill` and native `ask`.
- **Notes for sibling tasks:** When updating cross-agent docs, prefer describing the invocation split by behavior (`slash for all except Codex`) rather than listing agents independently on every sentence. Keep homepage agent mentions narrowly scoped to the feature card unless there is a real release/blog artifact to link. For future OpenCode docs work, mirror Codex wording only after checking whether the limitation is truly shared; OpenCode should not inherit Codex’s plan-mode caveat.

## Post-Implementation: Step 9

Follow task-workflow Step 9 for archival.
