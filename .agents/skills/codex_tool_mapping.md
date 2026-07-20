# Tool Mapping (Claude Code → Codex CLI)

When the source skill references Claude Code tools, use these Codex CLI equivalents:

| Claude Code Tool | Codex CLI Equivalent | Notes |
|---|---|---|
| `AskUserQuestion` | `functions.request_user_input` | Max 3 questions per call. 4 options per question work (verified live on Codex v0.144.6, 2026-07-20 — an earlier 3-option cap no longer applies; Codex appends its own "None of the above" row). Available in default mode via the `default_mode_request_user_input` feature (`ait setup` enables it), as well as plan/Suggest mode. In default mode the model prefers assumptions, so reserve prompts for genuinely unavoidable decisions. |
| `Bash(command)` | `functions.exec_command(command)` | Direct equivalent |
| `Read(file)` | `functions.exec_command("cat <file>")` | Use cat for file reading |
| `Write(file, content)` | `functions.apply_patch(...)` | Use Add File patch for new files |
| `Edit(file, ...)` | `functions.apply_patch(...)` | Use Update File patch for edits |
| `Glob(pattern)` | `functions.exec_command("find . -name '<pattern>'")` | Use find for file discovery |
| `Grep(pattern)` | `functions.exec_command("grep -rn '<pattern>' .")` | Use grep/rg for content search |
| `WebFetch(url)` | `web.run` with `open` | Web content fetching |
| `WebSearch(query)` | `web.run` with `search_query` | Web search |
| `EnterPlanMode` | _(not available)_ | Plan inline within the conversation |
| `ExitPlanMode` | _(not available)_ | Plan inline within the conversation |
| `Agent(...)` | _(not available)_ | Execute the sub-steps directly |
| `Skill(name)` | Read the referenced SKILL.md file directly | No sub-skill invocation mechanism |

## Codex CLI Adaptations

### AskUserQuestion Limits

Codex CLI's `request_user_input` accepts **4 options per question** — the same
as Claude's `AskUserQuestion` — verified live on Codex v0.144.6 (2026-07-20;
an earlier 3-option cap no longer applies). Codex renders one extra
auto-appended "None of the above" row, which is harmless. Present a source
skill's 4-option question as-is; no combining, splitting, or dropping is
needed.

Questions per call remain capped at 3 (Claude allows 4). When the source skill
batches 4 questions in one call, split them into two sequential
`request_user_input` calls.

`request_user_input` is available in **default mode** (via the
`default_mode_request_user_input` feature that `ait setup` enables) as well as
plan/Suggest mode. In default mode the model is steered toward assumptions, so
issue prompts only for decisions that genuinely cannot be defaulted. If user
input is unavailable, fall back to execution profiles or reasonable defaults.

### Plan Mode

Codex CLI has no separate `EnterPlanMode`/`ExitPlanMode`. When the source
skill references plan mode, plan inline: describe your approach as part of
the conversation output before executing.

### Sub-Skill References

When the source skill says "read and follow `.claude/skills/<name>/SKILL.md`",
read that file directly and follow its instructions. There is no sub-agent
or sub-skill invocation mechanism.

### Agent String

When recording `implemented_with` in task metadata, construct `codex/<name>`.
Do NOT guess your model ID — Codex models cannot reliably self-identify.

1. Check `AITASK_AGENT_STRING` env var — if set, use it directly.
2. Otherwise, read configured model: `grep '^model' ~/.codex/config.toml | sed 's/^model[[:space:]]*=[[:space:]]*//' | tr -d '"'`
3. Run: `./.aitask-scripts/aitask_resolve_detected_agent.sh --agent codex --cli-id <model_id>`
4. Parse the output — the value after the colon is your agent string.

### Task-Workflow Adaptations

These adaptations apply to skills that hand off to the shared task-workflow
(`aitask-pick`, `aitask-create`, `aitask-explore`, `aitask-fold`,
`aitask-review`, `aitask-pr-import`).

**Plan file creation:** When `aitask_query_files.sh plan-file <taskid>`
returns `NOT_FOUND`, this means **no plan file exists yet** — it does NOT
mean "no plan needed" or "skip plan creation." Always create the plan file
in `aiplans/` before beginning implementation. Follow the planning workflow
in the source skill for the correct format and content.

**Post-implementation finalization:** After implementation is complete, you
MUST explicitly run all finalization steps from the task-workflow (Steps 8
and 9). Do not assume these will be triggered automatically via
`request_user_input`. Specifically:

1. **Consolidate the plan file** — update `aiplans/` with final
   implementation notes, deviations, and outcomes
2. **Commit changes** — follow the commit message format:
   `<issue_type>: <description> (t<task_id>)`
3. **Archive the task** — run the archival workflow from the source skill

If `request_user_input` fails or is unavailable during finalization, proceed
with reasonable defaults: commit all implementation changes, then archive.
