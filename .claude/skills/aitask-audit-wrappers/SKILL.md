---
name: aitask-audit-wrappers
description: Audit and port aitask skill wrappers across code-agent trees, plus helper-script whitelist coverage.
user-invocable: true
---

## Overview

The aitasks framework keeps skills in one source-of-truth tree (`.claude/skills/aitask-*/SKILL.md`) and ports them to the per-agent wrapper trees so other code agents can invoke them:

- `.agents/skills/<name>/SKILL.md` — Codex CLI (and other shared-root agents) skill wrappers.
- `.opencode/skills/<name>/SKILL.md` — OpenCode skill wrappers.
- `.opencode/commands/<name>.md` — OpenCode command wrappers.

This skill audits every source-of-truth `aitask-*` skill against the wrapper locations and offers to port any that are missing. Phase 2 (added in t691_2) extends the audit to helper-script whitelist coverage across the helper-permission touchpoints from CLAUDE.md "Adding a New Helper Script".

## Usage

```
/aitask-audit-wrappers
/aitask-audit-wrappers --phase=skills
/aitask-audit-wrappers --phase=whitelist
/aitask-audit-wrappers --phase=all
```

Default: `--phase=all` runs both phases sequentially with a confirmation gate per phase.

## Workflow

### Step 1 — Argument parse

Accept `--phase=skills`, `--phase=whitelist`, or `--phase=all` (default `all`). Anything else is rejected.

### Step 2 — Phase 1 discovery

Run the helper to list wrapper gaps:

```bash
./.aitask-scripts/aitask_audit_wrappers.sh discover
```

Parse the output:
- `GAP:<tree>:<skill>` — wrapper missing in that tree.

Build a coverage matrix (one row per `aitask-*` skill, columns: agents, opencode-skill, opencode-command). Display it.

If the list is empty, print "Phase 1 — no wrapper gaps. ✓" and skip to Phase 2 (or exit if `--phase=skills`).

### Step 3 — Phase 1 confirmation gate

Use `AskUserQuestion` to ask: "Apply Phase 1 wrapper-port fixes?" with options:
- "Apply all" — fix every `GAP:` line.
- "Apply selected" — narrow with a follow-up multiSelect AskUserQuestion (one option per gap).
- "Skip Phase 1" — leave the wrapper trees untouched.

For "Apply selected", chunk the list into AskUserQuestion batches of ≤4 options.

### Step 4 — Phase 1 apply

For each approved gap:

```bash
./.aitask-scripts/aitask_audit_wrappers.sh apply-wrapper <tree> <skill_name>
```

Collect the `WROTE:` lines emitted by the helper.

If `apply-wrapper` refuses to overwrite an existing file (returns non-zero), surface it to the user with `AskUserQuestion`: "File exists — overwrite?" with options "Yes, overwrite" / "Skip this gap". On "Yes", re-run with `--force`.

### Step 5 — Phase 1 commit

Stage the changes and commit. Two commits if both phases run; one commit if only Phase 1.

```bash
git add .agents/skills/ .opencode/skills/ .opencode/commands/
git commit -m "feature: Audit and port aitask skill wrappers across code-agent trees"
```

(For audit runs that close a known gap tracked by an aitask, the commit message should also include the `(t<task_id>)` suffix per the standard convention.)

### Step 6 — Phase 1 idempotency assert

Re-run discovery. If any `GAP:` lines remain (excluding gaps the user explicitly chose to skip), warn loudly. The user can re-run the skill to address them.

### Step 7 — Phase 2 discovery (helper-script whitelist)

Skip if `--phase=skills`.

Run the helper-discovery + audit:

```bash
./.aitask-scripts/aitask_audit_wrappers.sh discover-helpers
```

Each `HELPER:<basename>` line is a helper invoked by some `aitask-*` SKILL.md or shared procedure (`task-workflow/`, `user-file-select/`, `ait-git/`). For each, run:

```bash
./.aitask-scripts/aitask_audit_wrappers.sh audit-helper-whitelist <helper>
```

