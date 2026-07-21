# Chatlink runtime (gateway daemon)

Maintainer-facing notes on the **gateway daemon** — the process started by
`ait chatlink --headless` (`.aitask-scripts/chatlink/daemon.py`). It owns the
session state machine, startup validation, reconciliation, and the audit log.

Two neighbouring concerns are owned elsewhere and are **cross-linked, not
restated** here:

- The relay spool layout, question/answer/payload schemas, `custom_id` encoding
  and timeout/cancel ownership → `aidocs/chat/qa_relay_protocol.md`.
- The sandbox image, container mounts, ownership labels and the orphan reaper →
  `aidocs/chat/chatlink_sandbox.md`.

User-facing setup and operation live on the website's Bug-Report Intake workflow
page; the Discord bot registration steps are in `aidocs/chat/discord_bot_setup.md`.

## Process split

`aitask_chatlink.sh` performs the mode split **in bash**, before any Python
import, so the daemon never imports Textual (guard-tested):

| Invocation | Module | Needs |
|---|---|---|
| `ait chatlink --headless` | `chatlink/daemon.py` | `pyyaml`, `discord.py` (+ `docker` at launch time) |
| `ait chatlink` | `chatlink/chatlink_app.py` | `textual`, `pyyaml` |

`chatlink_app.py` is the only module permitted to import Textual. The status TUI
is strictly read-only: it renders the sessions table and an audit-log tail, and
never commands the daemon.

## Startup: validate, then serve

`serve()` performs every refusable check **before** any side effect (adapter
connect, directory creation, logger wiring). Each failure returns a nonzero exit
with a single diagnostic line:

1. No config file found (`aitasks/metadata/chatlink_config.yaml`, or the path in
   `project_config.yaml` under `chatlink.config`).
2. Config missing or malformed — the loader returns `None` for an unreadable
   file, unparseable YAML, or a non-mapping document.
3. `intake_channel` absent or missing one of `provider` / `workspace_id` /
   `conversation_id`.
4. No bot token at `aitasks/metadata/chatlink_sessions/bot_token`.
5. The explore-relay agent command cannot be resolved (validated by an
   engine-owned `--dry-run`). A gateway that can never launch must not start.

**Docker is a warn-not-block.** A missing `docker` binary prints a warning and
the gateway still serves; launches then fail honestly, marking the session
`failed` and annotating the thread.

Bad *values* inside a well-formed config never refuse: each key degrades
independently to its clamped default with a stderr warning. Only the file itself
being broken is fatal.

## Session state machine

Pinned in `sessions_store.py`:

```
spawning → asking ⇄ working → awaiting_payload → done
    └──────────────────────────────────────────→ failed
```

| State | Meaning |
|---|---|
| `spawning` | Record persisted, sandbox not yet confirmed running. |
| `asking` | A question is posted; awaiting the reporter's answer. |
| `working` | The agent is exploring (entered on intake-accept and after each answer). |
| `awaiting_payload` | `payload.json` seen; validation and task creation in flight. |
| `done` | Task created and committed. **Terminal.** |
| `failed` | Session aborted. **Terminal.** |

`TERMINAL_STATES = {"done", "failed"}`.

**`spawning` is written before the launch call.** That ordering is the crash
contract: a gateway that dies mid-intake leaves a `spawning` record with no live
container, and startup reconciliation fail-closes it to `failed` — it is never
resumed.

Records are per-session JSON under
`aitasks/metadata/chatlink_sessions/sessions/`, written atomically (0700 dir /
0600 file). The **relay spool is the source of truth** for interaction outcomes;
a record's `interaction_outcomes` is derived from the spool and healed from it.

## Reconciliation

Three pure planners in `reconcile.py` (no I/O — they emit phase-ordered
`Action`s that the daemon loop executes):

- **Startup** — asks the launcher for the live set (see the reaper in
  `chatlink_sandbox.md`), then fail-closes every non-terminal record absent from
  it.
- **Reconnect** — re-queries state after a Gateway disconnect. `INTERACTION_RECEIVED`
  is non-replayable, so outcomes are persisted on receipt rather than replayed.
- **Agent death** — driven by the per-launch watchdog's thread-safe signal. The
  signal only enqueues; all durable cleanup runs on the daemon loop.

