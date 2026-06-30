---
priority: medium
risk_code_health: low
risk_goal_achievement: medium
effort: high
depends: [t1071_1]
issue_type: feature
status: Implementing
labels: [shadow, claudeskills]
gates: [risk_evaluated]
assigned_to: dario-e@beyond-eye.com
anchor: 1071
implemented_with: claudecode/opus4_8
created_at: 2026-06-29 12:06
updated_at: 2026-06-30 09:39
---

Capability B of t1071: a `/learn`-style "learn a skill from sources" command as a
**standalone** skill (NOT a shadow sub-procedure). Gather sources and generate a
complete static skill, applying house authoring standards. Analogous to the Hermes
agent `/learn` command
(https://hermes-agent.nousresearch.com/docs/user-guide/features/skills) — a
standards-guided prompt (no custom tool) that emits a `SKILL.md`.

**Sources (four types):** local file, URL, repo file/dir, **and a tmux pane id**.
The pane-id source is the key capability: given `%<N>`, the skill captures that
pane **read-only** (via `aitask_shadow_capture.sh`, dynamic incremental deepening —
+1000 scrollback lines per pass, user-confirmed, until the workflow start is
captured or scrollback is exhausted), analyzes the workflow, asks **which part** to
learn if multi-part, and asks **generalization** clarifying questions, then
generates the skill. Source-acquisition (per type) and a shared **`generate.md`**
core (`content → static SKILL.md`) are split per authoring standards.

**AC revised during planning (was: "the shadow gets only a thin routing entry"):**
The shadow must NOT run the learn itself — its mandate is advisory/read-only and a
learn run would occupy it. Shadow integration is therefore **deferred to a separate
follow-up child** of t1071 that has the shadow **spawn a dedicated learner agent**
(`/aitask-learn-skill <followed_pane_id>`) in a new pane (reusing `launch_in_tmux`
+ `aitask_codeagent.sh invoke`). Because the skill itself accepts a pane id and does
the capture/analysis, that follow-up is reduced to "spawn the learner." See
`aiplans/p1071/p1071_2_learn_skill_standalone_command.md` for the full design.

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
  machinery). Source resolution (file/URL/repo/pane-id) + acquisition, then hands
  off to `generate.md`.
- **NEW** `.claude/skills/aitask-learn-skill/generate.md` — shared core:
  analyze → multi-part selection → generalization Q&A → name/description →
  generate static SKILL.md → verify → commit → report.
- **No `aitask-shadow/SKILL.md` change in this task** — shadow integration is the
  deferred follow-up child (see AC note above).
- Follow-up tasks (created at the end, NOT implemented here): (1) cross-agent port
  of `aitask-learn-skill` to `.agents/skills/` and `.opencode/skills/` +
  `.opencode/commands/`; (2) shadow spawn-learner integration (depends on this
  task); (3) website docs covering the learn skill, the shadow→learner spawn, and
  the shadow's diagnose-errors capability (t1071_1).

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

**Authoritative record: `aiplans/p1071/p1071_2_learn_skill_standalone_command.md`**
(revised during planning). Summary:

1. Author `.claude/skills/aitask-learn-skill/generate.md` (shared core) and
   `SKILL.md` (source resolution for file/URL/repo/**pane-id** + acquisition →
   hand off to `generate.md`). Default STATIC output skills.
2. **No `aitask-shadow/SKILL.md` change here** — shadow integration is a deferred
   follow-up child.
3. File three follow-ups (Batch Task Creation Procedure): cross-agent port of
   `aitask-learn-skill` (Codex `.agents/skills/`, OpenCode `.opencode/skills/` +
   `.opencode/commands/`); shadow spawn-learner integration (depends on this
   task); website docs. Capability A (t1071_1) is Claude-only.

## Verification steps

- `./.aitask-scripts/aitask_skill_verify.sh` passes after adding the new skill.
- External-source dry-run (public md URL or local file) → well-formed static
  `SKILL.md` that itself passes verify; reports the invocation path.
- Pane-source dry-run via `aitask_shadow_capture.sh -` fixture → analyze →
  multi-part selection → generalization Q&A → generate; incremental deepening
  exercised; read-only throughout.
- Confirm the three follow-up tasks were created and committed (shadow follow-up
  `depends: [t1071_2]`; OpenCode port names `.opencode/commands/`).

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-06-30T06:40:03Z status=pass attempt=1 type=human
