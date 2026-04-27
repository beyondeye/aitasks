---
priority: medium
effort: low
depends: []
issue_type: bug
status: Done
labels: [whitelists, agentcrew]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_7_1m
created_at: 2026-04-27 16:37
updated_at: 2026-04-27 17:03
completed_at: 2026-04-27 17:03
---

## Problem

When code agents (Claude Code, Gemini CLI, OpenCode) run inside a crew worktree (`.aitask-crews/crew-<id>/`), they prompt for permission on every `ait crew status …` heartbeat / status update / command-list call — defeating the whitelist added by t650_1.

## Root cause: call-form mismatch

`aitask_crew_addwork.sh:211-230` writes per-agent instructions telling agents to invoke the **bare form** of the command:

```bash
ait crew status --crew <id> --agent <name> set --status <status>
ait crew status --crew <id> --agent <name> set --progress <N>
ait crew status --crew <id> --agent <name> heartbeat
ait crew command list --crew <id> --agent <name>
```

This is correct: the crew worktree is a narrow branch (~18 files tracked, no `ait` script checked out), and `ait` is installed to `~/.local/bin/ait` and resolved via PATH.

But the existing whitelist patterns only match the `./ait crew` form:

| File | Line | Current pattern |
|------|------|-----------------|
| `.claude/settings.local.json` | 123 | `"Bash(./ait crew:*)"` |
| `seed/claude_settings.local.json` | 28 | `"Bash(./ait crew:*)"` |
| `.gemini/policies/aitasks-whitelist.toml` | 501 | `commandPrefix = "./ait crew"` |
| `seed/geminicli_policies/aitasks-whitelist.toml` | 531 | `commandPrefix = "./ait crew"` |
| `seed/opencode_config.seed.json` | 17 | `"./ait crew *": "allow"` |

`./ait crew:*` does NOT match a `ait crew status …` invocation — the prefix differs. Result: every heartbeat call from a crew agent prompts the user.

Codex is exempt per the CLAUDE.md "Codex exception" (prompt-by-default model — no allow rules).

## Fix

Add a sibling whitelist entry for the bare `ait crew` form alongside each existing `./ait crew` entry. Keep both — `./ait crew` is still the form humans (and skills running from project root) use.

5 touchpoints (per CLAUDE.md "Adding a New Helper Script" checklist, adapted for an `ait` subcommand):

1. `.claude/settings.local.json` — add `"Bash(ait crew:*)"`
2. `seed/claude_settings.local.json` — same
3. `.gemini/policies/aitasks-whitelist.toml` — add a `[[rule]]` block with `commandPrefix = "ait crew"`, `decision = "allow"`, `priority = 100`
4. `seed/geminicli_policies/aitasks-whitelist.toml` — same
5. `seed/opencode_config.seed.json` — add `"ait crew *": "allow"`

No Codex change.

## Verification

After applying:
- Inside a crew worktree (e.g., `.aitask-crews/crew-brainstorm-635/`), launch a Claude Code agent and have it run `ait crew status --crew brainstorm-635 --agent <name> heartbeat`. It must execute without a permission prompt.
- Repeat for Gemini CLI and OpenCode (manual_verification candidate — sibling tasks recommended if covering all three agents).
- Inspect a fresh `bash install.sh --dir /tmp/scratchXY` — confirm the seed configs propagate the new entries (per the "Test the full install flow for setup helpers" CLAUDE.md guidance, scoped to whitelist propagation).

## Out of scope

- t669 (Postponed, identical symptom) — leave as-is per user direction during exploration.
- t456 (broader per-agent permission framework) — orthogonal.
- Other `ait <subcommand>` forms (e.g., `ait git`, `ait codeagent`) — only `ait crew` is invoked from inside crew worktrees per the addwork instructions; if other prompts surface, file a follow-up task.
