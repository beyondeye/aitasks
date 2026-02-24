---
Task: t227_6_document_the_new_claude_web_workflow.md
Parent Task: aitasks/t227_aitask_own_failure_in_cluade_web.md
Sibling Tasks: aitasks/t227/t227_1_*.md, aitasks/t227/t227_2_*.md, aitasks/t227/t227_3_*.md, aitasks/t227/t227_4_*.md, aitasks/t227/t227_5_*.md
Worktree: (none - current branch)
Branch: main
Base branch: main
---

# Plan: t227_6 — Document the new Claude Web workflow

## Context

Several new workflow patterns introduced by t227 children need documentation.

## Implementation Steps

### Step 1: Create aidocs/claude_web_workflow.md
- Standard workflow: lock (board) → pick → implement → archive
- Claude Web workflow: lock (board) → pickweb → implement → web-merge
- `.task-data-updated/` directory format and purpose
- Step-by-step instructions
- Troubleshooting section

### Step 2: Create claude-web execution profile
- `aitasks/metadata/profiles/claude-web.yaml` tailored for pickweb

### Step 3: Update CLAUDE.md
- Brief reference to Claude Web workflow
- Link to `aidocs/claude_web_workflow.md`
- Document userconfig.yaml

### Step 4: Update t227 parent task description
- Summary of t220 verification findings
- Child task outcomes

## Key Files
- **Create:** `aidocs/claude_web_workflow.md`, `aitasks/metadata/profiles/claude-web.yaml`
- **Modify:** `CLAUDE.md`

## Verification
- Review docs for accuracy
- Verify claude-web profile works with pickweb

## Post-Implementation (Step 9)
Archive this child task. Parent t227 auto-archives when all children complete.
