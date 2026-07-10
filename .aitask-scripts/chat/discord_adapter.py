"""discord_adapter — ``DiscordAdapter``: the ``ChatAdapter`` contract on Discord.

Slice of the layer: the first real platform adapter. Implements the frozen
``ChatAdapter`` ABC against ``discord.py`` (persistent Gateway connection,
bot token) with zero business logic — translate / authenticate / normalize
only. Nothing above the boundary may learn it is talking to Discord.

Structure (testability contract, t1074_2):

- **Module-level pure functions** do every platform→domain and
  domain→payload mapping. They take duck-typed objects (anything with the
  right attributes — real discord.py models or ``SimpleNamespace`` stubs)
  and import nothing from the SDK, so they unit-test on the stock venv.
- **``DiscordAdapter``** composes those functions around a duck-typed
  ``client`` passed to the constructor. The SDK is imported lazily and only
  inside :meth:`DiscordAdapter.connect` (the real-Gateway entry point) and
  the default ``sdk`` seam — constructing the adapter with fakes never
  imports ``discord``.
- **Ack ownership (amended contract):** interactions are yielded
  ``_acked=True`` with the ack *scheduled*: a defer task fires at
  ``DEFER_DELAY_SECONDS`` (2.0 s, inside Discord's 3 s window) unless the
  consumer's ``respond``/``open_modal`` becomes the initial response first.
  After the defer has fired the modal window is closed
  (``InteractionExpired``) — see ``Interaction``'s amended docstring.

Not exported from ``chat/__init__`` (the package surface is pinned
stdlib-only); import as ``from chat.discord_adapter import DiscordAdapter``.
Install the SDK tier with ``ait setup --with-chat``.
"""
from __future__ import annotations

import asyncio
import time
import uuid
from collections.abc import AsyncIterator
from io import BytesIO

from ._subscription import (  # shared hub (t1074_3); re-exported for tests
    _DISCONNECT,
    _ref_key,
    _Subscriber,
    _SubscriptionHub,
    SUBSCRIBER_QUEUE_MAXSIZE,
)
from .adapter import ChatAdapter
from .capabilities import Capabilities
from .errors import (
    AttachmentTooLarge,
    ChatError,
    ConversationNotFound,
    DeliveryFailed,
    InteractionExpired,
    PermissionDenied,
    RateLimited,
    UserNotFound,
)
from .interactions import (
    ActionRow,
    Button,
    Interaction,
    InteractionType,
    Modal,
    SelectMenu,
    SlashCommand,
)
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
    Mention,
    Message,
    MessageRef,
    Reaction,
    Role,
    User,
)

__all__ = ["DiscordAdapter"]

PROVIDER = "discord"

# Sentinel workspace id for guildless (DM/group) conversations. Discord DM
# permalinks really use this literal path segment (discord.com/channels/@me/…),
# and ConversationRef.workspace_id is a required field — so the DM fallback
# path yields valid refs and URLs instead of inventing a fake guild id.
DM_WORKSPACE = "@me"

# Scheduled-ack delay: safely inside Discord's 3 s interaction-ack deadline
# while leaving consumers a real window to make open_modal / respond the
# initial response (see the amended _acked contract).
DEFER_DELAY_SECONDS = 2.0

# Discord component/command wire constants (raw API payloads).
_BUTTON_STYLES = {"primary": 1, "secondary": 2, "success": 3, "danger": 4, "link": 5}
_COMMAND_OPTION_TYPES = {"string": 3, "integer": 4, "boolean": 5, "number": 10}
_BASE_MAX_ATTACHMENT_BYTES = 8 * 1024 * 1024  # non-boost tier; see capabilities()


# ---------------------------------------------------------------------- #
# Pure normalization: platform → domain
# ---------------------------------------------------------------------- #

def build_permalink(workspace_id: str, channel_id: str, message_id: str | None = None) -> str:
    """Build a Discord permalink — DM-safe.

    Guild refs → ``https://discord.com/channels/<guild>/<channel>[/<message>]``;
    guildless refs (``workspace_id`` empty/None/``@me``) use the literal
    ``@me`` segment Discord itself uses for DM links.
    """
    ws = workspace_id if workspace_id and workspace_id != DM_WORKSPACE else DM_WORKSPACE
    url = f"https://discord.com/channels/{ws}/{channel_id}"
    return f"{url}/{message_id}" if message_id else url


def user_to_domain(obj) -> User:
    """Normalize a discord user/member-shaped object to :class:`User`."""
    display = (
        getattr(obj, "display_name", None)
        or getattr(obj, "global_name", None)
        or getattr(obj, "name", None)
        or str(getattr(obj, "id", ""))
    )
    avatar = getattr(obj, "display_avatar", None)
    avatar_url = str(getattr(avatar, "url", "")) or None if avatar is not None else None
    return User(
        id=str(getattr(obj, "id", "")),
        display_name=str(display),
        username=getattr(obj, "name", None),
        email=None,  # Discord never exposes emails to bots — stays None (honest)
        avatar_url=avatar_url,
        is_bot=bool(getattr(obj, "bot", False)),
    )


def actor_from_user(obj, *, self_id: str | None = None) -> Actor:
    """Normalize a discord user/member-shaped object to :class:`Actor`."""
    uid = str(getattr(obj, "id", ""))
    is_bot = bool(getattr(obj, "bot", False))
    return Actor(
        id=uid,
        type=ActorType.BOT if is_bot else ActorType.USER,
        display_name=getattr(obj, "display_name", None) or getattr(obj, "name", None),
        is_self=self_id is not None and uid == str(self_id),
    )


def member_to_claims(obj, *, is_channel_member: bool = False) -> IdentityClaims:
    """Normalize a guild member-shaped object to :class:`IdentityClaims`.

    Claims never invent privileges: anything the object does not expose is
    ``False``/empty. Roles map with ``kind="discord_role"``; the implicit
    ``@everyone`` role (``is_default``/name match) is skipped as noise.
    """
    roles = []
    for r in getattr(obj, "roles", None) or []:
        if getattr(r, "is_default", None) and callable(r.is_default) and r.is_default():
            continue
        if getattr(r, "name", "") == "@everyone":
            continue
        roles.append(Role(id=str(getattr(r, "id", "")), name=str(getattr(r, "name", "")), kind="discord_role"))
    perms = getattr(obj, "guild_permissions", None)
    is_admin = bool(getattr(perms, "administrator", False))
    guild = getattr(obj, "guild", None)
    owner_id = getattr(guild, "owner_id", None)
    return IdentityClaims(
        user_id=str(getattr(obj, "id", "")),
        roles=roles,
        is_workspace_admin=is_admin,
        is_owner=owner_id is not None and str(owner_id) == str(getattr(obj, "id", "")),
        is_channel_member=bool(is_channel_member),
    )


