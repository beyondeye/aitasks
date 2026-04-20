---
priority: high
effort: low
depends: []
issue_type: documentation
status: Ready
labels: []
implemented_with: claudecode/opus4_7_1m
created_at: 2026-04-19 17:11
updated_at: 2026-04-20 09:14
---

Child of t594. Add forward-reading flow and bridging content to the ~10 onboarding-path pages.

## Context

Parent plan: `aiplans/p594_website_documentation_coherence.md`. The site currently has no "Next:" pointers, so a new user lands in a tree with no path to follow. This child adds the Overview → Getting Started → Installation → Workflows/tmux-ide path and writes missing section intros.

## Key Files to Modify

- `website/content/docs/_index.md` — doc root landing; add Next → Overview.
- `website/content/docs/overview.md` — Next → Getting Started.
- `website/content/docs/getting-started.md` — Next → Installation.
- `website/content/docs/installation/_index.md` — add Next → tmux-ide workflow (primary entry after install).
- `website/content/docs/installation/windows-wsl.md`, `terminal-setup.md`, `known-issues.md`, `git-remotes.md` — add Next footers.
- `website/content/docs/concepts/_index.md` — section intro explaining which concepts are required reading vs reference.
- `website/content/docs/skills/_index.md` — "Start here" marker pointing at `/aitask-pick`.

## Reference Files for Patterns (Authoritative Sources)

- `install.sh` at repo root — for verifying install commands.
- `.aitask-scripts/aitask_setup.sh` — for verifying first-run behavior claimed in getting-started.md.
- `CLAUDE.md` §"Project Overview" — the concise project description.

## Implementation Plan

1. Walk the reading path `_index → overview → getting-started → installation → workflows/tmux-ide`; for each page, add a "Next:" footer (short note + link) at the bottom.
2. Within `installation/` subfolder, add Next footers linking its pages in weight order.
3. Write a section intro for `concepts/_index.md`:
   - Required reading (tasks, plans, parent/child, task-lifecycle, locks).
   - Reference material (agent-attribution, verified-scores, agent-memory, git-branching-model, IDE model).
4. Add a "Start here" callout at the top of `skills/_index.md`: the hub skill is `/aitask-pick` — read that first, then branch out.
5. Verify install commands in `overview.md` and `getting-started.md` against `install.sh`.
6. Tighten overview/getting-started prose where redundant with Installation — keep self-contained completeness per conservative dedup stance.

## Verification Steps

- Click through every "Next:" link starting from `docs/_index.md` — all links resolve.
- `cd website && hugo build --gc --minify` succeeds.
- Read the path cold as if a first-time user — is the flow coherent?
