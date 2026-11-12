---
title: "Bug-Report Intake from Chat"
linkTitle: "Bug-Report Intake"
weight: 76
description: "Turn a Discord channel into a bug-report intake: an authorized report opens a thread, a sandboxed agent explores the repo, asks the reporter questions, and files a task"
depth: [intermediate]
---

The chatlink gateway turns a Discord channel into a bug-report intake for one
repository. When an authorized user posts a bug report there, the gateway opens a
thread on that message and starts a code agent in a sandbox, a disposable
container that holds a copy of your code. The agent explores the code for
probable causes, asks the reporter questions in the thread, and proposes a task.
The gateway checks the proposal, then creates and commits the task and posts its
ID in the thread. The reporter never touches a terminal.

```
#bugs channel          gateway (ait chatlink --headless)        sandbox container
─────────────          ─────────────────────────────────        ─────────────────
report posted   ──▶    authorize (allowlist)
                       open thread on the message
                       ⏳ reaction               ──────────▶    agent explores repo
                       ❓ reaction  ◀── question ──────────     asks a question
reporter answers ─▶    route answer             ──────────▶    continues
                       ⏳ reaction
                       validate payload         ◀── payload ── proposes a task
                       create + commit aitask
                       ✅ reaction + thread note
```

The gateway works with Discord only, and the agent it starts is Claude Code.
The [`ait chatlink` reference]({{< relref "/docs/commands/chatlink" >}}) lists
every command, config key, file and error message of the gateway.

## Set up the gateway and file a first report

The example sets up a project called `backend` with a `#bugs` channel.

1. **Install the chat dependency tier.**

   ```bash
   ait setup --with-chat
   ```

2. **Install Docker and build the sandbox image.** `ait setup` does not build
   the image for you:

   ```bash
   docker build -t ait-chatlink-agent .aitask-scripts/chatlink/docker/
   ```

   Without Docker the gateway still starts and watches the channel, but every
   report fails as soon as its thread opens.

3. **Create the Discord bot.**

   1. Create an application at
      <https://discord.com/developers/applications> with **New Application**,
      and note its **Application ID**.
   2. On the **Bot** page, enable both Privileged Gateway Intents: **Server
      Members Intent**, which the allowlist needs to resolve members and roles,
      and **Message Content Intent**, without which the bot cannot read a
      report's text. The gateway does not start while either is off.
   3. On the same page, use **Reset Token** and copy the token straight away:
      Discord shows it only once. Never commit it.
   4. Invite the bot to your server with this URL, replacing
      `<APPLICATION_ID>`. It requests the `bot` and `applications.commands`
      scopes and the minimum permissions the bot needs: View Channels, Send Messages, Send Messages
      in Threads, Create Public Threads, Create Private Threads, Manage
      Threads, Read Message History, Attach Files, Embed Links and Add
      Reactions.

      ```
      https://discord.com/oauth2/authorize?client_id=<APPLICATION_ID>&scope=bot+applications.commands&permissions=397552863296
      ```

      The invite adds the bot to the server, and the bot sees each channel
      according to that channel's permissions. It sees a public channel by
      default. For a private channel, add the bot or one of its roles under
      **Edit Channel → Permissions**.
   5. Turn on **Developer Mode** (User Settings → Advanced). Right-click the
      server and choose **Copy Server ID**, then right-click the intake channel
      and choose **Copy Channel ID**.

4. **Write the config** in `aitasks/metadata/chatlink_config.yaml`, which
   `ait setup` creates as a commented-out template. Replace its contents with
   your values:

   ```yaml
   intake_channel:
     provider: discord
     workspace_id: "123456789012345678"   # server ID
     conversation_id: "987654321098765432" # #bugs channel ID

   allowed_user_ids:
     - "111111111111111111"                # the reporter

   deny_message_mode: ephemeral            # show refusals while testing

   sandbox_env_passthrough:
     - ANTHROPIC_API_KEY                   # the agent's credentials

   repo_name: backend
   ```

   Nobody can file a report until you name at least one user in
   `allowed_user_ids` or one role in `allowed_role_ids`. With
   `deny_message_mode: ephemeral`, a refused user gets a private message from
   the bot instead of silence; switch it back to `ignore` once the allowlist is
   right. The agent in the sandbox has no credentials of its own, so
   `sandbox_env_passthrough` must name the environment variable that holds them.

   The file is shared with your team. Commit it:

   ```bash
   ./.aitask-scripts/aitask_metadata_commit.sh aitasks/metadata/chatlink_config.yaml
   ```

   To be prompted for these values instead, run `ait chatlink` and press `w`.
   The wizard writes the config and the token file, commits the config, and can
   check the token, the intents and the bot's channel access against Discord
   before it saves. It does not set `sandbox_env_passthrough`, so add that key by
   hand.

