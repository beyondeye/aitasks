---
priority: medium
effort: medium
depends: [t691_1]
issue_type: feature
status: Ready
labels: [claudeskills]
created_at: 2026-04-28 11:06
updated_at: 2026-04-28 11:06
---

## Context

Implements Phase 2 of `aitask-audit-wrappers` (parent t691). Extends the helper script and SKILL.md created in t691_1 with helper-script whitelist auditing across the 5 touchpoints from CLAUDE.md "Adding a New Helper Script". Detects which `.aitask-scripts/aitask_*.sh` helpers are referenced from `.claude/skills/aitask-*/SKILL.md` and verifies coverage in each agent's permission system.

Depends on t691_1 (Phase 1 must be complete; the helper script and SKILL.md must exist).

## The 5 touchpoints (from CLAUDE.md "Adding a New Helper Script")

| # | Touchpoint | Entry shape |
|---|---|---|
| 1 | `.claude/settings.local.json` | `"Bash(./.aitask-scripts/<name>.sh:*)"` in `permissions.allow` |
| 2 | `.gemini/policies/aitasks-whitelist.toml` | `[[rule]]` block with `commandPrefix = "./.aitask-scripts/<name>.sh"` |
| 3 | `seed/claude_settings.local.json` | mirror of #1 |
| 4 | `seed/geminicli_policies/aitasks-whitelist.toml` | mirror of #2 |
| 5 | `seed/opencode_config.seed.json` | `"./.aitask-scripts/<name>.sh *": "allow"` |

Codex `.codex/config.toml` is prompt-only — no allow entry needed.

## Key files to modify

**Edit:**
- `.aitask-scripts/aitask_audit_wrappers.sh` — add Phase 2 subcommands (discover-helpers, audit-helper-whitelist, apply-helper-whitelist).
- `.claude/skills/aitask-audit-wrappers/SKILL.md` — add Phase 2 workflow section: discovery output, AskUserQuestion gate (after Phase 1), per-helper diff display, batch apply, summary line.

## Reference files for patterns

- `.aitask-scripts/aitask_audit_wrappers.sh` (created in t691_1) — extend, do not rewrite.
- `.claude/skills/aitask-audit-wrappers/SKILL.md` (created in t691_1) — extend.
- `.aitask-scripts/aitask_install_merge.py` — for JSON deep-merge logic if needed (likely overkill here; prefer simple `jq` for JSON edits).
- `.aitask-scripts/lib/task_utils.sh` — re-use existing helpers.

## Implementation plan

1. **Discovery subcommand** `discover-helpers`:
   ```bash
   grep -hroE '\.aitask-scripts/aitask_[a-z_]+\.sh' .claude/skills/aitask-*/ \
     | sort -u
   ```
   Each unique basename emitted as `HELPER:<name>`.

2. **Audit subcommand** `audit-helper-whitelist <helper>`:
   - Touchpoint 1: `grep -q "Bash(\./\.aitask-scripts/${helper}:*)" .claude/settings.local.json` (escape `.` carefully).
   - Touchpoint 2: `grep -q "commandPrefix = \"./.aitask-scripts/${helper}\"" .gemini/policies/aitasks-whitelist.toml`.
   - Touchpoint 3: same as 1 against `seed/claude_settings.local.json`.
   - Touchpoint 4: same as 2 against `seed/geminicli_policies/aitasks-whitelist.toml`.
   - Touchpoint 5: `grep -q "\"./.aitask-scripts/${helper} \\*\": \"allow\"" seed/opencode_config.seed.json`.
   - For each missing one, emit `MISSING:<touchpoint>:<helper>`.

3. **Apply subcommand** `apply-helper-whitelist <helper>` `[--touchpoint N]`:
   - Format-aware insert: JSON entries via `jq`, TOML entries via `awk` at alphabetical position.
   - Emit `WROTE:<touchpoint>:<helper>:<file>` on each successful insert.

4. **SKILL.md Phase 2 section.** Append after the Phase 1 commit step:
   - Sub-step: run `discover-helpers`, then loop calling `audit-helper-whitelist <helper>`, collect all `MISSING:` lines.
   - Sub-step: AskUserQuestion: "Apply Phase 2 helper-whitelist fixes?" / "Skip Phase 2".
   - Sub-step: on apply, call `apply-helper-whitelist` for each missing entry; collect `WROTE:` lines; commit (separate commit from Phase 1).
   - Final summary block listing touchpoints touched.

5. **Phase-1 + Phase-2 confirmation flow.** Phase 1 confirmation gate triggers Phase 1 application; after that, Phase 2 discovery runs and presents its own gate. Edge case: if user skips Phase 1, Phase 2 still runs against the unchanged tree.

## Verification steps

1. `bash .aitask-scripts/aitask_audit_wrappers.sh discover-helpers` — outputs at least 10 helpers (the framework is non-trivial).
2. `bash .aitask-scripts/aitask_audit_wrappers.sh audit-helper-whitelist <each-helper>` — zero `MISSING:` lines on the current tree (after t691_1 closes Phase 1 gaps).
3. **Negative test:** delete one helper entry from `.claude/settings.local.json`, run audit, confirm it surfaces, run apply, confirm restored. Revert.
4. `bash tests/test_opencode_setup.sh` and `bash tests/test_gemini_setup.sh` — still pass.
5. `shellcheck .aitask-scripts/aitask_audit_wrappers.sh` — clean.

## Notes for sibling tasks

- Phase 1 (t691_1) lays down the helper + SKILL.md + Phase 1 subcommands. This child only extends.
- Web docs (t691_3) document both phases together — wait for this child to land before finalizing the docs.
