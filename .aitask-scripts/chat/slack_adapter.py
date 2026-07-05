"""slack_adapter — ``SlackAdapter``: the ``ChatAdapter`` contract on Slack.

Slice of the layer: the second real platform adapter. Implements the frozen
``ChatAdapter`` ABC against ``slack_bolt`` + ``slack_sdk`` in **Socket Mode**
(persistent outbound WebSocket — ``xoxb-`` bot token for the Web API,
``xapp-`` app-level token for the event stream; no public endpoint) with
zero business logic — translate / authenticate / normalize only. Nothing
above the boundary may learn it is talking to Slack.

Structure (testability contract, mirrors ``discord_adapter``):

- **Module-level pure functions** do every platform→domain and
  domain→payload mapping. Slack's API is JSON-native, so they take plain
  ``dict`` payloads (stubs are literal dicts) and import nothing from the
  SDK — they unit-test on the stock venv.
- **``SlackAdapter``** composes those functions around a duck-typed ``web``
  client (AsyncWebClient-shaped: snake_case Web API methods returning
  dict-shaped responses) passed to the constructor. The SDK is imported
  lazily and only inside :meth:`SlackAdapter.connect` (the real Socket Mode
  entry point) and the default ``sdk`` / ``http_get`` seams — constructing
  the adapter with fakes never imports ``slack_sdk`` or ``slack_bolt``.
- **Ack ownership (amended contract, instant-ack special case):** Slack's
  platform ack is the Socket Mode envelope ack — performed **on receipt,
  before the interaction is published** — so ``_acked=True`` means the ack
  has *already happened* (no delayed-defer scheduler; modals open via
  ``views.open`` within the ``trigger_id`` window, ~3 s).
- **Cursor pagination:** every paging Web API (``conversations.list`` /
  ``members`` / ``history`` / ``replies``) is driven through
  :meth:`SlackAdapter._paginate` — ``slack_sdk`` does not auto-paginate a
  single call, and one-page results silently truncate on real workspaces.

Not exported from ``chat/__init__`` (the package surface is pinned
stdlib-only); import as ``from chat.slack_adapter import SlackAdapter``.
Install the SDK tier with ``ait setup --with-chat``.
"""
from __future__ import annotations

import re
import time
import uuid
from collections.abc import AsyncIterator

from ._subscription import _DISCONNECT, _ref_key, _Subscriber, _SubscriptionHub
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

__all__ = ["SlackAdapter"]

PROVIDER = "slack"

# Slack limits (platform constants, not plan-dependent):
# chat.postMessage `text` accepts up to 40 000 characters (Block Kit section
# text is separately capped at 3 000 — noted in capabilities().metadata).
_MAX_MESSAGE_LENGTH = 40_000
# Per-file upload cap is 1 GiB platform-wide.
_MAX_ATTACHMENT_BYTES = 1024 * 1024 * 1024

# <@U012ABC> / <@U012ABC|display> mention tokens in message text.
_MENTION_RE = re.compile(r"<@([A-Z0-9]+)(?:\|[^>]*)?>")

# Slash-command name constraint (register_commands validation).
_COMMAND_NAME_RE = re.compile(r"^[a-z0-9_-]+$")

# map_slack_error string tables (see the mapper's docstring).
_ERR_CONV_GONE = {"channel_not_found", "thread_not_found", "is_archived"}
_ERR_MESSAGE_GONE = {"message_not_found", "file_not_found"}
_ERR_USER_GONE = {"user_not_found", "users_not_found"}
_ERR_PERMISSION = {
    "not_authed", "invalid_auth", "missing_scope", "not_in_channel",
    "user_not_in_channel", "no_permission", "restricted_action",
    "channel_not_allowed", "access_denied", "cant_update_message",
    "cant_delete_message",
}
_ERR_EXPIRED = {"expired_trigger_id", "trigger_expired"}


# ---------------------------------------------------------------------- #
# Pure helpers
# ---------------------------------------------------------------------- #

def ts_to_float(ts) -> float:
    """Slack ``ts`` string (``"1712345678.000200"``) → epoch-seconds float."""
    try:
        return float(ts)
    except (TypeError, ValueError):
        return 0.0


def _resp_data(resp) -> dict:
    """Response payload as a dict — accepts SlackResponse-shaped or plain dict."""
    data = getattr(resp, "data", None)
    if isinstance(data, dict):
        return data
    return resp if isinstance(resp, dict) else {}


def _error_string(exc: BaseException) -> str:
    """The Slack API ``error`` string carried by an exception, or ``""``."""
    resp = getattr(exc, "response", None)
    if resp is None:
        return ""
    get = getattr(resp, "get", None)
    if callable(get):
        return str(get("error") or "")
    try:
        return str(resp["error"])
    except Exception:  # noqa: BLE001 - duck access only
        return ""


# ---------------------------------------------------------------------- #
# Pure normalization: platform → domain
# ---------------------------------------------------------------------- #

def build_permalink(team_id: str, channel_id: str) -> str:
    """Conversation-level deep link (``slack.com/app_redirect``).

    Message permalinks come from ``chat.getPermalink`` (an API call —
    adapter-level); this pure form covers ``ConversationRef`` targets.
    """
    return f"https://slack.com/app_redirect?team={team_id}&channel={channel_id}"


def user_to_domain(d: dict) -> User:
    """Normalize a ``users.info`` user dict to :class:`User`.

    Fields Slack does not expose stay ``None`` — ``profile.email`` is only
    present with the ``users:read.email`` scope and is never invented.
    """
    profile = d.get("profile") or {}
    display = (
        profile.get("display_name")
        or profile.get("real_name")
        or d.get("real_name")
        or d.get("name")
        or str(d.get("id", ""))
    )
    return User(
        id=str(d.get("id", "")),
        display_name=str(display),
        username=d.get("name"),
        email=profile.get("email"),
        avatar_url=profile.get("image_512") or profile.get("image_192"),
        is_bot=bool(d.get("is_bot", False)),
    )


def actor_from_user(d: dict, *, self_id: str | None = None) -> Actor:
    """Normalize a user-shaped dict (or bare ``{"id": …}``) to :class:`Actor`."""
    uid = str(d.get("id", ""))
    is_bot = bool(d.get("is_bot", False))
    profile = d.get("profile") or {}
    return Actor(
        id=uid,
        type=ActorType.BOT if is_bot else ActorType.USER,
        display_name=profile.get("display_name") or d.get("real_name") or d.get("name"),
        is_self=self_id is not None and uid == str(self_id),
    )


def _actor_from_id(uid: str | None, *, self_id: str | None = None, bot: bool = False) -> Actor | None:
    """Actor from a bare user id (event envelopes carry ids, not profiles)."""
    if not uid:
        return None
    return Actor(
        id=str(uid),
        type=ActorType.BOT if bot else ActorType.USER,
        is_self=self_id is not None and str(uid) == str(self_id),
    )


