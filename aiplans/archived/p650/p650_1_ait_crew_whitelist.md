---
Task: t650_1_ait_crew_whitelist.md
Parent Task: aitasks/t650_brainstorm_bugs.md
Sibling Tasks: aitasks/t650/t650_2_brainstorm_heartbeat_procedure_reference.md, aitasks/t650/t650_3_brainstorm_heartbeat_explicit_commands.md
Base branch: main
plan_verified:
  - claudecode/opus4_7_1m @ 2026-04-26 16:22
---

# Plan: t650_1 — `ait crew` whitelist (verified)

## Context

Bug 1 of parent t650: code agents are prompted on every `ait crew <subcommand>` invocation because the `./ait crew` dispatcher entry is missing/malformed across the canonical 5-touchpoint whitelist set documented in `CLAUDE.md` ("Adding a New Helper Script", generalized here to a top-level `ait` verb).

Convention (verified against `./ait git` / `./ait codeagent` entries already present in all 5 touchpoints): whitelist at the dispatcher-verb level, not per-subcommand. This auto-covers all current and future `ait crew <subcommand>` invocations (init, addwork, setmode, status, command, runner, report, cleanup, dashboard, logview).

Codex (`.codex/`, `seed/codex_config.seed.toml`) is exempt per CLAUDE.md (prompt/forbidden-only permission model — no `allow` decision exists).

## Verification of existing plan

Re-checked all 5 touchpoints against the live tree (2026-04-26):

- `.claude/settings.local.json:122` — confirmed malformed `"Bash(ait crew *)"` (no `./` prefix, wrong `:*` style).
- `seed/claude_settings.local.json` — has `"Bash(./ait git:*)"` at line 27, no `crew` entry.
- `.gemini/policies/aitasks-whitelist.toml` — has `commandPrefix = "./ait git"` at line 489, no `crew` rule.
- `seed/geminicli_policies/aitasks-whitelist.toml` — has `commandPrefix = "./ait git"` at line 519, no `crew` rule.
- `seed/opencode_config.seed.json` — has `"./ait git *": "allow"` at line 16, no `crew` entry.

Plan is sound — no changes to approach.

## Concrete edits

### 1. `.claude/settings.local.json:122`

**Find:** `"Bash(ait crew *)"`
**Replace with:** `"Bash(./ait crew:*)"`

### 2. `seed/claude_settings.local.json`

Add `"Bash(./ait crew:*)"` next to the existing `"Bash(./ait git:*)"` entry (line 27).

### 3. `.gemini/policies/aitasks-whitelist.toml`

Append a `[[rule]]` block near the existing `./ait git` rule (line 489):

```toml
[[rule]]
toolName = "run_shell_command"
commandPrefix = "./ait crew"
decision = "allow"
priority = 100
```

### 4. `seed/geminicli_policies/aitasks-whitelist.toml`

Mirror the runtime gemini block (same `[[rule]]` content) near line 519.

### 5. `seed/opencode_config.seed.json`

Add `"./ait crew *": "allow"` near the existing `"./ait git *"` entry (line 16).

## Verification

```bash
grep "ait crew" .claude/settings.local.json seed/claude_settings.local.json \
                 .gemini/policies/aitasks-whitelist.toml \
                 seed/geminicli_policies/aitasks-whitelist.toml \
                 seed/opencode_config.seed.json
```

Expected: exactly the canonical entry per agent and no remaining malformed `"Bash(ait crew *)"` entry.

Sanity-check: an `ait crew` command in this Claude Code session should not trigger a permission prompt.

## Notes for sibling tasks

This child does NOT touch any brainstorm template or `aitask_crew_addwork.sh` — the heartbeat work in t650_2 / t650_3 is independent.

## Step 9 reference

Post-implementation: per task-workflow Step 9, archive child + plan via `./.aitask-scripts/aitask_archive.sh 650_1`. Parent t650 will be archived automatically once all three children complete.

## Final Implementation Notes

- **Actual work done:** Applied the planned 5-touchpoint edits exactly as designed:
  1. `.claude/settings.local.json:122` — replaced malformed `"Bash(ait crew *)"` with canonical `"Bash(./ait crew:*)"`.
  2. `seed/claude_settings.local.json` — added `"Bash(./ait crew:*)"` next to the existing `"Bash(./ait git:*)"` entry (line 27 → new entry at line 28).
  3. `.gemini/policies/aitasks-whitelist.toml` — appended a `[[rule]]` block for `commandPrefix = "./ait crew"` directly after the `./ait git` rule (new block at line 493).
  4. `seed/geminicli_policies/aitasks-whitelist.toml` — mirrored the runtime gemini block (new block at line 523).
  5. `seed/opencode_config.seed.json` — added `"./ait crew *": "allow"` next to `"./ait git *"` (line 16 → new entry at line 17).
- **Deviations from plan:** None. All edits matched the plan verbatim.
- **Issues encountered:** None.
- **Key decisions:** None — followed the dispatcher-verb-level whitelist convention already established for `./ait git` and `./ait codeagent`.
- **Verification result:** Final `grep "ait crew"` across the 5 touchpoints showed exactly one canonical entry per file, with the malformed entry gone:
  - `.claude/settings.local.json:122: "Bash(./ait crew:*)"`
  - `seed/claude_settings.local.json:28: "Bash(./ait crew:*)",`
  - `.gemini/policies/aitasks-whitelist.toml:495: commandPrefix = "./ait crew"`
  - `seed/geminicli_policies/aitasks-whitelist.toml:525: commandPrefix = "./ait crew"`
  - `seed/opencode_config.seed.json:17: "./ait crew *": "allow",`
- **Notes for sibling tasks:** This child only touched whitelist files — no brainstorm/heartbeat code paths were modified. The heartbeat fixes in t650_2 / t650_3 remain independent and can proceed without coordination. The fact that the runtime claude entry was malformed (no `./` prefix, wrong `:*` style) explains the symptom-level intermittence the user observed — fixing the format is what closes the prompt loop in addition to seeding the canonical entry into the 4 missing locations.
