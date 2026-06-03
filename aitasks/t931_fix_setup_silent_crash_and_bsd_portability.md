---
priority: high
effort: low
depends: []
issue_type: bug
status: Ready
labels: [ait_setup, macos, bash_scripts, execution_profiles]
created_at: 2026-06-03 16:45
updated_at: 2026-06-03 16:45
---

Fix macOS/BSD portability bugs in framework shell scripts surfaced while running `ait setup`.

## Symptoms
- `ait setup` silently aborted right after "Merged aitask permissions into .claude/settings.local.json" — it never printed the final "Setup complete!" + Summary banner, but gave no error, so it looked like it might have succeeded. Reproduced on multiple macOS systems.
- The recommended-permissions list printed with garbled trailing `",` on every line (e.g. `Bash(ls:*)",`).
- `aitask_skill_resolve_profile.sh` threw `awk: syntax error` and exited 2, breaking every profile-aware skill on macOS.

## Root causes (all BSD/macOS portability)
1. **Silent setup crash.** `assemble_aitasks_instructions` read the shared instructions seed only from `aitasks/metadata/aitasks_agent_instructions.seed.md`, which legacy / non-data-branch installs never populate (the seed ships in `seed/`). It did `warn; return 1`, but the warn was emitted inside a `$(...)` capture in the caller (so it was swallowed, hence no visible error), and `update_agentsmd`'s `|| return` propagated the non-zero status under `set -euo pipefail`, aborting the whole script before the success banner.
2. **Garbled display.** The permission preview used `sed 's/",\?$//'`; BSD/macOS sed does not support the `\?` quantifier in BRE, so the trailing `",` was never stripped.
3. **Resolver awk crash.** The profile resolver used the 3-argument `match(str, re, arr)` capture-array form, a GNU awk extension that is a hard syntax error under BSD/macOS awk.

## Fixes
- `aitask_setup.sh`:
  - `assemble_aitasks_instructions` now falls back to `seed/` for both the shared layer and the agent-specific layer when the `aitasks/metadata/` copy is absent.
  - The "seed not found" warning is emitted to stderr so it survives callers' command substitution.
  - `update_agentsmd` and `update_claudemd_git_section` are now best-effort (`|| return 0`) so a missing seed can never silently abort setup again (matching the codex/opencode siblings that already used `|| true`).
  - Permission-list preview switched to `sed -E 's/",?$//'`.
- `aitask_skill_resolve_profile.sh`: rewrote the YAML value extraction to use only POSIX awk (`~`, `sub()`, `substr()`) instead of the gawk-only 3-arg `match()`.
- `tests/test_agent_instructions.sh`: added T9b/T9c regression tests covering the `seed/` fallback (shared + agent-specific). Full suite 86/86.

## Notes
- This is the framework's Claude Code source of truth. Follow-up tasks should port the equivalent portability fixes to the Codex CLI (`.agents/skills/`) and OpenCode (`.opencode/`) trees if they carry their own copies of the resolver logic.