def channel_kind(obj) -> ConversationKind:
    """Classify a discord channel-shaped object into :class:`ConversationKind`.

    DM-shaped (``recipient``/``recipients``, or no guild) → DIRECT;
    thread-shaped (has a truthy ``parent_id`` inside a guild) → THREAD;
    everything else → CHANNEL. Discord has no separate PRIVATE kind at this
    boundary (visibility is permission overwrites — platform extras belong
    in ``metadata``).
    """
    if getattr(obj, "recipient", None) is not None or getattr(obj, "recipients", None):
        return ConversationKind.DIRECT
    if getattr(obj, "guild", None) is None:
        return ConversationKind.DIRECT
    if getattr(obj, "parent_id", None):
        return ConversationKind.THREAD
    return ConversationKind.CHANNEL


def channel_to_ref(obj) -> ConversationRef:
    """Build the opaque :class:`ConversationRef` for a channel-shaped object.

    Threads carry the *parent channel* as ``conversation_id`` and the thread
    id as ``thread_id`` (thread recovery contract); guildless channels use
    the ``@me`` workspace sentinel.
    """
    guild = getattr(obj, "guild", None)
    workspace = str(getattr(guild, "id", "")) if guild is not None else DM_WORKSPACE
    if not workspace:
        workspace = DM_WORKSPACE
    kind = channel_kind(obj)
    if kind is ConversationKind.THREAD:
        return ConversationRef(
            provider=PROVIDER,
            workspace_id=workspace,
            conversation_id=str(getattr(obj, "parent_id", "")),
            thread_id=str(getattr(obj, "id", "")),
        )
    return ConversationRef(
        provider=PROVIDER,
        workspace_id=workspace,
        conversation_id=str(getattr(obj, "id", "")),
    )


def channel_to_conversation(obj) -> Conversation:
    """Normalize a channel/thread-shaped object to :class:`Conversation`."""
    return Conversation(
        ref=channel_to_ref(obj),
        kind=channel_kind(obj),
        name=getattr(obj, "name", None),
        topic=getattr(obj, "topic", None),
        is_archived=bool(getattr(obj, "archived", False)),
    )


def attachment_to_domain(obj, uploader: Actor | None = None) -> Attachment:
    """Normalize a discord attachment-shaped object to :class:`Attachment`."""
    return Attachment(
        id=str(getattr(obj, "id", "")),
        filename=str(getattr(obj, "filename", "")),
        mime_type=getattr(obj, "content_type", None),
        size=getattr(obj, "size", None),
        url=getattr(obj, "url", None),
        uploader=uploader,
    )


def reaction_to_domain(obj) -> Reaction:
    """Normalize a discord reaction-shaped object to :class:`Reaction`.

    ``emoji`` is the unicode emoji as-is or the ``<:name:id>`` form for
    custom emoji (``str()`` of the platform emoji object). User lists are
    only populated when actually fetched — the count is honest, the ``me``
    flag travels in ``metadata``.
    """
    return Reaction(
        emoji=str(getattr(obj, "emoji", "")),
        count=int(getattr(obj, "count", 0) or 0),
        metadata={"me": bool(getattr(obj, "me", False))},
    )


def message_to_domain(obj, *, self_id: str | None = None) -> Message:
    """Normalize a discord message-shaped object to :class:`Message`."""
    channel = getattr(obj, "channel", None)
    conv_ref = channel_to_ref(channel) if channel is not None else ConversationRef(
        provider=PROVIDER, workspace_id=DM_WORKSPACE, conversation_id=""
    )
    author = actor_from_user(getattr(obj, "author", None), self_id=self_id)
    created = getattr(obj, "created_at", None)
    timestamp = created.timestamp() if hasattr(created, "timestamp") else float(created or 0.0)

    reply_to = None
    reference = getattr(obj, "reference", None)
    if reference is not None and getattr(reference, "message_id", None):
        ref_ws = str(getattr(reference, "guild_id", "") or "") or DM_WORKSPACE
        reply_to = MessageRef(
            conversation=ConversationRef(
                provider=PROVIDER,
                workspace_id=ref_ws,
                conversation_id=str(getattr(reference, "channel_id", "")),
            ),
            message_id=str(reference.message_id),
        )

    return Message(
        ref=MessageRef(conversation=conv_ref, message_id=str(getattr(obj, "id", ""))),
        author=author,
        text=str(getattr(obj, "content", "") or ""),
        timestamp=timestamp,
        attachments=[attachment_to_domain(a, author) for a in getattr(obj, "attachments", None) or []],
        mentions=[
            Mention(user_id=str(getattr(m, "id", "")), display_name=getattr(m, "display_name", None) or getattr(m, "name", None))
            for m in getattr(obj, "mentions", None) or []
        ],
        reactions=[reaction_to_domain(r) for r in getattr(obj, "reactions", None) or []],
        reply_to=reply_to,
        edited=getattr(obj, "edited_at", None) is not None,
    )


def interaction_to_domain(obj, *, self_id: str | None = None) -> Interaction:
    """Normalize a discord interaction-shaped object to :class:`Interaction`.

    Subtype mapping: ``application_command`` → COMMAND (command name arrives
    in ``custom_id``, options in ``values``); ``modal_submit`` →
    MODAL_SUBMIT (field ``custom_id`` → submitted value); component
    interactions → SELECT (``values`` under ``"values"``) or BUTTON by the
    payload's ``component_type``.
    """
    data = getattr(obj, "data", None) or {}
    type_name = str(getattr(getattr(obj, "type", None), "name", getattr(obj, "type", "")))

    if type_name == "application_command":
        itype = InteractionType.COMMAND
        custom_id = data.get("name")
        values = {o.get("name"): o.get("value") for o in data.get("options", []) or []}
    elif type_name == "modal_submit":
        itype = InteractionType.MODAL_SUBMIT
        custom_id = data.get("custom_id")
        values = {}
        for row in data.get("components", []) or []:
            for comp in row.get("components", []) or []:
                if comp.get("custom_id") is not None:
                    values[comp["custom_id"]] = comp.get("value")
    else:  # component interaction
        component_type = data.get("component_type")
        custom_id = data.get("custom_id")
        if data.get("values") is not None or component_type in (3, 5, 6, 7, 8):
            itype = InteractionType.SELECT
            values = {"values": list(data.get("values", []) or [])}
        else:
            itype = InteractionType.BUTTON
            values = {}

    channel = getattr(obj, "channel", None)
    conv_ref = channel_to_ref(channel) if channel is not None else ConversationRef(
        provider=PROVIDER, workspace_id=DM_WORKSPACE, conversation_id=str(getattr(obj, "channel_id", "") or "")
    )
    message = getattr(obj, "message", None)
    message_ref = (
        MessageRef(conversation=conv_ref, message_id=str(getattr(message, "id", "")))
        if message is not None else None
    )
    return Interaction(
        id=str(getattr(obj, "id", "")),
        type=itype,
        actor=actor_from_user(getattr(obj, "user", None), self_id=self_id),
        conversation=conv_ref,
        message=message_ref,
        custom_id=custom_id,
        values=values,
    )


