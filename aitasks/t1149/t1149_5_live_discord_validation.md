---
priority: medium
effort: high
depends: [t1149_3]
issue_type: feature
status: Implementing
labels: [tui]
gates: [risk_evaluated]
assigned_to: dario-e@beyond-eye.com
anchor: 1149
created_at: 2026-07-15 18:46
updated_at: 2026-07-20 09:54
---

## Context

Part of t1149 (chatlink config wizard TUI). OPTIONAL / deferrable child — the wizard (t1149_3) ships without it. Adds an optional live-validation step to the wizard that connects to Discord with the entered token and affirmatively verifies, at config time, the failure modes the troubleshooting table can only diagnose after the fact: token validity, privileged intents (Message Content / Server Members), intake-channel visibility, and bot permissions.

This is the riskiest child (async SDK inside Textual + missing teardown API) and was deliberately scoped out of t1149_3 so the wizard can land without it. Depends on t1149_3.

## Exploration facts (verified against source)

- `DiscordAdapter.connect(token, *, guild_id=None, defer_delay=...)` — async classmethod, `.aitask-scripts/chat/discord_adapter.py:631-712`. It builds `discord.Intents.default()` + `members=True` + `message_content=True`, constructs the client, `await client.login(token)` (bad token -> `discord.LoginFailure`), spawns `client.connect(reconnect=True)` as a background task, `wait_until_ready()`, returns the adapter.
- **The adapter has NO `close()` method** — the Gateway task is never torn down by the class. This child MUST build teardown (reach the underlying discord.py client and `await client.close()`; consider whether to add a proper `close()` to DiscordAdapter itself as the clean fix — preferred, since leaking a Gateway connection from a wizard is unacceptable).
- `connect()` does NO explicit intent/visibility/permission verification — disabled portal intents surface as Gateway errors; visibility/permissions come from post-connect helpers: `fetch_identity_claims()` (:1094-1117, `permissions_for(member).view_channel`), `_resolve_channel()` (:774, raises `ConversationNotFound`), `member_to_claims()` (:155), error mapping `map_discord_error()` (:560-573).
- The SDK is imported lazily (`_sdk()` seam :627, `import discord` in connect :646) — tests inject fakes through this seam.
- Both Textual and discord.py are asyncio; Textual runs its own event loop. Run the live check via a Textual worker (async worker on the same loop is possible since discord.py is pure asyncio — but verify no loop-ownership conflict; a thread + `asyncio.run()` in the worker is the safe default).
- Required intents/permissions authority: `aidocs/chat/discord_bot_setup.md` (invite `permissions=397552863296`, both privileged intents).

## Pinned contracts (from the approved parent plan)

1. **Fail-closed on any error**: every failure (login, timeout, missing intent, invisible channel, missing permission) renders as a specific check row with a fix hint; no exception escapes to the TUI; the connection is ALWAYS torn down (try/finally) — a test with an injected fake asserts teardown is called on every path, including failures.
2. **Optional step**: the wizard offers it after token entry ("Validate live now / Skip"); skipping is always possible; the wizard outcome does not depend on it.
3. **Timeout-bounded**: overall wall-clock cap on the whole live check (e.g. 15-30s) with progress state in the UI; never hangs the wizard.
4. **Owns its own docs delta**: adds the live-validation rows/paragraphs to `website/content/docs/workflows/bug-report-intake.md` troubleshooting (token validity, channel visibility, bot permissions now caught at config time) and a note in `aidocs/chat/discord_bot_setup.md`. t1149_4 deliberately excluded these.
5. **The token never leaves the machine except to Discord**; it is read from the entered value / `paths.read_token()` — never logged, never rendered.

## Key files to modify

- `.aitask-scripts/chat/discord_adapter.py` — add `close()` (teardown of the Gateway task + client) if chosen as the clean fix; keep it SDK-lazy.
- Wizard module from t1149_3 (`chatlink/wizard.py` or `chatlink_app.py`) — the optional LiveCheckScreen + worker.
- NEW small live-check helper (Textual-free, e.g. `chatlink/live_check.py`): `run_live_checks(token, intake_channel_ref, timeout) -> list[CheckResult]` reusing the t1149_1 `CheckResult` shape, so the screen just renders results. Checks: login OK; intents granted (verify via connected state / guild fetch behavior); channel resolvable + `view_channel`; the bot-permission set from `discord_bot_setup.md` present on the channel.
- Tests: fake adapter/SDK via the `_sdk()` seam; assert result rows per failure mode; assert teardown always runs (spy on close).

## Implementation plan

1. Decide teardown shape: add `DiscordAdapter.close()` (preferred) delegating to `client.close()`; guard for never-connected state.
2. `live_check.py` with the timeout-bounded check sequence, each mapped to a `CheckResult` (reuse severity/message/fix_hint fields).
3. Wizard integration: optional step after token entry; async/thread worker runs `run_live_checks`; render rows; Continue regardless of outcome.
4. Tests as above; verify no `import discord` happens at wizard import time (lazy seam preserved).

## Verification

- Fake-seam unit tests: each failure mode -> its distinct row; teardown called on success, failure, and timeout paths.
- `bash tests/test_chatlink_tui.sh` (wizard walk with live step skipped) still passes.
- Manual (needs a real bot token): valid token all-pass; revoked token -> token row fails; intent toggled off in portal -> intent row fails; bot removed from channel -> visibility row fails. UI never hangs; skipping works.
