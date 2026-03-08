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

## References

- Codex CLI docs: [Codex CLI overview](https://developers.openai.com/codex/cli) and [approval modes](https://developers.openai.com/codex/cli/features#approval-modes)
- aitasks Codex mapping note: [`.agents/skills/codex_tool_mapping.md`](https://github.com/beyondeye/aitasks/blob/main/.agents/skills/codex_tool_mapping.md)
