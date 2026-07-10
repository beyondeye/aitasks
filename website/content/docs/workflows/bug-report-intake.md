---
title: "Bug-Report Intake from Chat"
linkTitle: "Bug-Report Intake"
weight: 76
description: "Turn a Discord channel into a bug-report intake: an authorized report opens a thread, a sandboxed agent explores the repo, asks the reporter questions, and files a task"
depth: [intermediate]
---

The **chatlink gateway** turns a Discord channel into a bug-report intake for one
repository. When someone on the allowlist posts a bug report there, the gateway
opens a thread on that message, launches a **sandboxed code agent** that explores
the repository for probable causes, relays the agent's clarifying questions back
into the thread as Discord menus and dialogs, and finishes by committing a real
aitask — posted back to the thread with a link.

The reporter never touches a terminal. They describe a bug in chat, answer a
couple of questions, and get a task ID.

## How it fits together

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

The agent runs inside a disposable container. It can read the code and ask
questions; it cannot write to your repository, reach your git credentials, or see
the bot token. Its only output is a task proposal that the gateway validates and
commits on its behalf.

## Prerequisites

**1. The chat dependency tier.**

```bash
ait setup --with-chat
```

**2. Docker, and the sandbox image.** The image is **not** built automatically:

```bash
docker build -t ait-chatlink-agent .aitask-scripts/chatlink/docker/
```

Without Docker the gateway still starts and watches the channel, but every agent
launch fails and the session is marked failed. For the image contents and the
container's mounts, see the Chatlink sandbox maintainer doc in your checkout at
`aidocs/chat/chatlink_sandbox.md`.

**3. A Discord bot** installed in your server.

1. Create an application at
   <https://discord.com/developers/applications> → **New Application**. Note the
   **Application ID**.
2. On the **Bot** page, enable **both** Privileged Gateway Intents:
   - **Server Members Intent** — resolves members and roles, which the allowlist
     needs.
   - **Message Content Intent** — without it the bot receives every message with
     **empty text**, so no bug report is ever readable.
3. On the same page, **Reset Token** and copy the token once. Never commit it.
4. Invite the bot with the `bot` and `applications.commands` scopes and the
   minimum permission set: View Channels, Send Messages, Send Messages in
   Threads, Create Public Threads, Create Private Threads, Manage Threads, Read
   Message History, Attach Files, Embed Links, Add Reactions.

   ```
   https://discord.com/oauth2/authorize?client_id=<APPLICATION_ID>&scope=bot+applications.commands&permissions=397552863296
   ```

5. Turn on **Developer Mode** (User Settings → Advanced), then right-click your
   server → **Copy Server ID**, and right-click the intake channel → **Copy
   Channel ID**. You need both.

## Configure the gateway

Configuration lives in `aitasks/metadata/chatlink_config.yaml`, seeded by
`ait setup` as a fully commented-out template. It is checked in and shared with
your team.

| Key | Default | Meaning |
|---|---|---|
| `intake_channel` | unset | The channel to watch. For Discord, `workspace_id` is the **server (guild) ID** and `conversation_id` is the **channel ID**. The gateway refuses to start until this is set. |
| `allowed_user_ids` | `[]` | Users who may open bug reports. |
| `allowed_role_ids` | `[]` | Roles whose members may open bug reports. |
| `deny_message_mode` | `ignore` | `ignore` — an unauthorized message is silently skipped. `ephemeral` — the user gets a private refusal. |
| `repo_name` | unset | A logical project name, used only in audit and display output. |
| `max_concurrent_sandboxes` | `2` | Live sessions at once (1–16). |
| `intake_rate_per_user_per_hour` | `4` | Reports per user per hour (1–60). |
| `sandbox_memory` | `2g` | Container memory limit. |
| `sandbox_cpus` | `2` | Container CPU limit (1–16). |
| `sandbox_pids` | `512` | Container process limit (16–4096). |
| `sandbox_wall_clock_s` | `1800` | Hard wall-clock cap per session (60–14400). |

**Authorization is deny-by-default.** If both `allowed_user_ids` and
`allowed_role_ids` are empty, nobody can open a bug report — the gateway watches
the channel and ignores everything. This is the single most common reason a
freshly configured gateway appears to do nothing.

