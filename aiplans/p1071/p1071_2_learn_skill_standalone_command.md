---
Task: t1071_2_learn_skill_standalone_command.md
Parent Task: aitasks/t1071_shadow_error_diagnosis_and_learn_skill_command.md
Archived Sibling Plans: aiplans/archived/p1071/p1071_1_shadow_diagnose_errors_subprocedure.md
Base branch: main
plan_verified:
  - claudecode/opus4_8 @ 2026-06-30 09:38
---

# Plan — Capability B: standalone `aitask-learn-skill` (file / URL / repo / **tmux pane** sources)

## Context

t1071 Capability B: a `/learn`-style "learn a skill from sources" command. Modeled on
the Hermes agent `/learn` (researched: **no custom tool** — a standards-guided prompt
that, via normal file/web tools, gathers material and authors a `SKILL.md`; sources
include *"the workflow you just walked the agent through in this conversation"*).

**This task delivers the engine** — a standalone, user-invocable `/aitask-learn-skill`
that learns from four source types: local file, URL, repo file/dir, **and a tmux pane
id**. The pane-id source is the key new capability: given `%<N>`, the skill captures
that pane **read-only**, analyzes the workflow, asks **which part** to learn if the
session has several, and asks **generalization** clarifying questions — then generates a
static skill.

**Decisions made with the user during planning:**
- **Shadow integration is a separate follow-up child** (created here, not implemented).
  The shadow's mandate is advisory/read-only and a learn run would *occupy* it, so the
  shadow must not run the learn itself. Instead the follow-up will have the shadow
  **spawn a dedicated learner agent** = `/aitask-learn-skill <followed_pane_id>` in a new
  pane (reusing the existing `launch_in_tmux` + `aitask_codeagent.sh invoke` machinery).
  Because the *skill itself* accepts a pane id and does the capture/analysis, that
  follow-up is reduced to "spawn the learner" — all heavy lifting lands here.
- **Shared `generate.md` core** (`content → static SKILL.md`): kept as a sub-procedure of
  the skill (authoring-standards: long flows split out; also future-proofs the shadow
  follow-up). Currently one direct consumer (`SKILL.md`); MAINTAINER note records that.

## AC update (explicit — not a silent deviation)

The task says *"a `/learn`-style command as a standalone skill … The shadow gets only a
thin routing entry."* **Implementation Step 0 rewrites the task description/AC**
(`aitasks/t1071/t1071_2_learn_skill_standalone_command.md`, commit via `./ait git`) to:
"standalone `/aitask-learn-skill` learning from file / URL / repo / **tmux pane id**
sources (pane source: capture → analyze → multi-part selection → generalization Q&A →
generate); shared `generate.md` core; cross-agent port follow-up; **shadow integration
deferred to a new follow-up child** that spawns a learner agent pointed at the followed
pane." Removes the "thin routing entry" framing.

## Verified plan assumptions (child verify path)

- Reference files confirmed: `aitask-reviewguide-import/SKILL.md` (Step 1b source
  classify + `repo_fetch.sh`/`WebFetch` fetch), `repo_fetch.sh`
  (`repo_fetch_file`:151, `repo_list_md_files`:168), `aitask-contribute/SKILL.md`,
  `skill_authoring_conventions.md`.
- **Pane capture:** `./.aitask-scripts/aitask_shadow_capture.sh <pane_id>` captures a
  pane read-only; **depth = `SHADOW_CAPTURE_LINES` env (default 200, `-S -<N>`)**. The
  pane-source path drives this env in an **incremental deepening loop** (see Step 2) —
  NOT a fixed cap. `aitask_shadow_capture.sh -` cleans a piped buffer (the dry-run/test
  seam). It is a shared framework helper (not agent-specific), so ported skill copies can
  call it too.
- Sibling A (t1071_1) landed; greeting derives from shadow Step 3 at runtime (no parser).
- **CORRECTION** carried into the port follow-up: OpenCode dir is `.opencode/commands/`
  (plural) — confirmed on disk; `.opencode/command/` does not exist.

## Files (this task)