def member_to_claims(
    user_info: dict,
    usergroups: list[dict],
    *,
    is_channel_member: bool = False,
) -> IdentityClaims:
    """Normalize users.info flags + usergroup memberships to :class:`IdentityClaims`.

    ``usergroups`` is the pre-filtered list of usergroup dicts the user
    belongs to (the adapter does the membership scan). Claims never invent
    privileges: anything absent is ``False``/empty. Roles map with
    ``kind="slack_usergroup"`` — deliberately NOT coerced into a common
    role model (platform-honest, per the ``IdentityClaims`` contract).
    """
    roles = [
        Role(id=str(g.get("id", "")), name=str(g.get("name", "")), kind="slack_usergroup")
        for g in usergroups or []
    ]
    return IdentityClaims(
        user_id=str(user_info.get("id", "")),
        roles=roles,
        is_workspace_admin=bool(user_info.get("is_admin", False)),
        is_owner=bool(user_info.get("is_owner", False)),
        is_channel_member=bool(is_channel_member),
    )


def conversation_kind(d: dict) -> ConversationKind:
    """Classify a ``conversations.info`` dict into :class:`ConversationKind`.

    ``is_im`` → DIRECT; ``is_mpim`` / ``is_group`` / ``is_private`` →
    PRIVATE; everything else → CHANNEL. TEMPORARY is unused on Slack
    (no platform concept at this boundary).
    """
    if d.get("is_im"):
        return ConversationKind.DIRECT
    if d.get("is_mpim") or d.get("is_group") or d.get("is_private"):
        return ConversationKind.PRIVATE
    return ConversationKind.CHANNEL


def channel_to_ref(d: dict, *, team_id: str) -> ConversationRef:
    """Build the opaque channel-level :class:`ConversationRef`.

    Threads are not ``conversations.*``-addressable objects on Slack —
    thread refs are built with :func:`thread_ref` where a ``thread_ts``
    exists.
    """
    return ConversationRef(
        provider=PROVIDER,
        workspace_id=str(team_id or ""),
        conversation_id=str(d.get("id", "")),
    )


def thread_ref(channel_id: str, thread_ts: str, *, team_id: str) -> ConversationRef:
    """Thread :class:`ConversationRef`: parent channel + ``thread_ts`` anchor."""
    return ConversationRef(
        provider=PROVIDER,
        workspace_id=str(team_id or ""),
        conversation_id=str(channel_id),
        thread_id=str(thread_ts),
    )


def channel_to_conversation(d: dict, *, team_id: str) -> Conversation:
    """Normalize a ``conversations.info`` dict to :class:`Conversation`."""
    topic = d.get("topic")
    return Conversation(
        ref=channel_to_ref(d, team_id=team_id),
        kind=conversation_kind(d),
        name=d.get("name"),
        topic=(topic or {}).get("value") if isinstance(topic, dict) else topic,
        is_archived=bool(d.get("is_archived", False)),
    )


def attachment_to_domain(d: dict, uploader: Actor | None = None) -> Attachment:
    """Normalize a Slack file dict to :class:`Attachment`.

    ``url`` is the authed ``url_private`` — downloadable only through
    :meth:`SlackAdapter.download_attachment` (bearer token stays below the
    boundary).
    """
    return Attachment(
        id=str(d.get("id", "")),
        filename=str(d.get("name", "") or ""),
        mime_type=d.get("mimetype"),
        size=d.get("size"),
        url=d.get("url_private"),
        uploader=uploader,
    )


def reaction_to_domain(d: dict) -> Reaction:
    """Normalize a ``reactions.get`` item to :class:`Reaction`.

    ``emoji`` is the Slack reaction name as-is (``"thumbsup"`` — no
    colons); ``user_ids`` carries only what the API actually returned
    (honest — Slack truncates long user lists, the count stays right).
    """
    return Reaction(
        emoji=str(d.get("name", "")),
        count=int(d.get("count", 0) or 0),
        user_ids=[str(u) for u in d.get("users") or []],
    )


def message_to_domain(
    d: dict,
    *,
    channel: str,
    team_id: str,
    self_id: str | None = None,
) -> Message:
    """Normalize a Slack message dict to :class:`Message`.

    ``ts`` doubles as the message id (Slack's addressing scheme). A message
    with ``thread_ts != ts`` lives *in* a thread → its ref conversation
    carries ``thread_id`` and ``reply_to`` points at the thread parent. A
    thread parent (``thread_ts == ts``) is a channel-level message.
    """
    ts = str(d.get("ts", ""))
    thread_ts = d.get("thread_ts")
    in_thread = bool(thread_ts) and str(thread_ts) != ts
    conv = (
        thread_ref(channel, str(thread_ts), team_id=team_id)
        if in_thread
        else ConversationRef(provider=PROVIDER, workspace_id=str(team_id or ""), conversation_id=str(channel))
    )
    reply_to = None
    if in_thread:
        reply_to = MessageRef(
            conversation=ConversationRef(
                provider=PROVIDER, workspace_id=str(team_id or ""), conversation_id=str(channel)
            ),
            message_id=str(thread_ts),
        )
    uid = d.get("user") or d.get("bot_id")
    author = _actor_from_id(uid, self_id=self_id, bot="bot_id" in d and not d.get("user")) or Actor(
        id="", type=ActorType.SYSTEM
    )
    text = str(d.get("text", "") or "")
    return Message(
        ref=MessageRef(conversation=conv, message_id=ts),
        author=author,
        text=text,
        timestamp=ts_to_float(ts),
        attachments=[attachment_to_domain(f, author) for f in d.get("files") or []],
        mentions=[Mention(user_id=m) for m in _MENTION_RE.findall(text)],
        reactions=[reaction_to_domain(r) for r in d.get("reactions") or []],
        reply_to=reply_to,
        edited="edited" in d,
    )