def event_to_domain(kind: str, obj, *, self_id: str | None = None, timestamp: float | None = None) -> Event:
    """Normalize one Gateway dispatch to a domain :class:`Event`.

    ``kind`` is the lowercase discord.py event name without the ``on_``
    prefix (``message``, ``message_edit``, ``message_delete``,
    ``raw_message_delete``, ``reaction_add``, ``reaction_remove``,
    ``thread_create``, ``thread_delete``, ``member_join``,
    ``member_remove``, ``guild_channel_create``, ``interaction``).
    Payload keys follow the ``Event`` contract table exactly. Unmapped
    kinds → UNKNOWN with the raw object under ``payload["raw"]``.
    FILE_UPLOADED is never emitted for Discord — files arrive as message
    attachments on MESSAGE_CREATED (platform-honest).

    APP_MENTION: a ``message`` whose mentions include ``self_id``.
    """
    ts = timestamp if timestamp is not None else time.time()
    eid = f"{PROVIDER}:{kind}:{getattr(obj, 'id', '') or uuid.uuid4().hex}"

    if kind in ("message", "message_edit"):
        msg = message_to_domain(obj, self_id=self_id)
        etype = EventType.MESSAGE_EDITED if kind == "message_edit" else EventType.MESSAGE_CREATED
        if kind == "message" and self_id is not None and any(
            m.user_id == str(self_id) for m in msg.mentions
        ):
            etype = EventType.APP_MENTION
        return Event(
            id=eid, type=etype, timestamp=msg.timestamp or ts,
            actor=msg.author, conversation=msg.ref.conversation,
            payload={"message": msg},
        )

    if kind in ("message_delete", "raw_message_delete"):
        if getattr(obj, "channel", None) is not None:  # cached Message object
            msg = message_to_domain(obj, self_id=self_id)
            ref = msg.ref
            conv = msg.ref.conversation
        else:  # raw payload: ids only
            conv = ConversationRef(
                provider=PROVIDER,
                workspace_id=str(getattr(obj, "guild_id", "") or "") or DM_WORKSPACE,
                conversation_id=str(getattr(obj, "channel_id", "")),
            )
            ref = MessageRef(conversation=conv, message_id=str(getattr(obj, "message_id", getattr(obj, "id", ""))))
        return Event(id=eid, type=EventType.MESSAGE_DELETED, timestamp=ts,
                     conversation=conv, payload={"message_ref": ref})

    if kind in ("reaction_add", "reaction_remove"):
        # discord.py delivers (reaction, user); callers pass the reaction obj
        # with `.message` and the acting user attached as `.user` (or a raw
        # event-shaped object with ids).
        message = getattr(obj, "message", None)
        if message is not None:
            conv = channel_to_ref(getattr(message, "channel", None)) if getattr(message, "channel", None) is not None else None
            ref = MessageRef(conversation=conv, message_id=str(getattr(message, "id", "")))
        else:
            conv = ConversationRef(
                provider=PROVIDER,
                workspace_id=str(getattr(obj, "guild_id", "") or "") or DM_WORKSPACE,
                conversation_id=str(getattr(obj, "channel_id", "")),
            )
            ref = MessageRef(conversation=conv, message_id=str(getattr(obj, "message_id", "")))
        actor_obj = getattr(obj, "user", None) or getattr(obj, "member", None)
        return Event(
            id=eid,
            type=EventType.REACTION_ADDED if kind == "reaction_add" else EventType.REACTION_REMOVED,
            timestamp=ts,
            actor=actor_from_user(actor_obj, self_id=self_id) if actor_obj is not None else None,
            conversation=conv,
            payload={"message_ref": ref, "emoji": str(getattr(obj, "emoji", ""))},
        )

    if kind == "thread_create":
        conv = channel_to_conversation(obj)
        return Event(id=eid, type=EventType.THREAD_CREATED, timestamp=ts,
                     conversation=conv.ref, payload={"conversation": conv})

    if kind == "thread_delete":
        ref = channel_to_ref(obj)
        return Event(id=eid, type=EventType.THREAD_DELETED, timestamp=ts,
                     conversation=ref, payload={"conversation_ref": ref})

    if kind == "guild_channel_create":
        conv = channel_to_conversation(obj)
        return Event(id=eid, type=EventType.CHANNEL_CREATED, timestamp=ts,
                     conversation=conv.ref, payload={"conversation": conv})

    if kind in ("member_join", "member_remove"):
        user = user_to_domain(obj)
        return Event(
            id=eid,
            type=EventType.USER_JOINED if kind == "member_join" else EventType.USER_LEFT,
            timestamp=ts,
            actor=actor_from_user(obj, self_id=self_id),
            payload={"user": user},
        )

    if kind == "interaction":
        domain = interaction_to_domain(obj, self_id=self_id)
        return Event(
            id=eid, type=EventType.INTERACTION_RECEIVED, timestamp=ts,
            actor=domain.actor, conversation=domain.conversation,
            payload={"interaction": domain},
        )

    return Event(id=eid, type=EventType.UNKNOWN, timestamp=ts, payload={"raw": obj})


# ---------------------------------------------------------------------- #
# Pure translation: domain → platform payloads
# ---------------------------------------------------------------------- #

def components_to_payload(components: list[ActionRow]) -> list[dict]:
    """Translate domain ActionRows to raw Discord component payload dicts."""
    rows = []
    for row in components or []:
        items = []
        for comp in row.components:
            if isinstance(comp, Button):
                items.append({
                    "type": 2,
                    "style": _BUTTON_STYLES.get(comp.style, _BUTTON_STYLES["primary"]),
                    "label": comp.label,
                    "custom_id": comp.custom_id,
                    "disabled": comp.disabled,
                })
            elif isinstance(comp, SelectMenu):
                items.append({
                    "type": 3,
                    "custom_id": comp.custom_id,
                    "options": [
                        {"label": o.label, "value": o.value,
                         **({"description": o.description} if o.description else {})}
                        for o in comp.options
                    ],
                    **({"placeholder": comp.placeholder} if comp.placeholder else {}),
                    "min_values": comp.min_values,
                    "max_values": comp.max_values,
                })
        rows.append({"type": 1, "components": items})
    return rows


