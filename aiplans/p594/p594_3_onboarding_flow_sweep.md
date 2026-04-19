---
Task: t594_3_onboarding_flow_sweep.md
Parent Task: aitasks/t594_website_documentation_coherence.md
Parent Plan: aiplans/p594_website_documentation_coherence.md
Sibling Tasks: aitasks/t594/t594_{1,2,4,5,6}_*.md
Worktree: (none — work on current branch)
Branch: main
Base branch: main
---

# t594_3 — Onboarding flow sweep

## Context

Child of t594. The website currently has **no "Next:" pointers**, so a new user lands in the tree without a forward path. This child adds the Overview → Getting Started → Installation → Workflows/tmux-ide path and writes missing section intros. Runs independently of all other children.

## Scope

**In-bounds:**
- Add "Next:" (and optionally "Prev:") footers across onboarding-path pages.
- Write section intros for `concepts/_index.md` and `skills/_index.md` ("Start here" marker).
- Tighten overview/getting-started prose where redundant with Installation, keeping self-contained completeness.
- Verify install commands and first-run behavior against `install.sh` and `aitask_setup.sh`.

**Out-of-bounds:**
- Structural edits to any page.
- Removing content from `overview.md` or `getting-started.md` that belongs in self-contained walkthroughs.

## Key pages

- `website/content/docs/_index.md` (doc root, weight 1).
- `website/content/docs/overview.md` (weight 5).
- `website/content/docs/getting-started.md` (weight 20).
- `website/content/docs/installation/_index.md` (weight 10).
- `website/content/docs/installation/windows-wsl.md`, `terminal-setup.md`, `known-issues.md`, `git-remotes.md`.
- `website/content/docs/concepts/_index.md` (weight 25).
- `website/content/docs/skills/_index.md` (weight 50).

## Reading-path Next-footer sequence

`docs/_index.md` → `overview.md` → `getting-started.md` → `installation/_index.md` → `workflows/tmux-ide.md` (handoff to workflows).

Within `installation/`: `_index.md` → (OS-specific) → `terminal-setup.md` → `git-remotes.md` → `known-issues.md`.

## Authoritative sources

| Topic | Source |
|---|---|
| Install commands | `install.sh` at repo root |
| `ait setup` first-run | `.aitask-scripts/aitask_setup.sh` |
| Project summary | `CLAUDE.md` §"Project Overview" |

## Implementation plan

1. **Next-footer pass along the main reading path** — add a concise "Next:" note at the bottom of each page pointing to the next one and explaining why (one sentence).
2. **Installation subfolder Next chain** — intra-installation ordering by weight.
3. **`concepts/_index.md` section intro:**
   - Short paragraph explaining the section's role.
   - "Required reading" list: tasks, plans, parent/child, task lifecycle, locks.
   - "Reference material" list: agent-attribution, verified-scores, agent-memory, git-branching-model, IDE-model, execution-profiles.
4. **`skills/_index.md` "Start here" callout** — one paragraph at the top pointing at `/aitask-pick` as the hub skill, with the suggestion to read it first, then branch based on use case (creation = `/aitask-explore`; batch = `/aitask-pickrem` or `/aitask-pickweb`; review = `/aitask-review`, `/aitask-qa`).
5. **Verify install commands** in `overview.md` and `getting-started.md` against `install.sh` (the curl URL, any flags).
6. **Tighten prose** where redundant — keep self-contained completeness (conservative dedup stance).
7. **Hugo build check.**

## Verification

- Click every "Next:" link starting from `docs/_index.md` — all resolve.
- `cd website && hugo build --gc --minify` succeeds.
- Read the onboarding path cold as a first-time user simulation — is there a clear forward flow?
- `concepts/_index.md` opens with the section-intro paragraph and required/reference groupings.
- `skills/_index.md` opens with a "Start here" callout pointing at `/aitask-pick`.

## Step 9 reference

Archive via `./.aitask-scripts/aitask_archive.sh 594_3`.
