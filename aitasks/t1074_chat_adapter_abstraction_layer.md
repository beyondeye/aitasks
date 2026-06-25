---
priority: medium
effort: high
depends: []
issue_type: feature
status: Implementing
labels: [chat_surface, python]
children_to_implement: [t1074_1]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-06-25 10:14
updated_at: 2026-06-25 11:52
---

## Goal

Build the **first, lowest layer** of a new alternative interaction surface for
aitasks based on **Slack/Discord** (a long-term alternative/supplement to the
current tmux-based surface, inspired by — but not a clone of — Claude tag, and
informed by the Nous Research *Hermes agent*).

This task delivers a **low-level, platform-agnostic chat abstraction layer that
is NOT aitasks-specific**. The aitasks integration (mapping tasks/gates/monitor
onto chat) is built on top of this layer in **later, separate tasks** and is
explicitly out of scope here.

> Guiding principle (from the design doc): **abstract concepts, not APIs.** The
> agent/runtime above must never know whether it is talking to Slack or Discord.

## Background / references

- Design doc: 4-part "Slack vs Discord for AI Agent Platforms" analysis
  (provided by the user; the relevant parts are Part 3 *Designing a
  Cross-Platform Abstraction Layer* and Part 4 *Implementation Guide*). The
  proposed full stack is five layers — **this task is layer 1 (+ the seam of
  layer 2)** only:
  ```
  Agent Skills → Agent Runtime → Conversation Runtime → Messaging Runtime → Slack/Discord Adapter
  ```