def modal_to_payload(modal: Modal) -> dict:
    """Translate a domain Modal to a raw Discord modal payload dict.

    ``FormField.kind`` maps generically: ``"multiline"``/``"paragraph"`` →
    paragraph text input (style 2), anything else → short (style 1).
    """
    return {
        "custom_id": modal.custom_id,
        "title": modal.title,
        "components": [
            {
                "type": 1,
                "components": [{
                    "type": 4,
                    "custom_id": f.custom_id,
                    "label": f.label,
                    "style": 2 if f.kind in ("multiline", "paragraph") else 1,
                    "required": f.required,
                    **({"placeholder": f.placeholder} if f.placeholder else {}),
                }],
            }
            for f in modal.fields
        ],
    }


def commands_to_payload(specs: list[SlashCommand]) -> list[dict]:
    """Translate SlashCommand specs to the Discord bulk-upsert payload."""
    return [
        {
            "name": s.name,
            "description": s.description,
            "options": [
                {
                    "type": _COMMAND_OPTION_TYPES.get(o.kind, _COMMAND_OPTION_TYPES["string"]),
                    "name": o.name,
                    "description": o.description,
                    "required": o.required,
                }
                for o in s.options
            ],
        }
        for s in specs
    ]


def map_discord_error(exc: BaseException, *, target: str) -> ChatError:
    """Translate an SDK exception into the domain taxonomy — the single sink.

    ``target`` names what the failing operation was addressing —
    ``"conversation"`` | ``"message"`` | ``"user"`` | ``"attachment"`` —
    because a bare ``NotFound`` is ambiguous without it (a gone channel is
    ``ConversationNotFound``; a gone message is base ``ChatError``, the
    taxonomy has no MessageNotFound; a gone user is ``UserNotFound``).
    Matching is by exception class-name/attributes so this stays
    SDK-import-free (unit-tested with SimpleNamespace exceptions).
    """
    names = {c.__name__ for c in type(exc).__mro__}
    status = getattr(exc, "status", None)
    code = getattr(exc, "code", None)
    text = f"{type(exc).__name__}: {exc}"

    if "Forbidden" in names:
        return PermissionDenied(text)
    if "NotFound" in names or status == 404:
        if target == "conversation":
            return ConversationNotFound(text)
        if target == "user":
            return UserNotFound(text)
        return ChatError(text)  # message/attachment: no narrower taxonomy class
    if "RateLimited" in names or status == 429:
        return RateLimited(text)
    if status == 413 or code == 40005:
        return AttachmentTooLarge(text)
    return ChatError(text)


class _LiveInteraction:
    """Adapter-side state for one in-window interaction."""

    def __init__(self, native, domain: Interaction) -> None:
        self.native = native
        self.domain = domain
        self.defer_task: asyncio.Task | None = None
        self.deferred = False   # scheduled defer has fired
        self.responded = False  # an initial response (message or modal) was sent


# ---------------------------------------------------------------------- #
# The adapter
# ---------------------------------------------------------------------- #

