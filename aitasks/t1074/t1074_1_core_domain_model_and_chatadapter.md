---
priority: medium
effort: high
depends: []
issue_type: feature
status: Implementing
labels: [chat_surface, python]
assigned_to: dario-e@beyond-eye.com
anchor: 1074
created_at: 2026-06-25 11:52
updated_at: 2026-07-02 14:36
---

## Context

First child of t1074. Delivers the **complete, frozen, platform-agnostic contract**
for a low-level chat (Slack/Discord) abstraction layer — the bottom of the planned
5-layer stack (`… → Messaging Runtime → Slack/Discord Adapter`). Guiding principle
from the design analysis: **abstract concepts, not APIs** — nothing above the
adapter boundary may know whether it is talking to Slack or Discord. **No
aitasks-specific concepts here** (no task/gate/monitor wiring). This child has
**zero third-party deps** and is fully unit-testable; the two adapter children
(t1074_2 Discord, t1074_3 Slack) implement against the surface this child freezes.

Parent plan (decomposition + full contract rationale, incl. the reviewed design
concerns): `aiplans/p1074_chat_adapter_abstraction_layer.md`. Child plan:
`aiplans/p1074/p1074_1_core_domain_model_and_chatadapter.md`.

## Key Files to Create

New self-contained package `.aitask-scripts/chat/` (parallels `applink/`, `monitor/`):
- `__init__.py` — public API exports; **must import no aitasks module** (guard-tested).
- `model.py` — domain dataclasses + enums (see Surface).
- `errors.py` — error taxonomy (see Surface).
- `interactions.py` — interaction surface (components/modals/commands/`Interaction`).
- `capabilities.py` — `Capabilities` dataclass.
- `adapter.py` — `ChatAdapter` ABC.
- `mock.py` — `MockChatAdapter` (in-memory, deterministic; implements the whole ABC).

New tests (bash wrappers sourcing `.aitask-scripts/lib/python_resolve.sh`):
- `tests/test_chat_model.sh`, `tests/test_chat_mock.sh`, `tests/test_chat_no_aitasks_import.sh`.

## Reference Files for Patterns

- Dataclass/enum style: `.aitask-scripts/monitor/monitor_core.py` (`PaneSnapshot`, `PaneCategory`).
- ABC + duck-typed seams, pure routing (no sockets): `.aitask-scripts/applink/router.py`.
- Bash test wrapper + graceful dep SKIP idiom: `tests/test_applink_router.sh`
  (sources `python_resolve.sh`, `PYTHON="$(require_ait_python)"`, `import yaml` → SKIP/exit 0,
  inline python heredoc with `sys.path` inserts).

## Surface (must be implemented in full by MockChatAdapter)

**model.py:** `Workspace`; `Conversation` (+`ConversationKind`: CHANNEL/THREAD/DIRECT/PRIVATE/TEMPORARY);
`ConversationRef` (opaque, serialize→reconstruct round-trip; carries provider thread id for threads);
`Message`, `MessageRef`; `User`; `Actor` (`ActorType` USER/BOT/SYSTEM, `is_bot`); `IdentityClaims`
(platform-honest: `roles: list[Role]` where `Role.kind` ∈ {discord_role, slack_usergroup},
`is_workspace_admin`, `is_owner`, `is_channel_member`, `metadata`); `Attachment`, `Mention`, `Reaction`;
`Event` (+`EventType`: MESSAGE_CREATED/MESSAGE_EDITED/MESSAGE_DELETED/REACTION_ADDED/REACTION_REMOVED/
APP_MENTION/THREAD_CREATED/THREAD_DELETED/FILE_UPLOADED/USER_JOINED/USER_LEFT/CHANNEL_CREATED/
INTERACTION_RECEIVED/UNKNOWN); `Role`, `Permission`. Every entity carries `metadata: dict`.

**errors.py:** `ChatError` base + `ConversationNotFound`, `PermissionDenied`, `RateLimited`,
`AttachmentTooLarge`, `UserNotFound`, `DeliveryFailed`, `InteractionExpired`.

**interactions.py:** outbound `Button`, `SelectMenu`, `ActionRow`, `Modal`/`Form` (fields),
`SlashCommand` spec; inbound `Interaction` (subtype BUTTON/SELECT/MODAL_SUBMIT/COMMAND) carrying
originating `Actor`, source conversation/message, submitted values.

