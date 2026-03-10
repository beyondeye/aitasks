---
title: "Known Agent Issues"
linkTitle: "Known Issues"
weight: 30
description: "Known integration caveats for ai code agents used with aitasks"
---

This page tracks current workflow issues by code agent. Issues are grouped by agent below.

## Claude Code

#### Medium-effort models can miss workflow steps

In strict multi-step `aitask-*` workflows, medium-effort models may skip required checkpoints or finalization steps.

Use stronger reasoning/model settings when you need reliable workflow compliance.

## Gemini CLI

#### Per-project shell command policies are not applied

Gemini CLI supports policy files (`.gemini/policies/*.toml`) for pre-approving shell commands via `commandPrefix` and `commandRegex` rules. However, **per-project policy files are not applied** — the CLI ignores them even when they are correctly referenced in `.gemini/settings.json` via `policyPaths`.

Without a working allowlist, Gemini CLI prompts for manual approval on every `run_shell_command` call during aitasks workflows, making multi-step skills impractical to run.

**Workaround:** Use a global policy file instead. Global-level policies (stored in `~/.gemini/policies/`) do work correctly. `ait setup` now offers to install or merge the aitasks allowlist into `~/.gemini/policies/aitasks-whitelist.toml` after explicitly showing what file will be copied and where. If you skipped that step earlier, rerun `ait setup` and accept the global Gemini policy prompt.

#### Model self-detection requires a slow sub-agent call

Gemini CLI cannot directly self-identify which LLM model it is running — unlike Claude Code, which can read its own model ID from system context. The aitasks framework uses the [`cli_help`](../../commands/codeagent/) sub-agent to discover the active model. This always succeeds, but adds noticeable latency to the agent attribution step during task claiming.

**Workaround:** Launch Gemini CLI via [`ait codeagent invoke`](../../commands/codeagent/) instead of calling `gemini` directly. The wrapper sets the `AITASK_AGENT_STRING` environment variable before launching the agent, bypassing runtime model detection entirely.

## Codex CLI

#### Interactive checkpoints depend on Suggest mode

`aitasks` wrappers use `request_user_input` for workflow checkpoints (task confirmation, plan approval, commit review). In current Codex CLI mappings, `request_user_input` is only available in **Suggest mode**. Once the agent transitions to normal execution mode, interactive prompts stop working.

This causes two related problems:

- **Task locking is sometimes skipped.** Codex CLI may start implementation without first acquiring a task lock (Step 4), because lock acquisition requires writing metadata, which is not possible during the planning phase (read-only Suggest mode).
- **Post-implementation workflow stalls.** After implementation, the agent often fails to continue to finalization (commit, archive) because it can no longer prompt the user for approval decisions.

**Workaround:** After Codex completes its implementation, explicitly prompt it to continue the workflow (e.g., "please commit and archive the task"). Using [execution profiles](../../commands/codeagent/) (e.g., the `fast` profile) also helps by pre-answering workflow questions and reducing the dependency on `request_user_input`.

#### Model self-identification is unreliable

Codex CLI models cannot reliably self-report their model ID when prompted. Unlike Gemini CLI, there is no equivalent sub-agent (such as `cli_help`) that provides reliable results. The framework falls back to reading the configured model from `~/.codex/config.toml`, but this may not reflect the actual model if it was overridden at invocation time via CLI flags.

**Workaround:** Launch Codex CLI via [`ait codeagent invoke`](../../commands/codeagent/) instead of calling `codex` directly. The wrapper sets the `AITASK_AGENT_STRING` environment variable with the correct agent string, ensuring accurate `implemented_with` metadata.

## OpenCode

#### Plan mode may skip task locking

When OpenCode runs in plan mode, interactive skills (`aitask-pick`, `aitask-explore`, `aitask-review`, `aitask-fold`) may skip the task locking step because plan mode restricts the agent to read-only tools.

**Recommendation:** Use OpenCode in regular mode (not plan mode) for interactive skills that acquire task locks. These skills have their own internal planning phases.

#### Shallow implementation plans

OpenCode may produce high-level overviews instead of detailed step-by-step implementation plans during the task-workflow planning phase. The `opencode_planmode_prereqs.md` file contains explicit instructions to mitigate this, but results may vary by model.

**Workaround:** If the agent produces a shallow plan, prompt it directly: *"Please make a detailed plan of which files will be edited with which changes."* This usually triggers the agent to expand the plan with specific file paths, exact modifications, and code snippets.

## References

- Codex CLI docs: [Codex CLI overview](https://developers.openai.com/codex/cli) and [approval modes](https://developers.openai.com/codex/cli/features#approval-modes)
- aitasks Codex mapping note: [`.agents/skills/codex_tool_mapping.md`](https://github.com/beyondeye/aitasks/blob/main/.agents/skills/codex_tool_mapping.md)
- Gemini CLI docs: [Gemini CLI overview](https://ai.google.dev/gemini-api/docs/gemini-cli) and [sandbox policies](https://ai.google.dev/gemini-api/docs/gemini-cli/sandbox)
- aitasks Gemini mapping note: [`.gemini/skills/geminicli_tool_mapping.md`](https://github.com/beyondeye/aitasks/blob/main/.gemini/skills/geminicli_tool_mapping.md)
- OpenCode plan mode prereqs: [`.opencode/skills/opencode_planmode_prereqs.md`](https://github.com/beyondeye/aitasks/blob/main/.opencode/skills/opencode_planmode_prereqs.md)
- [`ait codeagent`](../../commands/codeagent/) — unified agent wrapper with `AITASK_AGENT_STRING` support
