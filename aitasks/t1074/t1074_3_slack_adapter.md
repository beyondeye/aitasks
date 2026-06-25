---
priority: medium
effort: high
depends: [t1074_2]
issue_type: feature
status: Ready
labels: [chat_surface, python]
anchor: 1074
created_at: 2026-06-25 11:53
updated_at: 2026-06-25 11:53
---

## Context

Third child of t1074 (depends on t1074_2 — Discord lands first and validates the
interface). Implements the **full** `ChatAdapter` contract for **Slack** via
`slack_bolt` + `slack_sdk` in **Socket Mode** (no public HTTP endpoint — fits a
local `ait` workspace). The opt-in `--with-chat` install scaffold already exists
(added in t1074_2); this child only **appends** the Slack SDKs to it. Still
**non-aitasks-specific** — pure platform↔domain translation.

Parent plan: `aiplans/p1074_chat_adapter_abstraction_layer.md`.
Child plan: `aiplans/p1074/p1074_3_slack_adapter.md`.

## Key Files

- **New:** `.aitask-scripts/chat/slack_adapter.py` — `SlackAdapter(ChatAdapter)`.
  Lazy `import slack_bolt`/`slack_sdk` inside network methods; module-level pure
  normalization functions for dependency-free testing (same pattern as the Discord adapter).
- **New:** `tests/test_chat_slack.sh`.
- **Edit (install flow):** `.aitask-scripts/aitask_setup.sh` — **append**
  `'slack-bolt>=1,<2'`, `'slack-sdk>=3,<4'` to `AIT_PIP_SPECS_CHAT` and
  `slack_bolt`, `slack_sdk` to `AIT_IMPORTS_CHAT` (the `--with-chat` flag + arrays
  already exist from t1074_2). Run `shellcheck .aitask-scripts/aitask_setup.sh`.

## Reference Files for Patterns

- The Discord adapter just landed: `.aitask-scripts/chat/discord_adapter.py` and
  `tests/test_chat_discord.sh` — mirror its structure (lazy import + pure
  normalization + stub tests). Read its archived plan
  `aiplans/archived/p1074/p1074_2_discord_adapter.md` for gotchas.
- Graceful test SKIP: `tests/test_applink_router.sh`.

## Slack specifics to implement

- Socket Mode (`xoxb-` bot token + `xapp-` app-level token, `connections:write`).
- Commonly-missed scopes/events: `channels:history`, `groups:history`, `message.channels`,
  `app_mention`, `files:read`/`files:write`.
- Block Kit components + `views.open`/`view_submission` modals; slash commands +
  interactivity payloads with the **3 s ack + `response_url` follow-up** contract
  (auto-defer/ack on receipt; past-window → `InteractionExpired`).
- Ephemeral: `chat.postEphemeral` (per-user, in channel/thread; `supports_ephemeral=True`);
  DM fallback then `DeliveryFailed` if needed (never public).
- Permalink: `chat.getPermalink`.
- Events: `message_deleted`, `reaction_removed`, `member_left_channel`, plus message
  create/edit, app_mention, file_shared → normalized `EventType`.
- Threads: message-anchored only (`thread_ts`); `supports_standalone_threads=False`
  (channel-rooted thread create raises `PermissionDenied`).
- `fetch_reactions` via `reactions.get`; `IdentityClaims` from usergroups
  (`kind=slack_usergroup`) + `is_workspace_admin`/`is_owner` flags.
- `search.messages` → `supports_message_search=True`. `Capabilities` with Slack limits.

## Implementation Plan (high level — see child plan)

1. Append Slack SDKs to the `AIT_PIP_SPECS_CHAT`/`AIT_IMPORTS_CHAT` arrays; shellcheck.
2. Implement pure normalization functions (Slack event/payload ↔ domain).
3. Implement `SlackAdapter(ChatAdapter)` via `slack_bolt` Socket Mode (lazy import),
   honoring the contract semantics (auto-defer, private-only ephemeral, subscription recovery).
4. Write `tests/test_chat_slack.sh` against `SimpleNamespace` stubs (no real libs), graceful SKIP.

## Verification

```bash
bash tests/test_chat_slack.sh            # PASSES with no slack libs installed (stub-based)
shellcheck .aitask-scripts/aitask_setup.sh
ait setup --with-chat && ~/.aitask/venv/bin/python -c "import slack_bolt, slack_sdk; print('ok')"
```
Stub-based normalization tests pass on the stock venv; `--with-chat` installs both
Slack SDKs into `~/.aitask/venv` alongside `discord.py`.
