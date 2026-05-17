# Stub Skill / Command Pattern (Canonical Authoring Reference)

This document describes the canonical "stub" pattern that every templated skill in the aitasks framework uses to dispatch to its per-profile rendered variant. Referenced by t777_6 (pilot conversion) and t777_8..t777_15 (other per-skill conversions).

## 3a. Purpose

A **stub** is the small, profile-agnostic dispatch logic that the agent reads when the user invokes a skill (e.g., `/aitask-pick`). It performs three steps:

1. Resolve the active execution profile (via `--profile <name>` argument override OR the resolver default).
2. Render the per-(skill, profile, agent) variant on demand (no-op if already up to date).
3. Read-and-follow the rendered variant — execute its instructions as if they were the skill body.

The stub is committed to git. The rendered variants live in trailing-hyphen directories (e.g., `.claude/skills/aitask-pick-fast-/`) that are gitignored via the single `*-/` glob per agent root.

**Per-agent, the stub lives at the agent's actual entry point** — not at a uniform path. Claude auto-discovers skill SKILL.md files; Codex loads SKILL.md by instruction reference; Gemini and OpenCode auto-discover **command wrappers**, not skills. The stub therefore takes different file shapes per agent (SKILL.md for Claude/Codex; command-wrapper file for Gemini/OpenCode). See §3g for the canonical mapping.

## 3b. Canonical stub body (Claude / Codex — `SKILL.md` form)

This goes at `.claude/skills/<skill_short_name>/SKILL.md` (Claude) and `.agents/skills/<skill_short_name>/SKILL.md` (Codex). The two files are identical except for the `<agent_literal>` substitution in Step 2.

```markdown
---
name: <skill_short_name>
description: <copied from authoring template frontmatter>
---

This is a profile-aware skill stub. Execute these steps in order, then stop:

1. **Resolve active profile.** Parse ARGUMENTS for `--profile <name>`. If
   found, use that as `<profile>` and remove the `--profile <name>` pair
   from ARGUMENTS. Otherwise run:
   `./.aitask-scripts/aitask_skill_resolve_profile.sh <skill_short_name>`
   and use the single-line stdout as `<profile>`.

2. **Render per-profile variant.** Run:
   `./ait skill render <skill_short_name> --profile <profile> --agent <agent_literal>`
   No-op if the per-profile SKILL.md is already up to date.

3. **Dispatch via Read-and-follow.** Read the file at
   `<agent_root>/<skill_short_name>-<profile>-/SKILL.md` and execute its
   instructions as if they were this skill, forwarding the (possibly
   stripped) ARGUMENTS unchanged.
```

Substitutions per stub:
- `<skill_short_name>` — e.g., `aitask-pick`
- `<agent_literal>` — `claude` for the Claude stub; `codex` for the Codex stub
- `<agent_root>` — `.claude/skills` for Claude; `.agents/skills` for Codex

## 3c. Canonical stub body (Gemini — command TOML form)

This goes at `.gemini/commands/<skill_short_name>.toml`, replacing the current static `@`-include to the Claude SKILL.md. The Gemini command-wrapper convention `@`-includes the runtime prereqs before the stub body, mirroring the existing pattern.

```toml
description = "<copied from authoring template frontmatter>"
prompt = """

@.agents/skills/geminicli_planmode_prereqs.md
@.agents/skills/geminicli_tool_mapping.md

This is a profile-aware skill stub. Execute these steps in order, then stop:

1. **Resolve active profile.** Parse {{args}} for `--profile <name>`.
   If found, use that as `<profile>` and remove the `--profile <name>`
   pair from the forwarded args. Otherwise run:
   `./.aitask-scripts/aitask_skill_resolve_profile.sh <skill_short_name>`
   and use the single-line stdout as `<profile>`.

2. **Render per-profile variant.** Run:
   `./ait skill render <skill_short_name> --profile <profile> --agent gemini`

3. **Dispatch via Read-and-follow.** Read the file at
   `.gemini/skills/<skill_short_name>-<profile>-/SKILL.md` and execute its
   instructions as if they were this command, forwarding the (possibly
   stripped) args unchanged.

Forwarded args: {{args}}
"""
```

The Gemini stub hardcodes `--agent gemini` in Step 2. The prereq includes (`geminicli_planmode_prereqs.md`, `geminicli_tool_mapping.md`) are pulled in at command-load time and are NOT duplicated into the rendered variant.

## 3d. Canonical stub body (OpenCode — command MD form)

This goes at `.opencode/commands/<skill_short_name>.md`, replacing the current static `@`-include to the Claude SKILL.md.

```markdown
---
description: <copied from authoring template frontmatter>
---

@.opencode/skills/opencode_planmode_prereqs.md
@.opencode/skills/opencode_tool_mapping.md

This is a profile-aware skill stub. Execute these steps in order, then stop:

1. **Resolve active profile.** Parse $ARGUMENTS for `--profile <name>`.
   If found, use that as `<profile>` and remove the `--profile <name>`
   pair. Otherwise run:
   `./.aitask-scripts/aitask_skill_resolve_profile.sh <skill_short_name>`
   and use the single-line stdout as `<profile>`.

2. **Render per-profile variant.** Run:
   `./ait skill render <skill_short_name> --profile <profile> --agent opencode`

3. **Dispatch via Read-and-follow.** Read the file at
   `.opencode/skills/<skill_short_name>-<profile>-/SKILL.md` and execute its
   instructions as if they were this command, forwarding the (possibly
   stripped) $ARGUMENTS unchanged.
```