5. **Install the token** in a file only your user can read. The file is
   gitignored, and the token is never passed into the sandbox. Skip this step if
   the wizard wrote it.

   ```bash
   mkdir -p aitasks/metadata/chatlink_sessions
   chmod 700 aitasks/metadata/chatlink_sessions
   printf '%s' 'YOUR_BOT_TOKEN' > aitasks/metadata/chatlink_sessions/bot_token
   chmod 600 aitasks/metadata/chatlink_sessions/bot_token
   ```

6. **Start the gateway** in a shell where the credentials variable is set:

   ```bash
   export ANTHROPIC_API_KEY=...
   ait chatlink --headless
   # chatlink gateway running (headless) — SIGINT/SIGTERM to stop.
   ```

   The gateway checks its setup first and stops with a one-line message when
   something is missing, such as the config, the intake channel or the token.
   To watch it, run `ait chatlink` in another window: it shows the setup
   checks, the sessions and the gateway's log, and never controls the gateway.

7. **File a bug from Discord.** In `#bugs`, the reporter posts:

   > Login times out for me on hotel wifi. It worked last week. The spinner just
   > hangs and eventually I get a blank error toast.

   The bot reacts ⏳ and opens a thread. In the thread the agent asks:

   > **Login step** — Which part of login hangs? (no answer ⇒ I'll assume all three)
   > *(select menu: `The password form` · `The 2FA step` · `The redirect back`)*

   The reporter picks `The 2FA step`, and the agent asks for a final
   confirmation of the task it proposes, showing its title, priority, effort,
   type, labels and a one-line summary. The reporter selects
   `Create as proposed`, and the gateway posts:

   > ✅ Task created: **t412** — Fix 2FA step timeout on high-latency connections

## What the reporter sees

- A thread on the report, named after the report's first words.
- Up to three questions, then a final confirmation. Each question is a
  select menu; one that accepts typed answers also has an **Answer…** button that
  opens a dialog. Typing changes into the confirmation makes the agent adjust
  the task and confirm once more.
- Only the reporter can answer. Anyone else who uses the controls gets the
  private reply "Only the user who opened this bug report can answer."
- A question left unanswered for about nine minutes times out. The agent
  takes the default it named in the question, which is always the most
  conservative reading, the one that widens the investigation and never
  narrows it. It notes that in the task, so a session never hangs.
- One status reaction on the report:
  - ⏳ the agent is working;
  - ❓ a question waits for the reporter;
  - ✅ the task was created;
  - ❌ the session failed.

## Limits and safety

- Only users and roles you allow can file reports, and every refusal is
  recorded in the gateway's log. The
  [authorization rules]({{< relref "/docs/commands/chatlink#authorization" >}})
  also let you block users or roles instead.
- The agent works on a copy of your last commit, without uncommitted changes,
  the `.git` directory or git credentials, so it cannot change your repository.
  The copy is deleted when the session ends. The container has network access,
  which the agent needs to reach its model API.
- The agent only proposes the task. The gateway rejects a proposal with an
  unknown issue type, an unknown label or control characters, and the session
  fails instead of creating a bad task.
- The bot token and your git credentials never enter the container.
- Ceilings cap concurrent sessions, reports per user per hour, and each
  container's memory, CPUs, processes and running time. Their defaults and
  ranges are in the [configuration keys]({{< relref "/docs/commands/chatlink#configuration-keys" >}}).

When something does not work, the
[troubleshooting table]({{< relref "/docs/commands/chatlink#troubleshooting" >}})
lists each symptom with its cause and fix.

---

**Next:** [Exploration-Driven Development]({{< relref "/docs/workflows/exploration-driven" >}})