Mid-life container deaths are signalled, never polled, by the daemon.

## Authorization and ceilings

`policy.decide()` gates intake (deny-by-default); `policy.may_answer()` gates
every interaction to the initiating reporter. The user and role dimensions each
run in `allowlist` or `denylist` mode (`user_authorization_mode` /
`role_authorization_mode`, both default `allowlist` — existing configs keep the
deny-by-default posture). Each dimension consults only its mode's active list
(`allowed_*` for allowlist, `denied_*` for denylist). Precedence is pinned:
explicit deny > explicit allow > default; the default allows (`ok_not_denied`)
only when both dimensions are denylist, else it denies. An empty allowlist
dimension still means "nobody" (fail-closed); `policy.effective_posture()`
classifies the resulting posture (`deny_all` / `open_members` / `restricted`,
naming the degenerate dimension) as the single source for preflight and the
wizard. The two families of denial reason are deliberately distinct so tests
can pin one negative control per reason:

| Family | Reasons |
|---|---|
| Policy (`policy.py`) | `no_config`, `no_claims`, `not_channel_member`, `user_not_allowed`, `role_not_allowed`, `user_denied`, `role_denied`, `not_initiator` (allow: `ok_user`, `ok_role`, `ok_not_denied`, `ok_initiator`) |
| Ceiling (`intake.py`) | `ceiling_sandboxes`, `ceiling_user_rate` |

Ceilings are `max_concurrent_sandboxes` (counted via `count_nonterminal`) and
`intake_rate_per_user_per_hour` over a 3600 s window.

## Audit log

`audit.get_logger()` wires a `FileHandler` at
`<sessions_dir>/chatlink_audit.log` on first call, falling back to a
`NullHandler` when the directory is unwritable. There is **no rotation**.

Secrets are never logged, and identifiers are truncated at call sites (first 8
characters plus an ellipsis) rather than by the logger. Events cover intake
accept/deny, ceiling rejections, state transitions, reconciliation counts, and
task creation.

## Secrets

The bot token is the only secret, and the token file is its only source —
chatlink defines no token environment variable. It lives at
`aitasks/metadata/chatlink_sessions/bot_token` (file 0600, directory 0700; the
directory is gitignored). It is passed only to `DiscordAdapter.connect()` and is
never included in the sandbox environment allowlist.

## Platform scope

The daemon constructs `DiscordAdapter` directly — there is no adapter-selection
seam. A Slack adapter exists under `.aitask-scripts/chat/`, and the config
comments anticipate Slack identifiers, but no chatlink code path builds one.
Intake is Discord-only until a selection seam lands.

## Module map

| Concern | Module |
|---|---|
| Headless daemon entry, event loop, startup validation | `daemon.py` |
| Read-only status TUI (only Textual importer) | `chatlink_app.py` |
| Config schema + fault-tolerant loader | `config.py` |
| Config path, token file, spool + workspace roots, secure-dir helpers | `paths.py` |
| Intake authorization, initiator gating | `policy.py` |
| Event pipeline: auth → ceilings → thread → launch; status reactions | `intake.py` |
| Persistent session records, ceiling queries | `sessions_store.py` |
| Relay spool library, identity, schemas (see `qa_relay_protocol.md`) | `relay.py` |
| Agent-side ask / payload helpers | `relay_ask.py`, `relay_payload.py` |
| Question → Discord components; answer assembly | `render.py` |
| Spool→Discord pump; `complete_session` sink | `flow.py` |
| Pure reconciliation planners | `reconcile.py` |
| Untrusted-payload validation (fail-closed) | `payload_guard.py` |
| Task creation from a validated payload | `task_create.py` |
| Audit logger | `audit.py` |
| Launcher seam re-export (see `chatlink_sandbox.md`) | `spawn_seam.py` |

## Verification

- `tests/test_chatlink_daemon.sh`, `tests/test_chatlink_config.sh`,
  `tests/test_chatlink_flow.sh`, `tests/test_chatlink_relay.sh`,
  `tests/test_chatlink_tui.sh` — daemon, config loader, flow pump, relay library
  and status-TUI suites, driven against `MockChatAdapter`; no live-platform calls.
- Sandbox suites are listed in `aidocs/chat/chatlink_sandbox.md`.
