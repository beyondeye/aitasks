---
priority: medium
effort: low
depends: [t227_5]
issue_type: documentation
status: Done
labels: [documentation, remote]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-02-24 16:52
updated_at: 2026-02-25 00:18
completed_at: 2026-02-25 00:18
---

Document the new Claude Web workflow, the updated locking model, and create a Claude Web execution profile.

## Context

Several new workflow patterns have been introduced by the t227 child tasks. These need to be documented for users and future development:
1. Locking as a separate pre-pick operation (via board)
2. Lock-aware aitask-pick (detects pre-existing locks)
3. aitask-pickweb for Claude Code Web (no cross-branch ops)
4. aitask-web-merge for post-completion integration
5. Per-user config (userconfig.yaml)

## Deliverables

### 1. Create `aidocs/claude_web_workflow.md`
- Standard workflow: lock (board) -> pick -> implement -> archive
- Claude Web workflow: lock (board) -> pickweb -> implement on branch -> web-merge
- Explanation of `.aitask-data-updated/` directory purpose and format
- Step-by-step instructions for running tasks on Claude Web
- Troubleshooting: merge failures, conflict handling

### 2. Create execution profile `aitasks/metadata/profiles/claude-web.yaml`
- Tailored defaults for the pickweb skill
- All necessary fields for Claude Web environment

### 3. Update CLAUDE.md
- Brief reference to Claude Web workflow and link to `aidocs/claude_web_workflow.md`
- Document the userconfig.yaml file and its purpose

### 4. Update t227 parent task description
- Summary of what was verified about t220 (stale locks -- complete, archival-based cleanup)
- Links to child tasks and their outcomes

## Key Files to Create/Modify
- `aidocs/claude_web_workflow.md` -- new documentation
- `aitasks/metadata/profiles/claude-web.yaml` -- new profile
- `CLAUDE.md` -- brief update

## Verification
- Review `aidocs/claude_web_workflow.md` for accuracy and completeness
- Verify the claude-web profile works with pickweb