Out-of-range ceilings are clamped to the nearest valid value with a warning; a
malformed YAML file makes the gateway refuse to start.

### The bot token

The token is **not** stored in the config file. It goes in a per-machine file
that is gitignored:

```bash
mkdir -p aitasks/metadata/chatlink_sessions
chmod 700 aitasks/metadata/chatlink_sessions
printf '%s' 'YOUR_BOT_TOKEN' > aitasks/metadata/chatlink_sessions/bot_token
chmod 600 aitasks/metadata/chatlink_sessions/bot_token
```

The gateway refuses to start without it. The token is never passed into the
sandbox container.

## Run it

```bash
ait chatlink --headless    # the gateway daemon
```

On success it prints:

```
chatlink gateway running (headless) — SIGINT/SIGTERM to stop.
```

The gateway validates everything before it connects, and refuses to start when
the config is missing or malformed, `intake_channel` is unset, the bot token is
absent, or the exploring-agent command cannot be resolved. A missing Docker
binary is only a warning — the gateway serves, and launches fail honestly.

To watch it, run the read-only status TUI in another window:

```bash
ait chatlink               # sessions table + audit-log tail
```

Press `r` to refresh, `q` to quit, and `j` to jump to another TUI. The TUI never
commands the gateway.

## What the reporter sees

1. **They post a bug report** in the intake channel. The gateway opens a thread
   on that message, named `bug:` plus the first 48 characters of the report, and
   adds a ⏳ reaction.
2. **The agent asks questions** in the thread — at most three clarifying
   questions, and always one final confirmation before anything is created. Each
   question appears as a **select menu**; if it accepts free text there is also an
   **`Answer…`** button that opens a dialog box. Questions with more than 25
   options paginate behind **Prev** / **Next** buttons.
3. **Only the reporter may answer.** Anyone else who touches the controls gets a
   private reply: *"Only the user who opened this bug report can answer."*
4. **Answered questions are closed out** — the controls disappear and the message
   is marked `*(answered)*`.
5. **Unanswered questions time out** after about nine minutes. The agent then
   proceeds with the conservative default it named in the question, and records
   in the task that the default was taken. A session never hangs.
6. **The task is created.** The gateway validates the agent's proposal, creates
   and commits the aitask, and posts it back:

   ```
   ✅ Task created: **t412** — Fix login timeout on slow connections
   ```

### Reactions as status

The gateway keeps one reaction on the original bug-report message:

| Reaction | Meaning |
|---|---|
| ⏳ | The agent is working. |
| ❓ | Waiting for the reporter to answer a question. |
| ✅ | The task was created. |
| ❌ | The session failed. |

## Walkthrough

A first run, end to end, for a project called `backend`.

**1. Install the tier and build the image.**

```bash
ait setup --with-chat
docker build -t ait-chatlink-agent .aitask-scripts/chatlink/docker/
```

**2. Create the bot** as described above, enabling both privileged intents, and
invite it to your server. Copy the server ID and the ID of the channel you want
to use — say `#bugs`.

**3. Write the config.** Replace the seeded template's commented-out block with
real values. A complete, minimal `aitasks/metadata/chatlink_config.yaml`:

```yaml
intake_channel:
  provider: discord
  workspace_id: "123456789012345678"   # server (guild) ID
  conversation_id: "987654321098765432" # #bugs channel ID

allowed_user_ids:
  - "111111111111111111"                # the reporter

deny_message_mode: ephemeral            # make refusals visible while testing

repo_name: backend
```

Everything else keeps its default. Start with `deny_message_mode: ephemeral` so
that an unauthorized attempt tells you so instead of failing silently; switch it
to `ignore` once the allowlist is right.

**4. Install the token.**

```bash
mkdir -p aitasks/metadata/chatlink_sessions
chmod 700 aitasks/metadata/chatlink_sessions
printf '%s' 'YOUR_BOT_TOKEN' > aitasks/metadata/chatlink_sessions/bot_token
chmod 600 aitasks/metadata/chatlink_sessions/bot_token
```

**5. Start the gateway.**

```bash
ait chatlink --headless
# chatlink gateway running (headless) — SIGINT/SIGTERM to stop.
```

**6. File a bug from Discord.** In `#bugs`, the reporter posts:

