---
Task: t356_gemini_cli_limitations.md
Worktree: (none - working on current branch)
Branch: main
Base branch: main
---

# Plan: Document Gemini CLI and Codex CLI Known Limitations (t356)

## Context

The website's Known Agent Issues page (`website/content/docs/installation/known-issues.md`) currently documents only two issues (one for Claude Code, one for Codex CLI). Since v0.9.0, Gemini CLI and OpenCode are first-class citizens, and several known limitations need to be documented for users. The task also requests a follow-up task for fixing the Gemini CLI allowlisting issue.

## File to Modify

**`website/content/docs/installation/known-issues.md`** — The only file that needs content changes.

## Changes

### 1. Update page intro text

Change the intro from "At the moment, known issues are limited to Claude Code and Codex CLI" to include all four agents.

### 2. Add Gemini CLI section (after Claude Code, before Codex CLI)

Two subsections:

#### a. Per-project shell command policies do not work

- Gemini CLI supports policy files (`.gemini/policies/*.toml`) for allowlisting shell commands via `commandPrefix` rules
- Per-project policy files are **not applied** — the Gemini CLI ignores them despite them being referenced in `settings.json` via `policyPaths`
- **Workaround:** Use a global policy file instead (located in `~/.gemini/policies/`). Global-level policies do work correctly. Copy or symlink `.gemini/policies/aitasks-whitelist.toml` to `~/.gemini/policies/aitasks-whitelist.toml`
- **Impact:** Without the allowlist, Gemini CLI prompts for approval on every shell command execution during aitasks workflows, making multi-step skills impractical

#### b. LLM model self-detection requires slow sub-agent call

- Gemini CLI cannot directly self-identify which model it's running (unlike Claude Code, which can read its own model ID from system context)
- The framework uses the `cli_help` sub-agent to discover the active model — this always succeeds but is noticeably slow (adds latency to the Agent Attribution step)
- **Impact:** The `implemented_with` metadata field can always be populated, but the model detection step takes longer than on other agents
- **Workaround:** Use `ait codeagent invoke` to launch Gemini CLI — it sets `AITASK_AGENT_STRING` env var, bypassing the need for runtime detection entirely

### 3. Expand Codex CLI section

Add two more subsections to the existing Codex CLI section:

#### a. LLM model self-identification is unreliable (NEW)

- Codex CLI models cannot reliably self-report their model ID when prompted
- Unlike Gemini CLI, there is no equivalent `cli_help` sub-agent that provides reliable results
- The framework falls back to reading the configured model from `~/.codex/config.toml`, but this may not reflect the actual model if overridden at invocation time
- **Impact:** The `implemented_with` metadata may be inaccurate if the model is overridden via CLI flags
- **Workaround:** Use `ait codeagent invoke` to launch Codex CLI — it sets `AITASK_AGENT_STRING` env var with the correct agent string

#### b. Task locking and workflow finalization issues (NEW)

- Codex CLI sometimes skips the task locking step (Step 4) before starting implementation
- Task locking cannot be performed during the planning phase because Codex has no separate plan mode with write access
- After implementation completes, Codex CLI often fails to continue the post-implementation workflow (Steps 8-9) automatically because `request_user_input` only works in Suggest mode — once the agent switches to normal execution mode, it can no longer prompt for user decisions
- **Impact:** Users must explicitly prompt Codex CLI to run finalization steps (commit, archive) after implementation
- **Workaround:** Use execution profiles (e.g., the `fast` profile) to pre-answer workflow questions and reduce dependency on `request_user_input`

### 4. Update References section

Add links for Gemini CLI docs and `ait codeagent` workaround.

### 5. Update installation `_index.md` reference

Change "See Known Agent Issues for current Claude Code and Codex CLI workflow limitations." to mention Gemini CLI too.

### 6. Create follow-up task

Create a new aitask for fixing the Gemini CLI per-project allowlisting by installing a global allowlist during `ait setup`.

## Verification

1. Check the page renders correctly:
   ```bash
   cd website && hugo build --gc --minify 2>&1 | tail -5
   ```
2. Verify markdown structure is valid (proper heading hierarchy, no broken links)
3. Read the final page content to confirm accuracy and proper English

## Final Implementation Notes

- **Actual work done:** Expanded the known-issues page from 2 agent sections to 3 (Claude Code, Gemini CLI, Codex CLI) with 5 documented issues total. Updated the installation index reference. Created follow-up task t361 for global allowlist installation.
- **Deviations from plan:** None — all planned changes were implemented as described.
- **Issues encountered:** None.
- **Key decisions:** Used relative Hugo links (`../../commands/codeagent/`) for internal references to the codeagent docs page rather than absolute URLs, consistent with other pages in the site. Merged the existing Codex CLI "Suggest mode" issue with the new task locking/workflow stalling content into a single expanded section rather than keeping them separate, since they share the same root cause (`request_user_input` limitation).

## Step 9: Post-Implementation

After implementation, follow the shared workflow Step 9 for archival.
