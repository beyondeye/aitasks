---
priority: medium
risk_code_health: low
risk_goal_achievement: medium
effort: low
depends: [t1120_6]
issue_type: documentation
status: Done
labels: [chat_surface]
gates: [risk_evaluated]
assigned_to: dario-e@beyond-eye.com
anchor: 1120
implemented_with: claudecode/opus4_8
created_at: 2026-07-05 12:01
updated_at: 2026-07-10 19:06
completed_at: 2026-07-10 19:06
---

## Context

Seventh child of t1120. User-facing documentation for the chatlink bug-report
intake feature. Chat-platform user docs were explicitly deferred to t1120
(t1074 gathered only maintainer groundwork in `aidocs/chat/`). Parent plan:
`aiplans/p1120_discord_bug_report_channel_integration.md`. All feature
children are landed — **document the current source of truth (read the landed
code/skills now), not the plan text** (plans may have drifted).

## Key deliverables

1. Website docs (`website/content/docs/workflows/`): a chatlink/bug-report
   intake workflow page — end-user setup narrative: Discord bot config (link
   to the steps in `aidocs/chat/discord_bot_setup.md`, adapted for end users:
   privileged intents, invite scopes, minimum permissions), channel + allowlist
   config (`aitasks/metadata/chatlink_config.yaml`), token placement, running
   `ait chatlink --headless`, the Q&A interaction from the reporter's view,
   reactions-as-status legend, sandbox/docker prerequisite.
   **Also add the bullet in the hand-curated
   `website/content/docs/workflows/_index.md`** (sidebar auto-builds; the
   index body does not).
2. aidocs runtime doc for maintainers if gaps remain after reading the landed
   children (e.g. `aidocs/chat/chatlink_runtime.md`: session lifecycle, relay
   spool, reaper).

## Conventions (binding)

- Read `aidocs/framework/documentation_conventions.md` first: current-state
  only (no version history in doc bodies); genericize passages naming
  supported coding agents; say "autonomous" not "auto-execution".
- Invented placeholder project names in examples (frontend/backend) — never
  the author's real repos.
- "cross-repo"/"linked repo" — never "sister".
- Do NOT document the `diffviewer` TUI; TUI lists mention board, monitor,
  minimonitor, codebrowser, settings, brainstorm (+ chatlink once landed).

## Verification

- `cd website && hugo build --gc --minify` passes.
- New page listed in `_index.md`; internal links resolve.
- Grep the new pages for "sister", real repo names, and version-history
  phrasing — all absent.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-07-10T14:40:48Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-07-10T16:04:34Z status=pass attempt=1 type=human

> **✅ gate:merge_approved** run=2026-07-10T16:05:53Z status=pass attempt=1 type=human

> **🔄 gate:risk_evaluated** run=2026-07-10T16:06:08Z-risk_evaluated-a1 status=running attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Note: stuckhash:fb45885658d6bb9d

> **✅ gate:risk_evaluated** run=2026-07-10T16:06:08Z-risk_evaluated-a1 status=pass attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Result: risk evaluated (## Risk section + both levels present)
> Log: `.aitask-gates/1120_7/risk_evaluated_2026-07-10T16:06:08Z-risk_evaluated-a1.log`
