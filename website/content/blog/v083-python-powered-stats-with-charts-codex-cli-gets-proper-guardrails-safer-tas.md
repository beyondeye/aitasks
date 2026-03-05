---
date: 2026-03-05
title: "v0.8.3: Python-powered Stats with Charts, Codex CLI Gets Proper Guardrails, and Safer Task Ownership"
linkTitle: "v0.8.3"
description: "v0.8.3 is a stability and polish release focused on making Codex CLI integration rock-solid and improving the stats experience."
author: "aitasks team"
---


v0.8.3 is a stability and polish release focused on making Codex CLI integration rock-solid and improving the stats experience.

## Python-powered Stats with Charts

The `ait stats` command has been rewritten in Python, making it noticeably faster. Even better, you can now get visual charts right in your terminal with `--plot` — just enable the optional `plotext` dependency during `ait setup`.

## Codex CLI Gets Proper Guardrails

If you're using Codex CLI with aitasks, interactive skills now properly require plan mode before running. No more cryptic failures when Codex tries to prompt you mid-execution. We also fixed broken YAML in skill definitions and added agent attribution tracking across all remote/async workflows.

## Safer Task Ownership

Before diving into implementation, the workflow now double-checks that you actually own the task — both the status and the assigned_to field. This prevents the frustrating scenario where two agents accidentally work on the same task.

---

---

**Full changelog:** [v0.8.3 on GitHub](https://github.com/beyondeye/aitasks/releases/tag/v0.8.3)