class DiscordAdapter(ChatAdapter):
    """``ChatAdapter`` on Discord (discord.py, Gateway + REST).

    Construction: pass a duck-typed ``client`` (tests use fakes — no SDK
    import); production code uses :meth:`connect`, the only Gateway/SDK
    entry point. ``guild_id`` scopes slash-command registration (guild
    commands propagate instantly; ``None`` = global, up to ~1 h). ``sdk``
    overrides the lazily-imported ``discord`` module namespace (test seam
    for File/Object/ui construction).
    """

    def __init__(
        self,
        client,
        *,
        guild_id: str | None = None,
        self_id: str | None = None,
        defer_delay: float = DEFER_DELAY_SECONDS,
        sdk=None,
    ) -> None:
        self._client = client
        self._guild_id = guild_id
        self._self_id = self_id
        self._defer_delay = defer_delay
        self._sdk_override = sdk
        self._hub = _SubscriptionHub()
        self._live: dict[str, _LiveInteraction] = {}

    # ------------------------------------------------------------------ #
    # SDK seam + real-Gateway construction
    # ------------------------------------------------------------------ #

    def _sdk(self):
        """The ``discord`` module namespace — lazy import, injectable."""
        if self._sdk_override is not None:
            return self._sdk_override
        import discord  # lazy: only real SDK paths reach here
        self._sdk_override = discord
        return discord

    @classmethod
    async def connect(
        cls,
        token: str,
        *,
        guild_id: str | None = None,
        defer_delay: float = DEFER_DELAY_SECONDS,
    ) -> "DiscordAdapter":
        """Log in and start the Gateway; returns a ready adapter.

        The only place that imports/instantiates the real SDK client.
        Registers the required intents (guilds, messages + content,
        reactions, members, DMs — matching aidocs/chat/discord_bot_setup.md)
        and wires every Gateway dispatch into the subscription hub.
        """
        import discord  # lazy heavyweight import (pattern: applink/content.py)

        intents = discord.Intents.default()
        intents.members = True
        intents.message_content = True
        client = discord.Client(intents=intents)
        adapter = cls(client, guild_id=guild_id, defer_delay=defer_delay, sdk=discord)

        @client.event
        async def on_ready():  # pragma: no cover - live Gateway only
            adapter._self_id = str(client.user.id)

        @client.event
        async def on_message(message):  # pragma: no cover - live Gateway only
            adapter._publish("message", message)

        @client.event
        async def on_message_edit(_before, after):  # pragma: no cover
            adapter._publish("message_edit", after)

        @client.event
        async def on_raw_message_delete(payload):  # pragma: no cover
            adapter._publish("raw_message_delete", payload)

        @client.event
        async def on_reaction_add(reaction, user):  # pragma: no cover
            reaction.user = user
            adapter._publish("reaction_add", reaction)

        @client.event
        async def on_reaction_remove(reaction, user):  # pragma: no cover
            reaction.user = user
            adapter._publish("reaction_remove", reaction)

        @client.event
        async def on_thread_create(thread):  # pragma: no cover
            adapter._publish("thread_create", thread)

        @client.event
        async def on_thread_delete(thread):  # pragma: no cover
            adapter._publish("thread_delete", thread)

        @client.event
        async def on_guild_channel_create(channel):  # pragma: no cover
            adapter._publish("guild_channel_create", channel)

        @client.event
        async def on_member_join(member):  # pragma: no cover
            adapter._publish("member_join", member)

        @client.event
        async def on_member_remove(member):  # pragma: no cover
            adapter._publish("member_remove", member)

        @client.event
        async def on_interaction(interaction):  # pragma: no cover
            adapter._on_interaction(interaction)

        @client.event
        async def on_disconnect():  # pragma: no cover
            adapter._hub.disconnect_all()

        await client.login(token)
        asyncio.get_running_loop().create_task(client.connect(reconnect=True))
        await client.wait_until_ready()
        adapter._self_id = str(client.user.id)
        return adapter

    # ------------------------------------------------------------------ #
    # Event ingestion (called by Gateway handlers; tests call directly)
    # ------------------------------------------------------------------ #

    def _publish(self, kind: str, obj) -> None:
        """Normalize one dispatch and broadcast it to all subscribers."""
        self._hub.publish(event_to_domain(kind, obj, self_id=self._self_id))

    def _on_interaction(self, native) -> Interaction:
        """Ingest INTERACTION_CREATE: schedule the owned ack, then publish.

        The yielded/published Interaction carries ``_acked=True`` under the
        amended contract: the ack is *irrevocably scheduled* — the defer
        task fires at ``defer_delay`` unless a consumer response becomes
        the initial response first (which cancels it).
        """
        domain = interaction_to_domain(native, self_id=self._self_id)
        domain._acked = True
        live = _LiveInteraction(native, domain)
        self._live[domain.id] = live
        try:
            loop = asyncio.get_running_loop()
            live.defer_task = loop.create_task(self._defer_later(live))
        except RuntimeError:
            # No running loop (sync test harness): the scheduled-ack task is
            # the caller's responsibility via _defer_later(live) directly.
            pass
        # Publish the SAME ack-owned object — re-normalizing the native here
        # would hand subscribers a fresh Interaction with _acked=False,
        # violating the ack-ownership contract (post-review fix, t1074_2).
        self._hub.publish(Event(
            id=f"{PROVIDER}:interaction:{domain.id}",
            type=EventType.INTERACTION_RECEIVED,
            timestamp=time.time(),
            actor=domain.actor,
            conversation=domain.conversation,
            payload={"interaction": domain},
        ))
        return domain

    async def _defer_later(self, live: _LiveInteraction) -> None:
        """The scheduled ack: defer unless a response already landed."""
        await asyncio.sleep(self._defer_delay)
        if live.responded or live.deferred:
            return
        try:
            await live.native.response.defer()
        except Exception:  # noqa: BLE001 - a lost race with a response is fine
            pass
        live.deferred = True

    # ------------------------------------------------------------------ #
    # Internal resolution helpers
    # ------------------------------------------------------------------ #

    @staticmethod
    def _snowflake(value: str):
        """Best-effort numeric id (fakes may use non-numeric ids)."""
        return int(value) if isinstance(value, str) and value.isdigit() else value

    async def _resolve_channel(self, ref: ConversationRef):
        """Resolve a ref to the live channel/thread object.

        THE existence probe: raises ``ConversationNotFound`` (via the error
        sink) when the conversation is gone.
        """
        cid = self._snowflake(_ref_key(ref))
        channel = None
        get_channel = getattr(self._client, "get_channel", None)
        if callable(get_channel):
            channel = get_channel(cid)
        if channel is None:
            try:
                channel = await self._client.fetch_channel(cid)
            except Exception as exc:  # noqa: BLE001 - single mapped sink
                raise map_discord_error(exc, target="conversation") from exc
        if channel is None:
            raise ConversationNotFound(f"no such conversation: {_ref_key(ref)}")
        return channel

    async def _resolve_message(self, message: MessageRef):
        """Resolve a MessageRef to the live message object (two-step targets)."""
        channel = await self._resolve_channel(message.conversation)
        try:
            return await channel.fetch_message(self._snowflake(message.message_id))
        except Exception as exc:  # noqa: BLE001
            raise map_discord_error(exc, target="message") from exc

    def _components_view(self, components: list[ActionRow] | None):
        """Build the SDK view for outbound components (None-safe)."""
        if not components:
            return None
        return _build_view(self._sdk(), components)

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
        if attachments:
            # Platform gap, surfaced loudly: discord.py sends files as fresh
            # uploads, not by re-attaching existing handles — silently
            # dropping them would fake a partial send as success. Send the
            # text, then upload files via upload_attachment.
            raise ChatError(
                "Discord cannot attach existing file handles to a message; "
                "use upload_attachment for files"
            )
        channel = await self._resolve_channel(conversation)
        kwargs: dict = {}
        view = self._components_view(components)
        if view is not None:
            kwargs["view"] = view
        if reply_to is not None:
            kwargs["reference"] = _MessageReference(reply_to)
        try:
            sent = await channel.send(text, **kwargs)
        except Exception as exc:  # noqa: BLE001
            raise map_discord_error(exc, target="conversation") from exc
        return message_to_domain(sent, self_id=self._self_id)

    async def edit_message(
        self,
        message: MessageRef,
        text: str,
        *,
        components: list[ActionRow] | None = None,
    ) -> Message:
        native = await self._resolve_message(message)
        kwargs: dict = {"content": text}
        view = self._components_view(components)
        if view is not None:
            kwargs["view"] = view
        try:
            edited = await native.edit(**kwargs)
        except Exception as exc:  # noqa: BLE001
            raise map_discord_error(exc, target="message") from exc
        msg = message_to_domain(edited if edited is not None else native, self_id=self._self_id)
        if not msg.edited:
            # Discord reflects edited_at on the returned object; enforce the
            # contract even when a fake echoes the pre-edit shape.
            msg.edited = True
        return msg

    async def delete_message(self, message: MessageRef) -> None:
        native = await self._resolve_message(message)
        try:
            await native.delete()
        except Exception as exc:  # noqa: BLE001
            raise map_discord_error(exc, target="message") from exc

    async def fetch_message(self, message: MessageRef) -> Message:
        native = await self._resolve_message(message)
        return message_to_domain(native, self_id=self._self_id)

    async def send_ephemeral(
        self,
        conversation: ConversationRef,
        actor: Actor,
        text: str,
        *,
        components: list[ActionRow] | None = None,
    ) -> EphemeralReceipt:
        """Private-only fallback chain: native (live interaction) → DM →
        ``DeliveryFailed``. Nothing is ever posted publicly."""
        view = self._components_view(components)

        # Native path: a live interaction from this actor in this conversation
        # (Discord's ephemeral flag only exists on interaction responses;
        # follow-up ephemerals work after the scheduled defer too).
        live = self._find_live(actor, conversation)
        if live is not None:
            try:
                kwargs: dict = {"ephemeral": True}
                if view is not None:
                    kwargs["view"] = view
                sent = await live.native.followup.send(text, **kwargs)
                live.responded = True
                msg = message_to_domain(sent, self_id=self._self_id) if sent is not None else None
                return EphemeralReceipt(path=EphemeralPath.NATIVE, message=msg)
            except Exception:  # noqa: BLE001 - fall through to DM (never public)
                pass

        # DM fallback.
        try:
            user = await self._fetch_native_user(actor.id)
            kwargs = {}
            if view is not None:
                kwargs["view"] = view
            sent = await user.send(text, **kwargs)
            msg = message_to_domain(sent, self_id=self._self_id) if sent is not None else None
            return EphemeralReceipt(path=EphemeralPath.DM, message=msg)
        except ChatError as exc:
            raise DeliveryFailed(f"no private path to actor {actor.id}: {exc}") from exc
        except Exception as exc:  # noqa: BLE001 - closed DMs etc.
            raise DeliveryFailed(f"no private path to actor {actor.id}: {exc}") from exc

    def _find_live(self, actor: Actor, conversation: ConversationRef) -> _LiveInteraction | None:
        for live in self._live.values():
            if live.domain.actor.id == actor.id and _ref_key(live.domain.conversation) == _ref_key(conversation):
                return live
        return None

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
        if kind is ConversationKind.THREAD:
            if parent is None:
                raise ValueError("kind=THREAD requires parent")
            if isinstance(parent, MessageRef):
                native_msg = await self._resolve_message(parent)
                try:
                    thread = await native_msg.create_thread(name=name or "thread")
                except Exception as exc:  # noqa: BLE001
                    raise map_discord_error(exc, target="conversation") from exc
            else:
                channel = await self._resolve_channel(parent)
                try:
                    # Standalone thread (supports_standalone_threads=True).
                    thread = await channel.create_thread(name=name or "thread")
                except Exception as exc:  # noqa: BLE001
                    raise map_discord_error(exc, target="conversation") from exc
            conv = channel_to_conversation(thread)
            self._publish("thread_create", thread)
            return conv

        if kind is ConversationKind.DIRECT:
            if not participants:
                raise ValueError("kind=DIRECT requires participants")
            user = await self._fetch_native_user(participants[0])
            try:
                dm = await user.create_dm()
            except Exception as exc:  # noqa: BLE001
                raise map_discord_error(exc, target="user") from exc
            return channel_to_conversation(dm)

        if kind is ConversationKind.CHANNEL:
            guild = self._require_guild()
            try:
                channel = await guild.create_text_channel(name or "channel")
            except Exception as exc:  # noqa: BLE001
                raise map_discord_error(exc, target="conversation") from exc
            conv = channel_to_conversation(channel)
            self._publish("guild_channel_create", channel)
            return conv

        raise PermissionDenied(f"Discord adapter cannot create {kind.value} conversations")

    def _require_guild(self):
        if self._guild_id is None:
            raise ChatError("no guild_id configured on this adapter")
        guild = None
        get_guild = getattr(self._client, "get_guild", None)
        if callable(get_guild):
            guild = get_guild(self._snowflake(self._guild_id))
        if guild is None:
            raise ConversationNotFound(f"guild {self._guild_id} not available")
        return guild

    async def archive_conversation(self, conversation: ConversationRef) -> None:
        channel = await self._resolve_channel(conversation)
        try:
            if hasattr(channel, "edit"):
                if conversation.thread_id or getattr(channel, "parent_id", None):
                    await channel.edit(archived=True)
                else:
                    # Channels have no archive on Discord: closest semantics
                    # is locking sends (documented platform gap).
                    await channel.edit(locked=True)
        except Exception as exc:  # noqa: BLE001
            raise map_discord_error(exc, target="conversation") from exc

    async def fetch_history(
        self,
        conversation: ConversationRef,
        *,
        before: MessageRef | None = None,
        after: MessageRef | None = None,
        limit: int = 100,
    ) -> list[Message]:
        channel = await self._resolve_channel(conversation)
        kwargs: dict = {"limit": limit}
        if before is not None:
            kwargs["before"] = _Snowflake(self._snowflake(before.message_id))
        if after is not None:
            kwargs["after"] = _Snowflake(self._snowflake(after.message_id))
        out: list[Message] = []
        try:
            async for native in channel.history(**kwargs):
                out.append(message_to_domain(native, self_id=self._self_id))
        except Exception as exc:  # noqa: BLE001
            raise map_discord_error(exc, target="conversation") from exc
        # Contract: chronological order. discord.py yields newest-first by
        # default; oldest_first flips server-side but fakes may not honor it,
        # so sort deterministically here.
        out.sort(key=lambda m: m.timestamp)
        return out

    async def fetch_participants(self, conversation: ConversationRef) -> list[User]:
        channel = await self._resolve_channel(conversation)
        members = getattr(channel, "members", None)
        if members is None and hasattr(channel, "fetch_members"):
            try:
                members = [m async for m in channel.fetch_members()]
            except TypeError:
                members = await channel.fetch_members()
            except Exception as exc:  # noqa: BLE001
                raise map_discord_error(exc, target="conversation") from exc
        return [user_to_domain(m) for m in members or []]

    # ------------------------------------------------------------------ #
    # Discovery
    # ------------------------------------------------------------------ #

    async def fetch_conversation(self, ref: ConversationRef) -> Conversation:
        channel = await self._resolve_channel(ref)
        return channel_to_conversation(channel)

    async def list_conversations(
        self, *, kinds: list[ConversationKind] | None = None
    ) -> list[Conversation]:
        out: list[Conversation] = []
        guilds = getattr(self._client, "guilds", None) or []
        for guild in guilds:
            for channel in getattr(guild, "text_channels", None) or []:
                out.append(channel_to_conversation(channel))
            for thread in getattr(guild, "threads", None) or []:
                out.append(channel_to_conversation(thread))
        for dm in getattr(self._client, "private_channels", None) or []:
            out.append(channel_to_conversation(dm))
        if kinds is not None:
            wanted = set(kinds)
            out = [c for c in out if c.kind in wanted]
        return out

    async def get_permalink(self, ref: ConversationRef | MessageRef) -> str:
        if isinstance(ref, MessageRef):
            conv = ref.conversation
            return build_permalink(conv.workspace_id, _ref_key(conv), ref.message_id)
        return build_permalink(ref.workspace_id, _ref_key(ref))

    # ------------------------------------------------------------------ #
    # Identity
    # ------------------------------------------------------------------ #

    async def _fetch_native_user(self, user_id: str):
        uid = self._snowflake(user_id)
        user = None
        get_user = getattr(self._client, "get_user", None)
        if callable(get_user):
            user = get_user(uid)
        if user is None:
            try:
                user = await self._client.fetch_user(uid)
            except Exception as exc:  # noqa: BLE001
                raise map_discord_error(exc, target="user") from exc
        if user is None:
            raise UserNotFound(f"no such user: {user_id}")
        return user

    async def fetch_user(self, user_id: str) -> User:
        return user_to_domain(await self._fetch_native_user(user_id))

    async def fetch_identity_claims(
        self, conversation: ConversationRef, user_id: str
    ) -> IdentityClaims:
        channel = await self._resolve_channel(conversation)
        guild = getattr(channel, "guild", None)
        if guild is None:
            # DM context: no roles/admin flags exist — honest minimal claims.
            user = await self._fetch_native_user(user_id)
            return IdentityClaims(user_id=str(getattr(user, "id", user_id)), is_channel_member=True)
        uid = self._snowflake(user_id)
        member = None
        get_member = getattr(guild, "get_member", None)
        if callable(get_member):
            member = get_member(uid)
        if member is None:
            try:
                member = await guild.fetch_member(uid)
            except Exception as exc:  # noqa: BLE001
                raise map_discord_error(exc, target="user") from exc
        is_member = False
        perms_for = getattr(channel, "permissions_for", None)
        if callable(perms_for):
            is_member = bool(getattr(perms_for(member), "view_channel", False))
        return member_to_claims(member, is_channel_member=is_member)

    # ------------------------------------------------------------------ #
    # Reconciliation
    # ------------------------------------------------------------------ #

    async def fetch_reactions(self, message: MessageRef) -> list[Reaction]:
        native = await self._resolve_message(message)
        return [reaction_to_domain(r) for r in getattr(native, "reactions", None) or []]

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
        # Pre-check BEFORE any network call (construction-spy tested).
        if len(content) > self.capabilities().max_attachment_bytes:
            raise AttachmentTooLarge(
                f"{filename}: {len(content)} bytes exceeds "
                f"{self.capabilities().max_attachment_bytes}"
            )
        channel = await self._resolve_channel(conversation)
        file = self._sdk().File(BytesIO(content), filename=filename)
        try:
            sent = await channel.send(file=file)
        except Exception as exc:  # noqa: BLE001
            raise map_discord_error(exc, target="attachment") from exc
        natives = getattr(sent, "attachments", None) or []
        if natives:
            att = attachment_to_domain(natives[0], actor_from_user(getattr(sent, "author", None), self_id=self._self_id))
        else:  # platform yielded no handle — synthesize the minimum honest one
            att = Attachment(id=str(getattr(sent, "id", "")), filename=filename, size=len(content))
        if att.mime_type is None:
            att.mime_type = mime_type
        return att

    async def download_attachment(self, attachment: Attachment) -> bytes:
        if attachment.url is None:
            raise ChatError(f"attachment {attachment.id} has no URL")
        # Discord CDN URLs are signed/expiring; fetch through the client's
        # HTTP session so auth stays below the boundary.
        http = getattr(self._client, "http", None)
        session = getattr(http, "_HTTPClient__session", None) or getattr(http, "session", None)
        if session is None:
            raise ChatError("client has no HTTP session to download with")
        try:
            async with session.get(attachment.url) as resp:
                if getattr(resp, "status", 200) == 404:
                    raise ChatError(f"attachment blob gone: {attachment.url}")
                return await resp.read()
        except ChatError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise map_discord_error(exc, target="attachment") from exc

    async def add_reaction(self, message: MessageRef, emoji: str) -> None:
        native = await self._resolve_message(message)
        try:
            await native.add_reaction(emoji)
        except Exception as exc:  # noqa: BLE001
            raise map_discord_error(exc, target="message") from exc

    async def remove_reaction(self, message: MessageRef, emoji: str) -> None:
        native = await self._resolve_message(message)
        try:
            await native.remove_reaction(emoji, _SelfSentinel(self._self_id))
        except Exception as exc:  # noqa: BLE001
            raise map_discord_error(exc, target="message") from exc

    # ------------------------------------------------------------------ #
    # Interactions
    # ------------------------------------------------------------------ #

    async def register_commands(self, specs: list[SlashCommand]) -> None:
        """Declarative bulk-overwrite sync (idempotent convergence).

        Guild-scoped when the adapter has a ``guild_id`` (instant
        propagation — the recommended mode); global otherwise (Discord may
        take up to ~1 h to propagate). Requires the ``applications.commands``
        OAuth scope on the bot invite.
        """
        payload = commands_to_payload(specs)
        http = getattr(self._client, "http", None)
        app_id = getattr(self._client, "application_id", None)
        if http is None or app_id is None:
            raise ChatError("client is not ready for command registration")
        try:
            if self._guild_id is not None:
                await http.bulk_upsert_guild_commands(app_id, self._snowflake(self._guild_id), payload)
            else:
                await http.bulk_upsert_global_commands(app_id, payload)
        except Exception as exc:  # noqa: BLE001
            raise map_discord_error(exc, target="conversation") from exc

    async def ack(self, interaction: Interaction) -> None:
        """Idempotent no-op: the ack deadline is adapter-owned (scheduled
        defer) — see the amended ``_acked`` contract."""
        interaction._acked = True

    async def respond(
        self,
        interaction: Interaction,
        text: str,
        *,
        components: list[ActionRow] | None = None,
        ephemeral: bool = False,
    ) -> Message | None:
        live = self._live.get(interaction.id)
        if live is None:
            raise InteractionExpired(f"interaction {interaction.id} is past its window")
        view = self._components_view(components)
        try:
            if not live.deferred and not live.responded:
                # Beat the scheduled defer: this becomes the initial response.
                self._cancel_defer(live)
                kwargs: dict = {"ephemeral": ephemeral}
                if view is not None:
                    kwargs["view"] = view
                await live.native.response.send_message(text, **kwargs)
                live.responded = True
                original = getattr(live.native, "original_response", None)
                if callable(original):
                    try:
                        sent = await original()
                        return message_to_domain(sent, self_id=self._self_id) if sent is not None else None
                    except Exception:  # noqa: BLE001 - no re-addressable handle
                        return None
                return None
            # Already deferred/responded: follow-up webhook.
            kwargs = {"ephemeral": ephemeral}
            if view is not None:
                kwargs["view"] = view
            sent = await live.native.followup.send(text, **kwargs)
            live.responded = True
            return message_to_domain(sent, self_id=self._self_id) if sent is not None else None
        except (ChatError,):
            raise
        except Exception as exc:  # noqa: BLE001 - past-window etc.
            raise InteractionExpired(f"interaction {interaction.id}: {exc}") from exc

    async def follow_up(
        self,
        interaction: Interaction,
        text: str,
        *,
        components: list[ActionRow] | None = None,
        ephemeral: bool = False,
    ) -> Message | None:
        live = self._live.get(interaction.id)
        if live is None:
            raise InteractionExpired(f"interaction {interaction.id} is past its window")
        view = self._components_view(components)
        kwargs: dict = {"ephemeral": ephemeral}
        if view is not None:
            kwargs["view"] = view
        try:
            sent = await live.native.followup.send(text, **kwargs)
        except Exception as exc:  # noqa: BLE001
            raise InteractionExpired(f"interaction {interaction.id}: {exc}") from exc
        return message_to_domain(sent, self_id=self._self_id) if sent is not None else None

    async def open_modal(self, interaction: Interaction, modal: Modal) -> None:
        """Open a modal — must beat the scheduled defer (amended contract:
        the modal window closes when the owned ack fires)."""
        live = self._live.get(interaction.id)
        if live is None:
            raise InteractionExpired(f"interaction {interaction.id} is past its window")
        if live.deferred or live.responded:
            raise InteractionExpired(
                f"interaction {interaction.id}: modal window closed "
                "(initial response already sent — open modals promptly after receipt)"
            )
        if interaction.type is InteractionType.MODAL_SUBMIT:
            raise InteractionExpired("a MODAL_SUBMIT interaction cannot open another modal")
        self._cancel_defer(live)
        try:
            await live.native.response.send_modal(_build_modal(self._sdk(), modal))
        except Exception as exc:  # noqa: BLE001
            raise InteractionExpired(f"interaction {interaction.id}: {exc}") from exc
        live.responded = True

    def _cancel_defer(self, live: _LiveInteraction) -> None:
        if live.defer_task is not None and not live.defer_task.done():
            live.defer_task.cancel()

    # ------------------------------------------------------------------ #
    # Events
    # ------------------------------------------------------------------ #

    async def subscribe(
        self,
        *,
        conversations: list[ConversationRef] | None = None,
        since: float | None = None,
    ) -> AsyncIterator[Event]:
        sub = _Subscriber(
            {_ref_key(r) for r in conversations} if conversations is not None else None,
            since,
        )
        self._hub.add(sub)
        try:
            while True:
                event = await sub.queue.get()
                if event is _DISCONNECT:
                    return
                yield event
        finally:
            self._hub.remove(sub)

    # ------------------------------------------------------------------ #
    # Capabilities
    # ------------------------------------------------------------------ #

    def capabilities(self) -> Capabilities:
        return Capabilities(
            supports_buttons=True,
            supports_selects=True,
            supports_modals=True,
            supports_slash_commands=True,
            supports_reactions=True,
            supports_files=True,
            supports_ephemeral=True,   # interaction context; DM fallback otherwise
            supports_dm=True,
            supports_voice=False,      # out of scope for this layer
            supports_editing=True,
            supports_thread_creation=True,
            supports_standalone_threads=True,
            supports_message_search=False,
            max_message_length=2000,
            max_attachment_bytes=_BASE_MAX_ATTACHMENT_BYTES,
            metadata={
                # Boost-tier servers raise the attachment cap (50/100 MiB);
                # the base non-boost limit is enforced (honest lower bound).
                "attachment_limit_note": "base tier; server boosts raise the platform cap",
            },
        )


