---
title: "Known Agent Issues"
linkTitle: "Known Issues"
weight: 30
description: "Known integration caveats for ai code agents used with aitasks"
---

This page tracks current workflow issues by code agent. At the moment, known issues are limited to Claude Code and Codex CLI.

## Claude Code

#### Medium-effort models can miss workflow steps

In strict multi-step `aitask-*` workflows, medium-effort models may skip required checkpoints or finalization steps.

Use stronger reasoning/model settings when you need reliable workflow compliance.

## Codex CLI

#### Interactive checkpoints depend on Suggest mode

`aitasks` wrappers use `request_user_input` for workflow checkpoints. In current Codex mappings, this is only available in Suggest mode.

#### Script-heavy flows can require frequent approvals

Codex approval controls are mode-based (Auto, Read-only, Full Access). During script-heavy `aitasks` flows, this can still produce frequent confirmations.

#### Recommendation: use OpenCode when running OpenAI models

If you prefer OpenAI models for `aitasks`, OpenCode is usually smoother for long interactive workflows.

## References

- Codex CLI docs: [Codex CLI overview](https://developers.openai.com/codex/cli) and [approval modes](https://developers.openai.com/codex/cli/features#approval-modes)
- OpenCode docs: [OpenCode intro](https://opencode.ai/docs/)
- aitasks Codex mapping note: [`.agents/skills/codex_tool_mapping.md`](https://github.com/beyondeye/aitasks/blob/main/.agents/skills/codex_tool_mapping.md)
- aitasks OpenCode mapping note: [`.opencode/skills/opencode_tool_mapping.md`](https://github.com/beyondeye/aitasks/blob/main/.opencode/skills/opencode_tool_mapping.md)
