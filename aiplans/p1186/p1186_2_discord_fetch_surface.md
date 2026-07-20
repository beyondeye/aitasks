---
Task: t1186_2_discord_fetch_surface.md
Parent Task: aitasks/t1186_chatlink_wizard_allowlist_live_pickers.md
Sibling Tasks: aitasks/t1186/t1186_1_authorization_modes.md, aitasks/t1186/t1186_3_wizard_step_reorder.md, aitasks/t1186/t1186_4_allowlist_picker_ui.md
Archived Sibling Plans: aiplans/archived/p1186/p1186_*_*.md
Worktree: (profile 'fast' — current branch)
Branch: main
Base branch: main
---

# p1186_2 — Discord fetch surface (adapter helpers + headless allowlist_fetch module)

Second sequential slice of t1186. Data source for the t1186_4 picker. Full context in
the parent plan and the task file (which pins the critical finding: the runtime
`fetch_participants` path is insufficient live — `TextChannel` has no `fetch_members`
and `channel.members` depends on a possibly-empty guild member cache).

## Steps

1. **discord_adapter.py — `fetch_roles(conversation) -> list[Role]`** next to
   `fetch_bot_permissions` (:1188), outside the ABC, `map_discord_error(exc,
   target="conversation")` wrapping: guild resolution as `_require_guild()` (:1048);
   `guild.roles` cache else `await guild.fetch_roles()`; skip `is_default`;
   `Role(id=str(r.id), name=r.name, kind="discord_role")`.
2. **discord_adapter.py — `fetch_channel_members(conversation) -> list[User]`**:
   resolve channel + guild; if `guild.chunked` use cache else `await guild.chunk()`,
   fallback `async for m in guild.fetch_members(limit=None)`; visibility-filter
   `channel.permissions_for(member).view_channel` (same oracle as
   `fetch_identity_claims` :1183-1185); return `user_to_domain(m)`. Leave
   `fetch_participants` untouched.
3. **New `.aitask-scripts/chatlink/allowlist_fetch.py`** mirroring `live_check.py`
   contracts (Textual-free + discord-import-free module level; injectable `connector`;
   sync `asyncio.run` entry; shared monotonic deadline; 5s suppressed teardown; never
   raises; token hygiene via imported `live_check._exc_names`):
   `run_allowlist_fetch(token, workspace_id, conversation_id, thread_id=None, *,
   timeout=FETCH_TIMEOUT_S, connector=None) -> AllowlistFetchResult` with
   `members [(id, display_name)]` (bots filtered), `roles [(id, name)]`,
   `members_error`/`roles_error` (sanitized, per-stage — partial results allowed),
   `members_truncated` (`MAX_MEMBERS = 500`). Members/roles fetched on the PARENT
   conversation ref (thread → parent, as live_check stage 4).
4. **Validation helpers** in the same module: `dedupe_ids` (order-preserving),
   `invalid_snowflakes` (`^\d{15,21}$` non-matches).
5. **Headless tests** in `tests/test_chatlink_wizard.sh` (textual-free section):
   FakeAdapter (`fetch_channel_members`/`fetch_roles`/`close`) + `connector_for`
   mirroring :238-284; assertions per the task file (all-pass, bot filter, truncation,
   per-stage isolation, class-name-only errors, hygiene sweep, timeout, teardown count,
   thread→parent ref, helper units).

## Verification

`bash tests/test_chatlink_wizard.sh` green (import guard intact); other chatlink tests
green. Chunking/visibility live behavior delegated to the aggregate
manual-verification sibling (unchunked-cache + visibility-exclusion scenarios).

Post-implementation per task-workflow Step 9; archive via `aitask_archive.sh 1186_2`.
