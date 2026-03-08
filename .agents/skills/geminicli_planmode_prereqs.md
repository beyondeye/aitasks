# Gemini CLI Plan Mode Prerequisites

These prerequisites apply to all Gemini CLI skills that use a multi-step
workflow with planning phases. Check them BEFORE reading or executing the
source Claude Code skill.

## Plan Mode Handling

Gemini CLI has no `EnterPlanMode`/`ExitPlanMode` toggle. Instead:

1. When the skill enters plan mode, announce "Entering planning phase" and
   use only read-only tools (`read_file`, `grep_search`, `glob`, `run_shell_command` with read-only commands)
2. Present your plan to the user and ask for approval before implementing
3. When the skill exits plan mode, announce "Planning complete" and proceed

## Checkpoints

At each checkpoint where the skill uses `AskUserQuestion`, use the Gemini CLI
equivalent to present the same options and wait for the user's choice.

## Abort Handling

Follow the abort procedure exactly as documented if the user selects abort
at any checkpoint.
