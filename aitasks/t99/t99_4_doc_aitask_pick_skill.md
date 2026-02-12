---
priority: medium
effort: medium
depends: []
issue_type: documentation
status: Ready
labels: [aitasks]
created_at: 2026-02-12 10:56
updated_at: 2026-02-12 10:56
---

## Context
This is child task 4 of t99 (Update Scripts and Skills Docs). The parent task updates README.md documentation for all aitask scripts and skills. Each child writes a documentation snippet file; a final consolidation task (t99_6) merges them into README.md.

## Goal
Document the /aitask-pick skill comprehensively. This is the most complex skill in the framework (817 lines) and the existing README docs are only a brief summary.

## Output
Write documentation to `aitasks/t99/docs/04_pick_skill.md`. This snippet file will contain an updated `### /aitask-pick [number]` section ready to replace the existing one in README.md.

## Skill to Review and Document

### /aitask-pick (`.claude/skills/aitask-pick/SKILL.md`)
- Read the full 817-line skill file
- The existing README docs (lines 125-141 of README.md) are a brief 17-line summary
- Expand to cover the full workflow while keeping it a README overview (not replicating the full SKILL.md)

**Required coverage:**
1. **Workflow overview** — List all 10 steps briefly: profile selection → task selection → child task handling → status checks → assignment → environment setup → planning → implementation → user review → post-implementation
2. **Direct task selection** — Document `/aitask-pick 10` (parent) and `/aitask-pick 10_2` (child) argument formats
3. **Execution profiles** — Brief mention with reference to the "Execution Profiles" section (already well-documented in README)
4. **Child task handling** — How parent tasks with children are drilled down, sibling context from archived plans
5. **Plan mode integration** — Three options when plan exists: use current, verify, create new
6. **Task decomposition** — How complex tasks can be broken into child tasks during planning
7. **User review cycle** — Post-implementation review with "need more changes" loop
8. **Issue update integration** — Automatic issue update/close for linked tasks
9. **Abort handling** — Status reversion, plan file handling, worktree cleanup
10. **Branch/worktree support** — Optional isolated branches for parallel work

**Tone:** Capabilities overview — what aitask-pick can do and how the workflow flows. Not a step-by-step manual.

## Reference Files
- `.claude/skills/aitask-pick/SKILL.md` — The authoritative source (817 lines)
- Current README.md lines 125-141 — The existing brief docs to be replaced
- Current README.md lines 176-223 — The Execution Profiles section (already good, just reference it)

## Documentation Format
Use `### /aitask-pick [number]` heading. Start with one-line description. Then features/workflow overview. Usage examples at end.

## Verification
- Snippet covers all 10 workflow steps at overview level
- Both argument formats documented (parent and child)
- Does not duplicate Execution Profiles content (references it instead)
- Comprehensive but stays at README level (not SKILL.md level of detail)
