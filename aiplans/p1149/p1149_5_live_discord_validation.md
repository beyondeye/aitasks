---
Task: t1149_5_live_discord_validation.md
Parent Task: aitasks/t1149_chatlink_config_wizard_tui.md
Sibling Tasks: aitasks/t1149/t1149_1_preflight_module.md, aitasks/t1149/t1149_2_config_status_panel.md, aitasks/t1149/t1149_3_config_wizard_flow.md, aitasks/t1149/t1149_4_wizard_docs_rewrite.md
Archived Sibling Plans: aiplans/archived/p1149/p1149_*_*.md
Worktree: (per picking profile)
Branch: (per picking profile)
Base branch: main
---

# p1149_5 — Live Discord validation step (optional)

Optional wizard step (after token entry): connect live with the entered
token and affirmatively verify token validity, privileged intents (Message
Content / Server Members), intake-channel visibility, and bot permissions —
catching at config time what the troubleshooting table today only diagnoses
after the fact. Deferrable; the wizard (t1149_3) ships without it.

## Verified exploration facts

- `DiscordAdapter.connect(token, *, guild_id=None, …)` — async classmethod,
  `.aitask-scripts/chat/discord_adapter.py:631-712`: requests both privileged
  intents, `client.login(token)` (bad token → `discord.LoginFailure`),
  background `client.connect(reconnect=True)` task, `wait_until_ready()`.
- **No `close()` on the adapter** — Gateway task never torn down. This child
  builds teardown; PREFERRED: add `DiscordAdapter.close()` delegating to
  `client.close()` (guarding never-connected state), keep it SDK-lazy.
- `connect()` performs no explicit intent/visibility/permission checks —
  drive post-connect helpers: `fetch_identity_claims()` :1094-1117
  (`permissions_for(member).view_channel`), `_resolve_channel()` :774
  (raises `ConversationNotFound`), `member_to_claims()` :155,
  `map_discord_error()` :560-573.
- SDK lazy via `_sdk()` seam :627 — tests inject fakes through it.
- Textual + discord.py are both asyncio; safe default = thread worker with
  its own `asyncio.run()`; verify loop ownership before sharing the loop.
- Permission authority: `aidocs/chat/discord_bot_setup.md`
  (invite `permissions=397552863296`, both privileged intents).

## Pinned contracts (parent plan)

1. **Fail-closed + guaranteed teardown**: every failure renders as a specific
   check row with a fix hint; no exception escapes; connection torn down in
   try/finally on ALL paths (success, failure, timeout) — fake-seam test
   asserts close is always called.
2. **Optional**: offered after token entry ("Validate live now / Skip");
   skip always available; wizard outcome independent of it.
3. **Timeout-bounded**: overall wall-clock cap (15–30s) with progress state;
   never hangs the wizard.
4. **Owns its docs delta**: live-validation rows in
   `website/content/docs/workflows/bug-report-intake.md` troubleshooting +
   note in `aidocs/chat/discord_bot_setup.md` (t1149_4 excluded these by
   design).
5. **Token hygiene**: never logged, never rendered; travels only to Discord.

## Implementation steps

1. `DiscordAdapter.close()` (preferred teardown shape) — SDK-lazy, safe on
   never-connected instances.
2. `chatlink/live_check.py` (Textual-free):
   `run_live_checks(token, intake_channel_ref, timeout) -> list[CheckResult]`
   reusing the t1149_1 `CheckResult` shape. Check sequence: login OK →
   intents granted (connected/guild-fetch behavior) → channel resolvable +
   `view_channel` → bot permission set from discord_bot_setup.md present.
3. Wizard integration: optional LiveCheckScreen; thread worker runs
   `run_live_checks`; render rows; Continue regardless of outcome.
4. Tests via the `_sdk()` fake seam: each failure mode → its distinct row;
   teardown spy called on success/failure/timeout; wizard import does not
   `import discord` (lazy seam preserved).

## Verification

- Fake-seam unit tests: distinct row per failure mode; teardown always called (success, failure, timeout paths).
- `bash tests/test_chatlink_tui.sh` — wizard walk with live step skipped still passes.
- Manual (real bot token): valid token all-pass; revoked token → token row fails; portal intent off → intent row fails; bot removed from channel → visibility row fails; UI never hangs; skip works.

Refer to Step 9 (Post-Implementation) of the task workflow for merge/archival.
