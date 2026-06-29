---
Task: t1071_2_learn_skill_standalone_command.md
Parent Task: aitasks/t1071_shadow_error_diagnosis_and_learn_skill_command.md
Sibling Tasks: aitasks/t1071/t1071_1_shadow_diagnose_errors_subprocedure.md
Archived Sibling Plans: aiplans/archived/p1071/p1071_*_*.md
Worktree: aiwork/t1071_2_learn_skill_standalone_command
Branch: aitask/t1071_2_learn_skill_standalone_command
Base branch: main
---

# Plan — Capability B: standalone `aitask-learn-skill` command

A `/learn`-style "learn a skill from sources" command as a **standalone** skill
(NOT a shadow sub-procedure): gather sources (local files, URLs, repo files/dirs),
apply house authoring standards, and generate a complete **static** skill. The
shadow gets only a thin routing entry to launch it while shadowing. Analogous to
the Hermes agent `/learn` command — a standards-guided prompt (no custom tool)
that emits a `SKILL.md`.

**Depends on t1071_1** (sequential sibling): both add a Step 3 routing line to
`aitask-shadow/SKILL.md`; running after A means this picks up A's edit cleanly.

## Exploration summary (already done — do not re-derive)

- **Standalone, not a shadow sub-procedure:** the command needs no pane capture
  and is reusable outside shadowing, so it is its own skill (`aitask-learn-skill`).
- **Static standalone skills ARE ported across agent trees** — confirmed both
  `.agents/skills/aitask-reviewguide-import/SKILL.md` and
  `.opencode/skills/aitask-reviewguide-import/SKILL.md` exist (hand-maintained).
  So per CLAUDE.md, this task must **file follow-up tasks** to port the new skill
  to Codex (`.agents/skills/`) and OpenCode (`.opencode/skills/` +
  `.opencode/command/`). Do the Claude version first; this is the **only**
  cross-agent port for t1071 (capability A is Claude-only).
- **Reuse the fetch half:** `aitask-reviewguide-import` already solves
  source-type classification + fetching via `.aitask-scripts/lib/repo_fetch.sh`
  (`repo_fetch_file`, `repo_list_md_files`) with a `WebFetch` fallback.

## Files

| File | Change |
|------|--------|
| `.claude/skills/aitask-learn-skill/SKILL.md` | **NEW** static, user-invocable skill |
| `.claude/skills/aitask-learn-skill/*.md` | **NEW** optional sibling sub-procedures (if flow warrants splitting) |
| `.claude/skills/aitask-shadow/SKILL.md` | Add 1 Step 3 routing entry invoking `/aitask-learn-skill` |
| (follow-up tasks) | Port to `.agents/skills/` + `.opencode/` — created, NOT implemented here |

## Step-by-step

### 1. Author `.claude/skills/aitask-learn-skill/SKILL.md`

Static skill: frontmatter `name`, `description`, `user-invocable: true`. No
`.j2`/profile/goldens machinery (model on `aitask-reviewguide-import` and
`aitask-contribute`). Workflow:

1. **Resolve source(s)** from argv or AskUserQuestion — mirror reviewguide-import
   Step 1/1b/1c: local file (`/`, `~`, `./` or exists locally) / repo single file
   (`/blob/`, `/-/blob/`, `/src/<file>`) / repo dir (`/tree/`, `/-/tree/`,
   `/src/<dir>`) / generic URL.
2. **Fetch** via `source .aitask-scripts/lib/repo_fetch.sh && repo_fetch_file URL`
   (or `repo_list_md_files URL` for a directory), with `WebFetch` raw-URL fallback
   exactly as reviewguide-import documents.
3. **Analyze & extract** the procedure/concepts the new skill should encode (what
   the skill does, its steps, any sub-procedures worth splitting out).
4. **Ask** for the new skill's `name` (snake/kebab) + one-line `description`
   (AskUserQuestion).
5. **Generate** `.claude/skills/<name>/SKILL.md` (minimal frontmatter; optional
   sibling `.md` sub-procedures per authoring standards — procedures in their own
   `.md`, no inlining). Default to **static** output skills; a profile-aware
   `.j2` skill drags in goldens + `aitask_skill_verify.sh` template complexity and
   is out of scope (or an explicit in-flow opt-in).
6. **Verify** — run `./.aitask-scripts/aitask_skill_verify.sh` (a static skill
   passes trivially), then stage + commit the generated skill.
7. **Report** the invocation path (`/<name>`).

Consider splitting the fetch/classify logic and the generate/verify logic into
sibling `.md` sub-procedures if SKILL.md grows long (authoring-standards
preference for no inlining).

### 2. Wire `aitask-shadow/SKILL.md`

Add one Step 3 routing entry: "Learn a skill from sources (files / URLs / repo)
→ invoke `/aitask-learn-skill`." (Greeting derives from Step 3 — do not hardcode.)
If `aidocs/framework/shadow_agent.md` enumerates shadow's external invocations,
update it too.

### 3. File cross-agent port follow-ups

Using the Batch Task Creation Procedure, create follow-up task(s) to port
`aitask-learn-skill` to:
- Codex: `.agents/skills/aitask-learn-skill/SKILL.md`
- OpenCode: `.opencode/skills/aitask-learn-skill/SKILL.md` + `.opencode/command/`

Adapt from the Claude version per CLAUDE.md ("done in the Claude Code version
first … suggest separate aitasks to update the corresponding skills/commands in
the other supported coding agents").

## Verification

- `./.aitask-scripts/aitask_skill_verify.sh` passes after adding the new skill.
- Dry-run against a known source (a public markdown URL or a local file); confirm
  it generates a well-formed static `SKILL.md` that itself passes
  `aitask_skill_verify.sh`, then reports the invocation path.
- Confirm the shadow Step 3 routing line invokes `/aitask-learn-skill` and the
  greeting still derives from Step 3 (no hardcoded copy).
- Confirm the Codex/OpenCode port follow-up task(s) were created and committed.

## Notes for sibling tasks

- This is the last child of t1071. On archival the parent archives automatically
  (once `children_to_implement` is empty).

## Post-implementation

Follow shared workflow **Step 9 (Post-Implementation)** for cleanup, gate
verification, archival, and merge.
