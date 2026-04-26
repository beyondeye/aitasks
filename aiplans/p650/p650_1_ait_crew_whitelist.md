---
Task: t650_1_ait_crew_whitelist.md
Parent Task: aitasks/t650_brainstorm_bugs.md
Sibling Tasks: aitasks/t650/t650_2_brainstorm_heartbeat_procedure_reference.md, aitasks/t650/t650_3_brainstorm_heartbeat_explicit_commands.md
Archived Sibling Plans: (none yet)
Worktree: (none — running on main per profile)
Branch: main
Base branch: main
---

# Plan: t650_1 — `ait crew` whitelist

## Context

Independent of the heartbeat-fix children. Bug 1 of parent t650: code agents are prompted on every `ait crew <subcommand>` invocation because the `./ait crew` dispatcher entry is missing/malformed across the canonical 5-touchpoint whitelist set documented in `CLAUDE.md` ("Adding a New Helper Script" — generalized here to a top-level `ait` verb instead of an individual helper script).

The convention (verified against `./ait git` and `./ait codeagent` entries already present in all 5 touchpoints) is to whitelist at the dispatcher-verb level, not per-subcommand. This auto-covers all current and future `ait crew <subcommand>` invocations: `init`, `addwork`, `setmode`, `status`, `command`, `runner`, `report`, `cleanup`, `dashboard`, `logview`.

Codex (`.codex/`, `seed/codex_config.seed.toml`) is exempt per CLAUDE.md (prompt/forbidden-only permission model — no `allow` decision exists).

## Concrete edits

### 1. `.claude/settings.local.json` (line 122)

**Find:**
```json
      "Bash(ait crew *)"
```
**Replace with:**
```json
      "Bash(./ait crew:*)"
```

### 2. `seed/claude_settings.local.json`

Add `"Bash(./ait crew:*)"` near the existing `"Bash(./ait git:*)"` entry. Mirror the runtime entry.

### 3. `.gemini/policies/aitasks-whitelist.toml`

Append a `[[rule]]` block near the existing `./ait git` / `./ait codeagent` blocks:

```toml
[[rule]]
toolName = "run_shell_command"
commandPrefix = "./ait crew"
decision = "allow"
priority = 100
```

### 4. `seed/geminicli_policies/aitasks-whitelist.toml`

Mirror the runtime gemini block (same `[[rule]]` content as above).

### 5. `seed/opencode_config.seed.json`

Add `"./ait crew *": "allow"` near the existing `"./ait git *"` entry.

## Verification

```bash
grep "ait crew" .claude/settings.local.json seed/claude_settings.local.json \
                 .gemini/policies/aitasks-whitelist.toml \
                 seed/geminicli_policies/aitasks-whitelist.toml \
                 seed/opencode_config.seed.json
```

Expected: exactly the canonical entry per agent and no remaining malformed `"Bash(ait crew *)"` entry.

Sanity-check by running an `ait crew` command in this Claude Code session — it should not trigger a permission prompt.

## Notes for sibling tasks

This child does NOT touch any brainstorm template or `aitask_crew_addwork.sh` — the heartbeat work in t650_2 / t650_3 is independent.
