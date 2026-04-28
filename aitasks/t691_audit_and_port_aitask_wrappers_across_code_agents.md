---
priority: medium
effort: high
depends: []
issue_type: feature
status: Ready
labels: [claudeskills]
children_to_implement: [t691_2, t691_3]
folded_tasks: [689]
created_at: 2026-04-28 08:35
updated_at: 2026-04-28 11:25
boardidx: 110
---

Spawned from /aitask-explore on 2026-04-28. Builds on t679 (dynamic skill counting in tests). Folds in t689 (manual one-off port that this skill should produce automatically when run on the current tree).

## Goal

Build a new user-invokable Claude skill (e.g. `aitask-audit-wrappers`) that automates the audit-and-port workflow described in CLAUDE.md "WORKING ON SKILLS / CUSTOM COMMANDS". When run, it scans the source-of-truth (`.claude/skills/aitask-*/SKILL.md`), ensures the corresponding wrappers exist in every supported code-agent tree, and generates any missing wrappers from templates. It also has a second phase that audits whitelist coverage of helper scripts invoked by framework skills, across all 5 touchpoints from CLAUDE.md "Adding a New Helper Script". Both phases are gated by user review and produce an audit task file, commit, and archive following the same conventions as the standard task-workflow.

## Scope: user-invokable `aitask-*` skills only

Library skills (`task-workflow`, `user-file-select`, `ait-git`) are out of scope per user direction — they are referenced by other skills but are not user-invokable slash commands.

## Today's coverage matrix (snapshot at 2026-04-28)

Source of truth: `.claude/skills/` — 25 entries (22 user-invokable `aitask-*` + 3 library skills out of scope).

| Agent | Wrapper location | Count | Today's gaps |
|---|---|---|---|
| Gemini CLI | `.gemini/commands/*.toml` | 21 | `aitask-add-model` |
| Codex CLI | `.agents/skills/<name>/SKILL.md` (consolidated, no `.codex/prompts/`) | 21 aitask-* (+ 4 helper docs) | `aitask-add-model` |
| OpenCode | `.opencode/skills/<name>/SKILL.md` | 21 | `aitask-add-model` |
| OpenCode | `.opencode/commands/<name>.md` | 20 | `aitask-add-model`, `aitask-qa` |

Documentation note: CLAUDE.md "Codex CLI" section mentions `.codex/prompts/` as the codex commands location, but the runtime tree only contains `.codex/config.toml` and `.codex/instructions.md`. Codex effectively shares its skills with Gemini via `.agents/skills/`. The new skill's own documentation should reflect the actual layout, and the implementer should fix the CLAUDE.md sentence as part of this work.

## Phase 1 — Skill/command wrapper audit and port

For each user-invokable `aitask-*` skill in `.claude/skills/`, ensure all four wrappers exist:

- `.gemini/commands/<name>.toml`
- `.agents/skills/<name>/SKILL.md`
- `.opencode/skills/<name>/SKILL.md`
- `.opencode/commands/<name>.md`

### Wrapper templates (derived from `aitask-stats` reference example)

**Gemini `.gemini/commands/<name>.toml`:**

```toml
description = "<from claude SKILL.md frontmatter>"
prompt = """

@.gemini/skills/geminicli_tool_mapping.md

Execute the following Claude Code skill. Follow each step precisely, translating tool references per the mapping above.

Arguments: {{args}}

@.claude/skills/<name>/SKILL.md
"""
```

**Codex `.agents/skills/<name>/SKILL.md`:**

```markdown
---
name: <name>
description: <from claude SKILL.md frontmatter>
---

## Source of Truth

This is a unified skill wrapper for Codex CLI and Gemini CLI. The authoritative skill definition is:

**`.claude/skills/<name>/SKILL.md`**

Read that file and follow its complete workflow.

**If you are Codex CLI:** For tool mapping and adaptations, read **`.agents/skills/codex_tool_mapping.md`**.

**If you are Gemini CLI:** For tool mapping and adaptations, read **`.agents/skills/geminicli_tool_mapping.md`**.

## Arguments

<short summary inferred from claude SKILL.md "## Usage" or "## Arguments" section>
```

**OpenCode `.opencode/skills/<name>/SKILL.md`:**

```markdown
---
name: <name>
description: <from claude SKILL.md frontmatter>
---

## Source of Truth

This is an OpenCode wrapper. The authoritative skill definition is:

**`.claude/skills/<name>/SKILL.md`**

Read that file and follow its complete workflow. For tool mapping and
OpenCode adaptations, read **`.opencode/skills/opencode_tool_mapping.md`**.

## Arguments

<short summary>
```

