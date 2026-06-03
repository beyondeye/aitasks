---
Task: t924_restructure_claude_md.md
Base branch: main
plan_verified: []
---

# Plan: Restructure CLAUDE.md — move on-demand sections to aidocs (t924)

## Context

`CLAUDE.md` is **always-loaded** context for every session in this repo. Several
sections are specialist rules only needed during specific work, yet they sit in
the always-loaded file and inflate every session's base context. The task
(t924, `issue_type: performance`) asks to relocate these to on-demand
`aidocs/framework/` files (merging with existing ones where appropriate), or —
where the content is really procedure/skill behavior — into the procedure/skill
that owns it. Intended outcome: a leaner CLAUDE.md that keeps only genuinely
always-relevant orientation, with each moved block reachable via a pointer or
already living where it's used.

Key finding from exploration: **most of the "Working on Skills" content already
exists** in `skill_authoring_conventions.md`, `stub-skill-pattern.md`, and
`adding_a_new_codeagent.md`. Per `documentation_conventions.md` ("read Y first;
if Y covers it, integrate collapses to cross-references"), item 4 is mostly
consolidation to pointers, not bulk migration.

Blast-radius note: rendered skill variant dirs (`*-/`) are **gitignored**;
`model-self-detection.md` has **no golden**. So the skill-touching moves need a
local rerender + `aitask_skill_verify.sh`, and only the small aitask-pick note
(item 5) churns committed goldens.

## The five relocations

### 1. Shell Conventions → new `aidocs/framework/shell_conventions.md`
- Create `aidocs/framework/shell_conventions.md`; move the entire CLAUDE.md
  `## Shell Conventions` block (CLAUDE.md:97-132, including the existing macOS
  portability pointer to `sed_macos_issues.md`) into it verbatim.
- In CLAUDE.md, replace the section with a pointer:
  `> **Read aidocs/framework/shell_conventions.md** when writing or editing any
  shell script under .aitask-scripts/ …`
- Fix the two now-stale cross-references that point back at CLAUDE.md:
  - `aidocs/framework/code_conventions.md`: "general shell style … lives
    directly in `CLAUDE.md`" → "lives in `aidocs/framework/shell_conventions.md`".
  - CLAUDE.md "Planning / Testing / Code Conventions" pointer (CLAUDE.md:338-339):
    "general shell style stays in the Shell Conventions section above" →
    point to `aidocs/framework/shell_conventions.md`.

### 2. Documentation Writing → merge into `aidocs/framework/documentation_conventions.md`
- Move the prose bullets (CLAUDE.md:166-183: current-state-only rule + the
  "Delete X, eventually integrate into Y" rule) into
  `documentation_conventions.md` as a new top section.
- Update that file's self-reference (it currently calls itself a "Companion to
  CLAUDE.md's 'Documentation Writing' section") since the content now lives there.
- Collapse the CLAUDE.md section + its existing pointer (CLAUDE.md:185-188) into
  a single pointer block to `documentation_conventions.md`.

### 3. Model Attribution → into the Model Self-Detection procedure
- Move CLAUDE.md:190-212 (mid-session `/model` switch detection + the `[1m]`
  1M-suffix caveat) into
  `.claude/skills/task-workflow/model-self-detection.md`, refining **step 2's
  Claude Code bullet** ("Read the exact model ID from the system message") — this
  is exactly the "fixes how the procedure works" case the task calls out.
- **Remove** the `## Model Attribution` section from CLAUDE.md entirely (no
  pointer — it's runtime procedure behavior, not a contributor pointer).
- The file `aidocs/framework/model_reference_locations.md` is already referenced
  by both; keep that reference inside the procedure text.

### 4. Working on Skills / Custom Commands → consolidate to pointers
- Verify against the three target docs and migrate only the genuinely-unique
  always-loaded bits not already covered:
  - source-of-truth statement (Claude Code first) + per-agent surfaces
    (Codex `.agents/skills/`, OpenCode `.opencode/`),
  - the IMPORTANT "do Claude first, suggest port follow-ups" rule,
  - invocation paths (`/aitask-pick --profile fast 42`, `ait skillrun pick …`).
  Target: `skill_authoring_conventions.md` (per-profile dispatch belongs there).
- The per-agent surface table, jinja patterns, and `agent_skill_root` mechanics
  (CLAUDE.md:251-301) are **already** in `stub-skill-pattern.md` §3g,
  `skill_authoring_conventions.md` §"Jinja templating", and
  `adding_a_new_codeagent.md` §1b → do not duplicate; redirect via pointers.
- Collapse CLAUDE.md's "Working on Skills" + "Skill templating and per-profile
  dispatch" into one concise pointer block (keep existing pointers to
  skill_authoring_conventions.md, stub-skill-pattern.md, adding_a_new_codeagent.md,
  agent_runtime_guards_audit.md).

### 5. Manual verification note → remove from CLAUDE.md, enrich aitask-pick skill
- Remove the Manual-verification bullet from CLAUDE.md "Project-Specific Notes"
  (CLAUDE.md:374-380). The other two notes (diffviewer transitional, cross-repo
  coordination) **stay**.
- Enrich the existing aitask-pick note (`.claude/skills/aitask-pick/SKILL.md.j2`
  line ~207) with the bits worth preserving: the Pass/Fail/Skip/Defer dispatch at
  Step 3 Check 3, the aggregate-sibling offer during parent planning (≥2
  children), and the `website/content/docs/workflows/manual-verification.md`
  pointer.

## Files touched
- `CLAUDE.md` — remove/trim 5 sections, add pointer blocks.
- `aidocs/framework/shell_conventions.md` — **new**.
- `aidocs/framework/documentation_conventions.md` — absorb doc-writing prose.
- `aidocs/framework/code_conventions.md` — fix stale shell cross-ref.
- `aidocs/framework/skill_authoring_conventions.md` — absorb unique skill-ops bits.
- `.claude/skills/task-workflow/model-self-detection.md` — absorb model-attribution nuance.
- `.claude/skills/aitask-pick/SKILL.md.j2` — enrich manual-verification note.
- `tests/golden/skills/aitask-pick/SKILL-{default,fast,remote}-claude.md` — regenerate.

## Implementation order
1. Items 1, 2, 4 (pure CLAUDE.md ↔ aidocs prose; no goldens).
2. Item 3 (edit closure source).
3. Item 5 (edit aitask-pick `.md.j2` note).
4. `grep` the repo for inbound references to the moved CLAUDE.md sections
   ("Shell Conventions section above", "Documentation Writing section",
   "lives directly in CLAUDE.md", "## Model Attribution") and redirect any.
5. Regenerate aitask-pick goldens (3 profiles, `claude`) per the
   skill_authoring_conventions.md "Regenerate goldens" loop.
6. Local rerender of changed closures (`aitask_skill_rerender.sh default|fast|remote`).

## Verification
- `grep -n '^## ' CLAUDE.md` — confirm Shell Conventions / Documentation Writing /
  Model Attribution / Skill-templating sections are gone or collapsed to pointers,
  and Manual-verification bullet removed.
- Confirm `aidocs/framework/shell_conventions.md` exists with the full block.
- `./.aitask-scripts/aitask_skill_verify.sh` → passes (stub markers, dep-closure
  render cleanliness, headless prerender freshness).
- `bash tests/test_skill_render_aitask_pick.sh` (or the matching render test) →
  Test 1 green against regenerated goldens.
- Final repo-wide `grep` shows no dangling cross-reference to a removed CLAUDE.md
  section.

## Step 9 (Post-Implementation)
Single-task workflow: commit (issue_type `performance` → `performance: …(t924)`
for CLAUDE.md/aidocs; skill+golden edits land in the same commit per the
"goldens land with the template edit" rule), then archive via
`./.aitask-scripts/aitask_archive.sh 924` and push. No branch/worktree (fast
profile works on current branch).

## Risk

### Code-health risk: low
- Documentation/closure reorganization only; no executable code paths change.
  Main hazard is stale inbound cross-references, covered by the grep sweep in
  implementation step 4 and verification. · severity: low · → mitigation: none
- Skill-template edit (item 5) churns committed goldens; mitigated by regenerating
  + running the render test in the same commit. · severity: low · → mitigation: none

### Goal-achievement risk: low
- Each relocation has a confirmed destination and the two structural forks
  (shell-conventions home; manual-verification handling) are already decided with
  the user. · severity: low · → mitigation: none
