---
title: "Known Agent Issues"
linkTitle: "Known Issues"
weight: 70
description: "Known integration caveats for ai code agents used with aitasks"
depth: [intermediate]
---

This page tracks current workflow issues by code agent. Issues are grouped by agent below.

## Claude Code

#### Medium-effort models can miss workflow steps

In strict multi-step `aitask-*` workflows, medium-effort models may skip required checkpoints or finalization steps.

Use stronger reasoning/model settings when you need reliable workflow compliance. If the agent stops mid-workflow before a final step (for example, the satisfaction-rating prompt), nudge it to *"continue the workflow"* or *"finish the workflow"* to complete the remaining steps.

## Codex CLI

#### Interactive checkpoints

`ait setup` enables the `default_mode_request_user_input` feature in the generated Codex config (`.codex/config.toml`), so `request_user_input` is available in Codex's default mode. This makes the interactive workflow checkpoints — task confirmation, plan approval, and commit review — *available* during the `aitask-*` workflow. Availability is necessary but not sufficient for reliable compliance: see [Reasoning effort and workflow compliance](#reasoning-effort-and-workflow-compliance) below.

> `ait codeagent invoke` launches the planning skills (`pick`, `explore`) through plan mode — it reliably surfaces their commit and merge approval prompts and suits the planning phase. The analysis skills (`qa`, `explain`) run in Codex's default mode.

#### Reasoning effort and workflow compliance

Set Codex's reasoning effort to **at least `high`** when running the `aitask-*` workflow. At lower effort, Codex may silently skip required non-skippable workflow steps and treat the archive as the end of the workflow even when the interactive prompts are available. Raising the effort to `high` resolves most of these compliance problems.

When you change the effort setting, Codex also asks whether to override the current plan-mode effort setting — accept it so the planning phase runs at `high` effort too.

Some skipped prompts are *not* compliance failures: execution profiles such as `fast` deliberately pre-answer prompts like task confirmation, email, and worktree creation. Those skips are expected — the caveat here is only about steps no profile pre-answers.

**Workaround:** even at `high` effort, Codex may occasionally stop mid-workflow before a final step (for example, the satisfaction-rating prompt). If it does, prompt it to *"continue the workflow"* or *"finish the workflow"* so it completes the remaining steps. This is not unique to Codex (see [Medium-effort models can miss workflow steps](#medium-effort-models-can-miss-workflow-steps)).

#### Model self-identification is unreliable

Codex CLI models cannot reliably self-report their model ID when prompted. The framework falls back to reading the configured model from `~/.codex/config.toml`, but this may not reflect the actual model if it was overridden at invocation time via CLI flags.

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
- OpenCode plan mode prereqs: [`.opencode/skills/opencode_planmode_prereqs.md`](https://github.com/beyondeye/aitasks/blob/main/.opencode/skills/opencode_planmode_prereqs.md)
- [`ait codeagent`](../../commands/codeagent/) — unified agent wrapper with `AITASK_AGENT_STRING` support

---

**Next:** [Git Remotes]({{< relref "git-remotes" >}})