def event_to_domain(d: dict, *, team_id: str, self_id: str | None = None) -> Event:
    """Normalize one Socket Mode ``events_api`` event dict to :class:`Event`.

    Payload keys follow the ``Event`` contract table exactly. Unmapped
    types/subtypes → UNKNOWN with the raw dict under ``payload["raw"]``.

    APP_MENTION: a plain ``message`` whose text mentions ``self_id``
    (single-source — ``connect()`` registers the ``app_mention`` envelope
    ack-only, so one user action never publishes twice).

    THREAD_CREATED is never emitted from the stream — Slack threads exist
    implicitly with the first reply; ``create_conversation(THREAD, …)``
    emits it synthetically.
    """
    etype_name = str(d.get("type", ""))
    subtype = d.get("subtype")
    event_ts = d.get("event_ts") or d.get("ts")
    ts = ts_to_float(event_ts) or time.time()
    eid = f"{PROVIDER}:{etype_name}:{event_ts or uuid.uuid4().hex}"

    if etype_name in ("message", "app_mention"):
        channel = str(d.get("channel", ""))
        if subtype == "message_changed":
            msg = message_to_domain(d.get("message") or {}, channel=channel, team_id=team_id, self_id=self_id)
            msg.edited = True  # the subtype IS the edit signal even if the nested dict lacks the key
            return Event(id=eid, type=EventType.MESSAGE_EDITED, timestamp=msg.timestamp or ts,
                         actor=msg.author, conversation=msg.ref.conversation,
                         payload={"message": msg})
        if subtype == "message_deleted":
            conv = ConversationRef(provider=PROVIDER, workspace_id=str(team_id or ""), conversation_id=channel)
            ref = MessageRef(conversation=conv, message_id=str(d.get("deleted_ts", "")))
            return Event(id=eid, type=EventType.MESSAGE_DELETED, timestamp=ts,
                         conversation=conv, payload={"message_ref": ref})
        if subtype:  # joins, topic changes, bot noise, … — not first-class here
            return Event(id=eid, type=EventType.UNKNOWN, timestamp=ts, payload={"raw": d})
        msg = message_to_domain(d, channel=channel, team_id=team_id, self_id=self_id)
        etype = EventType.MESSAGE_CREATED
        if etype_name == "app_mention" or (
            self_id is not None and any(m.user_id == str(self_id) for m in msg.mentions)
        ):
            etype = EventType.APP_MENTION
        return Event(id=eid, type=etype, timestamp=msg.timestamp or ts,
                     actor=msg.author, conversation=msg.ref.conversation,
                     payload={"message": msg})

    if etype_name in ("reaction_added", "reaction_removed"):
        item = d.get("item") or {}
        conv = ConversationRef(
            provider=PROVIDER, workspace_id=str(team_id or ""),
            conversation_id=str(item.get("channel", "")),
        )
        ref = MessageRef(conversation=conv, message_id=str(item.get("ts", "")))
        return Event(
            id=eid,
            type=EventType.REACTION_ADDED if etype_name == "reaction_added" else EventType.REACTION_REMOVED,
            timestamp=ts,
            actor=_actor_from_id(d.get("user"), self_id=self_id),
            conversation=conv,
            payload={"message_ref": ref, "emoji": str(d.get("reaction", ""))},
        )

    if etype_name in ("member_joined_channel", "member_left_channel"):
        uid = str(d.get("user", ""))
        conv = ConversationRef(
            provider=PROVIDER, workspace_id=str(team_id or ""),
            conversation_id=str(d.get("channel", "")),
        )
        return Event(
            id=eid,
            type=EventType.USER_JOINED if etype_name == "member_joined_channel" else EventType.USER_LEFT,
            timestamp=ts,
            actor=_actor_from_id(uid, self_id=self_id),
            conversation=conv,
            payload={"user": User(id=uid, display_name=uid)},  # envelope carries the id only
        )

    if etype_name == "channel_created":
        conv = channel_to_conversation(d.get("channel") or {}, team_id=team_id)
        return Event(id=eid, type=EventType.CHANNEL_CREATED, timestamp=ts,
                     conversation=conv.ref, payload={"conversation": conv})

    if etype_name == "file_shared":
        conv = ConversationRef(
            provider=PROVIDER, workspace_id=str(team_id or ""),
            conversation_id=str(d.get("channel_id", "")),
        )
        # The envelope carries only ids — honest minimal Attachment; callers
        # hydrate via fetch_message / download_attachment.
        att = attachment_to_domain({"id": d.get("file_id", ""), "name": (d.get("file") or {}).get("name", "")})
        return Event(
            id=eid, type=EventType.FILE_UPLOADED, timestamp=ts,
            actor=_actor_from_id(d.get("user_id"), self_id=self_id),
            conversation=conv,
            payload={"attachment": att, "message_ref": None},
        )

    return Event(id=eid, type=EventType.UNKNOWN, timestamp=ts, payload={"raw": d})


def interaction_to_domain(d: dict, *, team_id: str | None = None, self_id: str | None = None) -> Interaction:
    """Normalize a Slack interactivity payload dict to :class:`Interaction`.

    Payload types: ``block_actions`` → BUTTON or SELECT by the action's
    shape (``custom_id=action_id``; SELECT values under ``"values"``);
    ``view_submission`` → MODAL_SUBMIT (``custom_id=view.callback_id``;
    ``view.state.values`` flattened to ``{field custom_id: value}``); a
    slash-command payload (has ``command``) → COMMAND (name arrives in
    ``custom_id`` without the ``/``; raw text under ``values["text"]``).

    ``id`` is the payload's ``trigger_id`` (unique per interaction and
    present on all three payload shapes).
    """
    team = str(team_id or (d.get("team") or {}).get("id") or d.get("team_id") or "")
    iid = str(d.get("trigger_id") or uuid.uuid4().hex)
    actor = actor_from_user(d.get("user") or {"id": d.get("user_id", "")}, self_id=self_id)

    if d.get("command"):
        conv = ConversationRef(provider=PROVIDER, workspace_id=team,
                               conversation_id=str(d.get("channel_id", "")))
        return Interaction(
            id=iid, type=InteractionType.COMMAND, actor=actor, conversation=conv,
            custom_id=str(d.get("command", "")).lstrip("/"),
            values={"text": d.get("text", "")},
        )

    ptype = d.get("type")
    channel_id = str((d.get("channel") or {}).get("id", ""))
    container = d.get("container") or {}
    conv_thread = container.get("thread_ts")
    conv = (
        thread_ref(channel_id, str(conv_thread), team_id=team)
        if conv_thread and channel_id
        else ConversationRef(provider=PROVIDER, workspace_id=team, conversation_id=channel_id)
    )
    message_ts = container.get("message_ts") or (d.get("message") or {}).get("ts")
    message_ref = (
        MessageRef(conversation=conv, message_id=str(message_ts)) if message_ts else None
    )

    if ptype == "view_submission":
        view = d.get("view") or {}
        values: dict = {}
        for _block_id, actions in ((view.get("state") or {}).get("values") or {}).items():
            for action_id, v in (actions or {}).items():
                if "value" in v:
                    values[action_id] = v.get("value")
                elif v.get("selected_option") is not None:
                    values[action_id] = (v.get("selected_option") or {}).get("value")
                elif v.get("selected_options") is not None:
                    values[action_id] = [o.get("value") for o in v.get("selected_options") or []]
        return Interaction(
            id=iid, type=InteractionType.MODAL_SUBMIT, actor=actor, conversation=conv,
            message=message_ref, custom_id=view.get("callback_id"), values=values,
        )

    # block_actions (default)
    action = (d.get("actions") or [{}])[0]
    custom_id = action.get("action_id")
    if action.get("selected_option") is not None:
        itype = InteractionType.SELECT
        values = {"values": [(action.get("selected_option") or {}).get("value")]}
    elif action.get("selected_options") is not None:
        itype = InteractionType.SELECT
        values = {"values": [o.get("value") for o in action.get("selected_options") or []]}
    else:
        itype = InteractionType.BUTTON
        values = {}
    return Interaction(
        id=iid, type=itype, actor=actor, conversation=conv,
        message=message_ref, custom_id=custom_id, values=values,
    )


