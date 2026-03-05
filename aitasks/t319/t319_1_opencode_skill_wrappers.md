---
priority: high
effort: high
depends: []
issue_type: feature
status: Ready
labels: [opencode, codeagent]
created_at: 2026-03-06 01:17
updated_at: 2026-03-06 01:17
---

Create OpenCode skill wrappers and tool mapping for all 17 aitasks skills.

## Context

The aitasks framework added Codex CLI support (t130) with wrapper skills in `.agents/skills/`. Now we need equivalent OpenCode wrappers in `.opencode/skills/`. OpenCode's toolset is nearly 1:1 with Claude Code, making the tool mapping simpler than Codex.

## Key Insight: OpenCode Tools Are Nearly 1:1 with Claude Code

| Claude Code Tool | OpenCode Equivalent | Notes |
|---|---|---|
| `AskUserQuestion` | `ask` | Uses `follow_up` array with `options`, `header`, `multiple`. Not limited to 3 options like Codex. |
| `Bash` | `bash` | Direct equivalent |
| `Read` | `read` | Direct equivalent |
| `Write` | `write` | Direct equivalent |
| `Edit` | `edit` | Uses `old_string`/`new_string` |
| `Glob` | `glob` | Direct equivalent |
| `Grep` | `grep` | Direct equivalent |
| `WebFetch` | `webfetch` | Direct equivalent |
| `WebSearch` | `websearch` | Uses Exa AI |
| `Agent(...)` | `task` | Uses `subagent_type`, `prompt`, `description` |
| `Skill(name)` | `skill` | Uses `name` parameter — invokes `.opencode/skills/<name>/SKILL.md` |
| `EnterPlanMode` | _(not available)_ | Plan inline |
| `ExitPlanMode` | _(not available)_ | Plan inline |

## Key Differences from Codex Wrappers

- No `codex_interactive_prereqs.md` needed — OpenCode's `ask` tool works in all modes (not just plan mode like Codex's `request_user_input`)
- Wrappers are simpler — most just point to `.claude/skills/<name>/SKILL.md` + tool mapping
- Agent string format: `opencode/<model_name>` (uses `aitasks/metadata/models_opencode.json`)
- OpenCode supports pre-approving commands (unlike Codex which only has prompt/forbidden)

## Files to Create

1. **17 skill wrappers** in `.opencode/skills/aitask-*/SKILL.md` (same list as `.agents/skills/`):
   - aitask-changelog, aitask-create, aitask-explain, aitask-explore, aitask-fold
   - aitask-pick, aitask-pickrem, aitask-pickweb, aitask-pr-import
   - aitask-refresh-code-models, aitask-review, aitask-reviewguide-classify
   - aitask-reviewguide-import, aitask-reviewguide-merge, aitask-stats
   - aitask-web-merge, aitask-wrap

2. **`.opencode/skills/opencode_tool_mapping.md`** — shared tool mapping file, simpler than Codex version

3. **`seed/opencode_instructions.seed.md`** — Layer 2 OpenCode-specific additions (like `seed/codex_instructions.seed.md`)

4. **`seed/opencode_config.seed.json`** — permission whitelist for aitask scripts in OpenCode format:
   - OpenCode uses `opencode.json` at project root with glob-style permissions
   - Supports `"allow"`, `"ask"`, `"deny"` per tool. Last matching rule wins.
   - Must enumerate specific git operations and aitask scripts matching `seed/claude_settings.local.json`

## Reference Patterns

- `.agents/skills/aitask-pick/SKILL.md` (Codex wrapper template)
- `.agents/skills/codex_tool_mapping.md` (Codex tool mapping — adapt for OpenCode)
- `aidocs/opencode_tools.md` (OpenCode tool documentation, v1.2.17)
- `seed/codex_instructions.seed.md` (Layer 2 template)
- `seed/claude_settings.local.json` (Claude permission whitelist — map to OpenCode format)

## Verification

- All 17 skill wrapper files exist in `.opencode/skills/`
- Tool mapping file is accurate against `aidocs/opencode_tools.md`
- `seed/opencode_instructions.seed.md` follows Layer 1 + Layer 2 pattern
- `seed/opencode_config.seed.json` has permission whitelist matching Claude's
