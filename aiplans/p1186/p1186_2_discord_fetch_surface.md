---
Task: t1186_2_discord_fetch_surface.md
Parent Task: aitasks/t1186_chatlink_wizard_allowlist_live_pickers.md
Sibling Tasks: aitasks/t1186/t1186_3_wizard_step_reorder.md, aitasks/t1186/t1186_4_allowlist_picker_ui.md, aitasks/t1186/t1186_5_manual_verification_chatlink_wizard_allowlist_live_pickers.md
Archived Sibling Plans: aiplans/archived/p1186/p1186_1_authorization_modes.md
Base branch: main
plan_verified:
  - claudecode/fable5 @ 2026-07-21 10:50
---

# p1186_2 — Discord fetch surface (adapter helpers + headless allowlist_fetch module)

## Context

Second sequential slice of t1186 (chatlink wizard live allowlist pickers), after
t1186_1 (authorization modes, landed). Provides the data source for the t1186_4
picker UI: two Discord config-time adapter helpers plus a headless, Textual-free
fetch orchestration module the wizard will call from a thread worker. The task
file pins the critical finding: the runtime `fetch_participants` path is
insufficient live — `TextChannel` has no `fetch_members` and `channel.members`
depends on a possibly-empty guild member cache, so the new helper must actively
populate the guild member list (chunking).

## Plan verification (2026-07-21)

Existing plan `aiplans/p1186/p1186_2_discord_fetch_surface.md` re-checked against
current source — **all assumptions hold**; only minor line drift:

- `fetch_bot_permissions` precedent now at `discord_adapter.py:1198` (plan said
  :1188); `_require_guild` :1058; `fetch_participants` :1108 (untouched);
  `fetch_identity_claims` :1173 with the visibility oracle
  `channel.permissions_for(member).view_channel` at :1193-1195.
- `live_check.py` contracts confirmed: `_exc_names` :110, connector seam
  :133-136, shared monotonic deadline :138-141, bounded suppressed teardown
  :278-282, stage-4 thread→parent scoping via `parent_ref` :226-228.
- `Role` dataclass `chat/model.py:261-277`; `User` has `display_name`/`is_bot`;
  `user_to_domain` (`discord_adapter.py:132`) sets `is_bot`.
- `intake.py:181` drops bot actors (justifies bot filtering in results).
- Wizard test guards `tests/test_chatlink_wizard.sh:38-39` / :219-223;
  FakeAdapter pattern :238, `connector_for` :271, `run()` :282.
- `chatlink/allowlist_fetch.py` does not exist; no `fetch_roles` /
  `fetch_channel_members` anywhere — clean additive surface.

## Review-round corrections (pinned before coding)

Three planning-review findings, verified against source, amend the original
steps:

