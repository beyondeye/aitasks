---
priority: medium
effort: low
depends: []
issue_type: chore
status: Ready
labels: [installation, claudeskills, permissions]
created_at: 2026-04-28 12:29
updated_at: 2026-04-28 12:29
---

Spawned by t697's analysis. Two helper scripts — `aitask_add_model.sh` and `aitask_refresh_code_models.sh` — currently lack `commandPrefix` / `Bash(...)` whitelist entries in **all 5 helper-script touchpoints** named by CLAUDE.md "Adding a New Helper Script" (lines 82–96). The gemini policy files have `activate_skill` argsPattern rules for the *skill names* (`.gemini/policies/aitasks-whitelist.toml:585` and `:669`) but no matching helper-script `commandPrefix` rules — so framework developers in source hit a permission prompt on every invocation.

This is independent of t697's main thrust. Even though sibling task t700 will eventually filter both skills out of *user* installs, source-repo developers need the whitelist coverage now.

## Scope

For each of `aitask_add_model.sh` and `aitask_refresh_code_models.sh`, add an entry in:

1. `.claude/settings.local.json` — `"Bash(./.aitask-scripts/<name>.sh:*)"` in `permissions.allow`
2. `.gemini/policies/aitasks-whitelist.toml` — `[[rule]]` block with `commandPrefix = "./.aitask-scripts/<name>.sh"` and `decision = "allow"`
3. `seed/claude_settings.local.json` — mirror of #1
4. `seed/geminicli_policies/aitasks-whitelist.toml` — mirror of #2
5. `seed/opencode_config.seed.json` — `"./.aitask-scripts/<name>.sh *": "allow"` entry

Codex exception (CLAUDE.md:94) — prompt-only, no allow entry needed.

## How to verify scope

Run `./.aitask-scripts/aitask_audit_wrappers.sh` (the canonical audit script for this matrix) to confirm the precise gap before applying changes, and re-run after to confirm closure.

## References

- CLAUDE.md "Adding a New Helper Script" (lines 82–96) — the canonical 5-touchpoint table.
- t691_1 archived plan — landed identical whitelisting for `aitask_audit_wrappers.sh`; mirror its pattern.
- `aiplans/archived/p697_*.md` Part 1 — confirms the 0/5 gap for both helpers.

## Verification

After the edits, re-run `./.aitask-scripts/aitask_audit_wrappers.sh` and confirm both helpers report green across the 5 surfaces. Optionally run the install-flow harness with `--include-dev` (or whatever opt-in mechanism t700 lands) to confirm the entries propagate to user installs that explicitly request dev tools.
