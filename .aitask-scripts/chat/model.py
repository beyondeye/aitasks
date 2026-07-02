"""model — platform-agnostic domain model for the chat abstraction layer.

Slice of the layer: the nouns. Pure dataclasses/enums normalizing the
overlapping-but-different object models of Slack (workspace/channel/thread_ts/
user/usergroup) and Discord (guild/channel/thread/member/role) into one
vocabulary that higher layers consume without knowing the platform
("abstract concepts, not APIs").

Purpose: everything above the adapter boundary speaks only these types.
Platform extras that do not generalize live in each entity's ``metadata``
dict (always the last field) and are never promoted into the shared schema.

Contract: zero third-party and zero framework imports (stdlib only); all
list/dict defaults use ``field(default_factory=...)`` so instances never
share mutable state.
"""
from __future__ import annotations

import enum
from dataclasses import dataclass, field

__all__ = [
    "Workspace",
    "ConversationKind",
    "ConversationRef",
    "Conversation",
    "MessageRef",
    "Message",
    "User",
    "ActorType",
    "Actor",
    "Role",
    "IdentityClaims",
    "Attachment",
    "Mention",
    "Reaction",
    "EventType",
    "Event",
    "Permission",
    "EphemeralPath",
    "EphemeralReceipt",
]


@dataclass
class Workspace:
    """The top-level container a bot is installed into.

    What it abstracts: a Slack workspace (team) / a Discord guild (server).

    Purpose: scopes every conversation and identity lookup; ``provider``
    names the backing platform so refs from different adapters never mix.
    Contract: ``id`` is the platform's native workspace/guild id, opaque to
    higher layers.
    """

    id: str
    name: str
    provider: str
    metadata: dict = field(default_factory=dict)


class ConversationKind(enum.Enum):
    """Normalized taxonomy of places a message can live.

    What it abstracts: Slack public/private channels, threads (``thread_ts``
    trees), IMs and MPIMs / Discord text channels, (standalone or
    message-anchored) threads, DMs and group DMs.

    Purpose: higher layers branch on the *kind* of conversation (e.g. "post
    status into the task thread", "DM the approver") instead of on platform
    channel types.
    """

    CHANNEL = "channel"
    THREAD = "thread"
    DIRECT = "direct"
    PRIVATE = "private"        # private channel / restricted group
    TEMPORARY = "temporary"    # short-lived venue (e.g. Discord temporary/auto-archiving thread channel)