**(a) Guild resolution must NOT use `_require_guild()`.** The wizard's default
connector path is `DiscordAdapter.connect(token)` (live_check.py:147 calls
`connector(token)`), which leaves `_guild_id=None` — `_require_guild()`
(:1058-1060) would raise `ChatError("no guild_id configured")` on every real
run. Both helpers instead resolve the conversation's channel
(`await self._resolve_channel(conversation)`) and read
`getattr(channel, "guild", None)` — the exact pattern of `fetch_bot_permissions`
(:1214-1217) and `fetch_identity_claims` (:1176-1181). A guild-less channel
(DM) returns `[]` (honest n/a, mirroring `fetch_bot_permissions`'s `{}`).

**(b) Chunk-failure semantics (pinned).** In `fetch_channel_members`, member
population is best-effort layered — a `guild.chunk()` failure must NOT surface
as the stage error while `fetch_members` remains untried:
1. `guild.chunked` truthy → use `guild.members` cache.
2. Else if `guild.chunk` is callable → `await guild.chunk()`; on success use
   `guild.members`. Catch **`Exception` only** (never `BaseException` —
   `asyncio.CancelledError` from the caller's `wait_for` deadline must
   propagate); any chunk failure falls through to step 3.
3. `guild.fetch_members` callable → `members = [m async for m in
   guild.fetch_members(limit=None)]`. A failure HERE is terminal: wrap
   `map_discord_error(exc, target="conversation")` and raise (allowlist_fetch
   surfaces it as `members_error`).
4. Neither chunking nor `fetch_members` available (degenerate object) → use the
   `guild.members` cache as-is (best effort, possibly empty).

**(c) Adapter-level tests are required** (the wizard tests fake the helpers at
the allowlist_fetch seam, so they cannot prove the live-critical adapter
behavior — an implementation reading empty `channel.members` would still pass
them). Add SDK-free tests in `tests/test_chat_discord.sh` (see step 5b).

## Steps

1. **`discord_adapter.py` — `fetch_roles(conversation) -> list[Role]`** next to
   `fetch_bot_permissions` (:1198), outside the ABC, errors wrapped
   `map_discord_error(exc, target="conversation")`: resolve channel →
   `channel.guild` (per correction (a); guild None → `[]`); use `guild.roles`
   cache if non-empty, else `await guild.fetch_roles()` if callable
   (get-then-fetch); skip `is_default` (@everyone);
   `Role(id=str(r.id), name=r.name, kind="discord_role")`.
2. **`discord_adapter.py` — `fetch_channel_members(conversation) -> list[User]`**:
   resolve channel → `channel.guild` (guild None → `[]`); populate members per
   the pinned layered fallback in correction (b); visibility-filter
   `channel.permissions_for(member).view_channel` (same oracle as
   `fetch_identity_claims` :1193-1195; guard `permissions_for` with
   `callable()` as :1193 does — if absent, include the member rather than
   silently dropping everyone); return `user_to_domain(m)`. Leave
   `fetch_participants` untouched (runtime ABC surface).
3. **New `.aitask-scripts/chatlink/allowlist_fetch.py`** mirroring `live_check.py`
   contracts (Textual-free + discord-import-free module level; injectable
   `connector`; sync `asyncio.run` entry; shared monotonic deadline; 5s
   suppressed teardown; never raises; token hygiene via imported
   `live_check._exc_names`):
   `run_allowlist_fetch(token, workspace_id, conversation_id, thread_id=None, *,
   timeout=FETCH_TIMEOUT_S, connector=None) -> AllowlistFetchResult` with
   `members [(id, display_name)]` (bots filtered), `roles [(id, name)]`,
   `members_error`/`roles_error` (sanitized, per-stage — partial results
   allowed), `members_truncated` (`MAX_MEMBERS = 500`). Members/roles fetched on
   the PARENT conversation ref (thread → parent, as live_check stage 4).
4. **Validation helpers** in the same module: `dedupe_ids` (order-preserving),
   `invalid_snowflakes` (`^\d{15,21}$` non-matches).
5. **Headless orchestration tests** in `tests/test_chatlink_wizard.sh`
   (textual-free section): FakeAdapter
   (`fetch_channel_members`/`fetch_roles`/`close`) + `connector_for` mirroring
   the live_check test pattern; assertions: all-pass shape/ordering, bot
   filter, truncation at cap, per-stage failure isolation, class-name-only
   errors, token-hygiene sweep, timeout path, teardown close-count,
   thread→parent ref scoping, `dedupe_ids`/`invalid_snowflakes` units.

5b. **Adapter-level tests** in `tests/test_chat_discord.sh` (SDK-free fakes,
   next to the `fetch_bot_permissions` block :932-1011), proving the
   live-critical behavior the wizard-seam fakes cannot:
   - `fetch_roles`: resolves guild via `channel.guild` (adapter constructed
     WITHOUT `guild_id` — the connector-default regression case); cache path
     (`guild.roles` non-empty, no fetch call); `fetch_roles()` fallback when
     cache empty; `is_default` (@everyone) excluded; DM/guild-less → `[]`;
     error → mapped ChatError.
   - `fetch_channel_members`: chunked guild → cache used, `chunk()` NOT
     called; unchunked + `chunk()` succeeds → called once, cache used;
     `chunk()` raises → `fetch_members(limit=None)` fallback used (the
     empty-`channel.members` regression case); `chunk` missing →
     `fetch_members` fallback; `fetch_members` failure → mapped error;
     neither available → cache best-effort; visibility filter excludes a
     member whose `permissions_for(m).view_channel` is False; bot flag
     preserved through `user_to_domain`; DM/guild-less → `[]`.

## Verification

`bash tests/test_chat_discord.sh` and `bash tests/test_chatlink_wizard.sh`
green (import guards intact); other chatlink tests green
(`test_chatlink_config.sh`, `test_chatlink_preflight.sh`,
`test_chatlink_daemon.sh`, `test_chatlink_tui.sh`). Real-server
chunking/visibility behavior additionally delegated to the aggregate
manual-verification sibling t1186_5 (unchunked-cache + visibility-exclusion
scenarios on a live guild).

Post-implementation per task-workflow Step 9; archive via
`aitask_archive.sh 1186_2`.

## Risk

### Code-health risk: low
- Purely additive surface (two helpers outside the ABC + one new headless
  module); runtime paths (`fetch_participants`, policy, intake) untouched;
  contracts mirrored from the established `live_check.py` template with
  guard-tested import hygiene · severity: low · → mitigation: in-task headless
  tests incl. token-hygiene sweep and import guards

### Goal-achievement risk: medium
- The chunk/fetch-members fallback and visibility filter are discord.py-object-
  driven — even the new adapter-level fakes only encode our understanding of
  the SDK's shape; if live semantics differ (e.g. `guild.chunk()` behavior,
  permissions oracle divergence), the picker gets an empty/wrong member list,
  the exact failure the task exists to fix · severity: medium · → mitigation:
  adapter-level SDK-free tests in `test_chat_discord.sh` (step 5b — pins the
  layered fallback incl. the empty-`channel.members` regression) + t1186_5
  (aggregate manual-verification sibling: unchunked-cache scenario on a real
  server + member-without-visibility exclusion); feature-level drift covered by
  t1192 (existing "after" mitigation from parent decomposition)