| File | Change |
|------|--------|
| `aitasks/t1071/t1071_2_…md` | **Step 0:** rewrite description/AC (commit via `./ait git`) |
| `.claude/skills/aitask-learn-skill/SKILL.md` | **NEW** static, user-invocable — source resolution (file/URL/repo/**pane-id**) + fetch, then hand to `generate.md` |
| `.claude/skills/aitask-learn-skill/generate.md` | **NEW** core: analyze → multi-part select → generalization Q&A → name/description → generate static SKILL.md → verify → commit → report. MAINTAINER note (1 consumer today; shadow follow-up reuses the skill by spawning it). |
| (follow-up) cross-agent port | Port skill (`SKILL.md`+`generate.md`) to `.agents/skills/` + `.opencode/skills/` + `.opencode/commands/` — created, NOT implemented |
| (follow-up) **shadow spawn-learner** | NEW child of t1071, **depends on t1071_2** — shadow spawns `/aitask-learn-skill <followed_pane_id>`; needs a launch helper + an `aitask_codeagent.sh` invoke op + tmux-gateway routing + learner-pane lifecycle + shadow Step 3 entry. Created, NOT implemented. |
| (follow-up) **website docs** | NEW child of t1071, **depends on t1071_2 + the shadow spawn-learner follow-up** — document (a) the `aitask-learn-skill` command, (b) the shadow→learner spawn integration, (c) the shadow's diagnose-errors/troubleshoot capability (from t1071_1, already landed). Created, NOT implemented. |

## Step-by-step

### 0. Rewrite the task AC (see AC-update section); commit via `./ait git`.

### 1. Author shared core `.claude/skills/aitask-learn-skill/generate.md`

MAINTAINER note: "Consumer: `aitask-learn-skill/SKILL.md`. The shadow spawn-learner
follow-up reuses this by spawning the whole skill, not by reading this file. Keep
source-agnostic — input is already-gathered text." Steps (input = gathered source text):
1. **Analyze** the content; understand what the workflow/material is about.
2. **Multi-part selection** — if the content holds several distinct procedures, present
   them and ask which part(s) to learn (`AskUserQuestion`; multiSelect). Single-procedure
   content skips this.
3. **Generalization Q&A** — if the material is concrete (specific paths, task ids, names)
   and would benefit from generalization, ask clarifying questions on how to generalize
   (parameters/placeholders vs. keep literal). Skip when no generalization is needed.
4. **Name + description** (`AskUserQuestion`): new skill `name` (snake/kebab) + one-line
   `description`.
5. **Generate** `.claude/skills/<name>/SKILL.md` — minimal static frontmatter (`name`,
   `description`, `user-invocable: true`); standard section order (When to Use / Procedure
   / Pitfalls / Verification, per Hermes house style); optional sibling `.md`
   sub-procedures (no inlining). Default **static**; `.j2`/profile output out of scope.
6. **Verify** — `./.aitask-scripts/aitask_skill_verify.sh` (static passes trivially);
   stage + commit the generated skill.
7. **Report** the invocation path `/<name>`.

### 2. Author `.claude/skills/aitask-learn-skill/SKILL.md`

Static, user-invocable. Source resolution + fetch, then hand to `generate.md`:
1. **Classify the source** from argv or `AskUserQuestion`:
   - **tmux pane id** — arg matches `^%[0-9]+$` (e.g. `%5`). *(New.)*
   - local file / repo single file / repo dir / generic URL — mirror reviewguide-import
     Step 1b classification.
2. **Acquire content:**
   - **pane id → incremental deepening loop** (read-only; NOT a fixed cap):
     1. Capture an initial chunk: `SHADOW_CAPTURE_LINES=1000 ./.aitask-scripts/aitask_shadow_capture.sh <pane_id>`.
     2. Judge whether the **start** of the workflow-to-be-learned is present, or the
        earliest captured lines begin mid-workflow (truncated at the top).
     3. If truncated — confirm with the user ("the captured history may not include the
        start of this workflow; pull more?") and re-capture with `SHADOW_CAPTURE_LINES`
        increased by **+1000** each iteration (1000 → 2000 → 3000 …).
     4. Stop when the workflow's beginning is captured, OR scrollback is **exhausted** (a
        larger `SHADOW_CAPTURE_LINES` returns no additional lines — hit the top of
        history), OR the user says it is enough. Then hand the full capture to `generate.md`.
   - For a dry-run/test, accept piped content via `aitask_shadow_capture.sh -` (a fixture
     can simulate a truncated first chunk to exercise the deepening loop).
   - external → `source .aitask-scripts/lib/repo_fetch.sh && repo_fetch_file "URL"` (or
     `repo_list_md_files "URL"` for a dir) with the documented `WebFetch` raw-URL fallback;
     local files read directly. github/gitlab/bitbucket only.
3. **Read and follow `generate.md`** with the gathered content.

### 3. File follow-up tasks (Batch Task Creation Procedure; created, not implemented)

- **Cross-agent port** of `aitask-learn-skill` (`SKILL.md` + `generate.md`) to Codex
  (`.agents/skills/aitask-learn-skill/`) and OpenCode (`.opencode/skills/aitask-learn-skill/`
  + `.opencode/commands/` — plural). Claude version first.
- **Shadow spawn-learner integration** — new child of t1071, **`depends: [t1071_2]`**.
  Scope: on user request while shadowing, the shadow spawns a dedicated learner agent
  (`/aitask-learn-skill <followed_pane_id>`) in a new tmux pane via `launch_in_tmux` +
  a new `aitask_codeagent.sh invoke learn <pane_id>` op (per-agent argv), routed through
  the tmux gateway, with learner-pane lifecycle + a shadow Step 3 routing entry. The
  shadow stays advisory (it spawns; it never generates). Add a reverse coordination
  pointer per the task's plan.
- **Website documentation** — new child of t1071, **`depends: [t1071_2, <shadow-spawn-learner-id>]`**.
  Scope: add website docs for (a) the `/aitask-learn-skill` command (sources incl. pane id,
  multi-part selection, generalization), (b) the shadow→learner spawn integration, and
  (c) the shadow's existing diagnose-errors / troubleshoot capability (`plan-diagnose-errors.md`,
  t1071_1). Per the doc memories: describe the **current skill source** (not these plans),
  follow `aidocs/framework/documentation_conventions.md`, and if a new
  `website/content/docs/workflows/*.md` page is added, also add its bullet to the
  hand-curated `_index.md` grouping.

## Verification

- `./.aitask-scripts/aitask_skill_verify.sh` passes after the additions.
- **External-source dry-run:** feed a public markdown URL or local file; confirm
  `SKILL.md → generate.md` yields a well-formed static skill that itself passes
  `aitask_skill_verify.sh`, then reports `/<name>`.
- **Pane-source dry-run (fixture):** pipe a fixture transcript of a multi-step command
  sequence through `aitask_shadow_capture.sh -`; confirm the flow analyzes it, offers the
  multi-part selection, asks the generalization question, and generates a well-formed
  skill — read-only throughout (no write to any pane). Use a fixture whose first chunk
  looks truncated to exercise the **incremental deepening loop** (deepen → re-capture →
  detect exhaustion).
- **Grep checks:** `grep -n '%\[0-9\]' .claude/skills/aitask-learn-skill/SKILL.md` (pane
  classifier present); `generate.md` referenced by `SKILL.md`.
- Confirm all three follow-up tasks created + committed; the shadow follow-up has
  `depends: [t1071_2]`; the docs follow-up depends on both t1071_2 and the shadow
  follow-up; the OpenCode port names `.opencode/commands/` (plural).

## Risk

### Code-health risk: low
- Mostly markdown + reuse: NEW `aitask-learn-skill/{SKILL.md, generate.md}` and two
  follow-up tasks. The only runtime coupling is shelling out to the existing read-only
  `aitask_shadow_capture.sh` and `repo_fetch.sh` — no new code paths; `aitask_skill_verify.sh`
  passes trivially. · severity: low · → mitigation: TBD
- `generate.md` introduces a sub-procedure file (single consumer today). · severity: low
  · → mitigation: MAINTAINER note records the single consumer + the follow-up's reuse model.

### Goal-achievement risk: medium
- The pane-source analysis (understand a captured workflow, split multi-part, decide
  generalization) and the generated-skill quality are **heuristic agent judgment**, not
  deterministic; `aitask_skill_verify.sh` checks structure, not usefulness. · severity:
  medium · → mitigation: user confirms which part + the generalization Q&A + dry-run on
  both source kinds + the verify gate. Advisory/read-only — no destructive surface.
- A long workflow may exceed an initial capture window. · severity: low · → mitigation:
  the **incremental deepening loop** (Step 2) grows `SHADOW_CAPTURE_LINES` by +1000 per
  pass — with user confirmation — until the workflow start is captured or scrollback is
  exhausted; no silent truncation.
- Requirement coverage sound: four source types incl. pane id, multi-part + generalization,
  shared core, both follow-ups (port + deferred shadow spawn). · severity: low · → mitigation: TBD

## Notes for sibling tasks

- Last *originally-planned* child of t1071, but this task **creates new follow-up children**
  (cross-agent port; shadow spawn-learner `depends: [t1071_2]`; website docs `depends` on
  both), so the parent will **not** auto-archive when t1071_2 lands. Adjust any "final child
  / parent auto-archives" expectation.

## Post-implementation

Follow shared workflow **Step 9 (Post-Implementation)** for cleanup, gate verification,
archival, and merge.
