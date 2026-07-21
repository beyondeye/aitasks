---
priority: medium
effort: medium
depends: [t1186_1]
issue_type: enhancement
status: Implementing
labels: [tui]
gates: [risk_evaluated]
assigned_to: dario-e@beyond-eye.com
anchor: 1149
created_at: 2026-07-20 19:30
updated_at: 2026-07-21 10:03
---

## Context

Second slice of t1186 (chatlink wizard live allowlist pickers), after t1186_1
(authorization modes). Provides the data source for the picker UI (t1186_4): two new
Discord config-time adapter helpers plus a headless, Textual-free fetch orchestration
module the wizard will call from a thread worker. Follows the established
`fetch_bot_permissions` precedent (`chat/discord_adapter.py:1188-1226`): Discord-specific
config-time helpers live OUTSIDE the `ChatAdapter` ABC — no changes to
`slack_adapter.py` or `mock.py` (Slack parity is a separate follow-up task).

**Critical correctness finding (from planning review):** the runtime
`fetch_participants` path (`discord_adapter.py:1098-1108`) is NOT sufficient for the
picker. It reads `channel.members` (derived from the guild member cache, which can be
empty/incomplete in a short-lived config-time connection) and its `fetch_members()`
fallback only exists on Thread/Guild objects — a real `TextChannel` has no
`fetch_members`, so fake-based tests pass while production shows an empty picker.
The new helper must ensure the guild member list is actually populated.

## Key files to modify

- `.aitask-scripts/chat/discord_adapter.py` — two new async helpers next to
  `fetch_bot_permissions` (:1188), errors wrapped
  `map_discord_error(exc, target="conversation")`:
  - `async def fetch_roles(self, conversation: ConversationRef) -> list[Role]` —
    guild resolution as in `_require_guild()` (:1048-1057); `guild.roles` cache else
    `await guild.fetch_roles()` (get-then-fetch); skip `is_default` (@everyone);
    return `Role(id=str(r.id), name=r.name, kind="discord_role")` (Role dataclass:
    `chat/model.py:260-278`).
  - `async def fetch_channel_members(self, conversation: ConversationRef) -> list[User]`
    — resolve channel + guild; ensure members populated: if `guild.chunked` use cache,
    else `await guild.chunk()` (gateway chunking; Server Members Intent is already
    mandatory and live-check-verified — see `live_check.py:63-64`,
    `aidocs/chat/discord_bot_setup.md:28-39`), falling back to
    `async for m in guild.fetch_members(limit=None)` when chunking is unavailable;
    then visibility-filter with `channel.permissions_for(member).view_channel` (the
    same membership oracle `fetch_identity_claims` uses at :1183-1185); return
    `user_to_domain(m)` per member. `fetch_participants` itself is left untouched
    (runtime ABC surface).
- New `.aitask-scripts/chatlink/allowlist_fetch.py` — headless orchestration module
  mirroring `live_check.py` contracts (see its module docstring, :1-23): Textual-free
  AND discord-import-free at module level; lazy `DiscordAdapter` import behind an
  injectable `connector` seam; sync entry point running `asyncio.run` (thread-worker
  friendly); shared monotonic deadline passed to every `asyncio.wait_for`; bounded 5s
  teardown under `contextlib.suppress(BaseException)`; NEVER raises; token hygiene —
  exception class names only, never `str(exc)`/`repr(exc)` (import and reuse
  `live_check._exc_names`).
  - `run_allowlist_fetch(token, workspace_id, conversation_id, thread_id=None, *,
    timeout=FETCH_TIMEOUT_S, connector=None) -> AllowlistFetchResult`
  - `AllowlistFetchResult` dataclass: `members: list[tuple[str, str]]` (id,
    display_name; bots filtered out — intake drops bot actors anyway, `intake.py:181`),
    `roles: list[tuple[str, str]]` (id, name), `members_error: str | None`,
    `roles_error: str | None` (per-stage, sanitized), `members_truncated: bool`
    (cap `MAX_MEMBERS = 500`).
  - Members via `adapter.fetch_channel_members(parent_ref)` (parent conversation ref —
    same thread→parent scoping as live_check stage 4); roles via
    `adapter.fetch_roles(parent_ref)`. Partial results allowed: one stage failing does
    not blank the other.
- ID-validation helpers in `allowlist_fetch.py` (headless; imported by the wizard in
  t1186_4): `dedupe_ids(ids) -> list[str]` (order-preserving) and
  `invalid_snowflakes(ids) -> list[str]` (non-matches of `^\d{15,21}$`).

## Reference files for patterns

- `live_check.py` (whole file) — the contract template: connector seam (:96-116),
  deadline handling (:118-121), `_exc_names` (:90-93), teardown (:253-257).
- `fetch_bot_permissions` precedent + doc comment: `discord_adapter.py:1188-1226`.
- Fake connector test pattern: `tests/test_chatlink_wizard.sh:238-284` (FakeAdapter,
  `connector_for`, `run()` helper) and assertions :291-398.

## Implementation plan

1. Adapter: `fetch_roles`, then `fetch_channel_members` (chunk/fetch fallback +
   visibility filter).
2. `allowlist_fetch.py`: result dataclass, staged orchestration, caps, hygiene.
3. Validation helpers.
4. Headless tests.

## Verification

- New tests in `tests/test_chatlink_wizard.sh` (headless section — `textual` must stay
  out of `sys.modules`, guard at :38-39/:219-223): FakeAdapter exposing
  `fetch_channel_members`/`fetch_roles`/`close` + `connector_for`; assert: all-pass
  shape and ordering; bot filtering; truncation at cap (`members_truncated=True`,
  exactly MAX_MEMBERS entries); per-stage failure isolation (members fail + roles
  succeed and vice versa); sanitized class-name-only errors; token-hygiene sweep (token
  string never appears in any result field); timeout path; teardown close-count;
  thread_id → parent ref scoping; `dedupe_ids` / `invalid_snowflakes` unit tests.
- The chunking/visibility logic inside `fetch_channel_members` is discord.py-object-
  driven and cannot be faked meaningfully at this seam — it is explicitly delegated to
  the aggregate manual-verification sibling (unchunked-cache scenario on a real server,
  including a member without channel visibility being excluded).
- `bash tests/test_chatlink_wizard.sh` and all other chatlink tests green.