Each `MISSING:<touchpoint>:<helper>` indicates the helper is not whitelisted in that touchpoint:

| # | File | Entry shape |
|---|---|---|
| 1 | `.claude/settings.local.json` | `"Bash(./.aitask-scripts/<helper>:*)"` in `permissions.allow` |
| 3 | `.codex/rules/default.rules` | `prefix_rule(... decision = "allow")` |
| 4 | `seed/claude_settings.local.json` | mirror of #1 |
| 6 | `seed/codex_rules.default.rules` | mirror of #3 |
| 7 | `seed/opencode_config.seed.json` | `"./.aitask-scripts/<helper> *": "allow"` |

Touchpoint IDs 2 and 5 are intentionally left vacant — numbering stays stable across additions and removals of touchpoints (see `aidocs/adding_a_new_codeagent.md` §13).

Build a per-helper × per-touchpoint matrix (rows = helpers with at least one missing touchpoint, columns = the live touchpoint IDs). Display it.

If no `MISSING:` lines remain, print "Phase 2 — no helper-whitelist gaps. ✓" and skip to Step 9.

### Step 8 — Phase 2 confirmation gate

Use `AskUserQuestion`:
- Question: "Apply Phase 2 helper-whitelist fixes?"
- Header: "Phase 2"
- Options:
  - "Apply all" — close every `MISSING:` entry.
  - "Apply selected" — narrow with a follow-up multiSelect AskUserQuestion (one option per `MISSING:<touchpoint>:<helper>` pair, batched into pages of ≤4 options).
  - "Skip Phase 2" — leave the helper whitelists untouched.

### Step 9 — Phase 2 apply

For each approved entry:

```bash
./.aitask-scripts/aitask_audit_wrappers.sh apply-helper-whitelist <helper> --touchpoint <N>
```

Or apply all touchpoints for a helper at once:

```bash
./.aitask-scripts/aitask_audit_wrappers.sh apply-helper-whitelist <helper>
```

Collect `WROTE:<touchpoint>:<helper>:<file>` lines for the summary.

### Step 10 — Phase 2 commit

Stage the changed permission files and commit separately from Phase 1:

```bash
git add .claude/settings.local.json \
        .codex/rules/default.rules \
        seed/claude_settings.local.json \
        seed/codex_rules.default.rules \
        seed/opencode_config.seed.json
git commit -m "chore: Audit helper-script whitelist coverage across touchpoints"
```

(Audit runs invoked from a tracked aitask should append the `(t<task_id>)` suffix per the standard convention.)

### Step 11 — Phase 2 idempotency assert

Re-run helper discovery + audit. If any `MISSING:` lines remain (excluding entries the user explicitly chose to skip), warn loudly. The user can re-run with the missing entries selected.

## Output reference

Structured stdout lines emitted by the helper:

| Prefix | Meaning |
|---|---|
| `GAP:<tree>:<skill>` | Wrapper missing in `<tree>` for `<skill>` |
| `WROTE:<path>` | Wrapper file written |

All subcommands exit 0 unless catastrophic. Errors go to stderr.

## Self-bootstrap

The helper script audits the source of truth (`.claude/skills/aitask-*/SKILL.md`) and ports to the wrapper trees. When this skill is itself first introduced into the framework, its wrappers do not yet exist in the trees, so the helper would refuse to "audit" itself out of nothing. The first set of wrappers for `aitask-audit-wrappers` was therefore written by hand at introduction time. From then on the skill audits itself like any other.

## See also

- `aitask-add-model` — companion developer-facing skill for registering new code-agent models.
- CLAUDE.md "WORKING ON SKILLS / CUSTOM COMMANDS" — defines source of truth + per-agent ports.
- CLAUDE.md "Adding a New Helper Script" — defines the helper-script whitelist touchpoints scanned by Phase 2.
- `tests/test_opencode_setup.sh` and equivalent per-agent setup tests — verification of cross-agent counts (auto-adjust per t679).