# ---------------------------------------------------------------------- #
# SDK-namespace builders (take the module as a parameter → stub-testable)
# ---------------------------------------------------------------------- #

class _Snowflake:
    """Minimal id-holder accepted by discord.py wherever a Snowflake-like
    object (``.id``) is expected (history before/after, etc.)."""

    __slots__ = ("id",)

    def __init__(self, value) -> None:
        self.id = value


class _MessageReference:
    """Duck message-reference for channel.send(reference=…): discord.py
    accepts any object with message_id/channel_id/guild_id/fail_if_not_exists."""

    __slots__ = ("message_id", "channel_id", "guild_id", "fail_if_not_exists")

    def __init__(self, ref: MessageRef) -> None:
        self.message_id = int(ref.message_id) if ref.message_id.isdigit() else ref.message_id
        cid = ref.conversation.thread_id or ref.conversation.conversation_id
        self.channel_id = int(cid) if cid.isdigit() else cid
        ws = ref.conversation.workspace_id
        self.guild_id = int(ws) if ws.isdigit() else (None if ws == DM_WORKSPACE else ws)
        self.fail_if_not_exists = False

    def to_message_reference_dict(self) -> dict:  # discord.py duck hook
        out = {"message_id": self.message_id, "channel_id": self.channel_id,
               "fail_if_not_exists": self.fail_if_not_exists}
        if self.guild_id is not None:
            out["guild_id"] = self.guild_id
        return out


