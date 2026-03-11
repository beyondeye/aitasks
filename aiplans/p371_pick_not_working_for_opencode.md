---
Task: t371_pick_not_working_for_opencode.md
Worktree: (current branch)
Branch: main
Base branch: main
---

## Context

After renaming the "task-pick" operation to "pick" (t366), the project-level
`codeagent_config.json` still uses the old key. This causes OpenCode (and any
non-default agent) to never be resolved from config — falling back to the
hardcoded Claude Code default. Additionally, `build_invoke_command()` in
`aitask_codeagent.sh` passes raw args for OpenCode and Codex instead of invoking
the proper skill/command.

## Changes

### 1. Fix config key: `aitasks/metadata/codeagent_config.json`
- Change `"task-pick"` → `"pick"` in defaults object
- Also fixes settings TUI display (reads keys dynamically from JSON)

### 2. Fix OpenCode command building: `.aitask-scripts/aitask_codeagent.sh` (build_invoke_command)
- Use `--prompt` flag for skill invocations: `opencode --model <id> --prompt "/aitask-pick <args>"`
- This starts the interactive TUI with the prompt pre-loaded (unlike `opencode run` which is batch mode)
- Keep raw passthrough for batch-review/raw operations

### 3. Fix Codex command building: `.aitask-scripts/aitask_codeagent.sh`
- Add `$aitask-pick` and `$aitask-explain` skill invocations for pick/explain operations
- Keep raw passthrough for batch-review/raw operations

## Verification

- Dry-run invoke tests per agent
- Existing codeagent test suite
- Shellcheck

## Final Implementation Notes
- **Actual work done:** Fixed all issues — config key rename, OpenCode `--prompt` skill invocation, Codex skill invocation
- **Deviations from plan:** OpenCode uses `--prompt` flag (not `run` subcommand) to stay in interactive TUI mode
- **Issues encountered:** First attempt used `opencode run` (batch mode), corrected to `--prompt` flag for interactive TUI mode
- **Key decisions:** Used `--prompt "/aitask-pick <args>"` for OpenCode (starts interactive TUI with prompt pre-loaded), and `$aitask-pick` for Codex (matches Codex CLI's `$skill-name` invocation syntax)
- **Verification results:** All 71 codeagent tests pass. Dry-run output verified for all 4 agents. Shellcheck clean. Results:
  - `opencode --model openai/gpt-5.1-codex --prompt /aitask-pick 365`
  - `claude --model claude-opus-4-6 /aitask-pick 365`
  - `gemini -m gemini-2.5-pro /aitask-pick 365`
  - `codex -m gpt-5.4 $aitask-pick 365`

## Step 9: Post-Implementation
- Archive task, update linked issues, push
