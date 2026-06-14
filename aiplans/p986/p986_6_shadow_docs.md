---
Task: t986_6_shadow_docs.md
Parent Task: aitasks/t986_shadow_agent.md
Sibling Tasks: aitasks/t986/t986_1_*.md, aitasks/t986/t986_2_*.md, aitasks/t986/t986_3_*.md, aitasks/t986/t986_4_*.md, aitasks/t986/t986_5_*.md
Archived Sibling Plans: aiplans/archived/p986/p986_*_*.md
Worktree: aiwork/t986_6_shadow_docs
Branch: aitask/t986_6_shadow_docs
Base branch: main
---

# Plan: t986_6 — Docs (aidocs + website)

## Context

Document the shadow feature and the multi-agent-per-window change. **Dep:** t986_5
(behavior + config settled). Reflects t986_1..t986_5.

## Implementation steps

1. `aidocs/framework/tmux_gateway.md` — a window may now hold multiple real
   agents (state keyed by `pane_id`); the shadow pane is a helper/companion.
2. `aidocs/framework/tui_conventions.md` — revise the companion-pane / "one TUI
   per window, minimonitor is the only split-pane case" section: shadow is a
   second companion case.
3. `aidocs/framework/monitor_idle_and_prompt_detection.md` — document any
   AskUserQuestion/phase markers added in t986_2.
4. Add `aidocs/framework/shadow_agent.md` (architecture: capture → phase-detect →
   context-fetch → skill).
5. Website page for the shadow workflow (trigger key, single instruction-driven
   flow, the two settings). If a `content/docs/workflows/*.md` page is added,
   add a bullet to the hand-curated `workflows/_index.md` grouping.

## Verification

- `cd website && hugo build --gc --minify` succeeds with no broken references.
- Doc prose follows `documentation_conventions.md` (current-state-only, generic agent naming, placeholder project names).
- Cross-references updated; `workflows/_index.md` bullet added if a workflows page was created.

## Step 9 (Post-Implementation)

Standard cleanup/archival/merge per `task-workflow` Step 9.