**OpenCode `.opencode/commands/<name>.md`:**

```markdown
---
description: <from claude SKILL.md frontmatter>
---

@.opencode/skills/opencode_tool_mapping.md

Execute the following Claude Code skill. Follow each step precisely, translating tool references per the mapping above.

Arguments: $ARGUMENTS

@.claude/skills/<name>/SKILL.md
```

The `description` is verbatim from the Claude SKILL.md frontmatter. The `Arguments` line in Codex/OpenCode SKILL.md is the only soft-extracted field — auto-summarize from Claude `## Usage`/`## Arguments` sections; if extraction is ambiguous, surface for user confirmation per gap before writing.

### Per-skill Gemini whitelist (part of Phase 1)

For each newly-added skill wrapper, add the gemini activation rule:

```toml
[[rule]]
toolName = "activate_skill"
argsPattern = "<skill-name>"
decision = "allow"
priority = 100
```

Insert at the alphabetical position. Touch BOTH:
- `.gemini/policies/aitasks-whitelist.toml` (runtime)
- `seed/geminicli_policies/aitasks-whitelist.toml` (seed mirror)

Codex uses a prompt-only model; Claude self-registers from SKILL.md; OpenCode commands self-register — no per-skill allowlist needed for those three.

## Phase 2 — Helper-script whitelist audit (runnable independently)

### Discovery

Parse every `.claude/skills/aitask-*/SKILL.md` (user-invokable scope) for `.aitask-scripts/aitask_*.sh` invocations. The set of helpers actually invoked by framework skills is the audit scope — narrower than "every script in `.aitask-scripts/`" because only what skills actually use needs whitelisting.

### Audit

For each invoked helper, check coverage across all 5 touchpoints from CLAUDE.md "Adding a New Helper Script":

| # | Touchpoint | Entry shape |
|---|---|---|
| 1 | `.claude/settings.local.json` | `"Bash(./.aitask-scripts/<name>.sh:*)"` in `permissions.allow` |
| 2 | `.gemini/policies/aitasks-whitelist.toml` | `[[rules]]` block with `commandPrefix = "./.aitask-scripts/<name>.sh"` |
| 3 | `seed/claude_settings.local.json` | mirror of #1 |
| 4 | `seed/geminicli_policies/aitasks-whitelist.toml` | mirror of #2 |
| 5 | `seed/opencode_config.seed.json` | `"./.aitask-scripts/<name>.sh *": "allow"` |

Codex `.codex/config.toml` exception: prompt-only model — no allow entry.

### Auto-fix (with user review)

For every helper missing from any seed whitelist, the skill must auto-update the seed whitelist for ALL supported code agents (gemini seed, opencode seed, claude seed). Runtime whitelists are updated to match. Each proposed write is shown to the user for review/confirm before being committed.

This guarantees that fresh installs (`install.sh` → `ait setup`) get the right permissions baked in — closing the root cause of past friction where users were prompted on every helper invocation.

## Workflow / UX (model after task-workflow)

