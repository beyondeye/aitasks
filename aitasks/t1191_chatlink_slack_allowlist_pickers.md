---
priority: low
effort: medium
depends: []
issue_type: enhancement
status: Ready
labels: [tui]
gates: [risk_evaluated]
anchor: 1149
created_at: 2026-07-20 19:32
updated_at: 2026-07-20 19:32
boardidx: 90
---

## Origin

Follow-up carved out of t1186 (chatlink wizard live allowlist pickers) by explicit user
decision (2026-07-20): the wizard's member/role pickers ship Discord-only; Slack gets
its own task. Depends conceptually on the t1186 children landing first (seams:
`allowlist_fetch` module, `AllowlistScreen` picker UI, per-dimension authorization
modes) — see `aiplans/archived/p1186/` after t1186 archives.

## Goal

Slack parity for the chatlink config wizard's authorization-step pickers: fetch intake
channel members and Slack usergroups live, and let the operator multi-select instead of
hand-typing IDs. Manual entry stays the fallback (as for Discord).

## Context / starting points

- `chat/slack_adapter.py` already has `fetch_participants(conversation) -> list[User]`
  (:1130, via `conversations.members` + per-user `users.info`) and
  `fetch_identity_claims` (:1179, usergroup scan degrading to `roles=[]` on missing
  scope). There is NO usergroup-enumeration helper yet — needs a config-time helper
  (list usergroups → `Role(kind="slack_usergroup")`), following the same
  outside-the-ABC precedent as Discord's `fetch_roles` / `fetch_channel_members`
  (t1186_2).
- `chatlink/allowlist_fetch.py` (t1186_2) is Discord-wired via its lazy connector seam;
  extend or mirror it for Slack (provider-dispatched), keeping the live_check-class
  contracts: headless, never-raises, bounded deadline, token hygiene.
- Wizard gating: the fetch button is enabled only for `provider == "discord"` after
  t1186_4 — extend to slack.
- ID validation: Slack IDs are not snowflakes (`U…`/`S…` prefixes) — the
  discord-only `invalid_snowflakes` hard-block must stay provider-scoped; add
  Slack-shaped validation if desired.
- Required Slack scopes for member/usergroup listing (e.g. `usergroups:read`) must be
  documented in `aidocs/chat/` alongside the existing bot setup docs.

## Acceptance criteria

- Slack provider gets live member + usergroup pickers in the wizard authorization step,
  with manual entry preserved on every failure path.
- Injectable-fake tests only (never import slack_sdk in tests); all chatlink test files
  green.
- Docs updated (aidocs chat setup + website bug-report-intake workflow) for Slack
  picker support and any new scopes.