# ---------------------------------------------------------------------- #
# Pure translation: domain → platform payloads
# ---------------------------------------------------------------------- #

def _plain_text(text: str) -> dict:
    return {"type": "plain_text", "text": text}


def components_to_payload(components: list[ActionRow]) -> list[dict]:
    """Translate domain ActionRows to Block Kit ``actions`` blocks.

    Buttons keep only styles Block Kit knows (``primary``/``danger``;
    anything else is Slack's default). Block Kit buttons have no disabled
    state — ``Button.disabled`` does not translate (platform gap).
    ``max_values > 1`` selects become ``multi_static_select``.
    """
    blocks = []
    for row in components or []:
        elements = []
        for comp in row.components:
            if isinstance(comp, Button):
                el = {"type": "button", "text": _plain_text(comp.label), "action_id": comp.custom_id}
                if comp.style in ("primary", "danger"):
                    el["style"] = comp.style
                elements.append(el)
            elif isinstance(comp, SelectMenu):
                el = {
                    "type": "multi_static_select" if comp.max_values > 1 else "static_select",
                    "action_id": comp.custom_id,
                    "options": [
                        {
                            "text": _plain_text(o.label),
                            "value": o.value,
                            **({"description": _plain_text(o.description)} if o.description else {}),
                        }
                        for o in comp.options
                    ],
                }
                if comp.placeholder:
                    el["placeholder"] = _plain_text(comp.placeholder)
                elements.append(el)
        blocks.append({"type": "actions", "elements": elements})
    return blocks


def modal_to_payload(modal: Modal) -> dict:
    """Translate a domain Modal to a Slack ``views.open`` view payload.

    Each ``FormField`` becomes an ``input`` block with a
    ``plain_text_input`` element whose ``action_id`` is the field's
    ``custom_id`` (so ``view_submission`` state flattens back to the same
    keys). ``kind`` maps generically: ``"multiline"``/``"paragraph"`` →
    ``multiline=True``.
    """
    return {
        "type": "modal",
        "callback_id": modal.custom_id,
        "title": _plain_text(modal.title),
        "submit": _plain_text("Submit"),
        "blocks": [
            {
                "type": "input",
                "block_id": f.custom_id,
                "label": _plain_text(f.label),
                "optional": not f.required,
                "element": {
                    "type": "plain_text_input",
                    "action_id": f.custom_id,
                    "multiline": f.kind in ("multiline", "paragraph"),
                    **({"placeholder": _plain_text(f.placeholder)} if f.placeholder else {}),
                },
            }
            for f in modal.fields
        ],
    }


def map_slack_error(exc: BaseException, *, target: str) -> ChatError:
    """Translate an SDK exception into the domain taxonomy — the single sink.

    ``target`` names what the failing operation was addressing —
    ``"conversation"`` | ``"message"`` | ``"user"`` | ``"attachment"``.
    Slack's ``error`` strings are often self-describing
    (``channel_not_found`` vs ``user_not_found``), but the conversation-gone
    family still disambiguates by target (a gone channel under a *message*
    operation stays base ``ChatError`` — the taxonomy has no
    MessageNotFound), and bare HTTP statuses need the target entirely.
    Matching is duck-typed (class name / ``response["error"]`` /
    ``status``) so this stays SDK-import-free.
    """
    err = _error_string(exc)
    status = getattr(exc, "status", None)
    resp = getattr(exc, "response", None)
    if status is None:
        status = getattr(resp, "status_code", None)
    text = f"{type(exc).__name__}: {err or exc}"

    if err in _ERR_PERMISSION:
        return PermissionDenied(text)
    if err in _ERR_EXPIRED:
        return InteractionExpired(text)
    if err in _ERR_USER_GONE:
        return UserNotFound(text)
    if err in _ERR_CONV_GONE:
        return ConversationNotFound(text) if target == "conversation" else ChatError(text)
    if err in _ERR_MESSAGE_GONE:
        return ChatError(text)
    if err == "ratelimited" or status == 429:
        return RateLimited(text)
    if err == "file_uploads_exceed_max_size" or status == 413:
        return AttachmentTooLarge(text)
    if status == 404:
        if target == "conversation":
            return ConversationNotFound(text)
        if target == "user":
            return UserNotFound(text)
        return ChatError(text)
    return ChatError(text)


class _ApiError(Exception):
    """Wraps an ``ok: false`` response dict from a client that returns
    instead of raising (the real SDK raises ``SlackApiError``; duck-typed
    fakes may not) so both paths funnel through :func:`map_slack_error`."""

    def __init__(self, data: dict) -> None:
        super().__init__(str(data.get("error", "slack api error")))
        self.response = data


class _LiveInteraction:
    """Adapter-side state for one in-window interaction."""

    def __init__(self, payload: dict, domain: Interaction) -> None:
        self.payload = payload
        self.domain = domain
        self.response_url: str | None = payload.get("response_url") or None
        self.trigger_id: str | None = payload.get("trigger_id") or None
        self.received_at = time.time()
        self.responded = False


# ---------------------------------------------------------------------- #
# The adapter
# ---------------------------------------------------------------------- #

