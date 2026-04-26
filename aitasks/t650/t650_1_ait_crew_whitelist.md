---
priority: high
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [whitelists, agentcrew]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-04-26 14:17
updated_at: 2026-04-26 16:19
---

## Context

Bug 1 of the parent t650. Code agents are prompted on every `ait crew <subcommand>` invocation because the `./ait crew` dispatcher entry is missing or malformed across the canonical 5-touchpoint whitelist set documented in `CLAUDE.md` ("Adding a New Helper Script", generalized here to a top-level `ait` verb).

This child is independent of the heartbeat-fix children (t650_2, t650_3) and ships immediately.

## Key Files to Modify

| File | Current state | Action |
|---|---|---|
| `.claude/settings.local.json` (line 122) | `"Bash(ait crew *)"` (malformed: missing `./` prefix, wrong colon style) | Replace with `"Bash(./ait crew:*)"` |
| `seed/claude_settings.local.json` | missing | Add `"Bash(./ait crew:*)"` near the existing `"Bash(./ait git:*)"` entry |
| `.gemini/policies/aitasks-whitelist.toml` | missing | Add a `[[rule]]` block near the `./ait git` / `./ait codeagent` blocks |
| `seed/geminicli_policies/aitasks-whitelist.toml` | missing | Mirror the runtime gemini block |
| `seed/opencode_config.seed.json` | missing | Add `"./ait crew *": "allow"` near the existing `"./ait git *"` entry |

Codex (`.codex/`, `seed/codex_config.seed.toml`) is exempt per CLAUDE.md (prompt/forbidden-only permission model).

## Reference Files for Patterns

Verified against neighboring `./ait git` / `./ait codeagent` entries:

- Claude (runtime + seed): `"Bash(./ait crew:*)"`
- Gemini (runtime + seed):
  ```toml
  [[rule]]
  toolName = "run_shell_command"
  commandPrefix = "./ait crew"
  decision = "allow"
  priority = 100
  ```
- OpenCode (seed only): `"./ait crew *": "allow"`

The whitelist is at the dispatcher-verb level (`./ait crew`), not per-subcommand — this auto-covers all current and future `ait crew <subcommand>` invocations (init, addwork, setmode, status, command, runner, report, cleanup, dashboard, logview).

## Implementation Plan

1. Edit `.claude/settings.local.json:122` — replace the malformed entry.
2. Edit `seed/claude_settings.local.json` — add the canonical entry.
3. Edit `.gemini/policies/aitasks-whitelist.toml` — append the `[[rule]]` block.
4. Edit `seed/geminicli_policies/aitasks-whitelist.toml` — append the mirrored `[[rule]]` block.
5. Edit `seed/opencode_config.seed.json` — add the allow entry.

## Verification Steps

```bash
grep "ait crew" .claude/settings.local.json seed/claude_settings.local.json \
                 .gemini/policies/aitasks-whitelist.toml \
                 seed/geminicli_policies/aitasks-whitelist.toml \
                 seed/opencode_config.seed.json
```

Expected: exactly the canonical entry per agent and no remaining malformed entry.

Then sanity-check by running an `ait crew` command in this Claude Code session — it should not trigger a permission prompt.
