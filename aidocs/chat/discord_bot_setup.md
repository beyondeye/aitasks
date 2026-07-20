# Discord bot setup for the aitasks chat layer

Maintainer-facing groundwork (t1074_2). User-facing website docs are derived
from this page later, when the first chat-consuming feature lands (e.g. the
t1120 bug-report channel). Keep this current-state only.

## Connection model

The aitasks framework connects to Discord as a **bot the user installs into
their own server**: a Gateway bot authenticated by a **bot token**, holding a
persistent *outbound* WebSocket to Discord. No public HTTP endpoint, no
inbound firewall hole, no webhook URL. The adapter
(`.aitask-scripts/chat/discord_adapter.py`, `DiscordAdapter.connect(token,
guild_id=…)`) opens the Gateway and serves the full `ChatAdapter` contract
over it. Install the SDK tier with `ait setup --with-chat`.

## Platform-side setup (Discord Developer Portal)

1. **Create the application** at
   <https://discord.com/developers/applications> → *New Application*. Note
   the **Application ID** (used in the invite URL, and available to the
   adapter as `client.application_id` for slash-command registration).

2. **Bot user** (*Bot* page): a bot user is created with the application.
   "Public Bot" may stay on or off (off restricts installs to you);
   "Require OAuth2 Code Grant" stays **disabled**.

3. **Privileged Gateway intents** (*Bot* page → Privileged Gateway Intents)
   — enable BOTH:
   - **Server Members Intent** — needed to resolve members/roles
     (`fetch_participants`, `fetch_identity_claims`, USER_JOINED/USER_LEFT
     events).
   - **Message Content Intent** — without it the bot receives message events
     with **empty text** (`Message.text == ""`), which silently breaks
     everything above the adapter.

   The adapter requests these intents at connect time
   (`discord.Intents.default()` + `members` + `message_content`); the portal
   toggles must match or the Gateway connection is refused.

4. **Bot token** (*Bot* page → Reset Token): copy it once, store it in a
   secret manager / local env. **Never commit it.** The token is a
   constructor argument to `DiscordAdapter.connect` — the framework does not
   yet prescribe where it is stored (see "Framework-side configuration").

5. **Invite URL** — either the portal's *Installation* tab, or construct
   manually:

   ```
   https://discord.com/oauth2/authorize?client_id=<APPLICATION_ID>&scope=bot+applications.commands&permissions=397552863296
   ```

   - **Scopes:** `bot` + `applications.commands` (the latter is required for
     `register_commands` — slash-command bulk upsert).
   - **Permissions** (minimum for the full adapter surface): View Channels,
     Send Messages, Send Messages in Threads, Create Public Threads,
     Create Private Threads, Manage Threads (archive), Read Message History,
     Attach Files, Embed Links, Add Reactions, Manage Messages
     (delete_message of others' messages — drop if not needed).
     The decimal `permissions=` value above encodes this set; recompute in
     the portal's permission calculator when changing it.

6. **Authorize**: open the URL, pick the target server (requires *Manage
   Server* on it), confirm.

   The `ait chatlink` config wizard's optional live-validation step can
   verify this setup end-to-end (token, both privileged intents, channel
   visibility, and the permission set above) before the gateway ever runs.

7. **Guild ID for command scope**: enable Developer Mode (User Settings →
   Advanced), right-click the server → *Copy Server ID*. Passing this as
   `guild_id` to the adapter makes slash-command registration **guild-scoped
   (instant propagation — recommended)**; without it commands register
   globally and may take up to ~1 h to propagate.

## Framework-side configuration

**Decided here (t1074_2):** the adapter takes the bot token and optional
`guild_id` as `DiscordAdapter.connect()` arguments. Nothing else.

**Deferred to the runtime/feature layer (e.g. t1120):** where the token is
stored (env var vs config file vs secret store), allowed-user/role policy,
which channels the bot listens to, message-routing rules. Do not invent env
var names here — the runtime layer owns that schema.

## Operational notes

- DM permalinks use `https://discord.com/channels/@me/<channel>/<message>`;
  the adapter's `ConversationRef.workspace_id` for guildless conversations is
  the literal `"@me"`.
- Attachment cap enforced by the adapter is the base (non-boost) 8 MiB;
  boosted servers raise the platform cap but the adapter stays at the honest
  lower bound.
- Interactions are auto-acked by a scheduled defer (~2 s): consumers must
  open modals promptly after receiving an interaction (see the amended
  `_acked` contract in `.aitask-scripts/chat/interactions.py`).
