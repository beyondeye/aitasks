---
priority: medium
effort: high
depends: [t1071_1]
issue_type: feature
status: Ready
labels: [shadow, claudeskills]
gates: [risk_evaluated]
anchor: 1071
created_at: 2026-06-29 12:06
updated_at: 2026-06-29 12:06
---

Capability B of t1071: a `/learn`-style "learn a skill from sources" command as a
**standalone** skill (NOT a shadow sub-procedure). Gather sources (local files,
URLs, repo files/dirs), apply house authoring standards, and generate a complete
static skill. The shadow gets only a thin routing entry that can launch it while
shadowing. Analogous to the Hermes agent `/learn` command
(https://hermes-agent.nousresearch.com/docs/user-guide/features/skills) — a
standards-guided prompt (no custom tool) that emits a `SKILL.md`.

Auto-depends on t1071_1 (sequential sibling) because both add a routing line to
`aitask-shadow/SKILL.md` Step 3; running after A means this picks up A's edit
cleanly. The two routing additions are otherwise independent.

## Context

Why standalone (from exploration): the command needs no pane capture and is
reusable outside shadowing, so it is its OWN skill (proposed name
`aitask-learn-skill`), not a shadow `plan-*.md`. Static standalone skills DO get
hand-maintained copies in the other agent trees — confirmed
`.agents/skills/aitask-reviewguide-import/SKILL.md` and
`.opencode/skills/aitask-reviewguide-import/SKILL.md` both exist — so per
CLAUDE.md this child must FILE FOLLOW-UP TASKS to port the new skill to Codex
(`.agents/skills/`) and OpenCode (`.opencode/skills/` + `.opencode/command/`).
Do the Claude version first.

## Key files to modify / create

- **NEW** `.claude/skills/aitask-learn-skill/SKILL.md` — static
  (`name`, `description`, `user-invocable: true`; no `.j2`/profile/goldens
  machinery). Optionally NEW sibling `.md` sub-procedures if the flow is long
  enough to warrant splitting (authoring standards: procedures in their own
  `.md`, no inlining).
- `.claude/skills/aitask-shadow/SKILL.md` — add ONE Step 3 routing entry that
  invokes `/aitask-learn-skill` when the user asks to learn a skill from sources
  while shadowing. (Greeting derives from Step 3 — do not hardcode.)
- Follow-up tasks (created at the end, NOT implemented here): port
  `aitask-learn-skill` to `.agents/skills/` and `.opencode/`.

## Reference files for patterns

- `.claude/skills/aitask-reviewguide-import/SKILL.md` — closest model: static
  skill shape AND the fetch half. Reuse `.aitask-scripts/lib/repo_fetch.sh`
  (`repo_fetch_file`, `repo_list_md_files`) for GitHub/GitLab/Bitbucket with
  `WebFetch` fallback, and its Step 1b source-type classification
  (local file / repo single file / repo dir / generic URL).
- `.claude/skills/aitask-contribute/` — another static, user-invocable skill
  (cited in `shadow_agent.md` as the static-skill model).
- `aidocs/framework/skill_authoring_conventions.md` — house authoring standards
  to apply to BOTH this skill and the generated skill (static-skill shape, no
  inlining, invocation-path reporting).

## Implementation plan

1. Author `.claude/skills/aitask-learn-skill/SKILL.md`. Workflow:
   (a) Resolve source(s) from argv or AskUserQuestion (file path / URL / repo
       file / repo dir) — mirror reviewguide-import Step 1/1b/1c.
   (b) Fetch via `repo_fetch.sh` / `WebFetch` fallback.
   (c) Analyze & extract the procedure/concepts the skill should encode.
   (d) Ask for the new skill's name + description (AskUserQuestion).
   (e) Generate `.claude/skills/<name>/SKILL.md` (minimal frontmatter; optional
       sibling `.md` sub-procedures per authoring standards).
   (f) Run `./.aitask-scripts/aitask_skill_verify.sh` before committing (a static
       skill passes trivially) and stage+commit the generated skill.
   (g) Report the invocation path (`/<name>`).
   Default to STATIC output skills — a profile-aware `.j2` skill drags in goldens
   + `aitask_skill_verify.sh` template complexity and is out of scope (or an
   explicit opt-in handled in the flow).
2. Add the Step 3 routing entry to `aitask-shadow/SKILL.md` (+ update
   `aidocs/framework/shadow_agent.md` if it enumerates shadow's external
   invocations).
3. File follow-up port tasks (use the Batch Task Creation Procedure) for Codex
   (`.agents/skills/aitask-learn-skill/`) and OpenCode
   (`.opencode/skills/aitask-learn-skill/` + `.opencode/command/`). These are
   the ONLY cross-agent ports for t1071 — capability A is Claude-only.

## Verification steps

- `./.aitask-scripts/aitask_skill_verify.sh` passes after adding the new skill.
- Dry-run the flow against a known source (e.g. a public markdown URL or a local
  file) and confirm it generates a well-formed static `SKILL.md` that itself
  passes `aitask_skill_verify.sh`, then reports the invocation path.
- Confirm the shadow Step 3 routing line invokes `/aitask-learn-skill` and the
  greeting still derives from Step 3 (no hardcoded copy).
- Confirm the Codex/OpenCode port follow-up task(s) were created and committed.
