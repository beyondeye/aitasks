---
title: "Chatlink"
linkTitle: "Chatlink"
weight: 43
description: "ait chatlink command for the Discord bug-report gateway and its status TUI: config keys, authorization rules, startup checks, ceilings and troubleshooting"
depth: [advanced]
---

## ait chatlink

Runs the chat bug-report gateway, or the status TUI that watches it. The setup
steps are in [Bug-Report Intake]({{< relref "/docs/workflows/bug-report-intake" >}}).

```bash
ait chatlink --headless    # Run the gateway in the foreground; SIGINT or SIGTERM stops it
ait chatlink               # Open the read-only status TUI
```

| Invocation | Runs | Needs |
|---|---|---|
| `ait chatlink --headless` | The gateway: watches the intake channel, launches a sandboxed agent per accepted report, relays its questions, creates the task | `pyyaml` and `discord.py` (`ait setup --with-chat`); Docker and the sandbox image when a session launches |
| `ait chatlink` | The status TUI (see [Status TUI](#status-tui)) | `textual` and `pyyaml` |

On a successful start the gateway prints
`chatlink gateway running (headless) — SIGINT/SIGTERM to stop.` and keeps
running until it is stopped.

Intake works on Discord only. The gateway always connects through its Discord
adapter, and it only watches a channel whose `intake_channel.provider` is
`discord`. The exploring agent is Claude Code only: the gateway launches it
through the `explore-relay` operation (see
[Code Agent]({{< relref "/docs/commands/codeagent" >}})), in Claude Code's
headless print mode, which Claude Code bills at a higher per-token rate.

## Files

| File | Tracked | Written by | Purpose |
|---|---|---|---|
| `aitasks/metadata/chatlink_config.yaml` | yes | `ait setup` (commented-out template), the config wizard, or you | Gateway configuration. A different path can be set with `chatlink.config` in `aitasks/metadata/project_config.yaml` (repo-root-relative); a value that names no existing file falls back to the default path. |
| `aitasks/metadata/chatlink_sessions/bot_token` | no (gitignored) | the config wizard, or you | The Discord bot token, alone in the file. Mode `0600`, in a directory with mode `0700`. Surrounding whitespace is ignored; an empty file counts as missing. It is the only token source: no environment variable is read. |
| `aitasks/metadata/chatlink_sessions/chatlink_audit.log` | no | the gateway | The audit log: intake accepted or denied (with the reason), ceiling refusals, session state changes, startup reconciliation, task creation and push outcome. It is never rotated, and user ids appear truncated to their first 8 characters. |

`aitasks/metadata/chatlink_sessions/` also holds the per-session records, the
question-and-answer spools and the disposable workspace copies. Their layout is
contributor detail, kept in the maintainer docs listed under
[Internals](#internals).

A config you edit by hand is not committed for you, and an uncommitted file under
`aitasks/metadata/` holds back [`ait sync`]({{< relref "/docs/commands/sync#auto-commit-policy" >}}).
Commit it with
`./.aitask-scripts/aitask_metadata_commit.sh aitasks/metadata/chatlink_config.yaml`.
A wizard save commits the config itself and never commits the token file.

## Configuration keys

Every key is optional except `intake_channel`.

| Key | Default | Values | Meaning |
|---|---|---|---|
| `intake_channel` | unset | mapping | The channel to watch. `provider` (`discord`), `workspace_id` (the server ID) and `conversation_id` (the channel ID) are required non-empty strings. `thread_id` (string or `null`) and `metadata` (mapping) are optional; other keys are dropped with a warning. The gateway refuses to start while this is unset or incomplete. |
| `user_authorization_mode` | `allowlist` | `allowlist`, `denylist` | Mode of the user dimension. See [Authorization](#authorization). |
| `role_authorization_mode` | `allowlist` | `allowlist`, `denylist` | Mode of the role dimension. |
| `allowed_user_ids` | `[]` | list of IDs | Users who may open bug reports. Read only in `allowlist` mode. |
| `allowed_role_ids` | `[]` | list of IDs | Roles whose members may open bug reports. Read only in `allowlist` mode. |
| `denied_user_ids` | `[]` | list of IDs | Users who may not open bug reports. Read only in `denylist` mode. |
| `denied_role_ids` | `[]` | list of IDs | Roles whose members may not open bug reports. Read only in `denylist` mode. |
| `deny_message_mode` | `ignore` | `ignore`, `ephemeral` | What a refused reporter sees. `ignore`: nothing. `ephemeral`: a private reply from the bot. See [Refusals the reporter sees](#refusals-the-reporter-sees). |
| `repo_name` | unset | string | A logical project name. The config wizard shows it in its summary; the gateway does not use it. |
| `sandbox_env_passthrough` | `[]` | list of environment-variable names | Variables whose values the gateway copies from its own environment into each sandbox. The agent CLI in the sandbox has no other credentials, so this must name the variable that holds them, for example `ANTHROPIC_API_KEY`. Names must match `[A-Z][A-Z0-9_]*` (at most 64 characters); a listed variable that is unset when a session launches is skipped and logged. |
| `max_concurrent_sandboxes` | `2` | 1–16 | Sessions that may be open at once. |
| `intake_rate_per_user_per_hour` | `4` | 1–60 | Sessions one user may open in any 60-minute window. |
| `sandbox_memory` | `2g` | a number followed by `k`, `m` or `g` | Container memory limit (`docker run --memory`). |
| `sandbox_cpus` | `2` | 1–16 | Container CPU limit (`--cpus`). |
| `sandbox_pids` | `512` | 16–4096 | Container process limit (`--pids-limit`). |
| `sandbox_wall_clock_s` | `1800` | 60–14400 | Seconds a session's container may run before it is killed. |

IDs may be quoted strings or bare integers.

### Invalid values

A config file that is missing, unreadable, not valid YAML, or whose top level is
not a mapping stops the gateway from starting. Inside a valid file, each key
falls back on its own, with a `chatlink config: <key>: …` warning on the
gateway's stderr and in the status TUI's check panel:

- an integer key (`max_concurrent_sandboxes`, `intake_rate_per_user_per_hour`,
  `sandbox_cpus`, `sandbox_pids`, `sandbox_wall_clock_s`) is converted to a
  whole number first:
  - a decimal number is cut to its whole part with no warning, so
    `sandbox_cpus: 1.9` becomes `1`, not the default;
  - a quoted whole number such as `"3"` (surrounding spaces allowed) is
    accepted as that number;
  - any other text (`"3.5"`, `"abc"`) and `true` or `false` use the default,
    with a warning;
  - an empty value (`~`, or the key left out) uses the default with no
    warning;
- a number outside its range, after that conversion, is clamped to the
  nearest bound, with a warning;
- an unknown mode, or a `sandbox_memory` that does not match the pattern, uses
  the default;
- a list key that is not a list becomes `[]`, and empty or non-scalar entries
  are dropped;
- an `intake_channel` with a missing or empty required key counts as unset.

## Authorization

A report is accepted only from a member of the intake channel, and messages from
bots and from the gateway itself are ignored. Each of the two dimensions, users
and roles, reads only the list of its mode: `allowed_*` in `allowlist` mode,
`denied_*` in `denylist` mode. The other list is ignored. The rules apply in
this order:

1. **Explicit deny.** A user listed in `denied_user_ids` (user dimension in
   `denylist` mode), or holding a role listed in `denied_role_ids` (role
   dimension in `denylist` mode), is refused, whatever the other dimension
   allows.
2. **Explicit allow.** A user listed in `allowed_user_ids` (user dimension in
   `allowlist` mode), or holding a role listed in `allowed_role_ids` (role
   dimension in `allowlist` mode), is accepted.
3. **Default.** Anyone left is accepted only when both dimensions are in
   `denylist` mode. Otherwise they are refused.

An empty allowlist therefore lets nobody in through its dimension. With both
modes at their `allowlist` default and both allowed lists empty, nobody can open
a report. The same holds when one dimension is a `denylist` and the other is an
empty `allowlist`: the denylist has no effect, because the empty allowlist keeps
the default at "refuse".

These postures are valid configurations, so the gateway starts with them and
prints nothing about them. The status TUI's check panel and the config wizard
show a warning for each:

| Posture | Panel warning |
|---|---|
| Both dimensions `allowlist`, both lists empty | `both allowlists empty — deny-by-default: nobody can open a bug report` |
| One dimension `denylist`, the other an empty `allowlist` | `denylist has no effect — the empty <users\|roles> allowlist denies everyone` |
| Both dimensions `denylist`, both denied lists empty | `open access: any channel member can open a bug report` |
| A list is filled but its dimension's mode ignores it | `<key> is set but ignored — <mode key> is '<mode>'` |

Only the reporter may answer a session's questions. Anyone else who uses the
controls gets a private reply, and their input is discarded.

## Startup checks and refusals

`ait chatlink --headless` checks its setup before it connects to Discord or
creates anything. It stops at the first failing check, prints one line to
stderr, and exits with status 2 (status 1 for the package rows, which the
launcher checks before the gateway or the status TUI starts). The status TUI,
`ait chatlink` without `--headless`, makes only the row marked `TUI`:

| Order | Message | Cause | Fix |
|---|---|---|---|
| 1 | `Error: Missing Python packages: pyyaml discord.py. Run 'ait setup' and install the chat adapter tier.` (lists only the missing ones) | The chat tier is not installed. | `ait setup --with-chat` |
| TUI | `Error: Missing Python packages: textual pyyaml. Run 'ait setup' to install TUI dependencies.` (lists only the missing ones) | The status TUI's packages are not installed. | `ait setup` |
| 2 | `chatlink: no gateway config found — create aitasks/metadata/chatlink_config.yaml (seeded by 'ait setup') first.` | No config file at the default or configured path. | Run `ait setup` to restore the template, or set `chatlink.config` in `project_config.yaml`. |
| 3 | `chatlink: gateway config <path> is missing or malformed — fix the YAML before starting.` | The file is unreadable, is not valid YAML, or its top level is not a mapping. | Fix the file. Out-of-range values never cause this. |
| 4 | `chatlink: config has no valid intake_channel — the daemon refuses to watch without one.` | `intake_channel` is unset, or `provider`, `workspace_id` or `conversation_id` is missing or empty. | Set all three. |
| 5 | `chatlink: no bot token at <path> — write the bot token there (0600) before starting.` | The token file is missing, unreadable or empty. | Write the token file. |
| 6 | `chatlink: could not resolve the explore-relay agent command — run 'ait codeagent invoke explore-relay --headless --dry-run' manually to diagnose the code-agent config.` | The code-agent configuration cannot produce the exploring agent's command, for example because `explore-relay` is set to an agent other than Claude Code. | Run the command it names and fix what it reports. |

After these checks the gateway connects to Discord. A token Discord rejects, or
a privileged intent that is off in the Developer Portal, ends the gateway with a
Discord error before the running line appears.

Two conditions only warn, and the gateway starts anyway:

- **No `docker` binary.** Both the launcher and the gateway print a line
  beginning `chatlink: warning — 'docker' not found`. Each session then fails at
  launch.
- **Config values that fell back to a default or a bound**, as listed under
  [Invalid values](#invalid-values).

The gateway never checks for the sandbox image. A missing image shows up only
when a session launches, and in the status TUI's check panel as
`sandbox image ait-chatlink-agent not built`.

## Sessions

A session starts when an accepted user posts in the intake channel itself.
Messages inside threads, including the session threads, never start one.

- **Thread.** The gateway opens a thread on the report, named `bug: ` followed
  by the report's first 48 characters.
- **Status reaction.** The report carries one reaction at a time: ⏳ while the
  agent works, ❓ while a question waits for the reporter, ✅ once the task
  exists, ❌ when the session failed.
- **Questions.** The agent asks at most three clarifying questions, then always
  a final confirmation. Each question is a select menu, plus an `Answer…` button
  that opens a dialog when the question accepts free text. A question with more
  than 25 options shows 24 per page behind `Prev` and `Next` buttons. An answered
  question loses its controls and gains the line `*(answered)*`.
- **Timeouts.** The agent waits up to 540 seconds (9 minutes) for each answer.
  On a timeout it takes the default it named in the question and records in the
  task that it did so. That default is always the most conservative reading,
  the one that widens the investigation and never narrows it. Using the controls of a question that has timed out
  gets the private reply `This question has expired.`
- **Confirmation.** The confirmation shows the proposed task's title,
  priority, effort, type, labels and a one-line gist of its description. Its
  timeout default is to create the task as proposed. A free-text reply changes the proposal; the agent applies it and
  confirms once more. A further free-text reply on that second round is applied
  without another confirmation.
- **Task creation.** The agent's only output is a proposal. The gateway rejects
  it, and fails the session, when it is malformed, its `issue_type` is not in
  `aitasks/metadata/task_types.txt`, a label is not in
  `aitasks/metadata/labels.txt`, or its title or description contains control
  or invisible formatting characters. Otherwise it creates and commits the
  task, posts `✅ Task created: **t<N>** — <title>` and the task file's path in
  the thread, and then pushes the task data. A failed push is logged and the
  commit stays local.
- **Failure.** A rejected proposal or a failed task creation posts
  `❌ Bug-report session failed: <reason>`; a sandbox that cannot start posts
  `Could not start the analysis agent — session failed.` An agent that exits
  without a proposal, or is killed at `sandbox_wall_clock_s`, ends with ❌.
- **Gateway restart.** On start, the gateway marks every unfinished session
  whose container is no longer running as failed. Sessions are never resumed.

### Refusals the reporter sees

With `deny_message_mode: ephemeral`, a refused report gets one of these private
replies from the bot. Discord has no private reply to a channel message, so it
arrives as a direct message; if the user does not accept direct messages from
the server, it is only logged. With `ignore`, all three are only logged.

| Reply | Cause |
|---|---|
| `You are not authorized to open bug reports here.` | The authorization rules refused the user. |
| `All bug-report slots are busy — please try again later.` | `max_concurrent_sandboxes` sessions are open. |
| `Rate limit reached — please try again later.` | The user opened `intake_rate_per_user_per_hour` sessions in the last 60 minutes. |

The two ceilings are counted from the stored session records, so a restart does
not reset them. A session that has finished, or failed, no longer counts toward
`max_concurrent_sandboxes`, but still counts toward the user's hourly rate.

## Sandbox

Each session's agent runs in its own `ait-chatlink-agent` container, built by:

```bash
docker build -t ait-chatlink-agent .aitask-scripts/chatlink/docker/
```

`ait setup` does not build it. The container works on a copy of the
repository's committed `HEAD`, with no uncommitted changes, no `.git` directory
and no git credentials, and the copy is deleted when the session ends. The bot
token is never passed in; the only environment the gateway adds is
`sandbox_env_passthrough`. The container has network access, which the agent CLI
needs to reach its model API.

`sandbox_memory`, `sandbox_cpus` and `sandbox_pids` are passed to `docker run`.
The running gateway kills a container when it reaches `sandbox_wall_clock_s`. If
the gateway is down at that moment, it kills the container the next time it
starts.

## Status TUI

`ait chatlink` shows a status line (whether the gateway has written to the audit
log in the last 30 seconds), a check panel, the sessions table (session, state,
initiator, age) and the last 50 lines of the audit log. It refreshes every 2
seconds and never sends anything to the gateway.

The check panel lists the startup checks with their results, the authorization
posture, and three slower checks that run when the TUI opens and on `r`: the
`docker` binary, the sandbox image, and the exploring agent's command.

| Key | Action |
|---|---|
| `r` | Refresh now and re-run the slower checks |
| `w` | Open the config wizard |
| `q` | Quit |
| `j` | Open the [TUI switcher]({{< relref "/docs/tuis#navigating-between-tuis" >}}) |
| `?` | Edit keyboard shortcuts |

The wizard steps through the intake channel, the bot token, an optional live
check, the allowlist, the denied-message mode and `repo_name`, and the ceilings,
then writes the config and the token file at its summary step. Leaving before the summary writes neither. The
live check connects to Discord with the entered token and verifies the token,
both privileged intents, that the bot can see the intake channel, and the bot's
permissions there. The allowlist step can list the channel's members and roles to
pick from. The wizard keeps every key it does not edit, including
`sandbox_env_passthrough`, but does not keep comments in the file. An
interrupted wizard offers to resume its last values (never the token) on the
next start.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| A startup refusal from the table above | See [Startup checks and refusals](#startup-checks-and-refusals). | Fix what the row names. |
| The gateway exits with a Discord error about privileged intents | Server Members or Message Content intent is off on the Bot page. | Enable both, then start the gateway again. |
| The gateway exits with a Discord login error | The token is wrong or was reset. | Reset the token on the Bot page and rewrite the token file. |
| The gateway runs, and posts in the channel get no reaction or thread | On a newly configured gateway the most common cause is that no one is authorized: both allowlists are empty under the default modes. Otherwise the poster is not in an allowlist, or a ceiling is reached. | Check the status TUI's check panel and the audit log. Add the reporter to `allowed_user_ids` or a role to `allowed_role_ids`. Set `deny_message_mode: ephemeral` while testing so refusals reach the reporter. |
| The live check, or a running session, reports that the bot cannot see the intake channel, or lacks permissions there | The channel's permission overwrites exclude the bot, which is typical for a private channel. | Add the bot, or a role it holds, under **Edit Channel → Permissions**, or re-invite it with the invite URL from the workflow page. |
| `Could not start the analysis agent — session failed.` right after the thread opens | Docker is missing, or the sandbox image is not built. | Install Docker, then build the image. |
| ❌ on the report with no task, after the thread opened | The agent exited without a proposal or ran past `sandbox_wall_clock_s`. The usual cause is missing credentials in the sandbox. | Name the credentials variable in `sandbox_env_passthrough` and export it in the gateway's environment. Look for `env passthrough: <name> not set` in the audit log. |
| `❌ Bug-report session failed: issue_type not allowed: …` or `labels not allowed: …` | The proposal used a type or label missing from `task_types.txt` or `labels.txt`. | Add the value to that file and commit it, or let the reporter file again. |
| `Only the user who opened this bug report can answer.` | Someone other than the reporter used the controls. | Nothing to fix. |
| `All bug-report slots are busy — please try again later.` | `max_concurrent_sandboxes` reached. | Wait, or raise the ceiling (at most 16). |
| `Rate limit reached — please try again later.` | `intake_rate_per_user_per_hour` reached for that user. | Wait, or raise the ceiling (at most 60). |

## Internals

The sandbox image's contents, the container mounts and environment, and the
container labels are described in `aidocs/chat/chatlink_sandbox.md` in the
framework's source repository. The gateway's session states, startup
reconciliation and module map are in `aidocs/chat/chatlink_runtime.md`, and the
question-and-answer spool format is in `aidocs/chat/qa_relay_protocol.md`.
