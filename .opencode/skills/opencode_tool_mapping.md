# Tool Mapping (Claude Code → OpenCode)

When the source skill references Claude Code tools, use these OpenCode equivalents:

| Claude Code Tool | OpenCode Equivalent | Notes |
|---|---|---|
| `AskUserQuestion` | `ask` | Uses `follow_up` array with `options`, `header`, `multiple`. No option limit. |
| `Bash(command)` | `bash` | Direct equivalent |
| `Read(file)` | `read` | Direct equivalent |
| `Write(file, content)` | `write` | Direct equivalent |
| `Edit(file, ...)` | `edit` | Uses `old_string`/`new_string`, `replace_all` |
| `Glob(pattern)` | `glob` | Direct equivalent |
| `Grep(pattern)` | `grep` | Direct equivalent |
| `WebFetch(url)` | `webfetch` | Direct equivalent |
| `WebSearch(query)` | `websearch` | Uses Exa AI |
| `Agent(...)` | `task` | Uses `subagent_type` ("general" or "explore"), `prompt`, `description` |
| `Skill(name)` | `skill` | Uses `name` parameter — invokes `.opencode/skills/<name>/SKILL.md` |
| `EnterPlanMode` | _(not available)_ | Plan inline within the conversation |
| `ExitPlanMode` | _(not available)_ | Plan inline within the conversation |

## OpenCode Adaptations

### AskUserQuestion → ask

OpenCode's `ask` tool works in all modes (no plan mode restriction like Codex).
Use the `follow_up` array for structured questions:

```json
{
  "question": "Main question text",
  "follow_up": [{
    "question": "Select an option:",
    "header": "Choice",
    "multiple": false,
    "options": [
      {"label": "Option A", "description": "Description of A"},
      {"label": "Option B", "description": "Description of B"}
    ]
  }]
}
```

The `multiple` field corresponds to Claude Code's `multiSelect`.

### Plan Mode

OpenCode has no separate `EnterPlanMode`/`ExitPlanMode`. When the source
skill references plan mode, plan inline: describe your approach as part of
the conversation output before executing.

### Sub-Skill References

When the source skill says "read and follow `.claude/skills/<name>/SKILL.md`",
read that file directly and follow its instructions. You can also use the
`skill` tool to load `.opencode/skills/<name>/SKILL.md`.

### Agent String

When recording `implemented_with` in task metadata, identify as
`opencode/<model_name>`. Read `aitasks/metadata/models_opencode.json` to find the
matching `name` for your model ID. Construct as `opencode/<name>`.

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
and 9). Specifically:

1. **Consolidate the plan file** — update `aiplans/` with final
   implementation notes, deviations, and outcomes
2. **Commit changes** — follow the commit message format:
   `<issue_type>: <description> (t<task_id>)`
3. **Archive the task** — run the archival workflow from the source skill