The OpenCode stub hardcodes `--agent opencode` in Step 2.

## 3e. Why Read-and-follow, not slash-dispatch

The stub's Step 3 instructs the agent to **Read** the rendered file and follow it — not to invoke `/<skill>-<profile>-` as a nested slash command.

- Read-and-follow works in **all four agents** (every agent supports file reads). No per-agent validation matrix is required, and no fallback case is needed for agents that cannot programmatically slash-dispatch.
- Read-and-follow mirrors an idiom already used pervasively in the framework, e.g., `task-workflow/SKILL.md` instructing the agent to read `planning.md`, `execution-profile-selection.md`, etc.
- Slash-dispatch from within a SKILL.md is unverified for Codex / Gemini / OpenCode and would require a per-agent fallback that prints a shell-command hint and aborts.

Slash-dispatch may be added as a follow-up optimization in a separate task once empirically validated across all four agents.

## 3f. Stub authoring conventions (checklist for converters)

When converting a skill in t777_6 (pilot) or t777_8..15 (others), each conversion produces **4 stubs** plus 1 authoring template. The checklist:

- **Stub frontmatter `name:` / TOML `description=` / OpenCode frontmatter `description:` match the no-suffix slash command** (e.g., `aitask-pick`, NOT `aitask-pick-fast-`).
- **Stubs are committed to git.** Rendered variants (trailing-hyphen dirs) are gitignored.
- **One stub per (skill, agent surface)** — 4 stubs total per skill:
  1. Claude SKILL.md (per §3b)
  2. Codex SKILL.md (per §3b)
  3. Gemini command TOML (per §3c)
  4. OpenCode command MD (per §3d)
- **Stub body is profile-agnostic** — it never embeds profile-specific content or branches on profile keys. All profile-conditional logic belongs in the authoring template (`.claude/skills/<skill>/SKILL.md.j2`).
- **Stub MUST NOT modify state** beyond the resolve + render bash calls. No git operations, no task-file edits, no lock changes.
- **Authoring dir names MUST NOT end with `-`** — load-bearing for the `*-/` gitignore convention. Verified by the one-shot audit in t777_3 Step 5; future renames or new authoring skills must respect this hard rule.

## 3g. Per-agent surface table (canonical reference)

| Agent | Stub authoring location | `<agent_literal>` | Rendered variant location |
|-------|------------------------|-------------------|----------------------|
| Claude | `.claude/skills/<skill>/SKILL.md` | `claude` | `.claude/skills/<skill>-<profile>-/SKILL.md` |
| Codex | `.agents/skills/<skill>/SKILL.md` | `codex` | `.agents/skills/<skill>-<profile>-/SKILL.md` |
| Gemini | `.gemini/commands/<skill>.toml` `prompt` field | `gemini` | `.gemini/skills/<skill>-<profile>-/SKILL.md` |
| OpenCode | `.opencode/commands/<skill>.md` body | `opencode` | `.opencode/skills/<skill>-<profile>-/SKILL.md` |

Notes:
- In Claude, the rendered variant at `<skill>-<profile>-/SKILL.md` is technically auto-discoverable as a slash command (`/aitask-pick-fast-`). The stub flow never invokes that path; the trailing-hyphen slash command is a side effect of the dir naming and is not part of the normal invocation flow.
- In Codex, the rendered variant at `.agents/skills/<skill>-<profile>-/SKILL.md` is reached via the stub's Read instruction. Codex does not auto-discover slash commands.
- In Gemini and OpenCode, the rendered variant lives under `<agent_root>/skills/`, NOT under `<agent_root>/commands/`. The command wrapper is the stub; the rendered file is the dispatch target reached via Read-and-follow.
- `.gemini/skills/` is currently empty in this repo. Per-skill conversion tasks (t777_6+) create the gemini rendered dirs for the first time on first render call.

## 3h. Argument forwarding contract

The stub's Step 1 parses `ARGUMENTS` (Claude/Codex), `{{args}}` (Gemini), or `$ARGUMENTS` (OpenCode) for the optional `--profile <name>` pair. If found:
- Use the captured `<name>` as the active profile (overrides resolver).
- Remove the `--profile <name>` pair from the forwarded args before Step 3.

This mirrors today's `/aitask-pick --profile fast 16` user-facing convention: the user (or a Python TUI like `AgentCommandScreen`'s per-run editor, t777_17) supplies an override, the stub honors it, and the rendered variant receives the cleaned args (`16` only — no `--profile fast` residue).

Argument forwarding from `ait skillrun` (t777_5) and Python TUIs uses the same contract: append `--profile <name>` to the ARGUMENTS that get passed to the user-facing slash command (`/<skill>`). No TUI invokes the rendered slash command directly. The override path through ARGUMENTS is the **single** mechanism for non-default profile selection at invocation time.
