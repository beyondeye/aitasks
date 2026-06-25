---
Task: t1074_chat_adapter_abstraction_layer.md
Worktree: (none — profile 'fast', current branch)
Branch: main
Base branch: main
---

# Plan: t1074 — Low-level chat (Slack/Discord) abstraction layer

## Context

This is the **first, lowest layer** of a new alternative interaction surface for
aitasks based on **Slack/Discord** — a long-term alternative/supplement to the
tmux surface, inspired by (not a clone of) Claude tag and informed by the Nous
*Hermes agent*. The user supplied a 4-part design analysis whose conclusion is:
**abstract concepts, not APIs** — the agent/runtime above must never know whether
it is talking to Slack or Discord. The full target is a 5-layer stack
(`Agent Skills → Agent Runtime → Conversation Runtime → Messaging Runtime →
Slack/Discord Adapter`). **This task delivers only the bottom — the
platform-agnostic `ChatAdapter` + domain model + two concrete adapters.** Nothing
aitasks-specific is built here (no task/gate/monitor wiring, no persistence, no
Conversation Runtime — all explicitly deferred to later tasks).

In-repo precedent for the "external client ↔ workspace" pattern is `ait applink`
(`.aitask-scripts/applink/`): a clean transport/router/profile/session split.
We reuse its **module style** (self-contained package, lazy heavyweight imports,
bash test wrappers that SKIP when a dep is absent) — not its code (different
transport and domain model).

## Decisions (confirmed with user)