class SlackAdapter(ChatAdapter):
    """``ChatAdapter`` on Slack (slack_bolt Socket Mode + slack_sdk Web API).

    Construction: pass a duck-typed ``web`` client (tests use fakes — no
    SDK import); production code uses :meth:`connect`, the only
    SDK/Socket-Mode entry point. ``sdk`` overrides the lazily-imported
    ``slack_sdk`` namespace (webhook-client seam for ``response_url``
    posts); ``http_get`` overrides the authed download fetch.
    """

    def __init__(
        self,
        web,
        *,
        team_id: str | None = None,
        self_id: str | None = None,
        sdk=None,
        http_get=None,
    ) -> None:
        self._web = web
        self._team_id = team_id or ""
        self._self_id = self_id
        self._sdk_override = sdk
        self._http_get_override = http_get
        self._hub = _SubscriptionHub()
        self._live: dict[str, _LiveInteraction] = {}

    # ------------------------------------------------------------------ #
    # SDK seams + real Socket Mode construction
    # ------------------------------------------------------------------ #

    async def _http_get(self, url: str, headers: dict) -> bytes:
        """Authed GET returning body bytes — injectable (download seam)."""
        if self._http_get_override is not None:
            return await self._http_get_override(url, headers)
        import aiohttp  # pragma: no cover - live download path only

        async with aiohttp.ClientSession() as session:  # pragma: no cover
            async with session.get(url, headers=headers) as resp:
                if resp.status == 404:
                    raise ChatError(f"attachment blob gone: {url}")
                resp.raise_for_status()
                return await resp.read()

    @classmethod
    async def connect(
        cls,
        bot_token: str,
        app_token: str,
        *,
        team_id: str | None = None,
    ) -> "SlackAdapter":
        """Open the Socket Mode connection; returns a ready adapter.

        The only place that imports/instantiates the real SDKs. ``bot_token``
        (``xoxb-``) drives the Web API; ``app_token`` (``xapp-``, scope
        ``connections:write``) opens the event stream. Registers handlers
        for the subscribed events (see ``aidocs/chat/slack_app_setup.md``)
        and all interactivity payloads (ack on receipt — the instant-ack
        special case of the amended ``_acked`` contract). The ``app_mention``
        envelope is registered ack-only: mentions are detected on the
        ``message`` event (single source, no double-publish).
        """
        from slack_bolt.adapter.socket_mode.async_handler import (  # pragma: no cover
            AsyncSocketModeHandler,
        )
        from slack_bolt.async_app import AsyncApp  # pragma: no cover - live only
        import slack_sdk  # pragma: no cover

        app = AsyncApp(token=bot_token)
        adapter = cls(app.client, team_id=team_id, sdk=slack_sdk)

        auth = _resp_data(await app.client.auth_test())
        adapter._self_id = str(auth.get("user_id", "") or "")
        if not adapter._team_id:
            adapter._team_id = str(auth.get("team_id", "") or "")

        for event_name in (
            "message", "reaction_added", "reaction_removed",
            "member_joined_channel", "member_left_channel",
            "channel_created", "file_shared",
        ):
            @app.event(event_name)  # pragma: no cover - live stream only
            async def _on_event(event):  # noqa: ANN001
                adapter._publish_event(event)

        @app.event("app_mention")  # pragma: no cover - ack-only (see docstring)
        async def _on_app_mention(event):  # noqa: ANN001, ARG001
            return

        @app.action(re.compile(".*"))  # pragma: no cover - live only
        async def _on_action(ack, body):  # noqa: ANN001
            await adapter._on_interaction(body, ack)

        @app.view(re.compile(".*"))  # pragma: no cover - live only
        async def _on_view(ack, body):  # noqa: ANN001
            await adapter._on_interaction(body, ack)

        @app.command(re.compile(".*"))  # pragma: no cover - live only
        async def _on_command(ack, body):  # noqa: ANN001
            await adapter._on_interaction(body, ack)

        handler = AsyncSocketModeHandler(app, app_token)  # pragma: no cover
        listeners = getattr(getattr(handler, "client", None), "disconnect_listeners", None)
        if listeners is not None:  # pragma: no cover - best-effort transport hook
            listeners.append(lambda *_a, **_k: adapter._hub.disconnect_all())
        await handler.connect_async()  # pragma: no cover
        return adapter

    # ------------------------------------------------------------------ #
    # Event / interaction ingestion (handlers call these; tests directly)
    # ------------------------------------------------------------------ #

    def _publish_event(self, event: dict) -> None:
        """Normalize one events_api dict and broadcast it to subscribers."""
        self._hub.publish(event_to_domain(event, team_id=self._team_id, self_id=self._self_id))

    async def _on_interaction(self, payload: dict, ack=None) -> Interaction:
        """Ingest an interactivity payload: ack FIRST, then publish.

        The instant-ack special case of the amended contract: the platform
        ack (Socket Mode envelope response) is *performed* before the
        Interaction is visible anywhere, so ``_acked=True`` is literally
        true at yield time. The published INTERACTION_RECEIVED event
        carries the SAME ack-owned object — re-normalizing here would hand
        subscribers an ``_acked=False`` copy (t1074_2 regression).
        """
        if ack is not None:
            await ack()
        domain = interaction_to_domain(payload, team_id=self._team_id, self_id=self._self_id)
        domain._acked = True
        self._live[domain.id] = _LiveInteraction(payload, domain)
        self._hub.publish(Event(
            id=f"{PROVIDER}:interaction:{domain.id}",
            type=EventType.INTERACTION_RECEIVED,
            timestamp=time.time(),
            actor=domain.actor,
            conversation=domain.conversation,
            payload={"interaction": domain},
        ))
        return domain

    # ------------------------------------------------------------------ #
    # Web API plumbing
    # ------------------------------------------------------------------ #

    async def _api(self, method, *, target: str, **kwargs) -> dict:
        """One Web API call through the error sink; returns the data dict.

        Handles both client styles: a raising client (real SDK) and a fake
        that returns ``ok: false`` dicts — both funnel into
        :func:`map_slack_error` with this call site's ``target``.
        """
        try:
            resp = await method(**kwargs)
        except Exception as exc:  # noqa: BLE001 - single mapped sink
            raise map_slack_error(exc, target=target) from exc
        data = _resp_data(resp)
        if data.get("ok") is False:
            shim = _ApiError(data)
            raise map_slack_error(shim, target=target) from shim
        return data

    async def _paginate(
        self,
        method,
        key: str,
        *,
        target: str,
        limit: int | None = None,
        **kwargs,
    ) -> list:
        """Cursor-pagination loop over a paging Web API method.

        Follows ``response_metadata.next_cursor`` until it is empty or
        ``limit`` items are collected, concatenating each page's ``key``
        list. slack_sdk does not auto-paginate a single call — without this
        loop, real workspaces silently truncate at one page.
        """
        items: list = []
        cursor: str | None = None
        while True:
            call_kwargs = dict(kwargs)
            if cursor:
                call_kwargs["cursor"] = cursor
            if limit is not None:
                call_kwargs["limit"] = min(200, max(1, limit - len(items)))
            data = await self._api(method, target=target, **call_kwargs)
            items.extend(data.get(key) or [])
            if limit is not None and len(items) >= limit:
                return items[:limit]
            cursor = str(((data.get("response_metadata") or {}).get("next_cursor") or "")).strip()
            if not cursor:
                return items

    async def _resolve_conversation(self, ref: ConversationRef) -> dict:
        """THE existence probe: ``conversations.info`` on the channel id.

        Raises ``ConversationNotFound`` (via the sink) when the
        conversation is gone. Thread refs probe their parent channel —
        threads are not separately addressable objects on Slack.
        """
        data = await self._api(
            self._web.conversations_info, target="conversation",
            channel=ref.conversation_id,
        )
        return data.get("channel") or {}

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
            # Platform gap, surfaced loudly: Slack has no API to attach
            # pre-existing file handles to a chat.postMessage — silently
            # dropping them would fake a partial send as success. Send the
            # text, then upload files via upload_attachment (thread refs
            # land in-thread).
            raise ChatError(
                "Slack cannot attach existing file handles to a message; "
                "use upload_attachment for files"
            )
        kwargs: dict = {"channel": conversation.conversation_id, "text": text}
        thread_ts = conversation.thread_id or (reply_to.message_id if reply_to is not None else None)
        if thread_ts:
            kwargs["thread_ts"] = thread_ts
        if components:
            kwargs["blocks"] = components_to_payload(components)
        data = await self._api(self._web.chat_postMessage, target="conversation", **kwargs)
        msg_dict = dict(data.get("message") or {})
        msg_dict.setdefault("ts", data.get("ts", ""))
        return message_to_domain(
            msg_dict, channel=conversation.conversation_id,
            team_id=self._team_id, self_id=self._self_id,
        )

    async def edit_message(
        self,
        message: MessageRef,
        text: str,
        *,
        components: list[ActionRow] | None = None,
    ) -> Message:
        await self._resolve_conversation(message.conversation)
        kwargs: dict = {
            "channel": message.conversation.conversation_id,
            "ts": message.message_id,
            "text": text,
        }
        if components:
            kwargs["blocks"] = components_to_payload(components)
        data = await self._api(self._web.chat_update, target="message", **kwargs)
        msg_dict = dict(data.get("message") or {})
        msg_dict.setdefault("ts", data.get("ts", message.message_id))
        msg_dict.setdefault("text", data.get("text", text))
        msg = message_to_domain(
            msg_dict, channel=message.conversation.conversation_id,
            team_id=self._team_id, self_id=self._self_id,
        )
        msg.edited = True  # contract: the edit just happened
        return msg

    async def delete_message(self, message: MessageRef) -> None:
        await self._resolve_conversation(message.conversation)
        await self._api(
            self._web.chat_delete, target="message",
            channel=message.conversation.conversation_id, ts=message.message_id,
        )

    async def fetch_message(self, message: MessageRef) -> Message:
        await self._resolve_conversation(message.conversation)
        mid = message.message_id
        channel = message.conversation.conversation_id
        if message.conversation.thread_id:
            data = await self._api(
                self._web.conversations_replies, target="message",
                channel=channel, ts=message.conversation.thread_id,
                latest=mid, inclusive=True, limit=1,
            )
        else:
            data = await self._api(
                self._web.conversations_history, target="message",
                channel=channel, latest=mid, inclusive=True, limit=1,
            )
        # Exact-ts guard: the bounded-range lookup returns the NEAREST
        # message at-or-before `latest` — a deleted target would silently
        # yield a neighbor. Only an exact ts match is the requested message.
        for m in data.get("messages") or []:
            if str(m.get("ts")) == str(mid):
                return message_to_domain(m, channel=channel, team_id=self._team_id, self_id=self._self_id)
        raise ChatError(f"message {mid} not found in {channel}")

    async def send_ephemeral(
        self,
        conversation: ConversationRef,
        actor: Actor,
        text: str,
        *,
        components: list[ActionRow] | None = None,
    ) -> EphemeralReceipt:
        """Private-only fallback chain: ``chat.postEphemeral`` (Slack's true
        per-user ephemeral — no interaction context needed) → DM →
        ``DeliveryFailed``. Nothing is ever posted publicly. ANY native
        failure falls through — ``user_not_in_channel`` / ``not_in_channel``
        / ``no_permission`` / gone channel are normal approval-prompt flows,
        not errors."""
        blocks = components_to_payload(components) if components else None
        kwargs: dict = {
            "channel": conversation.conversation_id,
            "user": actor.id,
            "text": text,
        }
        if conversation.thread_id:
            kwargs["thread_ts"] = conversation.thread_id
        if blocks:
            kwargs["blocks"] = blocks
        try:
            await self._api(self._web.chat_postEphemeral, target="conversation", **kwargs)
            # Ephemerals have no fetchable/re-addressable handle → message=None.
            return EphemeralReceipt(path=EphemeralPath.NATIVE, message=None)
        except ChatError:
            pass  # fall through to DM — never public

        try:
            data = await self._api(self._web.conversations_open, target="user", users=actor.id)
            dm_id = str((data.get("channel") or {}).get("id", ""))
            dm_kwargs: dict = {"channel": dm_id, "text": text}
            if blocks:
                dm_kwargs["blocks"] = blocks
            sent = await self._api(self._web.chat_postMessage, target="conversation", **dm_kwargs)
            msg_dict = dict(sent.get("message") or {})
            msg_dict.setdefault("ts", sent.get("ts", ""))
            msg = message_to_domain(msg_dict, channel=dm_id, team_id=self._team_id, self_id=self._self_id)
            return EphemeralReceipt(path=EphemeralPath.DM, message=msg)
        except ChatError as exc:
            raise DeliveryFailed(f"no private path to actor {actor.id}: {exc}") from exc

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
            if isinstance(parent, ConversationRef):
                # Slack threads only anchor on messages —
                # supports_standalone_threads=False (contract-gated raise).
                raise PermissionDenied("Slack threads must anchor on a message (no standalone threads)")
            # Threads exist implicitly with the first reply: probe the parent
            # channel, then hand back the thread ref (no create API exists).
            await self._resolve_conversation(parent.conversation)
            ref = thread_ref(
                parent.conversation.conversation_id, parent.message_id, team_id=self._team_id,
            )
            conv = Conversation(ref=ref, kind=ConversationKind.THREAD, name=name)
            self._hub.publish(Event(
                id=f"{PROVIDER}:thread_created:{parent.message_id}",
                type=EventType.THREAD_CREATED,
                timestamp=time.time(),
                conversation=ref,
                payload={"conversation": conv},
            ))
            return conv

        if kind is ConversationKind.DIRECT:
            if not participants:
                raise ValueError("kind=DIRECT requires participants")
            data = await self._api(
                self._web.conversations_open, target="user", users=",".join(participants),
            )
            ch = dict(data.get("channel") or {})
            ch.setdefault("is_im", len(participants) == 1)
            return channel_to_conversation(ch, team_id=self._team_id)

        if kind in (ConversationKind.CHANNEL, ConversationKind.PRIVATE):
            kwargs: dict = {"name": name or "channel"}
            if kind is ConversationKind.PRIVATE:
                kwargs["is_private"] = True
            data = await self._api(self._web.conversations_create, target="conversation", **kwargs)
            conv = channel_to_conversation(dict(data.get("channel") or {}), team_id=self._team_id)
            self._hub.publish(Event(
                id=f"{PROVIDER}:channel_created:{conv.ref.conversation_id}",
                type=EventType.CHANNEL_CREATED,
                timestamp=time.time(),
                conversation=conv.ref,
                payload={"conversation": conv},
            ))
            return conv

        raise PermissionDenied(f"Slack adapter cannot create {kind.value} conversations")

    async def archive_conversation(self, conversation: ConversationRef) -> None:
        if conversation.thread_id:
            # Documented platform gap: Slack threads have no archive
            # operation (they follow their parent channel).
            raise ChatError("Slack threads cannot be archived")
        await self._api(
            self._web.conversations_archive, target="conversation",
            channel=conversation.conversation_id,
        )

    async def fetch_history(
        self,
        conversation: ConversationRef,
        *,
        before: MessageRef | None = None,
        after: MessageRef | None = None,
        limit: int = 100,
    ) -> list[Message]:
        kwargs: dict = {"channel": conversation.conversation_id}
        if before is not None:
            kwargs["latest"] = before.message_id      # exclusive (inclusive=False default)
        if after is not None:
            kwargs["oldest"] = after.message_id       # exclusive
        if conversation.thread_id:
            method = self._web.conversations_replies
            kwargs["ts"] = conversation.thread_id
        else:
            method = self._web.conversations_history
        raw = await self._paginate(method, "messages", target="conversation", limit=limit, **kwargs)
        out = [
            message_to_domain(m, channel=conversation.conversation_id,
                              team_id=self._team_id, self_id=self._self_id)
            for m in raw
        ]
        out.sort(key=lambda m: m.timestamp)  # contract: chronological order
        return out[:limit]

    async def fetch_participants(self, conversation: ConversationRef) -> list[User]:
        member_ids = await self._paginate(
            self._web.conversations_members, "members", target="conversation",
            channel=conversation.conversation_id,
        )
        users = []
        for uid in member_ids:
            data = await self._api(self._web.users_info, target="user", user=uid)
            users.append(user_to_domain(data.get("user") or {}))
        return users

    # ------------------------------------------------------------------ #
    # Discovery
    # ------------------------------------------------------------------ #

    async def fetch_conversation(self, ref: ConversationRef) -> Conversation:
        ch = await self._resolve_conversation(ref)
        return channel_to_conversation(ch, team_id=self._team_id)

    async def list_conversations(
        self, *, kinds: list[ConversationKind] | None = None
    ) -> list[Conversation]:
        raw = await self._paginate(
            self._web.conversations_list, "channels", target="conversation",
            types="public_channel,private_channel,im,mpim",
        )
        out = [channel_to_conversation(ch, team_id=self._team_id) for ch in raw]
        if kinds is not None:
            wanted = set(kinds)
            out = [c for c in out if c.kind in wanted]
        return out

    async def get_permalink(self, ref: ConversationRef | MessageRef) -> str:
        if isinstance(ref, MessageRef):
            data = await self._api(
                self._web.chat_getPermalink, target="message",
                channel=ref.conversation.conversation_id, message_ts=ref.message_id,
            )
            return str(data.get("permalink", ""))
        return build_permalink(ref.workspace_id, ref.conversation_id)

    # ------------------------------------------------------------------ #
    # Identity
    # ------------------------------------------------------------------ #

    async def fetch_user(self, user_id: str) -> User:
        data = await self._api(self._web.users_info, target="user", user=user_id)
        return user_to_domain(data.get("user") or {})

    async def fetch_identity_claims(
        self, conversation: ConversationRef, user_id: str
    ) -> IdentityClaims:
        user_data = await self._api(self._web.users_info, target="user", user=user_id)
        user_info = user_data.get("user") or {}
        member_ids = await self._paginate(
            self._web.conversations_members, "members", target="conversation",
            channel=conversation.conversation_id,
        )
        is_member = str(user_id) in {str(m) for m in member_ids}

        # Usergroup scan: optional richness. A missing usergroups:read scope
        # (or any scan failure) degrades to roles=[] — claims never invent
        # privileges, and a missing optional scope must not make identity
        # claims unusable. The degradation is surfaced in metadata.
        groups: list[dict] = []
        scan_error: str | None = None
        try:
            ug_data = await self._api(self._web.usergroups_list, target="user")
            for g in ug_data.get("usergroups") or []:
                users_data = await self._api(
                    self._web.usergroups_users_list, target="user", usergroup=g.get("id"),
                )
                if str(user_id) in {str(u) for u in users_data.get("users") or []}:
                    groups.append(g)
        except ChatError as exc:
            groups = []
            scan_error = str(exc)

        claims = member_to_claims(user_info, groups, is_channel_member=is_member)
        if scan_error is not None:
            claims.metadata["usergroups_degraded"] = scan_error
        return claims

    # ------------------------------------------------------------------ #
    # Reconciliation
    # ------------------------------------------------------------------ #

    async def fetch_reactions(self, message: MessageRef) -> list[Reaction]:
        await self._resolve_conversation(message.conversation)
        data = await self._api(
            self._web.reactions_get, target="message", full=True,
            channel=message.conversation.conversation_id, timestamp=message.message_id,
        )
        msg = data.get("message") or {}
        return [reaction_to_domain(r) for r in msg.get("reactions") or []]

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
        kwargs: dict = {
            "channel": conversation.conversation_id,
            "filename": filename,
            "content": content,
        }
        if conversation.thread_id:
            # Thread refs upload INTO the thread — without thread_ts the
            # file lands in the channel root.
            kwargs["thread_ts"] = conversation.thread_id
        data = await self._api(self._web.files_upload_v2, target="attachment", **kwargs)
        file_dict = data.get("file") or next(iter(data.get("files") or []), None)
        if file_dict:
            att = attachment_to_domain(
                file_dict,
                Actor(id=str(self._self_id or ""), type=ActorType.BOT, is_self=True),
            )
        else:  # platform yielded no handle — synthesize the minimum honest one
            att = Attachment(id="", filename=filename, size=len(content))
        if att.mime_type is None:
            att.mime_type = mime_type
        return att

    async def download_attachment(self, attachment: Attachment) -> bytes:
        if attachment.url is None:
            raise ChatError(f"attachment {attachment.id} has no URL")
        # url_private requires the bot bearer token; auth stays below the
        # boundary (higher layers never fetch platform URLs directly).
        token = getattr(self._web, "token", None)
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        try:
            return await self._http_get(attachment.url, headers)
        except ChatError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise map_slack_error(exc, target="attachment") from exc

    async def add_reaction(self, message: MessageRef, emoji: str) -> None:
        await self._reaction_op(self._web.reactions_add, message, emoji, noop_error="already_reacted")

    async def remove_reaction(self, message: MessageRef, emoji: str) -> None:
        await self._reaction_op(self._web.reactions_remove, message, emoji, noop_error="no_reaction")

    async def _reaction_op(self, method, message: MessageRef, emoji: str, *, noop_error: str) -> None:
        """Shared add/remove: name-normalize the emoji (accepts ``:tada:``
        and ``tada``) and honor the contract's no-op semantics."""
        await self._resolve_conversation(message.conversation)
        try:
            await self._api(
                method, target="message",
                channel=message.conversation.conversation_id,
                timestamp=message.message_id,
                name=emoji.strip(":"),
            )
        except ChatError as exc:
            if noop_error in str(exc):
                return  # contract: already-present add / absent remove is a no-op
            raise

    # ------------------------------------------------------------------ #
    # Interactions
    # ------------------------------------------------------------------ #

    async def register_commands(self, specs: list[SlashCommand]) -> None:
        """Validate and converge — Slack slash commands are app-config-level.

        Slack has no programmatic bulk registration (commands are declared
        on the app's *Slash Commands* config page — see
        ``aidocs/chat/slack_app_setup.md`` §5), so this validates the specs
        (caller bugs raise ``ValueError``) and returns: re-registering the
        same specs trivially converges (idempotent per the ABC contract).
        """
        for spec in specs:
            name = spec.name.lstrip("/")
            if not name or not _COMMAND_NAME_RE.match(name):
                raise ValueError(
                    f"invalid slash command name {spec.name!r} "
                    "(lowercase letters, digits, - and _ only)"
                )

    async def ack(self, interaction: Interaction) -> None:
        """Idempotent no-op: the platform ack already happened on receipt
        (instant-ack special case of the amended ``_acked`` contract)."""
        interaction._acked = True

    async def respond(
        self,
        interaction: Interaction,
        text: str,
        *,
        components: list[ActionRow] | None = None,
        ephemeral: bool = False,
    ) -> Message | None:
        msg = await self._response_url_post(interaction, text, components=components, ephemeral=ephemeral)
        live = self._live.get(interaction.id)
        if live is not None:
            live.responded = True
        return msg

    async def follow_up(
        self,
        interaction: Interaction,
        text: str,
        *,
        components: list[ActionRow] | None = None,
        ephemeral: bool = False,
    ) -> Message | None:
        return await self._response_url_post(interaction, text, components=components, ephemeral=ephemeral)

    async def _response_url_post(
        self,
        interaction: Interaction,
        text: str,
        *,
        components: list[ActionRow] | None,
        ephemeral: bool,
    ) -> Message | None:
        """Post through the interaction's ``response_url`` webhook.

        The webhook returns no message handle → ``None``
        (contract-sanctioned). An unknown/expired interaction or a failed
        post (Slack's window is ~30 min / 5 posts) → ``InteractionExpired``.
        """
        live = self._live.get(interaction.id)
        if live is None or not live.response_url:
            raise InteractionExpired(f"interaction {interaction.id} is past its window")
        payload: dict = {
            "text": text,
            "response_type": "ephemeral" if ephemeral else "in_channel",
            "replace_original": False,
        }
        if components:
            payload["blocks"] = components_to_payload(components)
        try:
            resp = await self._webhook_send(live.response_url, payload)
        except Exception as exc:  # noqa: BLE001 - past-window etc.
            raise InteractionExpired(f"interaction {interaction.id}: {exc}") from exc
        status = getattr(resp, "status_code", None)
        if status is not None and status != 200:
            raise InteractionExpired(
                f"interaction {interaction.id}: response_url returned {status}"
            )
        return None

    def _webhook_client(self, url: str):
        """Resolve the response_url webhook client — sdk-seam aware.

        The REAL SDK does not eagerly bind ``slack_sdk.webhook.async_client``
        on ``import slack_sdk`` (the submodule needs aiohttp), so bare
        attribute traversal raises ``AttributeError`` at the first live
        ``respond``. Fakes inject the nested shape and are used directly;
        anything else (no override, or the real module passed by
        ``connect``) resolves via a genuine submodule import.
        """
        sdk = self._sdk_override
        if sdk is not None:
            async_client = getattr(getattr(sdk, "webhook", None), "async_client", None)
            if async_client is not None:
                return async_client.AsyncWebhookClient(url)
        from slack_sdk.webhook.async_client import AsyncWebhookClient  # lazy real import
        return AsyncWebhookClient(url)

    async def _webhook_send(self, url: str, payload: dict):
        """response_url POST — via the webhook-client seam."""
        return await self._webhook_client(url).send_dict(payload)

    async def open_modal(self, interaction: Interaction, modal: Modal) -> None:
        """Open a modal via ``views.open`` — needs the interaction's
        ``trigger_id`` within its ~3 s window (instant ack does not narrow
        it; an expired trigger maps to ``InteractionExpired``)."""
        live = self._live.get(interaction.id)
        if live is None:
            raise InteractionExpired(f"interaction {interaction.id} is past its window")
        if interaction.type is InteractionType.MODAL_SUBMIT:
            # Platform rule mirrored from Discord: a modal submission does
            # not carry a fresh modal-opening trigger.
            raise InteractionExpired("a MODAL_SUBMIT interaction cannot open another modal")
        if not live.trigger_id:
            raise InteractionExpired(f"interaction {interaction.id} has no trigger_id")
        await self._api(
            self._web.views_open, target="message",
            trigger_id=live.trigger_id, view=modal_to_payload(modal),
        )

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
            supports_slash_commands=True,   # invocations arrive; registration is app-config-level
            supports_reactions=True,
            supports_files=True,
            supports_ephemeral=True,        # chat.postEphemeral — no interaction context needed
            supports_dm=True,
            supports_voice=False,           # out of scope for this layer
            supports_editing=True,
            supports_thread_creation=True,  # message-anchored only
            supports_standalone_threads=False,
            # Platform-honest: search.messages needs a USER token (xoxp-,
            # scope search:read); this adapter holds bot+app tokens only, so
            # an instance genuinely cannot search. See metadata.
            supports_message_search=False,
            max_message_length=_MAX_MESSAGE_LENGTH,
            max_attachment_bytes=_MAX_ATTACHMENT_BYTES,
            metadata={
                "blocks_section_text_limit": 3000,
                "message_search_note": (
                    "platform supports search.messages behind a user-token "
                    "(xoxp-, search:read) seam this layer does not hold; "
                    "flipping the flag requires that seam plus an ABC search "
                    "verb via the contract amendment path"
                ),
            },
        )
