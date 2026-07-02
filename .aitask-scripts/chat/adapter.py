"""adapter — the frozen ``ChatAdapter`` contract.

Slice of the layer: the verbs. One abstract, asyncio interface expressing
everything higher layers may ask of a chat platform — messaging, threads,
discovery, identity, files, reactions, interactions, events, capabilities —
as *capabilities, not REST endpoints* ("abstract concepts, not APIs").

Purpose: the single boundary between the framework and Slack/Discord.
Concrete adapters implement exactly this surface with zero business logic
(translate / authenticate / normalize only); nothing above it may know
which platform is speaking. The surface is FROZEN: adapters must not add
public methods — platform extras travel in ``metadata``; genuine gaps are
fixed by amending this ABC (and ``MockChatAdapter`` and the contract test)
here, never by diverging in an adapter.

Contract: stdlib-only. Every method is async except ``capabilities`` (static
data); ``subscribe`` is an async generator. All failures raise the
``errors`` taxonomy — SDK exception types never cross this boundary.
"""
from __future__ import annotations

import abc
from collections.abc import AsyncIterator

from .capabilities import Capabilities
from .interactions import ActionRow, Interaction, Modal, SlashCommand
from .model import (
    Actor,
    Attachment,
    Conversation,
    ConversationKind,
    ConversationRef,
    EphemeralReceipt,
    Event,
    IdentityClaims,
    Message,
    MessageRef,
    Reaction,
    User,
)

__all__ = ["ChatAdapter"]


