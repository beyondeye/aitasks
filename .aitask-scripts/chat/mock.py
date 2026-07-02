"""mock — in-memory, deterministic ``ChatAdapter`` implementation.

Slice of the layer: the test double. Implements the ENTIRE frozen contract
(every ABC method plus the four contract semantics: thread recovery,
pre-acked interactions, private-only ephemeral fallback, and the
subscription/no-replay rules) against plain dict stores — no network, no
third-party deps, no wall clock.

Purpose: the single biggest payoff of the abstraction — higher layers (and
this layer's own tests) run against ``MockChatAdapter`` with simulated
users/conversations/events and zero external platform. Test-only seams
(``inject_*``, ``set_window_closed``, ``simulate_disconnect``,
``register_user``, ``set_identity_claims``) are deliberately NOT part of
``ChatAdapter`` — real adapters do not have them.

Determinism: ids come from a counter (``c1``, ``m1``, ``e1``, ...) and
timestamps from a logical clock that ticks by 1.0 — no ``time.time()`` — so
event order and refs are reproducible run-to-run.
"""
from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

from .adapter import ChatAdapter
from .capabilities import Capabilities
from .errors import (
    AttachmentTooLarge,
    ChatError,
    ConversationNotFound,
    DeliveryFailed,
    InteractionExpired,
    PermissionDenied,
    UserNotFound,
)
from .interactions import ActionRow, Interaction, Modal, SlashCommand
from .model import (
    Actor,
    ActorType,
    Attachment,
    Conversation,
    ConversationKind,
    ConversationRef,
    EphemeralPath,
    EphemeralReceipt,
    Event,
    EventType,
    IdentityClaims,
    Message,
    MessageRef,
    Reaction,
    User,
    Workspace,
)

__all__ = ["MockChatAdapter"]

# Sentinel pushed into subscriber queues by simulate_disconnect() to end
# every active subscribe() stream (no replay of anything after it).
_DISCONNECT = object()


class _Subscriber:
    """One active subscribe() stream: its own queue + optional filter keys."""

    __slots__ = ("queue", "keys")

    def __init__(self, keys: set[tuple] | None) -> None:
        self.queue: asyncio.Queue = asyncio.Queue()
        self.keys = keys


