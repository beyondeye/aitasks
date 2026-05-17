---
priority: low
effort: low
depends: [t777_17]
issue_type: documentation
status: Ready
labels: [aitask_pick]
created_at: 2026-05-17 12:02
updated_at: 2026-05-17 12:02
---

## Context

Depends on most preceding children (specifically t777_1..15 so the conventions and helper scripts exist to document). Adds a "Skill Template Authoring Conventions" section to CLAUDE.md and user-facing documentation in the website.

Per project rule: "User-facing docs (website, README-level content) describe the **current state only**" — describe positively, no "previously we did X" framing.

## Key Files to Modify

- `CLAUDE.md` (modify) — add new section under "WORKING ON SKILLS / CUSTOM COMMANDS" (around the existing "Skill / Workflow Authoring Conventions" subsection)
- `website/content/docs/` — add or extend pages:
  - `workflows/skill-templating.md` (new) — explain `.j2` source, per-profile dirs, stub-dispatch, `ait skillrun`, `ait skill verify`
  - Update existing profile docs to reference the new mechanism
- `README.md` — brief `ait skillrun` mention if appropriate

## Reference Files for Patterns

- Existing "Adding a New Helper Script" section in CLAUDE.md (line 82) — pattern for procedural conventions
- Existing "Skill / Workflow Authoring Conventions" section in CLAUDE.md — pattern for skill-related conventions
- `website/content/docs/workflows/` — existing workflow doc structure

## Implementation Plan

### 1. CLAUDE.md
Add subsection (e.g. "Skill Template Authoring Conventions") covering:
- `.j2` template lives in `.claude/skills/<skill>/SKILL.md.j2` (Claude-first source of truth)
- Per-agent stub at `<agent>/skills/<skill>/SKILL.md` (committed; small dispatch body)
- Per-profile rendered output at `<agent>/skills/<skill>-<profile>/SKILL.md` (gitignored)
- `{% if agent == "..." %}` pattern for tool mappings
- `{% if profile.<key> %}` pattern for profile-driven branches
- `{% raw %}/{% endraw %}` for literal `{{` / `{%`
- `ait skill verify` is the source-of-truth for "templates render cleanly"
- Per-agent skill-path table
- Reference `.claude/skills/task-workflow/stub-skill-pattern.md` for canonical stub body

### 2. website/content/docs/workflows/skill-templating.md (new)
- User-facing intro to templated skills
- Examples: `ait skillrun pick --profile fast 42` vs direct `/aitask-pick`
- How profiles dispatch (no-suffix → resolve → suffixed slash command)
- How to view/edit per-run profile overrides via `AgentCommandScreen` UI

### 3. README.md
- Brief one-paragraph mention of `ait skillrun` if README has CLI command listing

### 4. Verify all references are accurate
- `ait skill verify` produces clean run
- All file paths in docs match what t777_1..15 created
- No "previously..." or "this used to..." wording

## Verification Steps

1. `cd website && ./serve.sh` renders the new page cleanly.
2. `markdownlint` (or equivalent) clean on CLAUDE.md and new docs.
3. All internal cross-references resolve.
4. Sanity-read by a fresh-context reader: can they understand the templating mechanism from CLAUDE.md alone?
