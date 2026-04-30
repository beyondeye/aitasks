---
priority: medium
effort: high
depends: []
issue_type: feature
status: Ready
labels: [installation, install_scripts, claudeskills]
created_at: 2026-04-28 12:29
updated_at: 2026-04-28 12:29
boardidx: 120
---

Spawned by t697's analysis. Implement the recommended dev-only filtering mechanism: a `audience: developers` frontmatter flag in `SKILL.md` files, plus install-time filtering in `install.sh` that drops dev-only skills, their helper scripts, and their whitelist entries from the user install. See `aiplans/archived/p697_*.md` Final Implementation Notes for the full analysis and rationale.

## Scope

1. **Document the field.** Add an `audience` frontmatter field entry to CLAUDE.md "Skill / Workflow Authoring Conventions". Allowed values: `developers` (filtered out of user installs) or absent (default — end-user, ships normally). Document the rationale and the install-time behavior.

2. **Mark the confirmed dev-only set** with `audience: developers` in their `SKILL.md` files:
   - `.claude/skills/aitask-add-model/SKILL.md`
   - `.claude/skills/aitask-audit-wrappers/SKILL.md`
   - `.claude/skills/aitask-refresh-code-models/SKILL.md`
   - All four mirror trees per skill: `.agents/skills/<name>/SKILL.md`, `.opencode/skills/<name>/SKILL.md`. The `.opencode/commands/<name>.md` and `.gemini/commands/<name>.toml` wrappers don't need the flag — they're filtered by their underlying skill name.

3. **Extend `install.sh`** to:
   - Scan each `.claude/skills/*/SKILL.md`, `.agents/skills/*/SKILL.md`, `.opencode/skills/*/SKILL.md` for `^audience: developers$` (literal grep — bash-only, no YAML parser needed).
   - For each match: exclude the skill directory; record the skill name; exclude `.opencode/commands/<name>.md` and `.gemini/commands/<name>.toml` whose `<name>` matches.
   - Inspect each excluded `SKILL.md` for the helper script(s) it references (e.g., `./.aitask-scripts/aitask_<name>.sh`); add those to an exclusion set; skip them when copying `.aitask-scripts/`.
   - Strip the corresponding whitelist entries from `claude_settings.local.json`, the gemini `aitasks-whitelist.toml` (`commandPrefix` AND the `activate_skill` argsPattern entries), and `opencode_config.seed.json` *before* writing them into the user project.
   - Add a `--include-dev` opt-in flag that bypasses all the filtering above (for power users / framework maintainers using `install.sh` to populate a dev clone).

4. **Test** via the install-flow harness per CLAUDE.md "Test the full install flow for setup helpers": run `bash install.sh --dir /tmp/scratchXY` end-to-end and verify:
   - `.claude/skills/aitask-add-model/`, `aitask-audit-wrappers/`, `aitask-refresh-code-models/` are absent in `/tmp/scratchXY/.claude/skills/`.
   - The matching `.agents/skills/`, `.opencode/skills/`, `.opencode/commands/`, `.gemini/commands/` files are absent.
   - `.aitask-scripts/aitask_add_model.sh`, `aitask_audit_wrappers.sh`, `aitask_refresh_code_models.sh` are absent.
   - `.claude/settings.local.json`, the gemini policy file, and the opencode config in `/tmp/scratchXY/` have no entries for those helpers.
   - Same run with `--include-dev` produces all of them.

## References

- `aiplans/archived/p697_analyze_dev_only_skill_filtering_in_install_tarball.md` — full analysis and rationale (Final Implementation Notes).
- CLAUDE.md "Adding a New Helper Script" — 5-touchpoint matrix this task must filter.
- t624 / t628 archived plans — fresh-install testing pattern.
- t691_1 archived plan — canonical example of helper-script whitelisting (the inverse operation this task suppresses at install time).

## Out of scope

- Whitelisting `aitask_add_model.sh` and `aitask_refresh_code_models.sh` in the source repo's 5 surfaces (separate sibling task: see Follow-up B).
- Any change to `aitask-changelog` (classified end-user; keep shipping to user installs).

## Verification

Run the install-flow harness above. Diff the output `/tmp/scratchXY/` tree against a baseline `--include-dev` run to confirm only the dev-only artifacts and their whitelist entries differ.