1. **Decompose into 3 child tasks**, sequential:
   - **t1074_1 — core** (dependency-free): domain model + `ChatAdapter` ABC +
     capability discovery + error taxonomy + `MockChatAdapter` + the package
     scaffold. No third-party deps; fully unit-testable.
   - **t1074_2 — Discord adapter** (`discord.py`, Gateway). Depends on t1074_1.
     Also introduces the opt-in dep tier (see #3).
   - **t1074_3 — Slack adapter** (`slack_bolt`+`slack_sdk`, Socket Mode).
     Depends on t1074_2 (sequential — Discord validates the interface first).
2. **Language/runtime:** Python, `asyncio` throughout (matches the framework
   venv + the design doc + the SDK ecosystem). Package is a **library** — no
   TUI/launcher in this task (a launcher arrives with the aitasks-integration
   layer later; live connection testing is a deferred follow-up).
3. **Dependency install — opt-in `ait setup --with-chat`** (mirrors the existing
   `--with-pypy` tier in `aitask_setup.sh`). New `AIT_PIP_SPECS_CHAT` /
   `AIT_IMPORTS_CHAT` arrays installed **only** when the flag is passed. The SDKs
   are **lazily imported** inside adapter methods so importing the package (and
   `MockChatAdapter`) never requires them. The core child adds **no** deps.

## Architecture

New self-contained package `.aitask-scripts/chat/` (parallels
`.aitask-scripts/applink/`, `monitor/`):

| File | Responsibility |
|------|----------------|
| `__init__.py` | Public API exports (model, `ChatAdapter`, errors, `MockChatAdapter`). **Must not import any aitasks module** — enforced by a guard test. |
| `model.py` | Domain dataclasses + enums: `Workspace`, `Conversation` (+`ConversationKind`: CHANNEL/THREAD/DIRECT/PRIVATE/TEMPORARY), `ConversationRef` (opaque reconnect token), `Message`, `MessageRef`, `User`, `Actor` identity (`ActorType`: USER/BOT/SYSTEM; `is_bot`), `IdentityClaims` (concern #4 — platform-honest, see below), `Attachment`, `Mention`, `Reaction`, `Event`, `Role`, `Permission`. **`EventType` (expanded, extensible):** MESSAGE_CREATED, MESSAGE_EDITED, MESSAGE_DELETED, REACTION_ADDED, REACTION_REMOVED, APP_MENTION, THREAD_CREATED, THREAD_DELETED, FILE_UPLOADED, USER_JOINED, USER_LEFT, CHANNEL_CREATED, INTERACTION_RECEIVED, UNKNOWN (raw payload preserved in `metadata`). Every entity carries a `metadata: dict` for platform extras. |
| `errors.py` | `ChatError` base + `ConversationNotFound`, `PermissionDenied`, `RateLimited`, `AttachmentTooLarge`, `UserNotFound`, `DeliveryFailed` (ephemeral/DM could not be delivered privately — concern #1), `InteractionExpired` (responding past the ack/follow-up window — concern #2/#3). |
| `interactions.py` | Platform-agnostic **interaction surface** (concern #1): outbound components (`Button`, `SelectMenu` + grouped `ActionRow`/`components` attachable to `send_message`/`edit_message`), `Modal`/`Form` (fields), `SlashCommand` registration spec; inbound `Interaction` (subtype: BUTTON / SELECT / MODAL_SUBMIT / COMMAND) carrying the originating `Actor`, source conversation/message, and submitted values. Defines the **ack/respond contract** (see below). |
| `capabilities.py` | `Capabilities` dataclass (concern #7): booleans + limits — `supports_buttons`, `supports_selects`, `supports_modals`, `supports_slash_commands`, `supports_reactions`, `supports_files`, `supports_ephemeral`, `supports_dm`, `supports_voice`, `supports_editing`, `supports_thread_creation`, `supports_standalone_threads`, `supports_message_search`, `max_message_length`, `max_attachment_bytes`. Returned by `ChatAdapter.capabilities()`. |
| `adapter.py` | `ChatAdapter` ABC. **Messaging:** `send_message(conversation, text, *, attachments=None, components=None, reply_to=None)`, `edit_message`, `delete_message`, `fetch_message`, `send_ephemeral(conversation, actor, text, *, components=None)`. **Conversations/threads:** `create_conversation(kind, *, parent=None, name=None, ...)`, `archive_conversation`, `fetch_history` (adapter owns pagination/cursor), `fetch_participants`. **Discovery (concern #4):** `fetch_conversation(ref)` (resolve / existence check → raises `ConversationNotFound`), `list_conversations(*, kinds=None)`, `get_permalink(ref)` → human-openable URL. **Identity (concern #2/#4):** `fetch_user(user_ref)`, `fetch_identity_claims(conversation, user_ref) -> IdentityClaims`. **Reconciliation (concern #2):** `fetch_reactions(message_ref)`. **Files/reactions:** `upload_attachment`, `download_attachment`, `add_reaction`, `remove_reaction`. **Interactions (concern #1):** `register_commands(specs)`, `ack(interaction)`, `respond(interaction, …, *, ephemeral=False)`, `follow_up(interaction, …)`, `open_modal(interaction, modal)`. **Events (concern #6):** `subscribe(*, conversations=None, since=None)` async-iterates normalized `Event`s. **Capabilities:** `capabilities() -> Capabilities`. |

### Thread support (first-class in the base layer)

Threads are the central primitive of the whole feature (the `Task → Thread →
Agent-discussion` pattern), so the base layer models them fully — only thread
*policy* (auto-threading, one-thread-per-task) is deferred to higher layers.

- **Model:** a thread is a `Conversation` with `kind=ConversationKind.THREAD`,
  addressed by an opaque `ConversationRef` carrying the provider thread id
  (Slack `thread_ts`, Discord `thread_id`).
- **Create:** `create_conversation(kind=THREAD, parent=…)` requires a `parent`:
  - `parent: MessageRef` → anchor the thread on a message (**both** platforms;
    Slack `thread_ts`, Discord message-thread).
  - `parent: ConversationRef` (a channel) → Discord standalone channel-thread;
    Slack raises `PermissionDenied`/`NotImplemented`, gated by
    `supports_standalone_threads()` (`True` Discord / `False` Slack).
- **Reply in-thread:** `send_message(thread_ref, …)` posts into the thread;
  `send_message(channel_ref, …, reply_to=MessageRef)` expresses a threaded reply
  off a channel message (Slack: passes the parent `thread_ts`).
- **Recovery contract:** a `THREAD` `ConversationRef` round-trips (serialize →
  reconstruct) and is sufficient for `fetch_history(thread_ref)` to return the
  thread's replies and `subscribe` to receive its events — this is the explicit
  thread-recovery requirement from the design doc.
- **Capability/event:** `supports_thread_creation()` + `THREAD_CREATED` event.

### Interaction surface (concern #1 — primitives, not aitasks policy)

The feature exists to *drive* aitasks from chat (plan approval, gate
pass/fail/skip/defer, task pick, AskUserQuestion answers, archive/defer). So the
base layer defines **generic** interaction primitives — never aitasks-specific
ones — so higher layers compose native UX without leaking SDK objects or
text-parsing:

- **Outbound components:** `Button`, `SelectMenu` (grouped in `ActionRow`), passed
  as `components=` to `send_message`/`edit_message`; `Modal`/`Form` opened via
  `open_modal`. `SlashCommand` specs registered via `register_commands`.
- **Inbound:** every component click / select / modal submit / command invocation
  arrives as an `Interaction` (also surfaced as an `INTERACTION_RECEIVED` event),
  carrying the originating `Actor`, the source conversation/message, and submitted
  values.
- **Ack / respond contract (concern #3 — deadline off the consumer's path):**
  both platforms require acknowledging an interaction within ~3 s (Discord: defer +
  follow-up webhook; Slack: ack + `response_url`). To keep this off the consumer's
  critical path, **adapters auto-defer/ack the interaction immediately on receipt,
  before it is yielded** from `subscribe()` (or to a handler). The `Interaction`
  thus arrives **already acked**; the consumer responds at its own pace via
  `respond(...)` / `follow_up(...)` (`ephemeral=True` allowed), which transparently
  use the post-ack follow-up transport. `ack(interaction)` is therefore **idempotent**
  (a no-op if the adapter already deferred). Responding past the platform's
  follow-up window raises `InteractionExpired`.

### Identity & authorization primitives (concern #2 — primitives, not policy)

Reactions/buttons are only actionable if the framework knows *who* acted. The base
layer exposes the **primitives**; allowlist enforcement and gate-ownership remain
higher-layer policy:

- Every `Interaction` and actor-bearing `Event` carries an `Actor` (`ActorType`
  USER/BOT/SYSTEM, `is_bot`, `roles`). Bot/self events are distinguishable
  (avoids self-trigger loops).
- `fetch_user(user_ref)` resolves a platform actor to a normalized `User`.
- **`IdentityClaims` (concern #4 — platform-honest, no false equivalence):** rather
  than a Discord-shaped `roles` list, `fetch_identity_claims(conversation, user_ref)`
  returns a generic claim set that each platform fills as it can:
  `roles: list[Role]` where each `Role` carries a `kind` (`discord_role` |
  `slack_usergroup`), `is_workspace_admin` / `is_owner` (Slack workspace flags),
  `is_channel_member: bool`, and `metadata` for raw provider data. Slack populates
  usergroups + admin/owner flags; Discord populates guild roles. Nothing is coerced
  into a pretend-common role model. A higher layer maps claims → authorization /
  gate-ownership **without** touching SDK objects — and that mapping/allowlist is
  **out of scope** here (aitasks policy).

### Discovery & permalinks (concern #4 — primitives, not task policy)

For restart/reconnect and linking back to chat artifacts: `fetch_conversation(ref)`
(resolve a stored ref / existence check, raising `ConversationNotFound` when gone),
`list_conversations(kinds=…)`, and `get_permalink(ref)` → a human-openable URL
(Slack `chat.getPermalink`; Discord `discord.com/channels/<g>/<c>/<m>`). Message
**search** is capability-gated (`supports_message_search`; Slack `search.messages`,
Discord none) and optional. Task-thread *mapping/ensure* semantics stay higher-layer.

### Ephemeral / status messaging (concern #5 + #1 — private-only fallback)

`send_ephemeral(conversation, actor, text, *, components=None)` plus
`respond(..., ephemeral=True)` for interaction responses. **Private-only fallback
contract (never leak to a public channel):** native ephemeral if the context
supports it (Slack `chat.postEphemeral`; Discord interaction-response flag) →
**DM the actor**. If neither private channel is available, the adapter **raises
`DeliveryFailed`** and posts **nothing public** — the higher layer decides what to
do (suppress, log, or post a deliberately non-sensitive generic notice). The
return value reports which private path was used. This protects approval prompts /
permission-denials / validation errors from leaking workflow state.

### Subscription contract (concern #6 — define now, durable persistence later)

`subscribe(*, conversations=None, since=None)` async-iterates `Event`s. Documented
semantics (even though durable persistence is deferred):

- **Scoping:** `conversations=None` → all visible; otherwise filtered to the given
  refs (thread refs included).
- **Delivery:** at-least-once *while connected*; **no replay across a disconnect.**
- **What is recoverable after a disconnect (concern #2 — stated explicitly):**
  - **Recoverable by re-query:** message create/edit/delete — via
    `fetch_history(conversation, after=last_seen)` (and `fetch_message` for current
    state); **reaction state** — via a new `fetch_reactions(message_ref)` that
    returns the *current* reaction set, so a missed REACTION_ADDED/REMOVED is
    reconciled by **diffing** against last-known state (not by replaying the event);
    conversation/thread existence — via `fetch_conversation`.
  - **NOT replayable:** `INTERACTION_RECEIVED` (button click, select, modal submit,
    slash command). These are transient gateway deliveries with no server-side
    queue — if the process is down when they fire, they are **lost** (the user sees
    a failed/expired interaction). The contract states this plainly: **higher layers
    must persist interaction outcomes idempotently the moment they are received and
    must be able to re-prompt** if a signal window was missed. The base layer will
    not pretend to recover them.
- **Reconciliation primitives provided:** `fetch_reactions(message_ref)`,
  `fetch_message`, `fetch_history(after=)`, `fetch_conversation`. Adapters
  auto-reconnect the underlying gateway (Discord Gateway / Slack Socket Mode);
  higher layers use these primitives for gap recovery instead of each reinventing
  it. (Durable event-store persistence = later task.)
| `mock.py` | `MockChatAdapter` — in-memory, deterministic; simulates conversations/users/messages/history/reactions and pushes synthetic `Event`s through `subscribe`. Zero external deps. |
| `discord_adapter.py` | `DiscordAdapter(ChatAdapter)` — lazy `import discord`. Pure normalization functions (duck-typed input → domain) kept module-level for dependency-free testing. |
| `slack_adapter.py` | `SlackAdapter(ChatAdapter)` — lazy `import slack_bolt`/`slack_sdk`, Socket Mode. Same pure-normalization split. |

**Key testability move (per testability-first decomposition):** each adapter's
platform→domain mapping is written as **pure functions taking duck-typed objects**
(e.g. `SimpleNamespace`), so normalization is unit-tested **without** the real SDK
installed. The lazy `import` lives only in the methods that make network calls.

## Child specifications

> Children are created **after this plan is approved** (plan mode is read-only).
> Each child file gets the full Context / Key files / Reference patterns /
> Implementation plan / Verification sections required for fresh-context execution.

### t1074_1 — core (domain model + ChatAdapter + Mock) — dependency-free
- **Files (new):** `.aitask-scripts/chat/{__init__,model,errors,interactions,capabilities,adapter,mock}.py`. This child owns the **complete, frozen** platform-agnostic contract (messaging + threads + interactions + identity + discovery + ephemeral + subscription + capabilities) so the adapter children implement against a stable surface.
- **Reference patterns:** dataclass/enum style from `monitor/monitor_core.py`
  (`PaneSnapshot`, `PaneCategory`); ABC + duck-typed seams from
  `applink/router.py`.
- **Tests (new, bash wrappers sourcing `lib/python_resolve.sh`):**
  `tests/test_chat_model.sh` (entity construction, `ConversationRef` opacity +
  `THREAD` ref serialize→reconstruct round-trip, enum coverage), `tests/test_chat_mock.sh`
  (full `MockChatAdapter` lifecycle: send/edit/delete/fetch/history pagination/react/
  subscribe-event-stream + **thread lifecycle**: create-thread-from-message,
  reply-in-thread, `fetch_history` on a recovered thread ref, `THREAD_CREATED` event,
  standalone-thread capability gating; **interactions**: components on a message →
  synthetic `Interaction`/`INTERACTION_RECEIVED` with `Actor`, ack→respond→follow_up,
  `open_modal`→`MODAL_SUBMIT`; **auto-defer**: a yielded `Interaction` is already
  acked (idempotent `ack`), `respond`/`follow_up` work afterward, past-window raises
  `InteractionExpired`; **identity**: `fetch_user`, `fetch_identity_claims` returns
  `IdentityClaims` (role `kind`, admin/owner/channel-member flags), bot/self-actor
  distinction; **discovery**: `fetch_conversation` existence raises
  `ConversationNotFound`, `get_permalink`, `list_conversations`; **ephemeral**:
  `send_ephemeral` private-only fallback (native→DM→`DeliveryFailed`, never public);
  **subscription/recovery**: conversation-scoped filtering, `fetch_history(after=)`
  backfill, `fetch_reactions` diff-reconciliation, and that `INTERACTION_RECEIVED` is
  documented non-replayable; **capabilities** struct values + every error in the
  taxonomy), `tests/test_chat_no_aitasks_import.sh` (guard: importing
  `chat` pulls in no `aitasks`/framework module).
- **Verification:** `bash tests/test_chat_model.sh && bash tests/test_chat_mock.sh
  && bash tests/test_chat_no_aitasks_import.sh` all PASS with the stock venv (no
  new deps).

### t1074_2 — Discord adapter (depends on t1074_1)
- **Files (new):** `.aitask-scripts/chat/discord_adapter.py`,
  `tests/test_chat_discord.sh`.
- **Files (edit) — install flow:** `aitask_setup.sh` — add `AIT_PIP_SPECS_CHAT`
  (`'discord.py>=2,<3'`) + `AIT_IMPORTS_CHAT` (`discord`) arrays and the
  `--with-chat` flag handling (mirror the `--with-pypy` blocks near lines 514+,
  3100; install `AIT_PIP_SPECS_CHAT` into the CPython venv only when the flag is
  set). **Read `aidocs/framework/aitasks_extension_points.md` first** (install-flow
  touchpoint checklist).
- **Reference patterns:** lazy heavyweight import — `applink/content.py` (`import
  msgpack` inside functions); dep-validation launcher idiom — `aitask_applink.sh`.
- **Surface:** implements the **full** `ChatAdapter` contract for Discord —
  components (buttons/selects), modals, slash-command registration, the
  `INTERACTION_CREATE` → `Interaction` mapping with the **3 s defer + follow-up
  webhook** ack/respond contract; ephemeral only as an interaction-response flag
  with **DM fallback** otherwise (`supports_ephemeral` context-dependent); permalink
  `discord.com/channels/<g>/<c>/<m>`; events `MESSAGE_DELETE`/
  `MESSAGE_REACTION_REMOVE`/`GUILD_MEMBER_REMOVE`/`INTERACTION_CREATE` (with required
  intents); **auto-defer** interactions on receipt; `fetch_reactions` from message
  reactions; `IdentityClaims` from guild roles (`kind=discord_role`);
  `supports_message_search=False`; `supports_standalone_threads=True`. Populate
  `Capabilities` with Discord limits (max message length, attachment size by boost
  tier).
- **Tests:** `tests/test_chat_discord.sh` exercises the pure normalization
  functions (events → domain `Event`/`Interaction`/`Actor`, components→payload) against
  `SimpleNamespace` stand-ins for discord objects (no real lib); if a future live
  test needs `discord`, it SKIPs gracefully (`import discord` guard → `exit 0`), per
  `tests/test_applink_router.sh`'s pyyaml SKIP.
- **Verification:** `bash tests/test_chat_discord.sh` PASSES without `discord`
  installed; `ait setup --with-chat` then `python -c "import discord"` succeeds.

### t1074_3 — Slack adapter (depends on t1074_2)
- **Files (new):** `.aitask-scripts/chat/slack_adapter.py`,
  `tests/test_chat_slack.sh`.
- **Files (edit):** `aitask_setup.sh` — **append** `'slack-bolt>=1,<2'`,
  `'slack-sdk>=3,<4'` to `AIT_PIP_SPECS_CHAT` and `slack_bolt`, `slack_sdk` to
  `AIT_IMPORTS_CHAT` (scaffold already added in t1074_2).
- **Surface:** implements the **full** `ChatAdapter` contract for Slack — Socket
  Mode (`xoxb-` bot token + `xapp-` app token); commonly-missed scopes/events
  (`channels:history`, `groups:history`, `message.channels`, `app_mention`,
  `files:read`); Block Kit components + `views.open`/`view_submission` modals;
  slash commands + interactivity payloads with the **3 s ack + `response_url`
  follow-up** contract; `chat.postEphemeral` (per-user, `supports_ephemeral=True`);
  `chat.getPermalink`; events `message_deleted`/`reaction_removed`/
  `member_left_channel`; `search.messages` → `supports_message_search=True`;
  `supports_standalone_threads=False`; **auto-defer** interactions on receipt
  (ack + `response_url`); `fetch_reactions` via `reactions.get`; `IdentityClaims`
  from usergroups (`kind=slack_usergroup`) + `is_workspace_admin`/`is_owner` flags.
  Populate `Capabilities` with Slack limits.
- **Tests:** `tests/test_chat_slack.sh` — same pure-normalization-with-stubs
  approach + graceful SKIP.
- **Verification:** `bash tests/test_chat_slack.sh` PASSES without slack libs;
  `ait setup --with-chat` installs both SDKs.

## Out of scope (later tasks)
Sync engine / persistence (SQLite/Postgres), event store, summarization,
embeddings, replay; the Conversation Runtime + Agent Runtime; all aitasks
integration (tasks↔threads, gates↔reactions, monitor/shadow↔chat, board,
notifications, multi-agent routing); credential/secret storage subsystem; live
integration tests against a Slack sandbox / Discord test server; any TUI/launcher.

## Risk

- **Code-health risk: low.** All-new, self-contained package with no edits to
  existing runtime code paths. The only existing-file edits are **additive** dep
  arrays + an opt-in flag in `aitask_setup.sh` (t1074_2/t1074_3), gated behind
  `--with-chat` so default installs are unchanged. Blast radius if someone edits
  it unaware: confined to the chat package; the no-aitasks-import guard test and
  the dependency-free core protect against accidental coupling.
- **Goal-achievement risk: medium.** The abstraction's real test is whether it
  cleanly supports the *later* aitasks integration — not built here, so interface-fit
  can't be fully proven this task. The surface was deliberately **widened** (per the
  reviewed concerns) to cover interactions, identity, discovery, ephemeral, and the
  subscription contract so later layers never leak SDK objects or text-parse — this
  reduces interface-fit risk but enlarges `t1074_1` (now the complete frozen
  contract: 7 modules). Mitigated by `MockChatAdapter` exercising the **whole**
  contract and by following the design doc + known platform protocols. Adapter↔SDK
  fidelity is only mock/stub-tested (live testing is a deliberate follow-up), so a
  real-API mismatch could surface later — the deferred live-integration follow-up is
  where real-API + ack-deadline fidelity gets validated.
- **Scope guard:** the widened surface adds **primitives only** — actor identity &
  role lookup, not allowlist/gate-ownership enforcement; permalink/existence, not
  task-thread mapping; generic components/commands, not plan-approval UX. All policy
  stays in the deferred higher layers.
- **Planned mitigations:** none gated as before/after for this decomposition —
  each adapter child verifies its own normalization; the deferred live-integration
  follow-up is the natural place to validate real-API fidelity (incl. the 3 s
  interaction-ack deadline, which mocks cannot prove).

## Post-approval execution (Step 7 onward)
1. Create the 3 children via the Batch Task Creation Procedure (`mode child`,
   `--parent 1074`; t1074_3 keeps the default sibling-dep on t1074_2).
2. Write `aiplans/p1074/p1074_{1,2,3}_*.md` from the specs above; commit.
3. Revert parent t1074 → `Ready`, clear `assigned_to`, release parent lock.
4. Manual-verification sibling: **recommend "No"** — this is a unit-tested library;
   live verification is the explicitly-deferred follow-up.
5. Child checkpoint: start t1074_1 or stop and pick children later.

## Verification (per child, summary)
Run the child's bash test wrapper(s); all PASS on the **stock** venv (core +
adapters via stubs). `ait setup --with-chat` provisions the real SDKs and
`python -c "import discord / slack_bolt / slack_sdk"` succeeds in `~/.aitask/venv`.
