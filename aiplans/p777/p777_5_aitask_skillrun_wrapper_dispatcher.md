---
Task: t777_5_aitask_skillrun_wrapper_dispatcher.md
Parent Task: aitasks/t777_modular_pick_skill.md
Sibling Tasks: aitasks/t777/t777_*_*.md
Parent Plan: aiplans/p777_modular_pick_skill.md
Base branch: main
---

# Plan: t777_5 — `ait skillrun` wrapper + dispatcher + 5-touchpoint whitelist

## Scope

Wrapper that renders → exec's the agent with natural slash command. NO `claude -p` (per [[feedback_avoid_claude_p_for_skill_invocation]]). Supports `--profile-override <yaml>` for t777_17.

## Step Order

1. **Write `aitask_skillrun.sh`** — args, autodetect agent (`$AIT_AGENT` → PATH), autodetect profile via t777_1 resolver, render via t777_2, exec agent with `'/<skill>-<profile> <args>'`. `--profile-override` merges + deletes override file after render. `--dry-run` prints commands without exec.
2. **Add `skillrun)` case** in `./ait`.
3. **Update `show_usage`** in `./ait` to mention `skillrun`.
4. **5-touchpoint whitelist** for `aitask_skillrun.sh`.

## Critical Files

- `.aitask-scripts/aitask_skillrun.sh` (new)
- `./ait` (modify)
- 5 whitelist files

## Pitfalls

- **Per-agent launch syntax** — verify exact CLI syntax for codex/gemini/opencode (claude is `claude '/skill args'`); they may differ.
- **`--profile-override` semantics** — the override is applied ONLY for this invocation; do not write to the project profile YAML.
- **No `claude -p`** — strict rule per memory.

## Verification

See task description. Smoke-test all 4 agents end-to-end after t777_6.