**capabilities.py:** `Capabilities` dataclass — `supports_buttons/selects/modals/slash_commands/
reactions/files/ephemeral/dm/voice/editing/thread_creation/standalone_threads/message_search`,
`max_message_length`, `max_attachment_bytes`.

**adapter.py — `ChatAdapter` ABC (async):**
- Messaging: `send_message(conversation, text, *, attachments=None, components=None, reply_to=None)`,
  `edit_message`, `delete_message`, `fetch_message`,
  `send_ephemeral(conversation, actor, text, *, components=None)`.
- Conversations/threads: `create_conversation(kind, *, parent=None, name=None, ...)`
  (kind=THREAD requires `parent`: MessageRef → message-anchored thread both platforms;
  channel ConversationRef → Discord standalone thread, Slack raises, gated by
  `supports_standalone_threads`), `archive_conversation`, `fetch_history` (owns pagination/cursor),
  `fetch_participants`.
- Discovery: `fetch_conversation(ref)` (resolve/existence → `ConversationNotFound`),
  `list_conversations(*, kinds=None)`, `get_permalink(ref)`.
- Identity: `fetch_user(user_ref)`, `fetch_identity_claims(conversation, user_ref) -> IdentityClaims`.
- Reconciliation: `fetch_reactions(message_ref)` (current reaction set, for diff-recovery).
- Files/reactions: `upload_attachment`, `download_attachment`, `add_reaction`, `remove_reaction`.
- Interactions: `register_commands(specs)`, `ack(interaction)` (idempotent), `respond(interaction, …,
  *, ephemeral=False)`, `follow_up(interaction, …)`, `open_modal(interaction, modal)`.
- Events: `subscribe(*, conversations=None, since=None)` async-iterates `Event`s.
- Capabilities: `capabilities() -> Capabilities`.

## Contract semantics (document in code + enforce in Mock)

- **Thread recovery:** a THREAD `ConversationRef` round-trips and suffices for
  `fetch_history` / `subscribe`.
- **Interaction ack:** adapters auto-defer/ack an interaction on receipt **before**
  yielding it; the yielded `Interaction` is already acked; consumer responds via
  `respond`/`follow_up`; `ack` idempotent; past-window → `InteractionExpired`.
  (Mock simulates: interactions arrive pre-acked.)
- **Ephemeral private-only fallback:** native ephemeral → DM → `DeliveryFailed`;
  **never** posts publicly. Return value reports the private path used.
- **Subscription recovery:** at-least-once while connected, no replay on disconnect.
  Recoverable by re-query: messages (`fetch_history(after=)`/`fetch_message`),
  reaction state (`fetch_reactions` diff), existence (`fetch_conversation`).
  **NOT replayable:** `INTERACTION_RECEIVED` — document that higher layers must
  persist interaction outcomes on receipt and re-prompt if missed.

## Implementation Plan (high level — see child plan for detail)

1. Scaffold the `chat/` package + `__init__.py` exports (no aitasks imports).
2. Implement `model.py`, `errors.py`, `interactions.py`, `capabilities.py` (pure data).
3. Implement `adapter.py` `ChatAdapter` ABC with the methods + docstringed contract above.
4. Implement `MockChatAdapter` covering the **entire** ABC + the four contract
   semantics, deterministically (synthetic event stream, in-memory stores).
5. Write the three bash test wrappers.

## Verification

```bash
bash tests/test_chat_model.sh && \
bash tests/test_chat_mock.sh && \
bash tests/test_chat_no_aitasks_import.sh
```
All PASS on the stock framework venv with **no new dependencies installed**.
Tests cover: entity construction + `ConversationRef`/THREAD round-trip + enum coverage;
full Mock lifecycle (send/edit/delete/fetch/history pagination/react/subscribe);
thread lifecycle + recovery; interactions + auto-defer + `InteractionExpired`;
identity + `IdentityClaims`; discovery (`ConversationNotFound`/permalink/list);
ephemeral private-only fallback (native→DM→`DeliveryFailed`, never public);
subscription scoping + `fetch_reactions` diff-reconciliation + non-replayable interactions;
`Capabilities` values; and the no-aitasks-import guard.
