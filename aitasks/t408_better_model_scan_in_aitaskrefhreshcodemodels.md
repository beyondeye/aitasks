---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Ready
labels: [modelvrapper]
created_at: 2026-03-17 12:31
updated_at: 2026-03-17 12:54
boardcol: backlog
boardidx: 80
---

in the skill aitask-refresh-code-models, we search the internet for updated code models, except for opencode where we query the opencode itseld for available llm models. I am asking myself if also codex/claudecode/geimini have similar functionality, and if yes substitute scanning the internet for new code models with just querying the clis

## Research Findings (2026-03-17)

**None of the three CLIs have built-in model listing commands:**

| CLI | Model Listing? | Notes |
|-----|----------------|-------|
| `claude` (Claude Code) | No | Has `--model` flag and `agents` subcommand, but no `models` listing command |
| `codex` (Codex CLI) | No | Has `-m` flag, no model discovery subcommand |
| `gemini` (Gemini CLI) | No | Has `-m` flag and `--list-extensions`, but no model listing |
| `opencode` | Yes | `opencode models --verbose` — already implemented via `aitask_opencode_models.sh` |

**Alternative considered:** Provider REST APIs (Anthropic `/v1/models`, OpenAI `/v1/models`, Google `/v1beta/models`) could list models if API keys were available, but CLIs use OAuth/stored credentials that aren't easily extractable for scripting.

**Conclusion:** Keep web scraping approach for claude/codex/gemini. Revisit periodically as CLIs evolve — any of them could add a `models` subcommand in future versions.