1. **Discovery:** scan source of truth + each agent tree; build coverage matrix for both phases.
2. **Report:** present matrix + concrete gaps. User chooses Phase 1, Phase 2, or both.
3. **Generation:** for each gap, generate the wrapper / whitelist entry from the templates above; show diff to user; collect approval.
4. **Task file:** auto-create an `aitasks/tNNN_*.md` documenting the audit run (analogous to t689's structure — gap matrix, touchpoints to add, verification commands).
5. **Commit:** group per phase (or per skill), using the conventional commit message format from CLAUDE.md "Commit Message Format" section.
6. **Archive:** follow the standard task-workflow archival path so the audit task ends up in `aitasks/archived/`.
7. **Verification:** run `bash tests/test_opencode_setup.sh` and `bash tests/test_gemini_setup.sh` — counts auto-adjust per t679 (no test edits needed).

## Self-bootstrap consideration

The new skill is itself an `aitask-*` Claude skill. Its first run on the tree where it is just being introduced should produce wrappers for itself (in gemini, codex, opencode trees) — the implementation must support self-porting on first run, not assume the wrappers already exist for it.

## Open decisions for the implementer

- Skill name: `aitask-audit-wrappers` vs `aitask-port-wrappers` vs another naming. Pick one consistent with the rest of the `aitask-*` family.
- Phase selection UX: `--phase=skills|whitelist|all` flag, or always run both phases with a confirmation gate per phase?
- Implementation language: bash (consistent with `.aitask-scripts/` helpers and the rest of the framework) or python (easier for templating multi-format wrappers, like the board TUI). Bash is closer to the existing convention; both viable.

## Verification

After implementation, the skill is self-verifying. A run on the current tree must:

1. Detect the same 2 gaps t689 documents (`aitask-add-model` everywhere, `aitask-qa` in opencode commands), close them, and produce a task file equivalent to t689 in structure.
2. `tests/test_opencode_setup.sh` and `tests/test_gemini_setup.sh` pass post-generation without test edits (counts self-adjust per t679).
3. Run again immediately after — should report zero gaps (idempotent).

## References

- t679 (archived) — dynamic skill counting in tests; foundation for self-adjusting verification
- t689 (folded into this task) — manual one-off port that this skill should automate
- CLAUDE.md "WORKING ON SKILLS / CUSTOM COMMANDS"
- CLAUDE.md "Adding a New Helper Script" (5-touchpoint table)

## Merged from t689: port aitask add model qa wrappers to non claude


Spawned from t679 during planning. Two skills added to `.claude/skills/` (the source of truth) were never propagated to the other agent trees, per the CLAUDE.md "WORKING ON SKILLS / CUSTOM COMMANDS" rule that says cross-agent ports should be tracked as separate tasks.

## Cross-agent skill gap

| Skill | `.claude/skills` | `.opencode/skills` | `.agents/skills` (codex) | `.opencode/commands` | `.gemini/commands` | gemini policy `activate_skill` |
|---|:-:|:-:|:-:|:-:|:-:|:-:|
| `aitask-add-model` | YES | — | — | — | — | — |
| `aitask-qa` | YES | YES | YES | — | YES | — |
| (other 20 `aitask-*`) | YES | YES | YES | YES | YES | YES |

Note: `.gemini/skills/` is intentionally empty (consolidated into `.agents/skills/` per `tests/test_gemini_setup.sh:41`).

## Touchpoints to add

### `aitask-add-model` (missing from every non-claude tree)

- `.opencode/skills/aitask-add-model/SKILL.md` — adapt from `.claude/skills/aitask-add-model/SKILL.md`.
- `.opencode/commands/aitask-add-model.md` — mirror existing wrappers (e.g. `.opencode/commands/aitask-create.md`).
- `.agents/skills/aitask-add-model/SKILL.md` — adapt from `.claude/skills/aitask-add-model/SKILL.md`.
- `.gemini/commands/aitask-add-model.toml` — mirror existing toml wrappers.
- `seed/geminicli_policies/aitasks-whitelist.toml` — add a `[[rule]]` block:
  ```toml
  [[rule]]
  toolName = "activate_skill"
  argsPattern = "aitask-add-model"
  decision = "allow"
  priority = 100
  ```
  Insert at the alphabetical position between `argsPattern = "aitask-changelog"` and `argsPattern = "aitask-contribute"`.

### `aitask-qa` (missing from opencode commands and gemini policy)

- `.opencode/commands/aitask-qa.md` — mirror existing wrappers.
- `seed/geminicli_policies/aitasks-whitelist.toml` — add a `[[rule]]` block for `argsPattern = "aitask-qa"` between `aitask-pr-import` and `aitask-refresh-code-models` (or wherever alphabetical).

The opencode skill, codex skill, and gemini command for `aitask-qa` already exist.

## Whitelisting touchpoints

Verify any helper-script paths inside the new SKILL.md files are already whitelisted across all five touchpoints listed in CLAUDE.md "Adding a New Helper Script". For these two skills, no new helper scripts should be needed — just wrappers around existing helpers.

## Verification

After the wrappers are added:

```bash
bash tests/test_opencode_setup.sh   # expect counts to grow by 2 (skill + command)
bash tests/test_gemini_setup.sh     # expect activate_skill count to grow by 2
```

Both tests now use dynamic counts (committed in t679), so the assertions self-adjust — no test edits needed.

Spot-check the new entries are present:

```bash
ls -d .opencode/skills/aitask-add-model .agents/skills/aitask-add-model
ls .opencode/commands/aitask-add-model.md .opencode/commands/aitask-qa.md
ls .gemini/commands/aitask-add-model.toml
grep -c '^toolName = "activate_skill"$' seed/geminicli_policies/aitasks-whitelist.toml   # was 20, expect 22
```

## Folded Tasks

The following existing tasks have been folded into this task. Their requirements are incorporated in the description above. These references exist only for post-implementation cleanup.

- **t689** (`t689_port_aitask_add_model_qa_wrappers_to_non_claude.md`)