class ChatAdapter(abc.ABC):
    """Abstract, platform-agnostic chat adapter (the frozen contract).

    What it abstracts: the Slack Web API + Socket Mode event stream, and the
    Discord REST + Gateway APIs, behind one asyncio interface.

    Purpose: everything above this boundary (messaging runtime, conversation
    runtime, agent runtime) is written once against this class and tested
    against ``MockChatAdapter``. Contract: see the module docstring; per-
    method contracts below. Credentials are adapter-construction concerns
    and are never persisted inside domain entities.
    """

    # ------------------------------------------------------------------ #
    # Messaging
    # ------------------------------------------------------------------ #

    @abc.abstractmethod
    async def send_message(
        self,
        conversation: ConversationRef,
        text: str,
        *,
        attachments: list[Attachment] | None = None,
        components: list[ActionRow] | None = None,
        reply_to: MessageRef | None = None,
    ) -> Message:
        """Post a message into a conversation.

        Abstracts Slack ``chat.postMessage`` / Discord channel ``send``.
        Purpose: the primary outbound primitive; posting into a THREAD ref
        posts into that thread, and ``reply_to`` on a channel ref expresses
        a threaded reply off the given message (Slack: parent ``thread_ts``;
        Discord: message reply). Contract: returns the posted ``Message``;
        raises ``ConversationNotFound`` for a dangling ref and
        ``PermissionDenied`` when the bot cannot post there.
        """

    @abc.abstractmethod
    async def edit_message(
        self,
        message: MessageRef,
        text: str,
        *,
        components: list[ActionRow] | None = None,
    ) -> Message:
        """Replace a message's text (and optionally its components).

        Abstracts Slack ``chat.update`` / Discord message ``edit``.
        Purpose: also the streaming primitive — progressive output is
        modeled as repeated edits of one message (works on both platforms).
        Contract: returns the updated ``Message`` with ``edited=True``;
        raises ``ConversationNotFound`` when the target is gone and
        ``PermissionDenied`` when editing another author's message.
        """

    @abc.abstractmethod
    async def delete_message(self, message: MessageRef) -> None:
        """Delete a message.

        Abstracts Slack ``chat.delete`` / Discord message ``delete``.
        Contract: idempotent from the caller's view is NOT guaranteed —
        deleting an already-deleted message may raise ``ChatError``;
        ``PermissionDenied`` when the bot may not delete it.
        """

    @abc.abstractmethod
    async def fetch_message(self, message: MessageRef) -> Message:
        """Fetch the current state of a single message.

        Abstracts Slack ``conversations.history``/``conversations.replies``
        point-lookup / Discord ``fetch_message``. Purpose: gap-recovery
        primitive — re-read a message after missed MESSAGE_EDITED events.
        Contract: raises ``ConversationNotFound`` when the conversation is
        gone; ``ChatError`` when the message itself no longer exists.
        """

    @abc.abstractmethod
    async def send_ephemeral(
        self,
        conversation: ConversationRef,
        actor: Actor,
        text: str,
        *,
        components: list[ActionRow] | None = None,
    ) -> EphemeralReceipt:
        """Deliver a message privately to one actor — never publicly.

        Abstracts Slack ``chat.postEphemeral`` / Discord's
        interaction-response ephemeral flag, with a DM fallback.
        Purpose: approval prompts, permission denials and validation errors
        must not leak workflow state into public channels.
        Contract (private-only fallback chain): native ephemeral when the
        context supports it → DM to ``actor`` → raise ``DeliveryFailed``.
        On the exhausted path NOTHING is posted publicly. Returns an
        ``EphemeralReceipt`` naming the private path used.
        """

    # ------------------------------------------------------------------ #
    # Conversations / threads
    # ------------------------------------------------------------------ #

    @abc.abstractmethod
    async def create_conversation(
        self,
        kind: ConversationKind,
        *,
        parent: MessageRef | ConversationRef | None = None,
        name: str | None = None,
        participants: list[str] | None = None,
    ) -> Conversation:
        """Create a conversation of the given kind.

        Abstracts Slack ``conversations.create``/``conversations.open`` and
        thread creation via first ``thread_ts`` reply / Discord channel and
        thread creation. Purpose: threads are the layer's central primitive
        (task → thread → discussion), so creation is first-class here.
        Contract: ``kind=THREAD`` REQUIRES ``parent`` — a ``MessageRef``
        anchors the thread on that message (both platforms); a channel
        ``ConversationRef`` creates a standalone thread (Discord only,
        gated by ``Capabilities.supports_standalone_threads``; unsupported
        platforms raise ``PermissionDenied``). ``kind=DIRECT`` requires
        ``participants`` (user ids). Emits THREAD_CREATED /
        CHANNEL_CREATED to subscribers.
        """

    @abc.abstractmethod
    async def archive_conversation(self, conversation: ConversationRef) -> None:
        """Archive (soft-close) a conversation.

        Abstracts Slack ``conversations.archive`` / Discord thread
        archiving (channels: closest available lock/archive semantics).
        Contract: the conversation remains fetchable with
        ``is_archived=True``; raises ``ConversationNotFound`` for a
        dangling ref.
        """

    @abc.abstractmethod
    async def fetch_history(
        self,
        conversation: ConversationRef,
        *,
        before: MessageRef | None = None,
        after: MessageRef | None = None,
        limit: int = 100,
    ) -> list[Message]:
        """Fetch messages from a conversation (adapter owns pagination).

        Abstracts Slack ``conversations.history``/``conversations.replies``
        cursors / Discord history iteration. Purpose: backfill and
        disconnect gap-recovery (``after=last_seen``); works on a THREAD
        ref reconstructed from storage (thread recovery). Contract:
        returns messages in chronological order, at most ``limit``; page
        backward with ``before=`` (older) and forward with ``after=``
        (newer); an empty list means the range is exhausted; raises
        ``ConversationNotFound`` for a dangling ref.
        """

    @abc.abstractmethod
    async def fetch_participants(self, conversation: ConversationRef) -> list[User]:
        """List the members of a conversation.

        Abstracts Slack ``conversations.members`` / Discord channel/thread
        member lists. Contract: raises ``ConversationNotFound`` for a
        dangling ref; large conversations may be truncated per platform
        limits (adapters document their bound in ``metadata``).
        """

    # ------------------------------------------------------------------ #
    # Discovery
    # ------------------------------------------------------------------ #

    @abc.abstractmethod
    async def fetch_conversation(self, ref: ConversationRef) -> Conversation:
        """Resolve a stored ref to its current ``Conversation``.

        Abstracts Slack ``conversations.info`` / Discord channel fetch.
        Purpose: THE existence check for reconnect flows — a persisted ref
        is probed here after restart. Contract: raises
        ``ConversationNotFound`` when the conversation no longer exists.
        """

    @abc.abstractmethod
    async def list_conversations(
        self, *, kinds: list[ConversationKind] | None = None
    ) -> list[Conversation]:
        """List conversations visible to the bot.

        Abstracts Slack ``conversations.list`` / Discord guild channel +
        thread enumeration. Contract: ``kinds=None`` lists all visible;
        otherwise filtered to the given kinds.
        """

    @abc.abstractmethod
    async def get_permalink(self, ref: ConversationRef | MessageRef) -> str:
        """Return a human-openable URL for a conversation or message.

        Abstracts Slack ``chat.getPermalink`` / Discord
        ``discord.com/channels/<guild>/<channel>[/<message>]`` URLs.
        Purpose: lets higher layers link chat artifacts from outside chat
        (task files, logs) without knowing URL schemes.
        """

    # ------------------------------------------------------------------ #
    # Identity
    # ------------------------------------------------------------------ #

    @abc.abstractmethod
    async def fetch_user(self, user_id: str) -> User:
        """Resolve a user id to a normalized ``User`` profile.

        Abstracts Slack ``users.info`` / Discord user/member fetch.
        Contract: raises ``UserNotFound`` for an unknown id; fields the
        platform does not expose stay ``None``.
        """

    @abc.abstractmethod
    async def fetch_identity_claims(
        self, conversation: ConversationRef, user_id: str
    ) -> IdentityClaims:
        """Fetch platform-honest authorization claims for a user in context.

        Abstracts Slack usergroup membership + admin/owner flags + channel
        membership / Discord guild roles + channel visibility. Purpose:
        the primitive an authorization layer maps to allowlists — policy
        itself is explicitly higher-layer. Contract: claims never invent
        privileges (absent knowledge → ``False``/empty); raises
        ``ConversationNotFound`` / ``UserNotFound`` accordingly.
        """

    # ------------------------------------------------------------------ #
    # Reconciliation
    # ------------------------------------------------------------------ #

    @abc.abstractmethod
    async def fetch_reactions(self, message: MessageRef) -> list[Reaction]:
        """Fetch the CURRENT reaction set of a message.

        Abstracts Slack ``reactions.get`` / Discord message reactions.
        Purpose: diff-based recovery for missed REACTION_ADDED/REMOVED
        events — consumers reconcile against last-known state instead of
        replaying events. Contract: authoritative at call time; raises
        ``ConversationNotFound`` / ``ChatError`` for dangling refs.
        """

    # ------------------------------------------------------------------ #
    # Files / reactions
    # ------------------------------------------------------------------ #

    @abc.abstractmethod
    async def upload_attachment(
        self,
        conversation: ConversationRef,
        filename: str,
        content: bytes,
        *,
        mime_type: str | None = None,
    ) -> Attachment:
        """Upload a file into a conversation.

        Abstracts Slack ``files.upload``(v2) / Discord file attachments.
        Contract: raises ``AttachmentTooLarge`` beyond
        ``Capabilities.max_attachment_bytes`` (or the platform's live
        refusal); returns the normalized ``Attachment`` handle.
        """

    @abc.abstractmethod
    async def download_attachment(self, attachment: Attachment) -> bytes:
        """Download an attachment's bytes through the adapter.

        Abstracts Slack authed file URLs (``url_private`` + bearer token) /
        Discord CDN URLs. Purpose: keeps auth details below the boundary —
        higher layers never fetch platform URLs directly. Contract: raises
        ``ChatError`` when the blob is gone.
        """

    @abc.abstractmethod
    async def add_reaction(self, message: MessageRef, emoji: str) -> None:
        """Add the bot's reaction to a message.

        Abstracts Slack ``reactions.add`` / Discord ``add_reaction``.
        Purpose: reactions double as cheap status signals (seen/ok/fail).
        Contract: adding an already-present reaction is a no-op; raises
        ``ConversationNotFound`` / ``PermissionDenied`` accordingly.
        """

    @abc.abstractmethod
    async def remove_reaction(self, message: MessageRef, emoji: str) -> None:
        """Remove the bot's reaction from a message.

        Abstracts Slack ``reactions.remove`` / Discord ``remove_reaction``.
        Contract: removing an absent reaction is a no-op; raise semantics
        as ``add_reaction``.
        """

    # ------------------------------------------------------------------ #
    # Interactions
    # ------------------------------------------------------------------ #

    @abc.abstractmethod
    async def register_commands(self, specs: list[SlashCommand]) -> None:
        """Register (or sync) the bot's slash commands.

        Abstracts Discord application-command registration / Slack slash
        commands (app-config-level — adapters document what can be
        automated; Slack may treat this as validation + no-op). Contract:
        idempotent — re-registering the same specs converges.
        """

    @abc.abstractmethod
    async def ack(self, interaction: Interaction) -> None:
        """Acknowledge an interaction — idempotent, normally a no-op.

        Abstracts Discord defer / Slack 200-ack. Purpose: the ~3 s platform
        ack deadline is handled by the ADAPTER, which auto-defers/acks every
        interaction before yielding it; consumers call this at most for
        explicitness. Contract: idempotent; never raises for an
        already-acked interaction.
        """

    @abc.abstractmethod
    async def respond(
        self,
        interaction: Interaction,
        text: str,
        *,
        components: list[ActionRow] | None = None,
        ephemeral: bool = False,
    ) -> Message | None:
        """Send the primary response to an interaction.

        Abstracts Discord follow-up webhook after defer / Slack
        ``response_url`` post. Purpose: consumers respond at their own pace
        (the ack already happened). Contract: ``ephemeral=True`` delivers
        privately to the interacting actor; returns the posted ``Message``
        or ``None`` when the platform yields no re-addressable handle;
        raises ``InteractionExpired`` past the follow-up window.
        """

    @abc.abstractmethod
    async def follow_up(
        self,
        interaction: Interaction,
        text: str,
        *,
        components: list[ActionRow] | None = None,
        ephemeral: bool = False,
    ) -> Message | None:
        """Send an additional response to an already-responded interaction.

        Abstracts Discord follow-up messages / subsequent Slack
        ``response_url`` posts. Contract: same return/raise semantics as
        ``respond``; may be called multiple times within the window.
        """

    @abc.abstractmethod
    async def open_modal(self, interaction: Interaction, modal: Modal) -> None:
        """Open a modal form in response to an interaction.

        Abstracts Discord modal responses / Slack ``views.open``. Purpose:
        the only rich-form entry point both platforms share — and both
        REQUIRE a live interaction as the trigger. Contract: the eventual
        submission arrives as a MODAL_SUBMIT ``Interaction``; raises
        ``InteractionExpired`` past the window.
        """

    # ------------------------------------------------------------------ #
    # Events
    # ------------------------------------------------------------------ #

    @abc.abstractmethod
    async def subscribe(
        self,
        *,
        conversations: list[ConversationRef] | None = None,
        since: float | None = None,
    ) -> AsyncIterator[Event]:
        """Async-iterate normalized inbound events.

        Abstracts the Slack Socket Mode stream / Discord Gateway dispatches.
        Purpose: the single push channel; each active ``subscribe`` iterator
        is an INDEPENDENT stream — concurrent subscribers each receive every
        matching event (no competition).

        Contract: ``conversations=None`` yields events for all visible
        conversations, otherwise filtered to the given refs (THREAD refs
        included; events without a conversation are delivered to all).
        Delivery is at-least-once per active subscription WHILE CONNECTED;
        there is NO replay across a disconnect. Recoverable by re-query:
        messages (``fetch_history(after=)`` / ``fetch_message``), reaction
        state (``fetch_reactions`` diff), existence (``fetch_conversation``).
        NOT replayable: INTERACTION_RECEIVED — higher layers must persist
        interaction outcomes on receipt and re-prompt if a window was
        missed. Adapters auto-reconnect their transport; ``since`` filters
        out events older than the given epoch timestamp.
        """
        # The unreachable yield marks this as an async-generator function so
        # implementations and the contract test agree on the method kind.
        if False:  # pragma: no cover
            yield  # type: ignore[unreachable]

    # ------------------------------------------------------------------ #
    # Capabilities
    # ------------------------------------------------------------------ #

    @abc.abstractmethod
    def capabilities(self) -> Capabilities:
        """Return this adapter's static feature flags and limits.

        Abstracts the Slack-vs-Discord feature matrix as data. Purpose:
        higher layers branch on capability, never on platform name.
        Contract: synchronous (static data); stable for the adapter
        instance's context.
        """
