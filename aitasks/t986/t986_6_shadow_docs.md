---
priority: medium
risk_code_health: low
risk_goal_achievement: low
effort: low
depends: [t986_5]
issue_type: documentation
status: Implementing
labels: [web_site, aitask_monitormini, development]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_8
created_at: 2026-06-14 16:04
updated_at: 2026-06-15 18:34
---

## Context

Child of t986 (shadow agent). Document the shadow feature and the multi-agent-
per-window change across aidocs (specialist rules) and the website.

**True deps:** t986_5 (the user-facing behavior + config must be settled before
documenting). Reflects t986_1..t986_5.

## Key Files to Modify / Create

- `aidocs/framework/tmux_gateway.md` — note that a tmux window may now hold
  multiple real agents (state keyed by `pane_id`), and how the shadow pane is a
  helper/companion.
- `aidocs/framework/tui_conventions.md` — update the companion-pane section:
  shadow is a second companion case alongside minimonitor; the "one TUI per
  window / minimonitor is the only split-pane case" wording needs revising to
  account for the shadow pane.
- `aidocs/framework/monitor_idle_and_prompt_detection.md` — if t986_2 added
  AskUserQuestion/phase markers, document them here.
- Consider a new `aidocs/` page (e.g. `aidocs/framework/shadow_agent.md`) for the
  shadow architecture (capture → phase-detect → context-fetch → skill).
- Website: a `website/content/.../` page for the shadow workflow. If a new
  `content/docs/workflows/*.md` page is added, also add a bullet to the
  hand-curated `workflows/_index.md` grouping (sidebar auto-builds; the index
  body does not).

## Reference Files for Patterns

- `aidocs/framework/documentation_conventions.md` — current-state-only rule (no
  version history in doc bodies); genericize any passage naming specific coding
  agents; manual-verification auto-mode wording.
- Existing TUI docs on the website for the page structure/voice.
- Use invented placeholder project names in user-facing docs (not real repos).

## Implementation Plan

1. Update the three aidocs files above to reflect the multi-agent-per-window
   model and the shadow companion.
2. Add the shadow architecture doc (aidocs) and a website page describing the
   feature, the trigger key, the single instruction-driven flow, and the two
   settings (default agent+model; same-window-vs-new-window).
3. If a workflows page is added, update `workflows/_index.md`.

## Verification Steps

- `cd website && hugo build --gc --minify` succeeds (no broken refs).
- Cross-references updated (no dangling links to renamed/added sections).
- Doc prose follows `documentation_conventions.md` (current-state-only;
  generic agent naming; placeholder project names).

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-06-15T15:34:01Z status=pass attempt=1 type=human

> **✅ gate:risk_evaluated** run=2026-06-15T15:34:03Z status=pass attempt=1 type=machine

> **✅ gate:review_approved** run=2026-06-15T16:01:28Z status=pass attempt=1 type=human
