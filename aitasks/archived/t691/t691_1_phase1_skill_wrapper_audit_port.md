---
priority: high
effort: high
depends: []
issue_type: feature
status: Done
labels: [claudeskills]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_7_1m
created_at: 2026-04-28 11:06
updated_at: 2026-04-28 11:25
completed_at: 2026-04-28 11:25
---

## Context

Implements Phase 1 of `aitask-audit-wrappers` (parent t691): the wrapper-tree audit + port phase that scans the source-of-truth Claude skills and ensures every code-agent tree has a matching wrapper. Self-bootstraps the new skill's own wrappers (since the helper would not yet exist on first run), then runs the helper to close the documented Phase-1 gaps.

Phase 2 (helper-script whitelist audit) is a separate child task (t691_2).

## Authoritative gap matrix (verified 2026-04-28, must close in this child)

| Skill | `.gemini/commands` | `.agents/skills` | `.opencode/skills` | `.opencode/commands` | gemini policy runtime | gemini policy seed |
|---|:-:|:-:|:-:|:-:|:-:|:-:|
| aitask-add-model | MISSING | MISSING | MISSING | MISSING | MISSING | MISSING |
| aitask-contribution-review | OK | OK | OK | OK | MISSING | OK |
| aitask-qa | OK | OK | OK | MISSING | MISSING | MISSING |

## Key files to modify

**New:**
- `.claude/skills/aitask-audit-wrappers/SKILL.md` (~200 lines, modeled on aitask-add-model + aitask-refresh-code-models)
- `.aitask-scripts/aitask_audit_wrappers.sh` (~450 LOC bash, Phase 1 subcommands only)
- `.gemini/commands/aitask-add-model.toml` (gap closure)
- `.gemini/commands/aitask-audit-wrappers.toml` (self-bootstrap)
- `.agents/skills/aitask-add-model/SKILL.md` (gap closure)
- `.agents/skills/aitask-audit-wrappers/SKILL.md` (self-bootstrap)
- `.opencode/skills/aitask-add-model/SKILL.md` (gap closure)
- `.opencode/skills/aitask-audit-wrappers/SKILL.md` (self-bootstrap)
- `.opencode/commands/aitask-add-model.md` (gap closure)
- `.opencode/commands/aitask-qa.md` (gap closure)
- `.opencode/commands/aitask-audit-wrappers.md` (self-bootstrap)

**Edit:**
- `.gemini/policies/aitasks-whitelist.toml` — 5 inserts (3 gap-closure activate_skill rules + 1 self-bootstrap activate_skill rule + 1 helper-whitelist `commandPrefix` rule)
- `seed/geminicli_policies/aitasks-whitelist.toml` — 4 inserts (2 gap-closure activate_skill rules: aitask-add-model + aitask-qa; + 1 self-bootstrap activate_skill rule + 1 helper-whitelist `commandPrefix` rule). aitask-contribution-review already in seed.
- `.claude/settings.local.json` — add `Bash(./.aitask-scripts/aitask_audit_wrappers.sh:*)` to `permissions.allow`
- `seed/claude_settings.local.json` — mirror
- `seed/opencode_config.seed.json` — `"./.aitask-scripts/aitask_audit_wrappers.sh *": "allow"`
- `CLAUDE.md` — update Codex CLI commands location sentence: `.codex/prompts/` does not exist; codex shares `.agents/skills/` with gemini.

## Reference files for patterns

- `.claude/skills/aitask-add-model/SKILL.md` — closest workflow shape (CLI args → validate → dry-run → confirm → apply → commit).
- `.claude/skills/aitask-refresh-code-models/SKILL.md` — scan→report→selective-apply pattern.
- `.aitask-scripts/lib/task_utils.sh:249` — `read_yaml_field()` and `format_yaml_list()` for YAML frontmatter (do NOT write a new parser).
- `.aitask-scripts/lib/terminal_compat.sh` — `die`/`warn`/`info`/`success` helpers; `sed_inplace` portability wrapper.
- `.aitask-scripts/aitask_fold_validate.sh` — `VALID:`/`INVALID:` structured output exemplar.
- `.aitask-scripts/aitask_archive.sh` — `ISSUE:`/`PR:`/`COMMITTED:` structured output exemplar.
- Existing wrapper templates (the file shown in each tree IS the template):
  - `.gemini/commands/aitask-stats.toml`
  - `.agents/skills/aitask-stats/SKILL.md`
  - `.opencode/skills/aitask-stats/SKILL.md`
  - `.opencode/commands/aitask-stats.md`

## Implementation plan

