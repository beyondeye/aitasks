# Tool Mapping (Claude Code → Codex CLI)

When the source skill references Claude Code tools, use these Codex CLI equivalents:

| Claude Code Tool | Codex CLI Equivalent | Notes |
|---|---|---|
| `AskUserQuestion` | `functions.request_user_input` | Max 3 questions per call, max 3 options per question. Only works in Suggest mode. |
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

Codex CLI's `request_user_input` supports max 3 options per question (Claude
allows 4) and max 3 questions per call (Claude allows 4). When the source
skill presents 4 options:

1. Combine the two least critical options into one if semantically possible
2. Or split into two sequential prompts
3. Or drop the least essential option

`request_user_input` only works in **Suggest mode**. If running in a mode
where user input is not available, use execution profiles or reasonable defaults.

### Plan Mode

Codex CLI has no separate `EnterPlanMode`/`ExitPlanMode`. When the source
skill references plan mode, plan inline: describe your approach as part of
the conversation output before executing.

### Sub-Skill References

When the source skill says "read and follow `.claude/skills/<name>/SKILL.md`",
read that file directly and follow its instructions. There is no sub-agent
or sub-skill invocation mechanism.

### Agent String

When recording `implemented_with` in task metadata, identify as
`codex/<model_name>`. Read `aitasks/metadata/models_codex.json` to find the
matching `name` for your model ID. Construct as `codex/<name>`.
