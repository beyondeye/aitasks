---
priority: medium
effort: high
depends: [t399_1]
issue_type: feature
status: Ready
labels: [aitask-redesign, claudeskills, codexcli, geminicli, opencode]
created_at: 2026-03-17 18:51
updated_at: 2026-03-17 18:51
---

## Implement Redesign Skill

### Context

This child implements the new `/aitask-redesign` workflow approved by
`t399_1`. The design goal is to keep the implementation mostly in markdown skill
files by reusing the repository's existing task/plan helpers rather than adding
new shell infrastructure. The finished result should be reachable from Claude,
OpenCode, and the unified Codex/Gemini wrappers.

### Key Files To Modify

- `.claude/skills/aitask-redesign/SKILL.md` - main source-of-truth skill
- `.claude/skills/aitask-redesign/` - optional helper markdowns if the source
  skill becomes too large for a single file
- `.agents/skills/aitask-redesign/SKILL.md` - unified Codex/Gemini wrapper
- `.opencode/skills/aitask-redesign/SKILL.md` - OpenCode wrapper
- `.opencode/commands/aitask-redesign.md` - OpenCode command entry point

### Reference Files For Patterns

- `.claude/skills/aitask-revert/SKILL.md` - source task resolution across active
  and archived states
- `.claude/skills/aitask-explore/SKILL.md` - guided discovery and task creation
- `.claude/skills/aitask-fold/SKILL.md` - save-for-later vs continue-now prompt
- `.opencode/skills/aitask-revert/SKILL.md` - OpenCode wrapper format
- `.agents/skills/aitask-revert/SKILL.md` - unified Codex/Gemini wrapper format

### Implementation Plan

1. Read `aidocs/aitask_redesign_spec.md` from child `t399_1` and treat it as
   the behavioral source of truth.
2. Create `.claude/skills/aitask-redesign/SKILL.md` with:
   - frontmatter
   - optional task-id argument handling
   - execution profile selection at the start
3. Implement source-task discovery:
   - direct id path
   - interactive path when no id is passed
   - use `./.aitask-scripts/aitask_revert_analyze.sh --find-task <id>` to locate
     the source task and source plan across active/archive storage
   - unpack deep-archived task data only when needed
4. Implement source-context gathering:
   - read the source task file
   - read the source plan file if present
   - gather any parent-level context the spec requires for redesign decisions
5. Implement redesign-trigger selection with clear options such as:
   - post-revert redesign
   - changed requirements
   - changed infrastructure or tech
   - brainstorm alternatives
   - other
6. Implement the guided redesign conversation:
   - one clarifying question at a time
   - produce 2-3 approaches with trade-offs
   - recommend one approach
   - require approval before writing files
7. Implement redesign task creation with
   `./.aitask-scripts/aitask_create.sh --batch --commit ...`.
8. Implement matching redesign plan creation in `aiplans/`, following the task
   and plan templates defined by child `t399_1`.
9. Implement the end-of-skill decision point:
   - continue to implementation now
   - save for later
   - reuse the existing profile pattern and `explore_auto_continue`
10. If the user continues immediately, hand off the new task to the shared
    task-workflow.
11. If the user saves for later, run the same satisfaction-feedback pattern used
    by other standalone skills.
12. Add wrapper files for OpenCode and unified Codex/Gemini by following the
    same wrapper structure used by the existing skills.
13. Only add new shell helpers if the implementation truly cannot be expressed
    with existing scripts and the gap is documented in the final notes.

### Verification Steps

- the Claude source skill has a coherent happy path for `/aitask-redesign 399`
- every referenced helper script and file path exists
- wrapper files point to the Claude source skill and match repository patterns
- the new redesign task and plan naming follow normal `t...` and `p...`
  conventions
