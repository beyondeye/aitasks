---
priority: low
effort: high
depends: []
issue_type: feature
status: Ready
labels: [claudeskills]
created_at: 2026-02-16 12:38
updated_at: 2026-02-16 12:38
boardidx: 10
boardcol: next
---

## Context

Follow-up improvements for the `/aitask-explore` skill (created in t129_2). These are ideas for making exploration more effective over time by building persistent project knowledge and adding configuration hooks.

## Improvement Ideas

### 1. Persistent Exploration Findings (Project Knowledge Base)

Store general findings about the current project that make future explorations faster/easier. For example, after exploring the codebase structure, save a summary that subsequent explorations can reference.

**Possible implementation:**
- Store findings in `aitasks/metadata/explore_findings/` as markdown files keyed by exploration type or topic
- Auto-load relevant findings at the start of each exploration based on the selected type
- Include a timestamp and staleness mechanism

**Pros:**
- Dramatically speeds up repeat explorations of the same project
- Builds institutional knowledge over time
- New team members benefit from past explorations

**Cons:**
- Findings can become stale as code evolves
- Need a mechanism to detect staleness (e.g., check if key files have changed since the finding was recorded)
- Storage overhead and potential for outdated information misleading Claude

**Staleness options:**
- a) Timestamp-based: flag findings older than N days and ask user if they need updating
- b) Git-hash-based: record git hash of key files at time of finding; if files changed, prompt for re-exploration
- c) Manual: user triggers a "refresh findings" command
- d) Hybrid: use git-hash for detection, timestamp as fallback

### 2. Per-Type User Directions (Exploration Configs)

Allow users to store general directions for each exploration type, specific to their project. For example:
- "Documentation for this project is in README.md, aiscripts/*.sh --help output, and SKILL.md files"
- "For debugging, always check the log output in /tmp/aitask_*.log first"

**Possible implementation:**
- Store in `aitasks/metadata/explore_directions/` with one file per exploration type (e.g., `documentation.md`, `debugging.md`, `scoping.md`)
- Loaded automatically when the matching exploration type is selected
- User can edit these files directly or through a setup flow

**Pros:**
- Tailors exploration to the specific project's conventions
- Reduces time spent on initial orientation
- User maintains control over what Claude should focus on

**Cons:**
- Yet another config file for users to manage
- May constrain exploration when directions are too narrow

### 3. Module-Specific Exploration Hints

Extend the per-type directions with per-module hints. For example, knowing that the `aiscripts/` module uses bash with specific conventions, or that `.claude/skills/` follows a particular pattern.

**Possible implementation:**
- Extend explore_directions files with module-specific sections
- Or use a directory structure: `explore_directions/<type>/<module>.md`

### 4. Exploration History

Track past explorations (what was explored, when, what task was created) to avoid redundant re-exploration and provide continuity.

**Possible implementation:**
- Append to `aitasks/metadata/explore_history.log` after each exploration
- Format: `<date> | <type> | <focus> | <task_created>`
- Show recent history at start of new exploration

## Verification Steps

1. For each improvement, verify it integrates cleanly with the existing SKILL.md workflow
2. Ensure staleness detection doesn't add excessive overhead to exploration startup
3. Test that exploration directions are loaded correctly for each type
