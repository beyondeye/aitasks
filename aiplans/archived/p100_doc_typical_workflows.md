---
Task: t100_doc_typical_workflows.md
Worktree: (current branch)
Branch: main
Base branch: main
---

# Plan: Document Typical Workflows in README (t100)

## Context

The aitask framework has comprehensive command reference and skill documentation in the README, but lacks a cohesive section showing how these tools work together in real development workflows. The task owner has provided 6 workflow descriptions (raw, stream-of-consciousness) that need to be organized, polished, and documented with proper cross-references to existing README sections.

## Approach

Add a new **"Typical Workflows"** section to `README.md` after the "Claude Code Integration" section and before "Task File Format". This placement ensures all tools/skills are already defined, allowing the workflows to use anchor links.

## Files to Modify

- `README.md` — Add new section and update Table of Contents

## Implementation Steps

### Step 1: Update Table of Contents

Add a new "Typical Workflows" entry to the ToC between "Claude Code Integration" and "Task File Format", with sub-entries for each workflow:

```
- [Typical Workflows](#typical-workflows)
  - [Capturing Ideas Fast](#capturing-ideas-fast)
  - [Complex Task Decomposition](#complex-task-decomposition)
  - [GitHub Issue Development Workflow](#github-issue-development-workflow)
  - [Parallel Development](#parallel-development)
  - [Multi-Tab Terminal Workflow](#multi-tab-terminal-workflow)
  - [Monitoring While Implementing](#monitoring-while-implementing)
```

### Step 2: Add the "Typical Workflows" section

Insert the full section after the `/aitask-changelog` subsection (line ~837, before `## Task File Format`). Each workflow will be a subsection (`###`) covering:

1. **Capturing Ideas Fast** — Based on workflow (*) about `ait create` and capturing intent quickly. Emphasize the philosophy of "capture now, refine later" and the iterative refinement pipeline (create → board → pick).

2. **Complex Task Decomposition** — Based on workflow (*) about child tasks. Document how `/aitask-pick` detects complex tasks, how to force decomposition, how archived sibling plans provide context, and the controlled execution of child tasks.

3. **GitHub Issue Development Workflow** — Based on workflow (*) about issue integration. Document the full cycle: `ait issue-import` → task creation → `/aitask-pick` implementation → `ait issue-update` → issue closed with implementation notes and commit references.

4. **Parallel Development** — Based on workflow (*) about multi-developer/multi-agent support. Document status tracking via git push, atomic locking, git worktree isolation, and safety considerations.

5. **Multi-Tab Terminal Workflow** — Based on workflow (*) about terminal-centric development. Document the recommended terminal setup (Warp, tmux, Ghostty), multiple tabs for different contexts, and IDE alternatives.

6. **Monitoring While Implementing** — Based on workflow (*) about using `ait board` while `/aitask-pick` runs. Document the parallel workflow of implementation + task management + idea capture.

Each workflow section will include:
- A brief description of the workflow and when to use it
- Cross-reference links to relevant commands and skills
- Practical tips

## Verification

- Verify all internal anchor links resolve correctly
- Read through the section to ensure it flows naturally
- Check that no existing README content is accidentally altered

## Final Implementation Notes
- **Actual work done:** Added 123 lines to README.md: a "Typical Workflows" section with 6 subsections covering capturing ideas, complex task decomposition, GitHub issue workflow, parallel development, multi-tab terminal setup, and monitoring while implementing. Updated the Table of Contents with the new section and sub-entries. All 6 raw workflow descriptions from the task were organized, rewritten in clear English, and enriched with cross-reference links to existing README sections.
- **Deviations from plan:** None — implementation followed the plan exactly.
- **Issues encountered:** None.
- **Key decisions:** Placed the section after "Claude Code Integration" and before "Task File Format" so all referenced tools/skills are already defined. Used `###` level headings for each workflow to match the existing document structure. Included a table for the multi-tab terminal layout for visual clarity.
