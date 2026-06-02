---
title: "/aitask-audit-wrappers"
linkTitle: "/aitask-audit-wrappers"
weight: 57
description: "Audit and port aitask skill wrappers across code-agent trees, plus helper-script whitelist coverage"
maturity: [experimental]
depth: [advanced]
---

Audit drift between the aitasks skill source-of-truth (`.claude/skills/aitask-*/SKILL.md`) and the code-agent wrapper trees, plus drift in helper-script whitelist coverage across the permission-system touchpoints. Generates missing wrappers from inline templates and inserts missing whitelist entries at the alphabetically-correct positions, with a per-phase user confirmation gate. Companion to [`/aitask-add-model`](../../skills/aitask-add-model/) — both are framework-development skills, useful when you are adding skills or helper scripts to the framework itself.

**Usage:**
```
/aitask-audit-wrappers
/aitask-audit-wrappers --phase=skills
/aitask-audit-wrappers --phase=whitelist
/aitask-audit-wrappers --phase=all
```

> **Note:** Must be run from the project root directory. See [Skills overview](..) for details.

## When to Use This Skill

After adding a new `.claude/skills/aitask-*/SKILL.md` to the framework, or a new `.aitask-scripts/aitask_*.sh` helper. Without an automated audit, drift between trees accumulates silently — earlier in the framework's history, manual one-off ports were the norm and gaps slipped through. This skill runs the same audit + port logic deterministically.

| Concern | Manual port | `/aitask-audit-wrappers` |
|---|---|---|
| Discovery | Hand-grep across trees | Automated (Phase 1: wrapper trees; Phase 2: helper-whitelist touchpoints) |
| Coverage matrix | Implicit | Structured `GAP:` / `MISSING:` output |
| Apply | Hand-write each wrapper | Inline templates rendered from source-of-truth `description` field |
| Idempotency check | None | Re-run discovery; refuses to declare success if anything remains |

## Phase 1 — Skill wrapper audit and port

Scans every `.claude/skills/aitask-*/SKILL.md` and ensures the per-agent wrappers exist:

- `.agents/skills/<name>/SKILL.md` — Codex CLI (and other shared-root agents) skill wrapper.
- `.opencode/skills/<name>/SKILL.md` — OpenCode skill wrapper.
- `.opencode/commands/<name>.md` — OpenCode command wrapper.

For each gap, the helper renders a wrapper from inline templates (description auto-extracted from the source-of-truth SKILL.md frontmatter via `read_yaml_field`). The skill displays the rendered diff per-gap, collects approval via `AskUserQuestion`, then writes approved wrappers at the alphabetically-correct positions.

## Phase 2 — Helper-script whitelist audit

Scans `.claude/skills/aitask-*/`, `.claude/skills/task-workflow/`, `.claude/skills/user-file-select/`, and `.claude/skills/ait-git/` for `.aitask-scripts/aitask_*.sh` references. For each helper found, verifies it is whitelisted in all helper-permission touchpoints:

| # | File | Entry shape |
|---|---|---|
| 1 | `.claude/settings.local.json` | `"Bash(./.aitask-scripts/<helper>:*)"` |
| 3 | `.codex/rules/default.rules` | `prefix_rule(... decision = "allow")` |
| 4 | `seed/claude_settings.local.json` | mirror of #1 |
| 6 | `seed/codex_rules.default.rules` | mirror of #3 |
| 7 | `seed/opencode_config.seed.json` | `"./.aitask-scripts/<helper> *": "allow"` |

Touchpoint IDs 2 and 5 are intentionally left vacant (numbering stays stable across additions and removals of touchpoints — see [`aidocs/framework/adding_a_new_codeagent.md`](https://github.com/beyondeye/aitasks/blob/main/aidocs/framework/adding_a_new_codeagent.md) §13). Codex helper allow entries live in `.rules` files rather than `.codex/config.toml`. Codex rules are experimental, so keep this touchpoint aligned with the current OpenAI Codex Rules documentation.

The skill displays a per-helper × per-touchpoint matrix, collects approval, and inserts missing entries at the alphabetically-correct positions. JSON entries are inserted with format-aware splicing; TOML entries are inserted as `[[rule]]` blocks.

## Output reference

Structured stdout lines emitted by the helper:

| Prefix | Meaning |
|---|---|
| `GAP:<tree>:<skill>` | Wrapper missing in `<tree>` for `<skill>` |
| `HELPER:<basename>` | Helper script discovered in skill references |
| `MISSING:<touchpoint>:<helper>` | Helper not whitelisted in touchpoint |
| `WROTE:<path>` | Wrapper file written |
| `WROTE:<touchpoint>:<helper>:<file>` | Helper-whitelist entry inserted |

All subcommands exit 0 unless catastrophic; errors go to stderr.

## Self-bootstrap

The audit is run by a helper that is itself audited. When the skill is first introduced into the framework, its wrappers do not exist in the four trees yet — so the helper would refuse to "audit" itself out of nothing. The first set of wrappers for `aitask-audit-wrappers` was therefore written by hand at introduction time. From then on the skill audits itself like any other.

## Idempotency

Re-running discovery after a successful apply produces empty output:

```bash
./.aitask-scripts/aitask_audit_wrappers.sh discover
./.aitask-scripts/aitask_audit_wrappers.sh discover-helpers \
  | sed 's|^HELPER:||' \
  | xargs -I{} ./.aitask-scripts/aitask_audit_wrappers.sh audit-helper-whitelist {}
```

Plus the framework's per-agent setup tests stay green: [`tests/test_opencode_setup.sh`](https://github.com/dario-bs/aitasks/blob/main/tests/test_opencode_setup.sh) and the equivalent suites for other supported agents derive their expected counts dynamically from the source of truth, so adding skills via this audit grows the test expectations naturally.

## Related

- [`/aitask-add-model`](../../skills/aitask-add-model/) — Sibling framework-development skill for registering new code-agent models.
- [Skill authoring conventions in CLAUDE.md](https://github.com/dario-bs/aitasks/blob/main/CLAUDE.md) — "WORKING ON SKILLS / CUSTOM COMMANDS" defines the source-of-truth layout.
