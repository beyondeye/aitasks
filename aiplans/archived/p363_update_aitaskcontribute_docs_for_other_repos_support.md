---
Task: t363_update_aitaskcontribute_docs_for_other_repos_support.md
Worktree: (none — working on current branch)
Branch: main
Base branch: main
---

# Plan: Refresh `/aitask-contribute` docs for project repo support (t363)

## Context

The `/aitask-contribute` skill and supporting scripts now work in two user-facing modes:
- contribute improvements to the `aitasks` framework
- contribute changes to the current project repository when that repository uses the aitasks framework

The website documentation still described the skill as if it only contributed changes back to the upstream `aitasks` repository. The docs needed to be updated to match the current behavior while staying concise and user-focused.

## Implementation Plan

1. Update the `/aitask-contribute` skill page so it leads with user value, explains the two supported contribution targets, and keeps the workflow description short and practical.
2. Update the contribution workflow guide so the `/aitask-contribute` section works for both framework and project-repo contributions, including the lifecycle diagram wording.
3. Update the overview blurb so the product-level description reflects both supported contribution targets.
4. Keep the wording precise but avoid unnecessary implementation detail. Mention code area maps only where that affects what a user will see in project mode.
5. Verify the edited docs render cleanly with a Hugo build.

## Verification

- Review the edited content against the current `/aitask-contribute` skill and script behavior
- Run `hugo build --gc --minify` in `website/`

## Final Implementation Notes

- **Actual work done:** Updated the `/aitask-contribute` skill doc, the contribution workflow guide, and the overview blurb. The copy now presents the feature in user-first language and clearly states that it supports both framework contributions and project-repo contributions.
- **Deviations from plan:** None. The implementation stayed within the planned three-page docs sweep.
- **Issues encountered:** None.
- **Key decisions:** Kept technical detail intentionally light. The docs mention project-mode code area maps only where needed to explain the user experience, and otherwise focus on the user outcome and workflow.
- **Verification:** `hugo build --gc --minify` completed successfully in `website/`.
