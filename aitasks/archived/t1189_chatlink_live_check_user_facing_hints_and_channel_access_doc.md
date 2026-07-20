---
priority: high
risk_code_health: low
risk_goal_achievement: low
effort: medium
depends: []
issue_type: bug
status: Done
labels: [tui, web_site]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1149
implemented_with: claudecode/fable5
created_at: 2026-07-20 18:11
updated_at: 2026-07-20 19:31
completed_at: 2026-07-20 19:31
---

## Context

Reported from a real chatlink wizard run: at Step 6 (live validation, t1149_5) the
`live_channel_visible` row failed with "bot lacks access to the intake channel" and a
fix hint pointing at `aidocs/chat/discord_bot_setup.md`. Three problems surfaced:

1. **Dead doc references for installed users.** `aidocs/` is framework-internal and is
   NOT shipped to user installs (`seed/` does not include it). User-facing fix hints must
   reference the public website doc instead:
   `https://www.aitasks.io/docs/workflows/bug-report-intake/`.
2. **Missed invite-URL opportunity.** The website doc carries a ready invite URL
   (`https://discord.com/oauth2/authorize?client_id=<APPLICATION_ID>&scope=bot+applications.commands&permissions=397552863296`),
   but the wizard makes the user go find it. In exactly the failure cases where it is
   needed (`live_channel_visible` / `live_permissions`), login has already succeeded and
   `DiscordAdapter` holds the bot's user ID (`_self_id`, set from `client.user.id` in
   `connect`), which equals the application ID for modern bots — so the wizard can render
   a fully concrete, ready-to-paste invite URL with `client_id` filled in.
3. **Channel-level access is undocumented.** Discord bots are invited to the *server*,
   not to a channel; per-channel access follows the channel's permission overwrites — for
   a private channel the bot (or its role) must be explicitly added in the channel's
   permission settings. Neither `website/content/docs/workflows/bug-report-intake.md`
   nor `aidocs/chat/discord_bot_setup.md` explains this, and the website troubleshooting
   table has no row for "bot lacks access to the intake channel".

## Affected code (enumerated sink surface)

User-facing `aidocs/` references in runtime hint strings:

- `.aitask-scripts/chatlink/live_check.py` — `_FIX_VISIBILITY` (~line 65) and
  `_FIX_PERMISSIONS` (~line 68) reference `aidocs/chat/discord_bot_setup.md`
- `.aitask-scripts/chatlink/preflight.py:307` — `fix_hint` references
  `aidocs/chat/chatlink_sandbox.md`
- `.aitask-scripts/chatlink/daemon.py:744` — stderr message references
  `aidocs/chat/chatlink_sandbox.md`
- `.aitask-scripts/lib/sandbox_launch.py:333` — message references
  `aidocs/chat/chatlink_sandbox.md`

(Code *comments* citing aidocs are fine — only user-visible strings need the change.)

## Acceptance criteria

1. All user-visible fix hints / error messages listed above reference the public website
   doc (bug-report-intake workflow page) instead of `aidocs/...` paths. Keep hints short;
   the canonical-permission-list comment pairing in `live_check.py`
   (`REQUIRED_BOT_PERMISSIONS` ↔ docs step) stays intact and is updated to whichever doc
   is canonical.
2. When the live check fails on `live_channel_visible` or `live_permissions`, the wizard
   surfaces a concrete invite URL with the real application ID substituted
   (`client_id=<bot user id>` from the connected adapter; scope+permissions as in the
   docs). The URL must reach the user through the results rendering
   (`LiveCheckScreen._apply_results` → `wiz_live_results` Static, markup=False), e.g. via
   the row's `fix_hint`. Token-hygiene contract of `live_check.py` is preserved (fixed
   templates; no `str(exc)`).
3. `run_live_checks` still returns exactly four rows and never raises; existing tests for
   live_check keep passing; new/updated tests cover the invite-URL-in-hint path (fake
   connector supplies a fake bot user id).
4. Website doc gains: (a) an explanation of server-invite vs. per-channel permission
   overwrites (private channels need the bot/role added explicitly), and (b) a
   troubleshooting-table row for "bot lacks access to the intake channel".
   `aidocs/chat/discord_bot_setup.md` gets the same channel-access clarification.

## Coordination

- **t1149_4 (wizard docs rewrite, child of t1149)** rewrites the same website page
  sections around the wizard. If t1149_4 lands first, apply AC 4 on the rewritten page;
  if this task lands first, t1149_4 must carry the channel-access content forward. Add a
  reverse coordination pointer in t1149_4 when implementing this task.
- **t1184 (manual verification of t1149_5)** exercises the failure rows this task
  changes; its checklist expectations ("fix hint" wording) may need a touch-up if wording
  changes materially.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-07-20T16:13:59Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-07-20T16:29:28Z status=pass attempt=1 type=human

> **🔄 gate:risk_evaluated** run=2026-07-20T16:31:01Z-risk_evaluated-a1 status=running attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Note: stuckhash:32e54e36d404e724

> **✅ gate:risk_evaluated** run=2026-07-20T16:31:01Z-risk_evaluated-a1 status=pass attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Result: risk evaluated (## Risk section + both levels present)
> Log: `.aitask-gates/1189/risk_evaluated_2026-07-20T16:31:01Z-risk_evaluated-a1.log`
