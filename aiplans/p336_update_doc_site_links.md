---
Task: t336_update_doc_site_links.md
Worktree: (current directory)
Branch: (current branch)
Base branch: main
---

# Implementation Plan

## Summary

Update README documentation links from the legacy GitHub Pages host to the custom domain rooted at `https://aitasks.io/`.

## Planned Changes

- Verify the custom-domain migration using repository configuration as the accepted source of truth for this task.
- Replace `https://beyondeye.github.io/aitasks/` with `https://aitasks.io/` in the README files covered by the task:
  - `README.md`
  - `docs/README.md`
  - `website/README.md`
- Preserve all existing path suffixes and fragment identifiers.
- Leave Hugo config, CNAME, and non-README references unchanged.

## Verification

- Search the three README files to confirm no `https://beyondeye.github.io/aitasks/` links remain.
- Spot-check representative updated links for the site root, docs subpaths, and anchor fragments.

## Step 9 Reminder

- Archive the task through the standard post-implementation workflow after review and commit.

## Final Implementation Notes

- **Actual work done:** Updated all README documentation links from the GitHub Pages host to `https://aitasks.io/` while preserving link paths and fragments.
- **Deviations from plan:** Used repo configuration rather than a live DNS/HTTP check because the current environment could not resolve the target domain.
- **Issues encountered:** Direct `curl` checks for the custom domain failed with DNS resolution errors in this environment.
- **Key decisions:** Kept the scope limited to README files only, and treated the task text's `aitaks.io` spelling as incorrect based on the selected implementation plan.
