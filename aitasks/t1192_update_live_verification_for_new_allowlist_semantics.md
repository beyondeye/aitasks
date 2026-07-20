---
priority: medium
effort: low
depends: []
issue_type: chore
status: Ready
labels: [tui]
gates: [risk_evaluated]
anchor: 1149
created_at: 2026-07-20 19:33
updated_at: 2026-07-20 19:33
---

## Origin

Risk-mitigation ("after") for t1186, created from the approved plan's risk evaluation
(`aiplans/p1186_chatlink_wizard_allowlist_live_pickers.md`, `## Risk` →
`### Planned mitigations`). Created at child-decomposition time rather than Step 8d
because the decomposed parent never reaches Step 8d; `depends: [1186]` defers it until
the whole t1186 feature (all children) has landed and archived.

## Risk addressed

- Per-dimension modes create a 4-combination policy matrix (plus precedence rule)
  restated across policy/preflight/docs/tests; a missed surface or an unpinned
  combination leaves the contract ambiguous · severity: medium
- Live-Discord member enumeration can only be proven against a real server; the
  dedicated `fetch_channel_members` helper (guild chunk / fetch_members fallback +
  visibility filter) addresses the known empty-cache failure mode, but chunking latency
  on very large guilds and fakes-pass-while-live-fails residual risk remain ·
  severity: medium

## Goal

Update the existing live-verification tasks/checklists to the post-t1186 reality so
they stop asserting pre-t1186 behavior:

- t1124 (discord live smoke), t1184 (live discord validation follow-up), and t1120_8 —
  review each checklist item against: the per-dimension authorization modes
  (`user_authorization_mode` / `role_authorization_mode`, `denied_*` lists, pinned
  precedence and degenerate-posture warnings), the reordered wizard step flow
  (token/live-check before allowlist, derived step numbering), and the picker fetch
  path (`fetch_channel_members` chunking + visibility filtering, `fetch_roles`).
- Rewrite stale items, add missing live scenarios (unchunked-cache member fetch on a
  freshly connected bot; visibility exclusion; degenerate-posture preflight/wizard
  warnings), and drop items that t1186's automated tests now cover.
