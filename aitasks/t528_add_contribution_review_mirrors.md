---
priority: low
effort: low
depends: []
issue_type: chore
status: Implementing
labels: [claudeskills, codexcli, geminicli, opencode]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-04-12 12:39
updated_at: 2026-04-12 12:42
---

## Context

During t522_3 (mirror fold-caller updates into alt-agent frontends), discovered that the `aitask-contribution-review` skill has **no mirror wrappers** in any of the alt-agent frontends. The task was introduced in commit ab3c60b5 (t355_6 "feature: Add contribution review skill and helper script") which only created `.claude/skills/aitask-contribution-review/SKILL.md` plus the helper script and seed config — wrapper files for Codex/Gemini/OpenCode were never added.

This is an oversight (confirmed by comparing the skill's `user-invocable` flag, which is unset/true — unlike the deliberately-internal `task-workflow`, `ait-git`, `user-file-select` skills that correctly set `user-invocable: false`).

## Scope

Add four thin delegator wrapper files, each matching the existing pattern used by `aitask-fold`, `aitask-explore`, and `aitask-pr-import`:

1. `.agents/skills/aitask-contribution-review/SKILL.md` — unified Codex CLI / Gemini CLI wrapper. Copy the structure from `.agents/skills/aitask-fold/SKILL.md` (27 lines: frontmatter, Prerequisites, Source of Truth pointer to `.claude/skills/aitask-contribution-review/SKILL.md`, Arguments section).

2. `.opencode/skills/aitask-contribution-review/SKILL.md` — OpenCode wrapper. Copy the structure from `.opencode/skills/aitask-fold/SKILL.md` (23 lines: frontmatter, Plan Mode Prerequisites, Source of Truth pointer, Arguments section).

3. `.gemini/commands/aitask-contribution-review.toml` — Gemini CLI command wrapper. Copy the structure from `.gemini/commands/aitask-fold.toml` (13 lines: `description = ...`, `prompt = """..."""` block with `@` imports for `geminicli_tool_mapping.md`, `geminicli_planmode_prereqs.md`, and `.claude/skills/aitask-contribution-review/SKILL.md`).

4. `.opencode/commands/aitask-contribution-review.md` — OpenCode command wrapper. Copy the structure from `.opencode/commands/aitask-fold.md` (13 lines: frontmatter description, `@` imports for `opencode_tool_mapping.md`, `opencode_planmode_prereqs.md`, and `.claude/skills/aitask-contribution-review/SKILL.md`).

## Reference Files for Patterns

- `.agents/skills/aitask-fold/SKILL.md` (27 lines) — pattern for `.agents/` mirror
- `.opencode/skills/aitask-fold/SKILL.md` (23 lines) — pattern for `.opencode/skills/` mirror
- `.gemini/commands/aitask-fold.toml` (13 lines) — pattern for Gemini command wrapper
- `.opencode/commands/aitask-fold.md` (13 lines) — pattern for OpenCode command wrapper
- `.claude/skills/aitask-contribution-review/SKILL.md` — the authoritative skill, for reading the `description` line and Arguments summary to include in the wrappers

## Description text

The skill description (from `.claude/skills/aitask-contribution-review/SKILL.md` frontmatter):
> Analyze a contribution issue, find related issues, and import as grouped or single task.

## Arguments text

The skill accepts an issue URL or number as an argument. Copy the argument description from the existing `.claude/skills/aitask-contribution-review/SKILL.md` if one is documented there; otherwise draft a one-line summary matching the skill's interface.

## Implementation Plan

1. Read the four reference files above to confirm the exact patterns.
2. Read `.claude/skills/aitask-contribution-review/SKILL.md` to get the authoritative description and argument semantics.
3. Create the four new wrapper files (one Write call each).
4. Commit with `git add .agents/skills/aitask-contribution-review/ .opencode/skills/aitask-contribution-review/ .gemini/commands/aitask-contribution-review.toml .opencode/commands/aitask-contribution-review.md` + `git commit -m "chore: Add aitask-contribution-review wrappers for alt-agent frontends (tNN)"`.

## Verification

- Each new wrapper should `@import` or prose-point at `.claude/skills/aitask-contribution-review/SKILL.md` so that future edits to the Claude Code source of truth are automatically inherited.
- `grep -l "aitask-contribution-review" .agents/skills/*/SKILL.md .opencode/skills/*/SKILL.md .gemini/commands/*.toml .opencode/commands/*.md` should hit exactly 4 files after the change.
- No tests to run — pure doc/wrapper change.

## Notes

- Do NOT inline any procedural steps — stick to the thin delegator pattern. t522_3 verified that the `.claude/` source-of-truth + thin-delegator architecture means alt-agent users automatically inherit all subsequent edits to the Claude Code skill.
- Consider whether `aitask-contribute` (the separate skill for opening issues) needs the same audit — a quick check showed it DOES have mirrors (`.agents/skills/aitask-contribute/SKILL.md`, `.opencode/skills/aitask-contribute/SKILL.md`, `.gemini/commands/aitask-contribute.toml`, `.opencode/commands/aitask-contribute.md`), so no follow-up is needed there.