class _SelfSentinel:
    """Member-shaped stand-in for remove_reaction(emoji, member=self-bot)."""

    __slots__ = ("id",)

    def __init__(self, self_id: str | None) -> None:
        self.id = int(self_id) if self_id and self_id.isdigit() else self_id


def _build_view(sdk, components: list[ActionRow]):
    """Build an SDK ui.View from domain ActionRows.

    Takes the sdk namespace as a parameter (stub-testable: a fake sdk
    records the Button/Select constructions).
    """
    view = sdk.ui.View(timeout=None)
    for row_index, row in enumerate(components):
        for comp in row.components:
            if isinstance(comp, Button):
                item = sdk.ui.Button(
                    label=comp.label,
                    custom_id=comp.custom_id,
                    disabled=comp.disabled,
                    style=getattr(sdk.ButtonStyle, comp.style, sdk.ButtonStyle.primary),
                    row=row_index,
                )
            elif isinstance(comp, SelectMenu):
                item = sdk.ui.Select(
                    custom_id=comp.custom_id,
                    placeholder=comp.placeholder,
                    min_values=comp.min_values,
                    max_values=comp.max_values,
                    options=[
                        sdk.SelectOption(label=o.label, value=o.value, description=o.description)
                        for o in comp.options
                    ],
                    row=row_index,
                )
            else:  # pragma: no cover - ActionRow only holds Button|SelectMenu
                continue
            view.add_item(item)
    return view


def _build_modal(sdk, modal: Modal):
    """Build an SDK ui.Modal from a domain Modal (sdk-as-parameter seam)."""
    native = sdk.ui.Modal(title=modal.title, custom_id=modal.custom_id)
    for f in modal.fields:
        native.add_item(sdk.ui.TextInput(
            label=f.label,
            custom_id=f.custom_id,
            required=f.required,
            placeholder=f.placeholder,
            style=sdk.TextStyle.paragraph if f.kind in ("multiline", "paragraph") else sdk.TextStyle.short,
        ))
    return native
