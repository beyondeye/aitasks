---
Task: t839_fix_claudemd_codex_root_stale_gemini_note.md
Worktree: (none — current branch, profile 'fast')
Branch: main
Base branch: main
---

# Plan: Fix stale "shared with Gemini CLI" parenthetical in CLAUDE.md

## Context

`CLAUDE.md:203` claims Codex CLI's `.agents/skills/` is "shared with Gemini CLI". This is wrong: per `.aitask-scripts/lib/agent_skills_paths.sh`:
- gemini → `.gemini/skills`
- codex → `.agents/skills` (the only agent that currently returns `agent_shared_skills_root=true`, with future `agy` per t814 / t834)

The shared-root nuance is already correctly explained in the "Skill templating and per-profile dispatch" subsection further down in CLAUDE.md ("Shared roots (currently `.agents/skills/` for codex; +`agy` later) carry an extra `-<agent>-` segment …"). So the cleanest fix is to drop the stale parenthetical entirely rather than rewriting it.

## Implementation Steps

1. Edit `CLAUDE.md` line 203, changing:
   ```
   - **Codex CLI:** `.agents/skills/` (shared with Gemini CLI); `.codex/` holds
   ```
   to:
   ```
   - **Codex CLI:** `.agents/skills/` (shared with future `agy` agent — see
     "Skill templating and per-profile dispatch" below); `.codex/` holds
   ```

2. **In-scope addition** (per user direction during checkpoint review):
   The "Working on Skills / Custom Commands" section of `CLAUDE.md` already
   links to `aidocs/skill_authoring_conventions.md` and
   `aidocs/stub-skill-pattern.md` but does NOT link to
   `aidocs/adding_a_new_codeagent.md` — the canonical end-to-end checklist
   for wiring a new code agent. Add a `> **Read aidocs/adding_a_new_codeagent.md**`
   pointer in that section so the doc is discoverable next to the others.

   The aidocs file itself is already correct (it identifies codex + future
   agy as the shared-root agents) — no content changes inside the aidocs
   file are needed.

3. No source-code files change — `agent_skills_paths.sh` is already correct.

## Verification

- Re-read `CLAUDE.md:201-205` and confirm no mention of "Gemini" in the Codex bullet.
- Confirm the templating subsection (further down) still owns the detailed shared-root explanation — no duplication added.

## Step 9 (Post-Implementation)

Profile 'fast' on current branch — no worktree to clean. Standard archival via `aitask_archive.sh 839`.

## Final Implementation Notes
- **Actual work done:**
  - `CLAUDE.md:203` — Replaced "(shared with Gemini CLI)" with "(shared with future `agy` agent — see 'Skill templating and per-profile dispatch' below)".
  - `CLAUDE.md:228-231` — Added new `> **Read aidocs/adding_a_new_codeagent.md**` pointer next to existing `skill_authoring_conventions.md` / `stub-skill-pattern.md` references, with one-line hook listing the doc's coverage (skill discovery / rendering, shared-root semantics, rerender driver, headless variants, goldens regeneration).
- **Deviations from plan:** The "Read aidocs/adding_a_new_codeagent.md" pointer was added on top of the original 1-line defect fix per user direction during the Step 6 checkpoint review ("if the work in this task is relevant please add this to the scope"). The aidocs file itself was confirmed already-correct, so no content edits inside it.
- **Issues encountered:** None.
- **Key decisions:**
  - Kept a brief parenthetical reference ("shared with future `agy` agent — see 'Skill templating and per-profile dispatch' below") rather than dropping the parenthetical entirely. Reasoning: readers landing on the "Working on Skills / Custom Commands" section read it before reaching the templating subsection further down, so the inline cue preserves the shared-root fact for left-to-right readers.
- **Upstream defects identified:** None.