class MockChatAdapter(ChatAdapter):
    """Deterministic in-memory chat platform implementing ``ChatAdapter``.

    What it abstracts: a whole chat platform (both the API and the user
    population), simulated. Purpose: unit-test higher layers and the
    contract itself without Slack/Discord. Contract: behaviorally faithful
    to every semantic documented on ``ChatAdapter`` — including the ones a
    naive mock would shortcut (per-subscriber broadcast delivery,
    per-interaction expiry, never-post-publicly ephemeral fallback).

    Knobs (constructor): ``native_ephemeral`` / ``dm_enabled`` shape the
    ephemeral fallback chain; ``standalone_threads`` mimics Discord (True,
    default) or Slack (False → ``PermissionDenied``);
    ``max_attachment_bytes`` bounds uploads.
    """

    def __init__(
        self,
        *,
        provider: str = "mock",
        workspace_id: str = "W1",
        native_ephemeral: bool = True,
        dm_enabled: bool = True,
        standalone_threads: bool = True,
        max_attachment_bytes: int = 8 * 1024 * 1024,
    ) -> None:
        self.workspace = Workspace(id=workspace_id, name="Mock Workspace", provider=provider)
        self.bot_actor = Actor(id="B0", type=ActorType.BOT, display_name="mock-bot", is_self=True)
        self._provider = provider
        self._native_ephemeral = native_ephemeral
        self._dm_enabled = dm_enabled
        self._standalone_threads = standalone_threads
        self._max_attachment_bytes = max_attachment_bytes

        self._clock = 0.0
        self._id_counter = 0

        self._conversations: dict[tuple, Conversation] = {}
        self._participants: dict[tuple, list[str]] = {}
        self._messages: dict[tuple, list[Message]] = {}
        self._attachment_blobs: dict[str, bytes] = {}
        self._users: dict[str, User] = {}
        self._claims: dict[tuple, IdentityClaims] = {}
        self._subscribers: list[_Subscriber] = []
        self._closed_windows: set[str] = set()

        # Test-inspectable records (not part of the ChatAdapter surface).
        self.registered_commands: list[SlashCommand] = []
        self.opened_modals: list[tuple[Interaction, Modal]] = []
        self.ephemeral_messages: list[Message] = []

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #

    def _tick(self) -> float:
        self._clock += 1.0
        return self._clock

    def _next_id(self, prefix: str) -> str:
        self._id_counter += 1
        return f"{prefix}{self._id_counter}"

    @staticmethod
    def _key(ref: ConversationRef) -> tuple:
        return (ref.workspace_id, ref.conversation_id, ref.thread_id)

    def _ref(self, conversation_id: str, thread_id: str | None = None) -> ConversationRef:
        return ConversationRef(
            provider=self._provider,
            workspace_id=self.workspace.id,
            conversation_id=conversation_id,
            thread_id=thread_id,
        )

    def _require_conversation(self, ref: ConversationRef) -> Conversation:
        conv = self._conversations.get(self._key(ref))
        if conv is None:
            raise ConversationNotFound(f"no such conversation: {ref}")
        return conv

    def _find_message(self, message: MessageRef) -> tuple[list[Message], int, Message]:
        self._require_conversation(message.conversation)
        msgs = self._messages.get(self._key(message.conversation), [])
        for i, m in enumerate(msgs):
            if m.ref.message_id == message.message_id:
                return msgs, i, m
        raise ChatError(f"message not found: {message.message_id}")

    def _check_window(self, interaction: Interaction) -> None:
        if interaction.id in self._closed_windows:
            raise InteractionExpired(f"interaction {interaction.id} follow-up window closed")

    def _emit(
        self,
        type_: EventType,
        *,
        actor: Actor | None,
        conversation: ConversationRef | None,
        payload: dict,
    ) -> Event:
        event = Event(
            id=self._next_id("e"),
            type=type_,
            timestamp=self._tick(),
            actor=actor,
            conversation=conversation,
            payload=payload,
        )
        for sub in self._subscribers:
            if (
                sub.keys is None
                or event.conversation is None
                or self._key(event.conversation) in sub.keys
            ):
                sub.queue.put_nowait(event)
        return event

    def _store_message(
        self,
        conversation: ConversationRef,
        text: str,
        author: Actor,
        *,
        attachments: list[Attachment] | None = None,
        components: list[ActionRow] | None = None,
        reply_to: MessageRef | None = None,
    ) -> Message:
        conv = self._require_conversation(conversation)
        msg = Message(
            ref=MessageRef(conversation=conv.ref, message_id=self._next_id("m")),
            author=author,
            text=text,
            timestamp=self._tick(),
            attachments=list(attachments or []),
            reply_to=reply_to,
            metadata={"components": list(components)} if components else {},
        )
        self._messages.setdefault(self._key(conv.ref), []).append(msg)
        return msg

    # ------------------------------------------------------------------ #
    # Messaging
    # ------------------------------------------------------------------ #

    async def send_message(
        self,
        conversation: ConversationRef,
        text: str,
        *,
        attachments: list[Attachment] | None = None,
        components: list[ActionRow] | None = None,
        reply_to: MessageRef | None = None,
    ) -> Message:
        """See ``ChatAdapter.send_message`` (bot-authored; emits MESSAGE_CREATED)."""
        msg = self._store_message(
            conversation,
            text,
            self.bot_actor,
            attachments=attachments,
            components=components,
            reply_to=reply_to,
        )
        self._emit(
            EventType.MESSAGE_CREATED,
            actor=self.bot_actor,
            conversation=msg.ref.conversation,
            payload={"message": msg},
        )
        return msg

    async def edit_message(
        self,
        message: MessageRef,
        text: str,
        *,
        components: list[ActionRow] | None = None,
    ) -> Message:
        """See ``ChatAdapter.edit_message`` (emits MESSAGE_EDITED)."""
        _msgs, _i, msg = self._find_message(message)
        msg.text = text
        msg.edited = True
        if components is not None:
            msg.metadata["components"] = list(components)
        self._emit(
            EventType.MESSAGE_EDITED,
            actor=self.bot_actor,
            conversation=msg.ref.conversation,
            payload={"message": msg},
        )
        return msg

    async def delete_message(self, message: MessageRef) -> None:
        """See ``ChatAdapter.delete_message`` (emits MESSAGE_DELETED)."""
        msgs, i, msg = self._find_message(message)
        del msgs[i]
        self._emit(
            EventType.MESSAGE_DELETED,
            actor=self.bot_actor,
            conversation=msg.ref.conversation,
            payload={"message_ref": msg.ref},
        )

    async def fetch_message(self, message: MessageRef) -> Message:
        """See ``ChatAdapter.fetch_message``."""
        _msgs, _i, msg = self._find_message(message)
        return msg

    async def send_ephemeral(
        self,
        conversation: ConversationRef,
        actor: Actor,
        text: str,
        *,
        components: list[ActionRow] | None = None,
    ) -> EphemeralReceipt:
        """See ``ChatAdapter.send_ephemeral``.

        Fallback chain: native (knob ``native_ephemeral``) → DM (knob
        ``dm_enabled``) → ``DeliveryFailed``. The exhausted path touches no
        public store — verified by tests.
        """
        conv = self._require_conversation(conversation)
        if self._native_ephemeral:
            # Native ephemerals are visible only to the actor: recorded in
            # the test-inspectable list, never in the public message store.
            msg = Message(
                ref=MessageRef(conversation=conv.ref, message_id=self._next_id("m")),
                author=self.bot_actor,
                text=text,
                timestamp=self._tick(),
                metadata={"ephemeral_for": actor.id, **({"components": list(components)} if components else {})},
            )
            self.ephemeral_messages.append(msg)
            return EphemeralReceipt(path=EphemeralPath.NATIVE, message=msg)
        if self._dm_enabled:
            dm_ref = await self._ensure_dm(actor.id)
            msg = self._store_message(dm_ref, text, self.bot_actor, components=components)
            return EphemeralReceipt(path=EphemeralPath.DM, message=msg)
        raise DeliveryFailed(f"no private path to {actor.id}: native ephemeral and DM both unavailable")

    async def _ensure_dm(self, user_id: str) -> ConversationRef:
        """Get-or-create the DM conversation with a user (internal)."""
        ref = self._ref(f"D_{user_id}")
        if self._key(ref) not in self._conversations:
            self._conversations[self._key(ref)] = Conversation(ref=ref, kind=ConversationKind.DIRECT)
            self._participants[self._key(ref)] = [user_id, self.bot_actor.id]
        return ref

    # ------------------------------------------------------------------ #
    # Conversations / threads
    # ------------------------------------------------------------------ #

    async def create_conversation(
        self,
        kind: ConversationKind,
        *,
        parent: MessageRef | ConversationRef | None = None,
        name: str | None = None,
        participants: list[str] | None = None,
    ) -> Conversation:
        """See ``ChatAdapter.create_conversation``.

        Mock specifics: a missing required argument (THREAD without
        ``parent``, DIRECT without ``participants``) raises ``ValueError``
        (caller bug, not a platform failure); standalone threads honor the
        ``standalone_threads`` knob (False → ``PermissionDenied``, the
        Slack behavior).
        """
        if kind is ConversationKind.THREAD:
            if parent is None:
                raise ValueError("create_conversation(kind=THREAD) requires parent")
            if isinstance(parent, MessageRef):
                # Message-anchored thread (both platforms).
                self._find_message(parent)
                base = parent.conversation
            else:
                # Standalone channel-thread (Discord yes / Slack raises).
                if not self._standalone_threads:
                    raise PermissionDenied("standalone threads not supported by this platform")
                self._require_conversation(parent)
                base = parent
            ref = self._ref(base.conversation_id, thread_id=self._next_id("t"))
            conv = Conversation(ref=ref, kind=kind, name=name)
            self._conversations[self._key(ref)] = conv
            self._messages.setdefault(self._key(ref), [])
            self._emit(
                EventType.THREAD_CREATED,
                actor=self.bot_actor,
                conversation=ref,
                payload={"conversation": conv},
            )
            return conv

        if kind is ConversationKind.DIRECT:
            if not participants:
                raise ValueError("create_conversation(kind=DIRECT) requires participants")
            ref = self._ref(self._next_id("D"))
        else:
            ref = self._ref(self._next_id("C"))
        conv = Conversation(ref=ref, kind=kind, name=name)
        self._conversations[self._key(ref)] = conv
        self._participants[self._key(ref)] = list(participants or [])
        self._messages.setdefault(self._key(ref), [])
        if kind is not ConversationKind.DIRECT:
            self._emit(
                EventType.CHANNEL_CREATED,
                actor=self.bot_actor,
                conversation=ref,
                payload={"conversation": conv},
            )
        return conv

    async def archive_conversation(self, conversation: ConversationRef) -> None:
        """See ``ChatAdapter.archive_conversation``."""
        conv = self._require_conversation(conversation)
        conv.is_archived = True

    async def fetch_history(
        self,
        conversation: ConversationRef,
        *,
        before: MessageRef | None = None,
        after: MessageRef | None = None,
        limit: int = 100,
    ) -> list[Message]:
        """See ``ChatAdapter.fetch_history``.

        Without cursors returns the most recent ``limit`` messages (still
        chronological); ``after=`` pages forward, ``before=`` backward.
        """
        self._require_conversation(conversation)
        msgs = self._messages.get(self._key(conversation), [])
        if after is not None:
            idx = self._index_of(msgs, after)
            return msgs[idx + 1 : idx + 1 + limit]
        if before is not None:
            idx = self._index_of(msgs, before)
            older = msgs[:idx]
            return older[-limit:] if limit else []
        return msgs[-limit:] if limit else []

    @staticmethod
    def _index_of(msgs: list[Message], ref: MessageRef) -> int:
        for i, m in enumerate(msgs):
            if m.ref.message_id == ref.message_id:
                return i
        raise ChatError(f"cursor message not found: {ref.message_id}")

    async def fetch_participants(self, conversation: ConversationRef) -> list[User]:
        """See ``ChatAdapter.fetch_participants`` (registered users only)."""
        self._require_conversation(conversation)
        ids = self._participants.get(self._key(conversation), [])
        return [self._users[uid] for uid in ids if uid in self._users]

    # ------------------------------------------------------------------ #
    # Discovery
    # ------------------------------------------------------------------ #

    async def fetch_conversation(self, ref: ConversationRef) -> Conversation:
        """See ``ChatAdapter.fetch_conversation``."""
        return self._require_conversation(ref)

    async def list_conversations(
        self, *, kinds: list[ConversationKind] | None = None
    ) -> list[Conversation]:
        """See ``ChatAdapter.list_conversations``."""
        convs = list(self._conversations.values())
        if kinds is not None:
            wanted = set(kinds)
            convs = [c for c in convs if c.kind in wanted]
        return convs

    async def get_permalink(self, ref: ConversationRef | MessageRef) -> str:
        """See ``ChatAdapter.get_permalink`` (mock URL scheme)."""
        if isinstance(ref, MessageRef):
            conv = ref.conversation
            self._find_message(ref)
            tail = f"/{ref.message_id}"
        else:
            conv = ref
            self._require_conversation(conv)
            tail = ""
        thread = f"/{conv.thread_id}" if conv.thread_id else ""
        return f"https://mock.chat/{conv.workspace_id}/{conv.conversation_id}{thread}{tail}"

    # ------------------------------------------------------------------ #
    # Identity
    # ------------------------------------------------------------------ #

    async def fetch_user(self, user_id: str) -> User:
        """See ``ChatAdapter.fetch_user``."""
        user = self._users.get(user_id)
        if user is None:
            raise UserNotFound(f"no such user: {user_id}")
        return user

    async def fetch_identity_claims(
        self, conversation: ConversationRef, user_id: str
    ) -> IdentityClaims:
        """See ``ChatAdapter.fetch_identity_claims``.

        Returns claims installed via ``set_identity_claims`` or an
        all-defaults claim set (never invents privileges).
        """
        self._require_conversation(conversation)
        if user_id not in self._users:
            raise UserNotFound(f"no such user: {user_id}")
        claims = self._claims.get((self._key(conversation), user_id))
        return claims if claims is not None else IdentityClaims(user_id=user_id)

    # ------------------------------------------------------------------ #
    # Reconciliation
    # ------------------------------------------------------------------ #

    async def fetch_reactions(self, message: MessageRef) -> list[Reaction]:
        """See ``ChatAdapter.fetch_reactions`` (current authoritative set)."""
        _msgs, _i, msg = self._find_message(message)
        return list(msg.reactions)

    # ------------------------------------------------------------------ #
    # Files / reactions
    # ------------------------------------------------------------------ #

    async def upload_attachment(
        self,
        conversation: ConversationRef,
        filename: str,
        content: bytes,
        *,
        mime_type: str | None = None,
    ) -> Attachment:
        """See ``ChatAdapter.upload_attachment`` (emits FILE_UPLOADED)."""
        self._require_conversation(conversation)
        if len(content) > self._max_attachment_bytes:
            raise AttachmentTooLarge(
                f"{len(content)} bytes > limit {self._max_attachment_bytes}"
            )
        att_id = self._next_id("f")
        att = Attachment(
            id=att_id,
            filename=filename,
            mime_type=mime_type,
            size=len(content),
            url=f"mock://files/{att_id}",
            uploader=self.bot_actor,
        )
        self._attachment_blobs[att_id] = bytes(content)
        self._emit(
            EventType.FILE_UPLOADED,
            actor=self.bot_actor,
            conversation=conversation,
            payload={"attachment": att, "message_ref": None},
        )
        return att

    async def download_attachment(self, attachment: Attachment) -> bytes:
        """See ``ChatAdapter.download_attachment``."""
        blob = self._attachment_blobs.get(attachment.id)
        if blob is None:
            raise ChatError(f"attachment blob not found: {attachment.id}")
        return blob

    async def add_reaction(self, message: MessageRef, emoji: str) -> None:
        """See ``ChatAdapter.add_reaction`` (bot's reaction; emits REACTION_ADDED)."""
        self._apply_reaction(message, emoji, self.bot_actor, add=True)

    async def remove_reaction(self, message: MessageRef, emoji: str) -> None:
        """See ``ChatAdapter.remove_reaction`` (emits REACTION_REMOVED when present)."""
        self._apply_reaction(message, emoji, self.bot_actor, add=False)

    def _apply_reaction(self, message: MessageRef, emoji: str, actor: Actor, *, add: bool) -> None:
        _msgs, _i, msg = self._find_message(message)
        reaction = next((r for r in msg.reactions if r.emoji == emoji), None)
        if add:
            if reaction is None:
                reaction = Reaction(emoji=emoji)
                msg.reactions.append(reaction)
            if actor.id in reaction.user_ids:
                return  # no-op: already reacted
            reaction.user_ids.append(actor.id)
            reaction.count += 1
            event_type = EventType.REACTION_ADDED
        else:
            if reaction is None or actor.id not in reaction.user_ids:
                return  # no-op: nothing to remove
            reaction.user_ids.remove(actor.id)
            reaction.count -= 1
            if reaction.count <= 0:
                msg.reactions.remove(reaction)
            event_type = EventType.REACTION_REMOVED
        self._emit(
            event_type,
            actor=actor,
            conversation=msg.ref.conversation,
            payload={"message_ref": msg.ref, "emoji": emoji},
        )

    # ------------------------------------------------------------------ #
    # Interactions
    # ------------------------------------------------------------------ #

    async def register_commands(self, specs: list[SlashCommand]) -> None:
        """See ``ChatAdapter.register_commands`` (idempotent replace)."""
        self.registered_commands = list(specs)

    async def ack(self, interaction: Interaction) -> None:
        """See ``ChatAdapter.ack`` — idempotent (interactions arrive pre-acked)."""
        interaction._acked = True

    async def respond(
        self,
        interaction: Interaction,
        text: str,
        *,
        components: list[ActionRow] | None = None,
        ephemeral: bool = False,
    ) -> Message | None:
        """See ``ChatAdapter.respond`` (expiry per ``Interaction.id``)."""
        return await self._interaction_reply(interaction, text, components, ephemeral)

    async def follow_up(
        self,
        interaction: Interaction,
        text: str,
        *,
        components: list[ActionRow] | None = None,
        ephemeral: bool = False,
    ) -> Message | None:
        """See ``ChatAdapter.follow_up`` (same semantics as ``respond``)."""
        return await self._interaction_reply(interaction, text, components, ephemeral)

    async def _interaction_reply(
        self,
        interaction: Interaction,
        text: str,
        components: list[ActionRow] | None,
        ephemeral: bool,
    ) -> Message | None:
        self._check_window(interaction)
        if ephemeral:
            receipt = await self.send_ephemeral(
                interaction.conversation, interaction.actor, text, components=components
            )
            # Native ephemerals yield no re-addressable handle (see ABC).
            return receipt.message if receipt.path is EphemeralPath.DM else None
        return await self.send_message(interaction.conversation, text, components=components)

    async def open_modal(self, interaction: Interaction, modal: Modal) -> None:
        """See ``ChatAdapter.open_modal`` (records into ``opened_modals``)."""
        self._check_window(interaction)
        self.opened_modals.append((interaction, modal))

    # ------------------------------------------------------------------ #
    # Events
    # ------------------------------------------------------------------ #

    async def subscribe(
        self,
        *,
        conversations: list[ConversationRef] | None = None,
        since: float | None = None,
    ) -> AsyncIterator[Event]:
        """See ``ChatAdapter.subscribe``.

        Mock fidelity: each call registers its OWN queue (broadcast
        fan-out — concurrent subscribers never steal each other's events);
        the stream ends at ``simulate_disconnect()``; events emitted while
        this subscriber is not registered are never delivered to it
        (no buffering, no replay).
        """
        sub = _Subscriber(
            {self._key(r) for r in conversations} if conversations is not None else None
        )
        self._subscribers.append(sub)
        try:
            while True:
                event = await sub.queue.get()
                if event is _DISCONNECT:
                    return
                if since is not None and event.timestamp < since:
                    continue
                yield event
        finally:
            if sub in self._subscribers:
                self._subscribers.remove(sub)

    # ------------------------------------------------------------------ #
    # Capabilities
    # ------------------------------------------------------------------ #

    def capabilities(self) -> Capabilities:
        """See ``ChatAdapter.capabilities`` (reflects the constructor knobs)."""
        return Capabilities(
            supports_ephemeral=self._native_ephemeral,
            supports_dm=self._dm_enabled,
            supports_standalone_threads=self._standalone_threads,
            supports_message_search=False,
            max_message_length=4000,
            max_attachment_bytes=self._max_attachment_bytes,
        )

    # ------------------------------------------------------------------ #
    # Test-helper seams (NOT part of the ChatAdapter surface)
    # ------------------------------------------------------------------ #

    def register_user(self, user: User) -> None:
        """Install a user into the simulated platform directory."""
        self._users[user.id] = user

    def set_identity_claims(self, conversation: ConversationRef, claims: IdentityClaims) -> None:
        """Install the claims ``fetch_identity_claims`` returns for a user."""
        self._claims[(self._key(conversation), claims.user_id)] = claims

    def add_participant(self, conversation: ConversationRef, user_id: str) -> None:
        """Add a user id to a conversation's participant list."""
        self._require_conversation(conversation)
        self._participants.setdefault(self._key(conversation), []).append(user_id)

    def inject_message(
        self,
        conversation: ConversationRef,
        text: str,
        author: Actor,
        *,
        reply_to: MessageRef | None = None,
        mention_bot: bool = False,
    ) -> Message:
        """Simulate another actor posting a message (emits MESSAGE_CREATED,
        plus APP_MENTION when ``mention_bot=True``)."""
        msg = self._store_message(conversation, text, author, reply_to=reply_to)
        self._emit(
            EventType.MESSAGE_CREATED,
            actor=author,
            conversation=msg.ref.conversation,
            payload={"message": msg},
        )
        if mention_bot:
            self._emit(
                EventType.APP_MENTION,
                actor=author,
                conversation=msg.ref.conversation,
                payload={"message": msg},
            )
        return msg

    def inject_interaction(self, interaction: Interaction) -> Interaction:
        """Simulate a user gesture arriving from the platform.

        Faithful to the auto-defer contract: the interaction is marked
        acked BEFORE it is emitted/yielded (consumers never see an unacked
        interaction). Emits INTERACTION_RECEIVED.
        """
        interaction._acked = True
        self._emit(
            EventType.INTERACTION_RECEIVED,
            actor=interaction.actor,
            conversation=interaction.conversation,
            payload={"interaction": interaction},
        )
        return interaction

    def inject_reaction(self, message: MessageRef, emoji: str, actor: Actor) -> None:
        """Simulate another actor reacting (emits REACTION_ADDED)."""
        self._apply_reaction(message, emoji, actor, add=True)

    def set_window_closed(self, interaction_id: str) -> None:
        """Close ONE interaction's follow-up window (keyed by id — other
        live interactions stay responsive)."""
        self._closed_windows.add(interaction_id)

    def simulate_disconnect(self) -> None:
        """End every active ``subscribe`` stream (gateway drop).

        Events emitted afterwards are not buffered for the dropped
        subscribers — re-subscribing recovers state only via the re-query
        primitives, and missed INTERACTION_RECEIVED events are lost
        (the documented non-replayable case).
        """
        for sub in self._subscribers:
            sub.queue.put_nowait(_DISCONNECT)
