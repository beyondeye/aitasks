---
date: 2026-03-10
title: "v0.10.0: Contribute Back Without Forking, Code Agent Commit Attribution, and Code Agent and Model Statistics"
linkTitle: "v0.10.0"
description: "v0.10.0 brings a major new contribution workflow, smarter commit attribution, and a bunch of quality-of-life improvements across the board."
author: "aitasks team"
---


v0.10.0 brings a major new contribution workflow, smarter commit attribution, and a bunch of quality-of-life improvements across the board.

## Contribute Back Without Forking

The new `/aitask-contribute` command lets you open structured issues against upstream repositories directly from your local changes — no fork required. It works with GitHub, GitLab, and Bitbucket, and even parses contributor metadata when issues are imported back. If your project defines `code_areas.yaml`, you get hierarchical area drill-down to scope your contributions precisely.

## Code Agent Commit Attribution

Commit messages now automatically include accurate code-agent and model attribution. Whether you're using Claude Code, Codex CLI, Gemini CLI, or OpenCode, the `Co-Authored-By` trailer reflects the actual agent and model that wrote the code. You can customize the coauthor email domain via `project_config.yaml`.

## Code Agent and Model Statistics

`ait stats` now tracks which code agents and LLM models are doing the work. You get breakdowns by agent, by model, weekly trend tables, and four new plot histograms. Great for understanding how your team's AI tooling usage evolves over time.

## Code Area Maps

A new `code_areas.yaml` file lets you define your project's structure, and the `/aitask-contribute` workflow now supports both framework-level and project-level contributions with automatic codemap generation and area drill-down.

## Python Codemap Scanner

The codemap scanning engine has been rewritten from bash to Python, bringing better performance and new filtering options like `--include-framework-dirs` and `--ignore-file`.

---

---

**Full changelog:** [v0.10.0 on GitHub](https://github.com/beyondeye/aitasks/releases/tag/v0.10.0)
