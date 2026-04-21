---
priority: medium
effort: medium
depends: []
issue_type: chore
status: Ready
labels: [task_workflow, documentation]
folded_tasks: [384]
created_at: 2026-04-21 09:11
updated_at: 2026-04-21 09:11
---

Scan all active Claude Code memory files for this project, consolidate each feedback entry into the appropriate durable location, then delete the memory files and `MEMORY.md` index.

**Durable-location policy:**
- Memories that fit CLAUDE.md → consolidate inline here.
- Memories that belong in a specific skill/workflow file → create a dedicated follow-up aitask (one per memory) that addresses the concern at the referenced location.
- Goal (from folded-in t384): no implicit behavior; make rules reproducible across Claude Code / Codex / Gemini / OpenCode by putting workflow-internal rules into `.claude/skills/task-workflow/` (which ports to other agent trees).

## Memory root

`/home/ddt/.claude/projects/-home-ddt-Work-aitasks/memory/`

8 active files + `MEMORY.md` index. The index also lists 14 entries whose files no longer exist — those resolve automatically when `MEMORY.md` is deleted.

## CLAUDE.md consolidation (do inline)

| # | File | Target section in CLAUDE.md |
|---|---|---|
| 3 | `feedback_eventually_integrate.md` | *Documentation Writing* — "Delete X, integrate into Y" = redirect cross-refs now, defer content migration to follow-up |
| 5 | `feedback_no_autopush_config.md` | *TUI Conventions* — Runtime TUI saves must not auto-commit/push project-level config; only user-level (gitignored) layer is writable at runtime |
| 6 | `feedback_profile_vs_guard.md` | *Skill/Workflow Authoring Conventions* — **reword** the existing "Use guard variables, not prose" bullet (CLAUDE.md:160) to distinguish: profile keys for user opt-in/out; guards for preventing double-firing only. Don't simply append. |
| 7 | `feedback_refactor_duplicates_first.md` | New *Planning Conventions* section — when a plan touches the same data in 3+ places, propose a single-source-of-truth refactor before accepting the duplicated edit |
| 8 | `feedback_tui_footer_sibling_keys.md` | *TUI Conventions* — contextual footer: uppercase sub-action (e.g., D) adjacent to its lowercase primary (d), not demoted to the tail |

For each entry, carry over the "Why" (grounding incident) and "How to apply" guidance — these are the transferable parts.

## Follow-up aitasks to create (do NOT inline into CLAUDE.md)

Create each of these as a standalone aitask during planning of this task:

1. **Memory #1 — await_review_checkpoint:** Create aitask to update `.claude/skills/task-workflow/SKILL.md` so Step 8 "Implementation complete, please review and test" review checkpoint fires unconditionally, regardless of profile (`fast`, auto mode, etc.). Plan approval / satisfaction feedback answers must not be treated as commit approval. Include the exact guardrails from the memory: no profile key currently legitimately skips Step 8.
2. **Memory #2 — docs_vs_source:** Create aitask to update `.claude/skills/task-workflow/planning.md` (and/or `.claude/skills/aitask-explore/SKILL.md`) so any task whose scope includes documentation review, coherence, or accuracy must launch at least one Explore agent for source-vs-docs verification with concrete citations on both sides, and bake the drift list into the plan as first-class scope items per child task.
3. **Memory #4 — manual_verification_aggregate:** Create aitask to update `.claude/skills/task-workflow/planning.md` so parent tasks with 2+ TUI-touching siblings get a single aggregate manual-verification sibling task (naming pattern `t<parent>_<last>_manual_verification_*`, issue_type `test`, depends on all TUI-touching siblings). **Pre-check:** verify the current state of t583 (`t583_manual_verification_module_for_task_workflow.md`) before codifying — the memory is 3 days old and references t583 as a "future module"; the pattern may have evolved or been superseded.

Each follow-up aitask should cite the original memory's framing and the incident that motivated it (see memory files before deletion).

## Deletion

After the CLAUDE.md inline consolidation lands AND the three follow-up aitasks exist:

1. Delete the 8 memory files.
2. Delete `MEMORY.md`.
3. Leave the `memory/` directory itself in place (Claude Code may recreate it).

## Mirror to other code-agent trees

After CLAUDE.md updates land, per the standard `WORKING ON SKILLS / CUSTOM COMMANDS` policy, create follow-up aitasks to mirror any changes into `.opencode/`, `.gemini/`, `.codex/`, `.agents/` where applicable. CLAUDE.md itself is Claude-Code-specific, but if any of the inlined rules should propagate to other agents' project-instructions files, call that out explicitly.

## Non-goals

- Migrating feedback rules into runtime guards or test assertions — this is a documentation-consolidation task.
- Restructuring the rest of CLAUDE.md beyond the specific inserts/rewordings needed.

## Acceptance

- [ ] 5 memories (3, 5, 6, 7, 8) consolidated into CLAUDE.md at the correct sections
- [ ] CLAUDE.md:160 "guard variables" bullet reworded (not just appended) to reflect memory #6
- [ ] 3 follow-up aitasks created (for memories 1, 2, 4)
- [ ] 8 memory files + `MEMORY.md` deleted
- [ ] Follow-up aitasks filed to mirror applicable CLAUDE.md rules into other code-agent trees if needed

## Merged from t384: fixes from claude memory


claude code has memory files at /home/ddt/.claude/projects/-home-ddt-Work-aitasks/memory where it stores feedback on rejects by user about how it executed user commands. create a plan to update existing task workflows with this feedback, then delete this memory files. we don't want any behavior that is implicit. we want reproducible behavior also in the other code agents we use

## Folded Tasks

The following existing tasks have been folded into this task. Their requirements are incorporated in the description above. These references exist only for post-implementation cleanup.

- **t384** (`t384_fixes_from_claude_memory.md`)
