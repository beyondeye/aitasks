# Tool Mapping (Claude Code → Gemini CLI)

When the source skill references Claude Code tools, use these Gemini CLI equivalents.
Most tools have direct equivalents and are not listed.
Only non-trivial differences are shown:

| Claude Code Tool | Gemini CLI Equivalent | Notes |
|---|---|---|
| `AskUserQuestion` | Gemini CLI equivalent | Full-featured, no constraints |
| `Bash(command)` | `run_shell_command(command)` | Also requires `description` param |
| `Read(file)` | `read_file(file_path)` | Supports `start_line`/`end_line` |
| `Write(file, content)` | `write_file(file_path, content)` | Auto-creates parent dirs |
| `Edit(file, ...)` | `replace(file_path, old_string, new_string)` | Single occurrence by default; use `allow_multiple` for all |
| `Glob(pattern)` | `glob(pattern)` | Direct equivalent |
| `Grep(pattern)` | `grep_search(pattern)` | Direct equivalent, ripgrep-based |
| `WebFetch(url)` | `web_fetch(prompt)` | URL + analysis instructions in `prompt` |
| `WebSearch(query)` | `google_web_search(query)` | Direct equivalent |
| `Agent(...)` | `codebase_investigator` or `generalist` | Use `codebase_investigator` for explore, `generalist` for general tasks |
| `EnterPlanMode` | _(not available)_ | Plan inline within the conversation |
| `ExitPlanMode` | _(not available)_ | Plan inline within the conversation |
| `Skill(name)` | `activate_skill(name)` | Native skill activation |

## Gemini CLI Adaptations

### AskUserQuestion

Gemini CLI has a full-featured equivalent with no constraints. Use it
identically to Claude Code's `AskUserQuestion` — present questions with
options, headers, and multi-select as needed. No adaptation required.

### Plan Mode

Gemini CLI has no separate `EnterPlanMode`/`ExitPlanMode`. When the source
skill references plan mode, plan inline: describe your approach as part of
the conversation output before executing.

### Sub-Skill References

When the source skill says "read and follow `.claude/skills/<name>/SKILL.md`",
read that file directly and follow its instructions. You can also use
`activate_skill(name)` to load `.gemini/skills/<name>/SKILL.md`.

### Agent String

When recording `implemented_with` in task metadata, construct `geminicli/<name>`.

1. Check `AITASK_AGENT_STRING` env var — if set, use it directly.
2. Otherwise, identify your model ID from system context.
   Fallback: `jq -r '.model // empty' ~/.gemini/settings.json 2>/dev/null`
3. Match against `aitasks/metadata/models_geminicli.json` (`cli_id` → `name`).
4. Construct `geminicli/<name>` (e.g., `geminicli/gemini2_5pro`).

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