@dataclass
class ConversationRef:
    """Opaque, serializable handle to a conversation.

    What it abstracts: Slack ``channel_id`` (+ ``thread_ts`` for threads) /
    Discord ``guild_id`` + ``channel_id`` (a Discord thread is itself a
    channel id, carried here in ``thread_id``).

    Purpose: the reconnect token of the whole layer — higher layers persist
    it and re-attach to existing work after a restart (thread recovery)
    without knowing the platform. Treat it as opaque: construct it only from
    adapter results or ``from_dict``.

    Contract: ``to_dict()`` → ``from_dict()`` round-trips every field
    (including ``thread_id`` and ``metadata``); equality compares
    ``provider``/``workspace_id``/``conversation_id``/``thread_id`` and
    ignores ``metadata`` (``compare=False``); a THREAD ref reconstructed
    from its dict is sufficient for ``fetch_history`` / ``subscribe``.
    """

    provider: str
    workspace_id: str
    conversation_id: str
    thread_id: str | None = None
    metadata: dict = field(default_factory=dict, compare=False)

    def to_dict(self) -> dict:
        """Serialize to a plain dict (JSON/YAML-safe if metadata is)."""
        return {
            "provider": self.provider,
            "workspace_id": self.workspace_id,
            "conversation_id": self.conversation_id,
            "thread_id": self.thread_id,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "ConversationRef":
        """Reconstruct a ref serialized by :meth:`to_dict` (round-trip)."""
        return cls(
            provider=d["provider"],
            workspace_id=d["workspace_id"],
            conversation_id=d["conversation_id"],
            thread_id=d.get("thread_id"),
            metadata=dict(d.get("metadata", {})),
        )


@dataclass
class Conversation:
    """A resolved conversation (channel, thread, DM, ...).

    What it abstracts: Slack ``conversations.info`` results / Discord
    channel & thread objects.

    Purpose: the full record behind a ``ConversationRef`` — what higher
    layers get back from discovery (``fetch_conversation`` /
    ``list_conversations``). Contract: ``ref`` is the canonical handle;
    ``name``/``topic`` may be ``None`` where the platform has no such
    concept (e.g. DMs).
    """

    ref: ConversationRef
    kind: ConversationKind
    name: str | None = None
    topic: str | None = None
    is_archived: bool = False
    metadata: dict = field(default_factory=dict)


@dataclass
class MessageRef:
    """Opaque, serializable handle to a single message.

    What it abstracts: Slack ``(channel, ts)`` / Discord
    ``(channel_id, message_id)``.

    Purpose: lets higher layers edit/delete/react-to/reply-to a message and
    anchor threads on it without holding the full ``Message``. Contract:
    equality compares ``conversation`` + ``message_id`` and ignores
    ``metadata`` (``compare=False``).
    """

    conversation: ConversationRef
    message_id: str
    metadata: dict = field(default_factory=dict, compare=False)


@dataclass
class Message:
    """A normalized chat message.

    What it abstracts: Slack message events/objects (incl. ``thread_ts``
    replies) / Discord message objects.

    Purpose: the single message shape higher layers read and render;
    streaming output is modeled as repeated ``edit_message`` on one of
    these (works on both platforms — no native-streaming assumption).
    Contract: ``timestamp`` is epoch seconds; ``reply_to`` carries the
    threaded-reply parent when the platform expresses one; ``reactions``
    reflect the state at fetch time (reconcile via ``fetch_reactions``).
    """

    ref: MessageRef
    author: Actor
    text: str
    timestamp: float
    attachments: list[Attachment] = field(default_factory=list)
    mentions: list[Mention] = field(default_factory=list)
    reactions: list[Reaction] = field(default_factory=list)
    reply_to: MessageRef | None = None
    edited: bool = False
    metadata: dict = field(default_factory=dict)


@dataclass
class User:
    """A normalized platform user profile.

    What it abstracts: Slack ``users.info`` profiles / Discord user &
    member objects.

    Purpose: the identity record behind an actor id — display fields for
    rendering plus ``is_bot`` for self/bot filtering. Contract: fields the
    platform does not expose (e.g. Discord has no email) stay ``None``
    rather than being faked.
    """

    id: str
    display_name: str
    username: str | None = None
    email: str | None = None
    avatar_url: str | None = None
    is_bot: bool = False
    metadata: dict = field(default_factory=dict)


class ActorType(enum.Enum):
    """Who (or what) performed an action.

    What it abstracts: Slack user vs ``bot_message`` subtypes vs system
    messages / Discord users vs bots vs webhook & system authors.

    Purpose: lets event consumers cheaply distinguish humans from bots from
    platform-generated notices — the first line of defense against
    self-trigger loops.
    """

    USER = "user"
    BOT = "bot"
    SYSTEM = "system"


@dataclass
class Actor:
    """The acting identity attached to events, messages and interactions.

    What it abstracts: the "who did this" field of Slack events (``user`` /
    ``bot_id``) and Discord events (author/member), unified.

    Purpose: a lightweight identity stamp (full profile via ``fetch_user``);
    ``is_self`` marks the adapter's own bot identity so consumers can drop
    their own echoes (self-trigger-loop protection). Contract: ``is_bot``
    is derived — true for BOT and SYSTEM actors.
    """

    id: str
    type: ActorType
    display_name: str | None = None
    is_self: bool = False
    metadata: dict = field(default_factory=dict)

    @property
    def is_bot(self) -> bool:
        """True when the actor is not a human user (BOT or SYSTEM)."""
        return self.type is not ActorType.USER


@dataclass
class Role:
    """A platform-native grouping a user belongs to.

    What it abstracts: a Discord guild role (``kind="discord_role"``) or a
    Slack usergroup (``kind="slack_usergroup"``) — deliberately NOT coerced
    into a pretend-common role model.

    Purpose: raw material for higher-layer authorization mapping; ``kind``
    keeps the platform provenance explicit so policy code never confuses a
    Slack usergroup with a Discord role. Contract: ``kind`` is one of the
    documented strings; new platforms add new kinds rather than overloading
    existing ones.
    """

    id: str
    name: str
    kind: str
    metadata: dict = field(default_factory=dict)


@dataclass
class IdentityClaims:
    """Platform-honest authorization claims for a user in a conversation.

    What it abstracts: Slack usergroup membership + workspace admin/owner
    flags + channel membership / Discord guild-role membership + channel
    visibility. Each platform fills only what it truly has.

    Purpose: the primitive an authorization layer maps to allowlists and
    gate-ownership — without touching SDK objects. This layer supplies the
    claims; policy (who may approve what) is explicitly higher-layer.
    Contract: absent knowledge defaults to ``False``/empty — a claim set
    never invents privileges the platform did not assert.
    """

    user_id: str
    roles: list[Role] = field(default_factory=list)
    is_workspace_admin: bool = False
    is_owner: bool = False
    is_channel_member: bool = False
    metadata: dict = field(default_factory=dict)


@dataclass
class Attachment:
    """A file attached to (or uploadable into) a conversation.

    What it abstracts: Slack file objects / Discord attachment objects.

    Purpose: a platform-neutral file handle — enough to list, render and
    ``download_attachment`` without platform URLs leaking meaning upward.
    Contract: ``size`` is bytes when known; ``url`` may require adapter-side
    auth to fetch (always download through the adapter, not raw HTTP).
    """

    id: str
    filename: str
    mime_type: str | None = None
    size: int | None = None
    url: str | None = None
    uploader: Actor | None = None
    metadata: dict = field(default_factory=dict)


@dataclass
class Mention:
    """A user mention inside a message.

    What it abstracts: Slack ``<@U123>`` tokens / Discord ``<@id>`` tokens,
    already resolved out of the raw text markup.

    Purpose: consumers react to "was I / this user mentioned" without
    parsing platform markup. Contract: ``user_id`` matches ``Actor.id`` /
    ``User.id`` space.
    """

    user_id: str
    display_name: str | None = None
    metadata: dict = field(default_factory=dict)


@dataclass
class Reaction:
    """An emoji reaction aggregate on a message.

    What it abstracts: Slack reactions (name + users) / Discord reactions
    (emoji + count + users).

    Purpose: reactions double as lightweight signals (ack/approve patterns),
    so the model carries who reacted, not just counts. Contract: ``emoji``
    is the platform's canonical emoji name/glyph; ``user_ids`` may be
    truncated by platform limits — ``fetch_reactions`` returns the current
    authoritative set.
    """

    emoji: str
    count: int = 0
    user_ids: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


class EventType(enum.Enum):
    """Normalized taxonomy of inbound events.

    What it abstracts: Slack Events API types (``message``, ``reaction_added``,
    ``app_mention``, ...) / Discord Gateway dispatches (``MESSAGE_CREATE``,
    ``MESSAGE_REACTION_ADD``, ``INTERACTION_CREATE``, ...), renamed into
    framework vocabulary.

    Purpose: one event language for every subscriber; platform events with
    no mapping arrive as ``UNKNOWN`` with the raw payload preserved instead
    of being silently dropped.
    """

    MESSAGE_CREATED = "message_created"
    MESSAGE_EDITED = "message_edited"
    MESSAGE_DELETED = "message_deleted"
    REACTION_ADDED = "reaction_added"
    REACTION_REMOVED = "reaction_removed"
    APP_MENTION = "app_mention"
    THREAD_CREATED = "thread_created"
    THREAD_DELETED = "thread_deleted"
    FILE_UPLOADED = "file_uploaded"
    USER_JOINED = "user_joined"
    USER_LEFT = "user_left"
    CHANNEL_CREATED = "channel_created"
    INTERACTION_RECEIVED = "interaction_received"
    UNKNOWN = "unknown"        # unmapped platform event; raw payload under payload["raw"]


@dataclass
class Event:
    """A normalized inbound event yielded by ``ChatAdapter.subscribe``.

    What it abstracts: one Slack Events API delivery / one Discord Gateway
    dispatch, after normalization.

    Purpose: the single push-channel from platform to higher layers.

    Contract — ``payload`` keys by ``type`` (enforced by ``MockChatAdapter``):
    MESSAGE_CREATED/MESSAGE_EDITED/APP_MENTION → ``{"message": Message}``;
    MESSAGE_DELETED → ``{"message_ref": MessageRef}``;
    REACTION_ADDED/REACTION_REMOVED → ``{"message_ref": MessageRef,
    "emoji": str}`` (the reacting actor is on ``Event.actor``);
    THREAD_CREATED/CHANNEL_CREATED → ``{"conversation": Conversation}``;
    THREAD_DELETED → ``{"conversation_ref": ConversationRef}``;
    FILE_UPLOADED → ``{"attachment": Attachment, "message_ref":
    MessageRef | None}``; USER_JOINED/USER_LEFT → ``{"user": User}``;
    INTERACTION_RECEIVED → ``{"interaction": Interaction}``;
    UNKNOWN → ``{"raw": <provider payload>}``.
    Delivery is at-least-once per active subscription while connected; see
    ``ChatAdapter.subscribe`` for the recovery contract.
    """

    id: str
    type: EventType
    timestamp: float
    actor: Actor | None = None
    conversation: ConversationRef | None = None
    payload: dict = field(default_factory=dict)
    metadata: dict = field(default_factory=dict)


@dataclass
class Permission:
    """A named permission — deliberately minimal at this layer.

    What it abstracts: nothing platform-specific yet — Slack scopes and
    Discord permission bits differ too much for a common enum, so this is a
    thin named handle (platform detail in ``metadata``).

    Purpose: a stable type for future permission plumbing without
    pretending the platforms share a permission model today.
    """

    name: str
    metadata: dict = field(default_factory=dict)


class EphemeralPath(enum.Enum):
    """Which private path delivered an ephemeral message.

    What it abstracts: Slack native ephemeral (``chat.postEphemeral``) or
    Discord interaction-response ephemeral flag (NATIVE) vs the DM fallback
    (DM).

    Purpose: makes ``send_ephemeral``'s fallback observable so higher
    layers can phrase follow-ups correctly ("see my DM" vs inline).
    """

    NATIVE = "native"
    DM = "dm"


@dataclass
class EphemeralReceipt:
    """Result of a private-only delivery (``ChatAdapter.send_ephemeral``).

    What it abstracts: the heterogeneous returns of Slack
    ``chat.postEphemeral`` (no message handle) vs a DM post (full message).

    Purpose: reports which private path was used and, when the platform
    returns one, the posted message. Contract: ``message`` may be ``None``
    (native ephemerals often yield no re-addressable handle).
    """

    path: EphemeralPath
    message: Message | None = None
    metadata: dict = field(default_factory=dict)
