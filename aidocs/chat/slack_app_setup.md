# Slack app setup for the aitasks chat layer

Maintainer-facing groundwork gathered during t1074_2; the **reference input
for t1074_3** (the Slack adapter). User-facing website docs come later with
the chat-consuming feature tasks.

## Connection model

Same posture as Discord: the framework connects as an **app the user installs
into their own workspace**, over **Socket Mode** — a persistent *outbound*
WebSocket. No public Request URL, no inbound endpoint. Two tokens are
involved:

- **Bot token** (`xoxb-…`) — Web API calls (send, edit, upload, …).
- **App-level token** (`xapp-…`, scope `connections:write`) — opens the
  Socket Mode connection that delivers events and interactivity payloads.

`ait setup --with-chat` will install both Slack SDKs once t1074_3 appends
`slack-bolt`/`slack-sdk` to `AIT_PIP_SPECS_CHAT` (scaffold landed in
t1074_2).

## Platform-side setup (api.slack.com)

1. **Create the app** at <https://api.slack.com/apps> → *Create New App*.
   Prefer **from an app manifest** for one-shot creation (the manifest can
   declare everything below declaratively); "from scratch" works too.

2. **Socket Mode**: *Settings → Socket Mode* → toggle **Enable Socket Mode**
   ON. Create the **app-level token** with the `connections:write` scope —
   this is the `xapp-` token.

3. **Bot token scopes** (*OAuth & Permissions → Scopes → Bot Token Scopes*):

   - `chat:write` — send/edit/delete messages
   - `app_mentions:read` — APP_MENTION events
   - `channels:history`, `groups:history`, `im:history`, `mpim:history` —
     message events + `fetch_history` across public/private/DM/group
   - `channels:read`, `groups:read`, `im:read`, `mpim:read` —
     `list_conversations` / `fetch_conversation`
   - `im:write` — open DMs (`create_conversation(DIRECT)`, ephemeral DM
     fallback)
   - `users:read` — `fetch_user`
   - `usergroups:read` — `IdentityClaims.roles` (`kind=slack_usergroup`)
   - `files:read`, `files:write` — attachments
   - `reactions:read`, `reactions:write` — reactions + `fetch_reactions`
   - `search:read` — only if `supports_message_search=True` is exercised

   Commonly missed: the four `*:history` scopes and `files:read` — without
   them events arrive but backfill/attachments fail.

4. **Event subscriptions** (*Event Subscriptions* → Enable, "Subscribe to
   bot events" — no Request URL needed in Socket Mode):
   `message.channels`, `message.groups`, `message.im`, `message.mpim`,
   `app_mention`, `reaction_added`, `reaction_removed`, `member_joined_channel`,
   `member_left_channel`, `file_shared`, `channel_created`.

5. **Interactivity** (*Interactivity & Shortcuts*): toggle ON (Socket Mode —
   no Request URL). Slash commands are declared on the *Slash Commands* page;
   note that unlike Discord there is no bulk programmatic registration — the
   adapter's `register_commands` can only validate/no-op (document per the
   ABC contract).

6. **App Home**: toggle the **Messages Tab** ON (allows DMs to the app).

7. **Install to workspace** (*Install App*): produces the **bot token**
   (`xoxb-`). Invite the bot to channels with `/invite @<app-name>`.

## Framework-side configuration

Same split as Discord: tokens are adapter-construction arguments
(`SlackAdapter.connect(bot_token, app_token)` shape — t1074_3 decides the
exact signature); storage/env-var schema and channel/user policy belong to
the runtime layer (e.g. t1120). Do not invent env var names here.

## Platform notes for t1074_3 (from the parent plan)

- 3 s ack + `response_url` follow-up contract for interactivity; instant ack
  = the amended `_acked` contract's "already performed" special case (no
  delayed-defer needed, modals via `views.open` trigger_id within its window).
- `chat.postEphemeral` is a true per-user ephemeral in-channel
  (`supports_ephemeral=True` without interaction context — richer than
  Discord).
- `supports_standalone_threads=False` (threads only anchor on messages);
  `search.messages` → `supports_message_search=True`.
