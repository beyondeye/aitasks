---
title: "Agent attribution"
linkTitle: "Agent attribution"
weight: 80
description: "How each task records which code agent and model implemented it."
depth: [advanced]
---

## What it is

**Agent attribution** is the per-task record of which code agent and model did the implementation. It surfaces in three places:

1. The task's `implemented_with` frontmatter field, written at the start of implementation in the form `<agent>/<model>` — for example `claudecode/opus4_7_1m`, `geminicli/gemini3pro`, `codex/gpt5_4`. The `<model>` segment is the `name` field from `aitasks/metadata/models_<agent>.json`, not the raw runtime CLI ID.
2. A `Co-Authored-By:` trailer appended to the implementation commit, naming the model with a project-configurable email domain.
3. The verified-scores subsystem, which keys per-operation satisfaction ratings off the same `<agent>/<model>` string.

The `<model>` segment is a normalized short ID resolved from the agent's runtime model — Claude Code reads it from its system message, Codex CLI from `~/.codex/config.toml`, Gemini CLI from `~/.gemini/settings.json`, and OpenCode from its system context. A wrapper-set `AITASK_AGENT_STRING` environment variable overrides self-detection when present.

## Why it exists

When a task ships, you want to know which model actually built it — not which model was configured a week earlier when the plan was written, and not just "Claude" without a version. Attribution makes that visible in the task file, in `git log` (via the trailer), and in the verified-scores history. It also catches mid-session model switches that would otherwise silently mis-credit the work.

## How to use

Attribution is automatic — the workflow runs the model self-detection sub-procedure at the start of implementation and writes `implemented_with` for you. You normally never edit the field by hand. The full procedure (detection, normalization, fallback) lives in [`task-workflow/agent-attribution.md`](https://github.com/beyondeye/aitasks/blob/main/.claude/skills/task-workflow/agent-attribution.md) and [`model-self-detection.md`](https://github.com/beyondeye/aitasks/blob/main/.claude/skills/task-workflow/model-self-detection.md) on GitHub.

## See also

- [Verified scores]({{< relref "/docs/concepts/verified-scores" >}}) — what attribution feeds into
- [Tasks]({{< relref "/docs/concepts/tasks" >}}) — where the field lives

---

**Next:** [Locks]({{< relref "/docs/concepts/locks" >}})