1. **Helper script `aitask_audit_wrappers.sh`** with these subcommands (all exit 0 unless catastrophic):
   - `discover` → emit `GAP:<tree>:<skill_name>` lines for each missing wrapper across the 4 trees.
   - `discover-policy` → emit `POLICY_GAP:<runtime|seed>:<skill_name>` for each missing `activate_skill` rule in either gemini policy.
   - `render-wrapper <tree> <skill_name>` → write template to stdout for one of: `gemini`, `agents`, `opencode-skill`, `opencode-command`. Templates inline as heredocs. Pulls `description` from `.claude/skills/<skill_name>/SKILL.md` frontmatter via `read_yaml_field`.
   - `apply-wrapper <tree> <skill_name>` [`--force`] → write the rendered wrapper to its canonical path. Refuses to overwrite existing files unless `--force`. Emits `WROTE:<path>` on success.
   - `apply-policy <runtime|seed> <skill_name>` → insert a new `[[rule]]` block at the alphabetical position via `awk`. Emits `WROTE:<path>:<line>`.
   - `--help` mirror of other helpers.
2. **Frontmatter description extraction.** Use `read_yaml_field "$skill_md" "description"`. For OpenCode/Codex `## Arguments` summary, grep the source SKILL.md for the first paragraph under `## Usage` or `## Arguments`. If nothing found, emit `ARGS_AMBIGUOUS:<skill_name>` so the SKILL.md surfaces it for user confirmation.
3. **SKILL.md `aitask-audit-wrappers/SKILL.md`** workflow:
   - Step 1: parse CLI args (`--phase=skills|whitelist|all` reserved for child 2; this child supports `--phase=skills` only).
   - Step 2: run `discover` + `discover-policy`. Print matrix.
   - Step 3: per-gap show diff (run `render-wrapper` and a 2-line preview), collect approval via `AskUserQuestion` (multiSelect).
   - Step 4: apply approved fixes via `apply-wrapper` / `apply-policy`. Show `WROTE:` lines.
   - Step 5: commit. Two commits required:
     - Code commit (`git add` + `git commit`): all wrapper files + policy edits + helper script + CLAUDE.md fix.
     - No plan commit needed when the skill is invoked freestanding (this child's plan commit goes via `./ait git`).
   - Step 6: re-run discover; refuse to exit if non-zero output (idempotency assertion).
4. **Self-bootstrap.** Hand-write the four wrappers and two policy entries for `aitask-audit-wrappers` itself. Use the wrapper templates above with description `"Audit and port aitask skill wrappers across code-agent trees, plus helper-script whitelist coverage."`.
5. **5-touchpoint helper whitelist.** Add `aitask_audit_wrappers.sh` to all 5 touchpoints (claude/local + claude/seed + gemini/runtime + gemini/seed + opencode/seed). Insert at alphabetical position relative to existing `aitask_*.sh` entries.
6. **First-run gap closure.** Manually invoke the helper subcommands (or hand-write the 5 missing wrappers + 5 policy inserts) so the resulting tree has zero `GAP:` and zero `POLICY_GAP:` output.
7. **CLAUDE.md fix.** Edit the "Codex CLI" subsection of "WORKING ON SKILLS / CUSTOM COMMANDS" to reflect that codex commands live in `.agents/skills/` (consolidated with gemini), not `.codex/prompts/`.

## Verification steps

1. `bash tests/test_opencode_setup.sh` — pass (counts auto-adjust).
2. `bash tests/test_gemini_setup.sh` — pass (activate_skill counts grow by 4 in seed).
3. `bash .aitask-scripts/aitask_audit_wrappers.sh discover` — empty output.
4. `bash .aitask-scripts/aitask_audit_wrappers.sh discover-policy` — empty output.
5. `shellcheck .aitask-scripts/aitask_audit_wrappers.sh` — clean.
6. Spot-check files exist:
   ```bash
   ls .opencode/skills/aitask-add-model/SKILL.md \
      .agents/skills/aitask-add-model/SKILL.md \
      .gemini/commands/aitask-add-model.toml \
      .opencode/commands/aitask-add-model.md \
      .opencode/commands/aitask-qa.md \
      .opencode/commands/aitask-audit-wrappers.md \
      .agents/skills/aitask-audit-wrappers/SKILL.md \
      .opencode/skills/aitask-audit-wrappers/SKILL.md \
      .gemini/commands/aitask-audit-wrappers.toml
   ```
7. Confirm both gemini policy files contain `activate_skill` rules for aitask-add-model, aitask-contribution-review, aitask-qa, aitask-audit-wrappers.
