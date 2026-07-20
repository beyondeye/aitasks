---
priority: medium
effort: high
depends: []
issue_type: enhancement
status: Ready
labels: [tui]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 4a36c12bb96d.681bafac2cb9.d73bba2fc21f
children_to_implement: [t1186_1, t1186_2, t1186_3, t1186_4]
anchor: 1149
created_at: 2026-07-20 18:06
updated_at: 2026-07-20 19:31
---

## Goal

Replace the chatlink config wizard's manual allowlist entry (step 2/7) with live Discord-backed pickers: select intake-channel members and server roles from fetched lists instead of hand-typing snowflake IDs. Also decide and implement explicit semantics for "no one selected".

## Motivation (user report)

> "in chat link wizard at step 2 we are currently required to explicitly set the user ids authorized to open a bug report, and by default users not listed here are blocked. currently the list of users must be edited manually. this is very bad UX. it should be possible to fetch the user list from the discord channel and choose, or at least if no user selected by default allow all users in the channel. similar issue with user role... if fetching this information from the discord server can be done only later after connecting, then this step of the wizard should be presented later."

## Current state (exploration findings)

**Step 2 = `AllowlistScreen`** (`.aitask-scripts/chatlink/wizard.py:255-287`), title
`"Step 2/7 - Who may open a bug report (deny-by-default)"`:
- Two plain `Input` widgets `#wiz_user_ids` / `#wiz_role_ids`, prefilled from state.
- Parsing: `_parse_ids` (wizard.py:272-274) splits on `_ID_SPLIT_RE = r"[,\s]+"` (wizard.py:52).
- **Zero validation**: no snowflake/numeric check, no dedupe, no existence check against Discord.
- Only guard is a one-shot both-empty warning (`self._warned_empty`, wizard.py:279-284) - press Next again to accept.
- Values shaped in `build_edits()` (wizard.py:139-140) as `allowed_user_ids` / `allowed_role_ids`; written only at the summary step via `config_write.write_config()` (wizard.py:582).
- Summary renders both lists concatenated into one line (wizard.py:531-536) - no visual user/role split.

**Empty-list semantics are DENY-ALL and symmetric** - the user's assumption
("empty roles = allow all roles") is NOT current behavior.
`policy.decide()` (`.aitask-scripts/chatlink/policy.py:48-67`) evaluates:
```
config is None               -> deny no_config
claims None / no user_id     -> deny no_claims
not claims.is_channel_member -> deny not_channel_member
user_id in allowed_user_ids  -> ALLOW ok_user
any(role.id in allowed_role_ids) -> ALLOW ok_role
allowed_role_ids non-empty   -> deny role_not_allowed
else                         -> deny user_not_allowed   # the both-empty branch
```
Runtime call site: `intake.py:184-196` (`_handle_message`); a claims-fetch
`ChatError` leaves `claims=None` -> deny (fail-closed).

This deny-by-default posture is a **pinned t1120 contract** restated in 6+ surfaces:
- `seed/chatlink_config.yaml:28-35` ("Both lists empty (or unset) means nobody is allowed")
- `.aitask-scripts/chatlink/preflight.py:240-249` (WARN row, not FAIL - daemon still starts)
- `.aitask-scripts/chatlink/__init__.py:13`, `aidocs/chat/chatlink_runtime.md:103`
- `website/content/docs/workflows/bug-report-intake.md:103`
- `tests/test_chatlink_config.sh` (one negative control per deny reason), `tests/test_chatlink_preflight.sh:112`, `tests/test_chatlink_tui.sh:347,530`

**Live Discord connection already exists** (t1149_5): `LiveCheckScreen`
(wizard.py:374-456, step 6/7, advisory-only, thread worker + generation-token
guard) calls `live_check.run_live_checks(token, workspace_id, conversation_id,
thread_id, timeout=30, connector=None)` (`.aitask-scripts/chatlink/live_check.py:96`).
Contracts to respect: Textual-free + discord-import-free at module level, never
raises, never hangs (shared 30s deadline, bounded 5s teardown), token hygiene
(exception **class names** only, never `str(exc)`).

