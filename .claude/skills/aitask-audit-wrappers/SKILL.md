---
name: aitask-audit-wrappers
description: Audit and port aitask skill wrappers across code-agent trees, plus helper-script whitelist coverage.
user-invocable: true
---

## Overview

The aitasks framework keeps skills in one source-of-truth tree (`.claude/skills/aitask-*/SKILL.md`) and ports them to four wrapper trees so other code agents can invoke them:

- `.gemini/commands/<name>.toml` — Gemini CLI command wrappers.
- `.agents/skills/<name>/SKILL.md` — unified Codex CLI + Gemini CLI skill wrappers.
- `.opencode/skills/<name>/SKILL.md` — OpenCode skill wrappers.
- `.opencode/commands/<name>.md` — OpenCode command wrappers.

Plus two `activate_skill` policy lists that grant the Gemini CLI permission to invoke each skill:

- `.gemini/policies/aitasks-whitelist.toml` (runtime; gitignored layer)
- `seed/geminicli_policies/aitasks-whitelist.toml` (seed mirror; shipped with the framework)

This skill audits every source-of-truth `aitask-*` skill against all six locations and offers to port any that are missing. Phase 2 (added in t691_2) extends the audit to helper-script whitelist coverage across the 5 touchpoints from CLAUDE.md "Adding a New Helper Script".

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
./.aitask-scripts/aitask_audit_wrappers.sh discover-policy
```

Parse the output:
- `GAP:<tree>:<skill>` — wrapper missing in that tree.
- `POLICY_GAP:<runtime|seed>:<skill>` — `activate_skill` rule missing in that policy file.

Build a coverage matrix (one row per `aitask-*` skill, columns: gemini, agents, opencode-skill, opencode-command, policy-runtime, policy-seed). Display it.

If both lists are empty, print "Phase 1 — no wrapper gaps. ✓" and skip to Phase 2 (or exit if `--phase=skills`).

### Step 3 — Phase 1 confirmation gate

Use `AskUserQuestion` to ask: "Apply Phase 1 wrapper-port fixes?" with options:
- "Apply all" — fix every `GAP:` / `POLICY_GAP:` line.
- "Apply selected" — narrow with a follow-up multiSelect AskUserQuestion (one option per gap).
- "Skip Phase 1" — leave the wrapper trees untouched.

For "Apply selected", chunk the list into AskUserQuestion batches of ≤4 options.

### Step 4 — Phase 1 apply

For each approved gap:

```bash
./.aitask-scripts/aitask_audit_wrappers.sh apply-wrapper <tree> <skill_name>
./.aitask-scripts/aitask_audit_wrappers.sh apply-policy  <runtime|seed> <skill_name>
```

Collect the `WROTE:` lines emitted by the helper.

If `apply-wrapper` refuses to overwrite an existing file (returns non-zero), surface it to the user with `AskUserQuestion`: "File exists — overwrite?" with options "Yes, overwrite" / "Skip this gap". On "Yes", re-run with `--force`.

### Step 5 — Phase 1 commit

Stage the changes and commit. Two commits if both phases run; one commit if only Phase 1.

```bash
git add .gemini/commands/ .agents/skills/ .opencode/skills/ .opencode/commands/ \
        .gemini/policies/aitasks-whitelist.toml seed/geminicli_policies/aitasks-whitelist.toml
git commit -m "feature: Audit and port aitask skill wrappers across code-agent trees"
```

(For audit runs that close a known gap tracked by an aitask, the commit message should also include the `(t<task_id>)` suffix per the standard convention.)

### Step 6 — Phase 1 idempotency assert

Re-run discovery. If any `GAP:` or `POLICY_GAP:` lines remain (excluding gaps the user explicitly chose to skip), warn loudly. The user can re-run the skill to address them.

### Step 7 — Phase 2 (added in t691_2)

[Reserved — implemented in t691_2.]

## Output reference

Structured stdout lines emitted by the helper:

| Prefix | Meaning |
|---|---|
| `GAP:<tree>:<skill>` | Wrapper missing in `<tree>` for `<skill>` |
| `POLICY_GAP:<runtime|seed>:<skill>` | `activate_skill` rule missing in policy |
| `WROTE:<path>` | Wrapper file written |
| `WROTE:<file>:<skill>` | Policy entry inserted |

All subcommands exit 0 unless catastrophic. Errors go to stderr.

## Self-bootstrap

The helper script audits the source of truth (`.claude/skills/aitask-*/SKILL.md`) and ports to the four wrapper trees. When this skill is itself first introduced into the framework, its wrappers do not yet exist in the trees, so the helper would refuse to "audit" itself out of nothing. The first set of wrappers for `aitask-audit-wrappers` was therefore written by hand at introduction time. From then on the skill audits itself like any other.

## See also

- `aitask-add-model` — companion developer-facing skill for registering new code-agent models.
- CLAUDE.md "WORKING ON SKILLS / CUSTOM COMMANDS" — defines source of truth + per-agent ports.
- CLAUDE.md "Adding a New Helper Script" — defines the 5 helper-script whitelist touchpoints scanned by Phase 2.
- `tests/test_opencode_setup.sh` and `tests/test_gemini_setup.sh` — verification of cross-agent counts (auto-adjust per t679).