> Login times out for me on hotel wifi. It worked last week. The spinner just
> hangs and eventually I get a blank error toast.

The bot reacts ⏳ and opens a thread. A moment later, in the thread:

> **chatlink** — Which part of login hangs?
> *(select menu: `The password form` · `The 2FA step` · `The redirect back`)*
> *(button: `Answer…`)*
>
> (no answer ⇒ I'll assume all three)

The reaction on the original message flips to ❓. The reporter picks
`The 2FA step`; the question collapses to `*(answered)*` and the reaction returns
to ⏳.

Then the confirmation:

> **chatlink** — Create this task?
> **Fix 2FA step timeout on high-latency connections** — bug · high priority ·
> medium effort · labels: `auth`
> *(select menu: `Create as proposed`)* *(button: `Answer…`)*

The reporter selects `Create as proposed`. The gateway validates, commits, and
posts:

> ✅ Task created: **t412** — Fix 2FA step timeout on high-latency connections
> `aitasks/t412_fix_2fa_step_timeout.md`

The original message now carries ✅.

**7. Watch it happen.** In another terminal, `ait chatlink` shows the session
moving through its states and tails the audit log.

## Limits and safety

- **Deny-by-default.** An empty allowlist authorizes nobody. Denials are logged.
- **The agent is sandboxed.** It runs in a container against a **disposable copy
  of your committed `HEAD`** — no uncommitted work, no `.git` directory, and no
  git credentials, so it cannot reach or modify your repository. The copy is
  deleted with the session. (The container does have network access: the agent
  CLI needs to reach its model API.)
- **The agent never creates the task.** It writes a proposal; the gateway
  re-validates it (rejecting unknown issue types, unknown labels, and control
  characters) and only then creates and commits the task. A bad proposal fails
  the session rather than producing a bad task.
- **Secrets stay out of the sandbox.** The bot token and your git credentials are
  never passed into the container.
- **Ceilings bound the blast radius.** Concurrent sessions, per-user hourly rate,
  memory, CPU, process count, and a hard wall-clock cap are all enforced, and
  every container is killed at its deadline even if the gateway restarts.
- **Everything is audited** to `aitasks/metadata/chatlink_sessions/chatlink_audit.log`.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `no gateway config found` | `chatlink_config.yaml` is absent. | Run `ait setup`, or point `chatlink.config` in `project_config.yaml` at your file. |
| `gateway config … is missing or malformed` | The YAML does not parse, or is not a mapping. | Fix the YAML. Individual out-of-range *values* only warn and clamp — this error means the file itself is broken. |
| `config has no valid intake_channel` | `intake_channel` is unset or missing `provider`, `workspace_id`, or `conversation_id`. | Set all three. |
| `no bot token at …` | The token file is missing or empty. | Write it with mode `0600` as shown above. |
| `could not resolve the explore-relay agent command` | The code-agent configuration cannot launch the exploring agent. | Run `ait codeagent invoke explore-relay --headless --dry-run` to diagnose. |
| `warning — 'docker' not found` | Docker is not installed. | Install Docker **and** build the image — it is not built for you. |
| The bot sits in the channel and nothing happens. | Deny-by-default: both allowlists are empty, so no one may initiate. | Add the reporter to `allowed_user_ids` (or a role to `allowed_role_ids`). Set `deny_message_mode: ephemeral` to see refusals while testing. |
| A thread opens but the report looks empty. | The **Message Content** intent is off, so message text arrives empty. | Enable it on the Bot page and restart the gateway. |
| Members or roles do not resolve, so the allowlist never matches. | The **Server Members** intent is off. | Enable it on the Bot page and restart the gateway. |
| *"Only the user who opened this bug report can answer."* | Someone other than the reporter clicked the controls. | Expected. Only the reporter may answer. |
| *"All bug-report slots are busy"* | `max_concurrent_sandboxes` reached. | Wait, or raise the ceiling (max 16). |
| *"Rate limit reached"* | `intake_rate_per_user_per_hour` reached for that user. | Wait, or raise the ceiling (max 60). |
| The session fails right after the thread opens. | The sandbox image is missing. | `docker build -t ait-chatlink-agent .aitask-scripts/chatlink/docker/` |

---

**Next:** [Exploration-Driven Development]({{< relref "/docs/workflows/exploration-driven" >}})