**Fetch primitives available:**
- `DiscordAdapter.fetch_participants(conversation)` (`chat/discord_adapter.py:1098-1108`) - reads `channel.members`, falls back to `channel.fetch_members()`. **Channel** members only - naturally scoped to the intake channel.
- `DiscordAdapter.fetch_identity_claims(...)` (`:1163-1186`) and `member_to_claims()` (`:164-188`) - the ONLY place roles are read today (one member's `.roles`, skipping `@everyone`, emitting `Role(id, name, kind="discord_role")`).
- **No guild-role enumeration exists anywhere** - no `guild.roles` / `guild.fetch_roles()` call in the repo. `_require_guild()` (`:1048-1057`) is the natural anchor for a new helper.
- **Precedent to follow:** `fetch_bot_permissions()` (`:1188-1224`) is explicitly documented as a *Discord-specific config-time helper outside the `ChatAdapter` ABC*, with get-then-fetch fallback and `map_discord_error(exc, target=...)` wrapping. Following it avoids expanding the ABC across `slack_adapter.py` + `mock.py`.
- Permissions: role listing needs **no extra bot permission**; guild member enumeration depends on the **Server Members Intent**, which is already mandatory and already verified by `live_check` (`_FIX_INTENTS`, live_check.py:63-64, `aidocs/chat/discord_bot_setup.md:28-39`).

**Step ordering** is the index tuple `_STEPS` (wizard.py:697-698):
`IntakeChannelScreen, AllowlistScreen, DenyRepoScreen, CeilingsScreen, TokenScreen, LiveCheckScreen, SummaryScreen`.
Navigation is purely index-based (`start_wizard()`, wizard.py:665-694). Reordering
works mechanically **except**: (a) `make_step()` (wizard.py:674-679) hardcodes
`if cls in (TokenScreen, LiveCheckScreen, SummaryScreen)` for the `seams` arg;
(b) every `step_title` hardcodes its own `"Step N/7"` string - no derived numbering.
`LiveCheckScreen` reads `state["token"]`, `workspace_id`, `conversation_id`,
`thread_id`, so it must stay after steps 1 and 5.

## Scope

1. **Step reorder so the allowlist can be a picker.** The token (step 5) must be
   entered before any fetch is possible. Move `TokenScreen` (and likely
   `LiveCheckScreen`) ahead of `AllowlistScreen`. Requires fixing the two coupling
   points above - strongly prefer **deriving step numbers** from `_STEPS` index and
   **declaring seam needs on the screen class** rather than hardcoding a class
   tuple in `make_step()`.

2. **New Discord config-time fetch helper(s)**, following the
   `fetch_bot_permissions` precedent (outside the ABC, `map_discord_error`
   wrapping, get-then-fetch fallback):
   - guild roles -> `list[Role]` (skip `@everyone`, `kind="discord_role"`)
   - reuse `fetch_participants` for channel members
   Wrap them for the wizard in a `live_check`-style sync/thread-worker entry
   point that inherits the same never-raises / bounded-deadline / token-hygiene
   contracts.

3. **Picker UI in `AllowlistScreen`**: multi-select over fetched members and
   roles, showing display name + id. Must include:
   - **Manual-entry fallback** - offline, no token yet, fetch failed, or
     non-Discord provider must all still work (today's free-text path stays).
   - **Bounds + search/filter** - member lists can be large; cap results and make
     the list searchable rather than rendering thousands of rows.
   - Advisory-only failure: a failed fetch degrades to manual entry, never blocks
     the wizard.

4. **Decide the "nobody selected" semantics** (see Design decisions below) and
   implement consistently across `policy.decide()`, `config.py`,
   `seed/chatlink_config.yaml`, `preflight.py`, wizard summary, `aidocs/chat/`,
   `website/content/docs/workflows/bug-report-intake.md`, and the pinned tests.

5. **ID validation** for the manual path: snowflake-shaped check + dedupe, so a
   typo is caught at config time instead of silently denying forever.

## Design decisions for planning

**A. "No one selected" semantics - RECOMMENDED: explicit mode, not overloaded empty list.**

The reporter asked for "if no user selected, allow all users in the channel".
Implementing that as *empty list = allow all* silently flips a fail-closed
security contract to fail-open: an operator who clears the list, or whose YAML
fails to parse a key, would go from "nobody" to "everybody". It also inverts the
meaning of the existing `preflight` WARN and breaks the pinned negative-control
tests.

Recommended instead: an **explicit selector** surfaced in the wizard, e.g.
`authorization_mode: allowlist | channel_members` (default `allowlist`,
preserving current behavior for existing configs). `channel_members` mode allows
any user for whom `claims.is_channel_member` is true - a semantic the runtime
*already computes and enforces first* (`policy.py:59`), so the change is small
and auditable. Empty allowlists in `allowlist` mode keep meaning "nobody".

Record the rejected alternative (empty = allow-all) and why. If planning instead
chooses the implicit form, it must be a deliberate, documented contract change
with the negative-control tests rewritten rather than deleted.

**B. Slack parity.** The pickers are Discord-only initially (as `live_check`
already is - the wizard gates it on `provider == "discord"`). `slack_adapter.py`
has the same `fetch_participants` / `fetch_identity_claims` surface, so a Slack
picker is a natural follow-up; decide whether to carve it out as a separate task.

**C. Where roles come from.** Guild roles vs. only roles actually present on
channel members. Guild-wide is more complete; member-derived needs no new adapter
method. Weigh against list size.

## Constraints

- `live_check.py`-class contracts apply to any new fetch path: **Textual-free and
  discord-import-free at module level** (lazy SDK import via injectable
  connector), **never raises, never hangs** (bounded deadline + bounded teardown),
  **token hygiene** (exception class names only - never `str(exc)`/`repr(exc)`,
  which can embed the token).
- Daemon must remain Textual-import-free (guard-tested).
- Fail-closed posture of `load_config` must not change.
- No config file is written before `SummaryScreen._do_save()` (wizard.py:579) -
  the picker must not introduce early writes.
- Tests must be injectable-fake based (`connector` seam); never import `discord`.

## Acceptance criteria

- Wizard offers selectable member and role lists fetched live from Discord, with
  manual entry preserved as a fallback on every failure path.
- Step order allows fetching (token available before the allowlist step), with
  step numbering derived rather than hardcoded.
- "Nobody selected" semantics are explicit, documented, and consistent across all
  code/doc/test surfaces listed in Scope item 4.
- Negative controls for each deny reason still exist and still pass (rewritten,
  not deleted, if semantics change).
- `tests/test_chatlink_wizard.sh`, `test_chatlink_tui.sh`, `test_chatlink_config.sh`,
  `test_chatlink_preflight.sh` updated and green.

## Related

- Follow-up to t1149 (chatlink config wizard TUI); builds directly on t1149_5
  (live Discord validation).
- Verification overlap: t1184 (live discord validation followup), t1124
  (discord live smoke), t1120_8 - these verify existing behavior and are NOT
  folded in; they may need updating once the allowlist semantics change.
