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

Use stronger reasoning/model settings when you need reliable workflow compliance.

## Codex CLI

#### Interactive checkpoints

`ait setup` enables the `default_mode_request_user_input` feature in the generated Codex config (`.codex/config.toml`), so `request_user_input` is available in Codex's default mode. Interactive workflow checkpoints — task confirmation, plan approval, and commit review — work throughout the `aitask-*` workflow, including post-implementation finalization (commit, archive).

> `ait codeagent invoke` still launches interactive Codex skill operations (`pick`, `explain`, `qa`, `explore`) through plan mode; whether that remains necessary is under review.

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