- Reference implementation: Hermes agent
  (https://github.com/NousResearch/hermes-agent,
  https://hermes-agent.nousresearch.com/docs/user-guide/messaging/discord,
  https://hermes-agent.nousresearch.com/docs/user-guide/messaging/slack).
  Key validated decisions: **persistent WebSocket gateway, not webhooks**
  (Discord Gateway API via bot token; Slack **Socket Mode** via `slack_bolt`
  with `xoxb-` bot token + `xapp-` app-level token). No public HTTP endpoint
  required — works behind a firewall / on a local machine, which fits a local
  `ait` workspace. Deny-by-default allowlist; reactions as status (👀/✅/❌);
  attachment download/cache; `!`-prefix fallback for slash commands inside
  threads.
- Inspiration: Claude tag (mention-based, in-thread live progress checklists,
  channel-scoped access). Inspiration only — NOT a clone.
- In-repo precedent (style reference, NOT to be entangled with): `ait applink`
  (`.aitask-scripts/applink/`, `aidocs/applink/`) already demonstrates the
  framework's "external client interacts with the workspace" pattern — a clean
  transport/router/profile/session/audit split. Its transport (LAN WebSocket +
  MessagePack grid) and domain model differ; reuse the *architectural style*,
  not the code.
- User notes stub: `aidocs/slack/pros_and_cons.md`.

## Scope — what this task delivers

Implement in **Python** (matches the framework runtime — applink/monitor/TUIs —
and the SDK/LLM ecosystem), `asyncio` throughout (no thread-based design). The
layer must be a **self-contained module**, decoupled from `aitask_*.sh` scripts.

1. **Platform-agnostic domain model** (platform extras live only in a per-entity
   `metadata` field; never leaked upward):
   - `Workspace`
   - `Conversation` + `ConversationKind` enum (CHANNEL / THREAD / DIRECT /
     PRIVATE / TEMPORARY)
   - `ConversationRef` — opaque reconnect token (e.g. Slack `channel_id` +
     `thread_ts`; Discord `guild` + `thread_id`); the orchestrator treats it as
     opaque. Supports **thread recovery** (reconnect to existing work after a
     restart).
   - `Message`, `MessageRef`
   - `User` (normalized: id, display_name, username, email, avatar, is_bot,
     metadata)
   - `Attachment` (id, filename, mime_type, size, url, uploader)
   - `Mention` (→ `User`)
   - `Reaction` (emoji, users, count)
   - `Event` (id, type, timestamp, actor, payload) with a **normalized internal
     event taxonomy**: MESSAGE_CREATED, MESSAGE_EDITED, REACTION_ADDED,
     THREAD_CREATED, FILE_UPLOADED, USER_JOINED (framework names, not
     Slack's/Discord's).
   - `Role` / `Permission` (kept minimal at this layer).

2. **`ChatAdapter` interface** — capabilities, not REST endpoints. Async methods:
   `create_conversation`, `archive_conversation`, `send_message`,
   `edit_message`, `delete_message`, `fetch_message`, `fetch_history`
   (adapter owns pagination: before/after/limit), `fetch_participants`,
   `upload_attachment`, `download_attachment`, `add_reaction`,
   `remove_reaction`, `subscribe` (yields normalized `Event`s).

3. **Capability discovery** so higher layers adapt instead of hard-coding
   platform assumptions: `supports_ephemeral_messages()` (Slack yes, Discord
   no), `supports_thread_creation()`, `supports_voice()`, `supports_editing()`.
   Message streaming = edit-an-existing-message (works on both); no assumption of
   native streaming.

4. **Normalized error taxonomy** (adapters translate platform errors):
   `ConversationNotFound`, `PermissionDenied`, `RateLimited`,
   `AttachmentTooLarge`, `UserNotFound`.

5. **Two concrete adapters**, each implementing `ChatAdapter` with **zero
   business logic** (translate / authenticate / normalize only):
   - **Slack adapter** — `slack_bolt` + `slack_sdk`, **Socket Mode**. Handle the
     commonly-missed scopes/events (`channels:history`, `groups:history`,
     `message.channels`, `app_mention`, `files:read`/`files:write`).
   - **Discord adapter** — `discord.py`, **Gateway** (bot token). Map
     channel/thread/DM, mentions, reactions, attachments, required gateway
     intents.

6. **`MockChatAdapter`** — in-memory, deterministic, platform-free
   implementation of `ChatAdapter` for unit-testing higher layers and this layer
   itself (the design doc calls this out as the single biggest payoff of the
   abstraction). Drives tests that simulate users / conversations / events /
   history / reactions with no external platform.

7. **Tests** — unit tests against `MockChatAdapter` and adapter-level
   normalization tests (mock the SDK clients; do NOT hit live Slack/Discord).
   Integration tests against a Slack sandbox / Discord test server are a
   follow-up, not part of this task.

## Explicitly OUT of scope (later tasks)

- Synchronization engine + local persistence (SQLite/Postgres), event store,
  conversation cache, incremental sync.
- Summarization pipeline, embeddings / vector store, conversation replay.
- The **Conversation Runtime** (task workspaces, participant state) and **Agent
  Runtime** (prompts, tool execution, orchestration).
- All aitasks integration: mapping tasks ↔ conversations/threads, gates ↔
  reactions/approvals, monitor/shadow ↔ chat, board, notifications, multi-agent
  (planner/main/shadow/reviewer) routing.
- Credential storage/secrets management policy (note the requirement — tokens
  must never be persisted inside domain entities — but the full credential
  subsystem is later).
- Choice of "one shared thread vs separate threads per agent" orchestration.

## Open questions for planning

- **Module location / packaging.** It is deliberately decoupled and
  non-aitasks-specific. Candidates: a self-contained package under
  `.aitask-scripts/lib/` (e.g. `chat/` or `chatlib/`) vs a top-level
  standalone package. Decide where, and how it declares its third-party deps
  (`slack_bolt`, `slack_sdk`, `discord.py`) given the framework's current
  Python dependency story.
- **Ship both adapters at once, or land the interface + `MockChatAdapter` +
  one real adapter first** (Discord adapters are simpler per the design doc;
  Slack apps are richer)? Likely a child-task split:
  (1) domain model + `ChatAdapter` + capabilities + errors + `MockChatAdapter`,
  (2) Discord adapter, (3) Slack adapter — pull tests early per child
  (testability-first).
- **Two-layer vs monolithic.** The design doc suggests eventually splitting
  "Messaging Transport" from "Conversation Runtime"; confirm this task stays at
  the Messaging Transport / `ChatAdapter` level and does not creep upward.

## Acceptance criteria

- A self-contained, `asyncio`-based Python module exposing the domain model,
  the `ChatAdapter` interface, capability-discovery methods, and the normalized
  error taxonomy — with no aitasks-specific concepts.
- Working Slack (Socket Mode) and Discord (Gateway) adapters implementing
  `ChatAdapter`, each translating platform objects/events into the normalized
  model and platform errors into the normalized taxonomy.
- A `MockChatAdapter` sufficient to unit-test higher layers without any external
  platform.
- Unit tests (mock-adapter + adapter-normalization) pass; no live-platform calls
  in the test suite.
- No leakage of Slack/Discord types above the adapter boundary (verified by the
  interface surface and tests).
