#!/usr/bin/env bash
# test_chat_discord.sh — DiscordAdapter tests (t1074_2).
#
# Two tiers, both no-network and SDK-free (the `discord` package is NEVER
# imported — everything runs against SimpleNamespace stubs and fakes):
#   Tier 1: pure normalization functions (platform→domain, domain→payload,
#           permalinks, the map_discord_error target matrix).
#   Tier 2: adapter-level behavior — ABC satisfaction/signature pinning,
#           method behavior through fake client/channel/message objects,
#           the subscription hub fan-out contract, and the delayed-defer
#           (owned-ack) interaction scheme.
# Run: bash tests/test_chat_discord.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# shellcheck source=../.aitask-scripts/lib/python_resolve.sh
source "$PROJECT_DIR/.aitask-scripts/lib/python_resolve.sh"

PYTHON="$(require_ait_python)"

"$PYTHON" - "$PROJECT_DIR" <<'PYEOF'
import asyncio
import inspect
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

root = Path(sys.argv[1])
sys.path.insert(0, str(root / ".aitask-scripts"))

# Guard: this suite must run on the stock venv — no SDK anywhere.
assert "discord" not in sys.modules

import chat
from chat.adapter import ChatAdapter
from chat.errors import (
    AttachmentTooLarge, ChatError, ConversationNotFound, DeliveryFailed,
    InteractionExpired, PermissionDenied, RateLimited, UserNotFound,
)
from chat.interactions import (
    ActionRow, Button, FormField, Interaction, InteractionType, Modal,
    SelectMenu, SelectOption, SlashCommand, CommandOption,
)
from chat.model import (
    Actor, ActorType, Attachment, ConversationKind, ConversationRef,
    EphemeralPath, EventType, MessageRef,
)
import chat.discord_adapter as da
from chat.discord_adapter import (
    DiscordAdapter, build_permalink, channel_kind, channel_to_conversation,
    channel_to_ref, commands_to_payload, components_to_payload,
    event_to_domain, interaction_to_domain, map_discord_error,
    member_to_claims, message_to_domain, modal_to_payload, user_to_domain,
)

assert "discord" not in sys.modules, "importing discord_adapter must not import the SDK"

PASS = 0
def check(label, cond, detail=""):
    global PASS
    assert cond, f"FAIL: {label} {detail}"
    PASS += 1
    print(f"ok - {label}")


# ===================================================================== #
# Tier 1 — pure normalization
# ===================================================================== #

# --- permalinks: guild and @me (DM) forms ---
check("permalink guild+message",
      build_permalink("11", "22", "33") == "https://discord.com/channels/11/22/33")
check("permalink guild only",
      build_permalink("11", "22") == "https://discord.com/channels/11/22")
check("permalink DM uses @me",
      build_permalink("@me", "22", "33") == "https://discord.com/channels/@me/22/33")
check("permalink empty workspace falls back to @me",
      build_permalink("", "22") == "https://discord.com/channels/@me/22")

# --- channel kind / ref mapping ---
guild = SimpleNamespace(id=100, owner_id=7)
text_channel = SimpleNamespace(id=200, guild=guild, name="general", topic="t", parent_id=None)
thread = SimpleNamespace(id=300, guild=guild, name="thr", topic=None, parent_id=200, archived=False)
dm = SimpleNamespace(id=400, guild=None, recipient=SimpleNamespace(id=8), name=None, topic=None, parent_id=None)

check("kind: text channel", channel_kind(text_channel) is ConversationKind.CHANNEL)
check("kind: thread", channel_kind(thread) is ConversationKind.THREAD)
check("kind: DM", channel_kind(dm) is ConversationKind.DIRECT)

tref = channel_to_ref(thread)
check("thread ref: parent as conversation_id, thread_id set",
      tref.conversation_id == "200" and tref.thread_id == "300" and tref.workspace_id == "100")
dref = channel_to_ref(dm)
check("DM ref: @me workspace (required field stays valid)",
      dref.workspace_id == "@me" and dref.conversation_id == "400")
check("ref provider is discord", tref.provider == "discord")
conv = channel_to_conversation(thread)
check("conversation: name/kind/ref", conv.name == "thr" and conv.kind is ConversationKind.THREAD)

# --- user / actor / claims ---
user = SimpleNamespace(id=8, name="ada", display_name="Ada", global_name=None, bot=False)
u = user_to_domain(user)
check("user_to_domain basics", u.id == "8" and u.display_name == "Ada" and u.username == "ada" and not u.is_bot)
check("user email stays None (Discord never exposes)", u.email is None)

bot_user = SimpleNamespace(id=9, name="bot", display_name="Bot", bot=True)
from chat.discord_adapter import actor_from_user
a = actor_from_user(bot_user, self_id="9")
check("actor: bot + is_self", a.type is ActorType.BOT and a.is_self)

member = SimpleNamespace(
    id=8, guild=guild,
    roles=[SimpleNamespace(id=1, name="@everyone"), SimpleNamespace(id=2, name="admins")],
    guild_permissions=SimpleNamespace(administrator=True),
)
claims = member_to_claims(member, is_channel_member=True)
check("claims: @everyone skipped, discord_role kind",
      [r.name for r in claims.roles] == ["admins"] and claims.roles[0].kind == "discord_role")
check("claims: admin flag honest", claims.is_workspace_admin is True)
check("claims: owner from guild.owner_id", claims.is_owner is False)
owner_claims = member_to_claims(SimpleNamespace(id=7, guild=guild, roles=[], guild_permissions=None))
check("claims: owner matches owner_id", owner_claims.is_owner is True)
check("claims: absent knowledge is False/empty",
      owner_claims.is_workspace_admin is False and owner_claims.roles == [])

# --- message normalization ---
now = datetime(2026, 7, 5, 12, 0, tzinfo=timezone.utc)
native_msg = SimpleNamespace(
    id=500, channel=text_channel, content="hi <@9>",
    author=user, created_at=now, edited_at=None,
    attachments=[SimpleNamespace(id=600, filename="a.txt", content_type="text/plain", size=3, url="http://cdn/a")],
    mentions=[SimpleNamespace(id=9, name="bot", display_name="Bot")],
    reactions=[SimpleNamespace(emoji="👍", count=2, me=False)],
    reference=SimpleNamespace(message_id=499, channel_id=200, guild_id=100),
)
m = message_to_domain(native_msg)
check("message: ref + author + text",
      m.ref.message_id == "500" and m.author.id == "8" and m.text == "hi <@9>")
check("message: timestamp from created_at", m.timestamp == now.timestamp())
check("message: attachment normalized",
      m.attachments[0].filename == "a.txt" and m.attachments[0].mime_type == "text/plain")
check("message: mention + reaction",
      m.mentions[0].user_id == "9" and m.reactions[0].emoji == "👍" and m.reactions[0].count == 2)
check("message: reply_to from reference", m.reply_to.message_id == "499")
check("message: edited False without edited_at", m.edited is False)
edited_msg = SimpleNamespace(**{**native_msg.__dict__, "edited_at": now})
check("message: edited True with edited_at", message_to_domain(edited_msg).edited is True)

# --- events → domain (payload contract table) ---
ev = event_to_domain("message", native_msg)
check("event message → MESSAGE_CREATED + payload.message",
      ev.type is EventType.MESSAGE_CREATED and ev.payload["message"].ref.message_id == "500")
ev = event_to_domain("message", native_msg, self_id="9")
check("event message mentioning self → APP_MENTION", ev.type is EventType.APP_MENTION)
ev = event_to_domain("message_edit", edited_msg)
check("event message_edit → MESSAGE_EDITED", ev.type is EventType.MESSAGE_EDITED)

raw_del = SimpleNamespace(message_id=500, channel_id=200, guild_id=100)
ev = event_to_domain("raw_message_delete", raw_del)
check("event raw delete → MESSAGE_DELETED + message_ref",
      ev.type is EventType.MESSAGE_DELETED and ev.payload["message_ref"].message_id == "500")

reaction = SimpleNamespace(emoji="👍", message=native_msg, user=user)
ev = event_to_domain("reaction_add", reaction)
check("event reaction_add → payload {message_ref, emoji} + actor",
      ev.type is EventType.REACTION_ADDED and ev.payload["emoji"] == "👍"
      and ev.payload["message_ref"].message_id == "500" and ev.actor.id == "8")
ev = event_to_domain("reaction_remove", reaction)
check("event reaction_remove → REACTION_REMOVED", ev.type is EventType.REACTION_REMOVED)

ev = event_to_domain("thread_create", thread)
check("event thread_create → THREAD_CREATED + Conversation",
      ev.type is EventType.THREAD_CREATED and ev.payload["conversation"].kind is ConversationKind.THREAD)
ev = event_to_domain("thread_delete", thread)
check("event thread_delete → conversation_ref", ev.payload["conversation_ref"].thread_id == "300")
ev = event_to_domain("guild_channel_create", text_channel)
check("event channel_create → CHANNEL_CREATED", ev.type is EventType.CHANNEL_CREATED)
ev = event_to_domain("member_join", member)
check("event member_join → USER_JOINED + user", ev.type is EventType.USER_JOINED and ev.payload["user"].id == "8")
ev = event_to_domain("member_remove", member)
check("event member_remove → USER_LEFT", ev.type is EventType.USER_LEFT)
ev = event_to_domain("totally_new_event", SimpleNamespace(id=1))
check("event unknown kind → UNKNOWN + raw", ev.type is EventType.UNKNOWN and "raw" in ev.payload)

# --- interactions → domain ---
def fake_native_interaction(type_name, data, iid=900):
    return SimpleNamespace(
        id=iid, type=SimpleNamespace(name=type_name), data=data,
        channel=text_channel, user=user, message=native_msg,
    )

i = interaction_to_domain(fake_native_interaction("component", {"component_type": 2, "custom_id": "ok_btn"}))
check("interaction button", i.type is InteractionType.BUTTON and i.custom_id == "ok_btn")
check("interaction carries actor/conversation/message",
      i.actor.id == "8" and i.conversation.conversation_id == "200" and i.message.message_id == "500")
i = interaction_to_domain(fake_native_interaction("component", {"component_type": 3, "custom_id": "sel", "values": ["a", "b"]}))
check("interaction select + values", i.type is InteractionType.SELECT and i.values == {"values": ["a", "b"]})
i = interaction_to_domain(fake_native_interaction(
    "modal_submit",
    {"custom_id": "form1", "components": [{"components": [{"custom_id": "fld", "value": "v"}]}]}))
check("interaction modal_submit + field values",
      i.type is InteractionType.MODAL_SUBMIT and i.custom_id == "form1" and i.values == {"fld": "v"})
i = interaction_to_domain(fake_native_interaction(
    "application_command", {"name": "deploy", "options": [{"name": "env", "value": "prod"}]}))
check("interaction command: name in custom_id, options in values",
      i.type is InteractionType.COMMAND and i.custom_id == "deploy" and i.values == {"env": "prod"})
check("interaction arrives unacked from pure fn (adapter owns acking)", i._acked is False)

# --- domain → payloads ---
rows = components_to_payload([ActionRow(components=[
    Button(custom_id="b1", label="Go", style="danger"),
    SelectMenu(custom_id="s1", options=[SelectOption(value="v", label="L", description="d")],
               placeholder="pick", min_values=1, max_values=2),
])])
check("components payload: row shape", rows[0]["type"] == 1 and len(rows[0]["components"]) == 2)
btn, sel = rows[0]["components"]
check("button payload", btn == {"type": 2, "style": 4, "label": "Go", "custom_id": "b1", "disabled": False})
check("select payload", sel["type"] == 3 and sel["options"][0]["value"] == "v"
      and sel["placeholder"] == "pick" and sel["max_values"] == 2)

mp = modal_to_payload(Modal(custom_id="m1", title="T", fields=[
    FormField(custom_id="f1", label="Name"),
    FormField(custom_id="f2", label="Notes", kind="multiline", required=False),
]))
check("modal payload: fields wrapped in rows, styles by kind",
      mp["custom_id"] == "m1"
      and mp["components"][0]["components"][0]["style"] == 1
      and mp["components"][1]["components"][0]["style"] == 2
      and mp["components"][1]["components"][0]["required"] is False)

cp = commands_to_payload([SlashCommand(name="task", description="d", options=[
    CommandOption(name="id", description="i", kind="integer", required=True)])])
check("commands payload: bulk-upsert shape",
      cp == [{"name": "task", "description": "d",
              "options": [{"type": 4, "name": "id", "description": "i", "required": True}]}])

# --- map_discord_error: full target matrix ---
class Forbidden(Exception): pass
class NotFound(Exception): pass
class HTTPException(Exception):
    def __init__(self, msg="", status=None, code=None):
        super().__init__(msg); self.status = status; self.code = code

for target in ("conversation", "message", "user", "attachment"):
    e = map_discord_error(Forbidden("no"), target=target)
    check(f"Forbidden→PermissionDenied (target={target})", type(e) is PermissionDenied)

check("NotFound×conversation → ConversationNotFound",
      type(map_discord_error(NotFound("x"), target="conversation")) is ConversationNotFound)
check("NotFound×message → base ChatError (no MessageNotFound in taxonomy)",
      type(map_discord_error(NotFound("x"), target="message")) is ChatError)
check("NotFound×user → UserNotFound",
      type(map_discord_error(NotFound("x"), target="user")) is UserNotFound)
check("NotFound×attachment → base ChatError",
      type(map_discord_error(NotFound("x"), target="attachment")) is ChatError)
check("429 → RateLimited",
      type(map_discord_error(HTTPException("slow", status=429), target="message")) is RateLimited)
check("413 → AttachmentTooLarge",
      type(map_discord_error(HTTPException("big", status=413), target="attachment")) is AttachmentTooLarge)
check("code 40005 → AttachmentTooLarge",
      type(map_discord_error(HTTPException("big", code=40005), target="attachment")) is AttachmentTooLarge)
check("unknown exception → base ChatError",
      type(map_discord_error(RuntimeError("?"), target="message")) is ChatError)


# ===================================================================== #
# Tier 2 — adapter-level, no-network
# ===================================================================== #

# --- fakes -----------------------------------------------------------------
class FakeMessage(SimpleNamespace):
    async def edit(self, **kwargs):
        self.content = kwargs.get("content", getattr(self, "content", ""))
        self.edited_at = now
        return self
    async def delete(self): self.deleted = True
    async def add_reaction(self, emoji): self.added = getattr(self, "added", []) + [emoji]
    async def remove_reaction(self, emoji, member): self.removed = getattr(self, "removed", []) + [(emoji, member.id)]
    async def create_thread(self, name=None):
        return SimpleNamespace(id=301, guild=guild, name=name, topic=None, parent_id=self.channel.id, archived=False)

def fake_message(mid=500, channel=None, **kw):
    base = dict(id=mid, channel=channel or text_channel, content="hi", author=user,
                created_at=now, edited_at=None, attachments=[], mentions=[],
                reactions=[], reference=None)
    base.update(kw)
    return FakeMessage(**base)

class FakeChannel:
    def __init__(self, cid=200, guild_obj=guild, fetch_message_exc=None, send_exc=None):
        self.id = cid; self.guild = guild_obj; self.parent_id = None
        self.name = "general"; self.topic = None
        self.send_calls = []; self.history_kwargs = None
        self._fetch_message_exc = fetch_message_exc
        self._send_exc = send_exc
        self._messages = {}
    async def send(self, content=None, **kwargs):
        if self._send_exc: raise self._send_exc
        self.send_calls.append((content, kwargs))
        sent = fake_message(mid=777, channel=self, content=content or "")
        if "file" in kwargs:
            f = kwargs["file"]
            sent.attachments = [SimpleNamespace(id=888, filename=f.filename, content_type=None,
                                                size=len(f.fp.getvalue()), url="http://cdn/up")]
        return sent
    async def fetch_message(self, mid):
        if self._fetch_message_exc: raise self._fetch_message_exc
        return self._messages.get(mid) or fake_message(mid=mid, channel=self)
    def history(self, **kwargs):
        self.history_kwargs = kwargs
        msgs = [fake_message(mid=2, channel=self, created_at=datetime(2026, 7, 5, 12, 2, tzinfo=timezone.utc)),
                fake_message(mid=1, channel=self, created_at=datetime(2026, 7, 5, 12, 1, tzinfo=timezone.utc))]
        async def gen():
            for m in msgs: yield m
        return gen()
    async def create_thread(self, name=None):
        return SimpleNamespace(id=302, guild=self.guild, name=name, topic=None, parent_id=self.id, archived=False)
    def permissions_for(self, member): return SimpleNamespace(view_channel=True)

class FakeHTTP:
    def __init__(self, session=None):
        self.session = session; self.guild_cmds = None; self.global_cmds = None
    async def bulk_upsert_guild_commands(self, app_id, guild_id, payload):
        self.guild_cmds = (app_id, guild_id, payload)
    async def bulk_upsert_global_commands(self, app_id, payload):
        self.global_cmds = (app_id, payload)

class FakeClient:
    def __init__(self, channels=None, users=None, fetch_channel_exc=None, fetch_user_exc=None):
        self.channels = channels or {}; self.users = users or {}
        self.http = FakeHTTP(); self.application_id = 4242
        self._fetch_channel_exc = fetch_channel_exc
        self._fetch_user_exc = fetch_user_exc
        self.guilds = []; self.private_channels = []
    def get_channel(self, cid): return self.channels.get(cid)
    async def fetch_channel(self, cid):
        if self._fetch_channel_exc: raise self._fetch_channel_exc
        if cid in self.channels: return self.channels[cid]
        raise NotFound(f"channel {cid}")
    def get_user(self, uid): return self.users.get(uid)
    async def fetch_user(self, uid):
        if self._fetch_user_exc: raise self._fetch_user_exc
        if uid in self.users: return self.users[uid]
        raise NotFound(f"user {uid}")

class FakeSDKButton(SimpleNamespace): pass
class FakeView:
    def __init__(self, timeout=None): self.items = []
    def add_item(self, item): self.items.append(item)
class FakeSDK(SimpleNamespace):
    """Records SDK-class constructions (view/modal/file builders)."""
def make_fake_sdk():
    ui = SimpleNamespace(
        View=FakeView,
        Button=lambda **kw: FakeSDKButton(kind="button", **kw),
        Select=lambda **kw: FakeSDKButton(kind="select", **kw),
        Modal=lambda **kw: FakeView() and SimpleNamespace(items=[], add_item=lambda self=None: None, **kw),
        TextInput=lambda **kw: FakeSDKButton(kind="text", **kw),
    )
    class _File:
        def __init__(self, fp, filename=None): self.fp = fp; self.filename = filename
    return SimpleNamespace(
        ui=ui, File=_File,
        ButtonStyle=SimpleNamespace(primary=1, secondary=2, success=3, danger=4, link=5),
        TextStyle=SimpleNamespace(short=1, paragraph=2),
        SelectOption=lambda **kw: FakeSDKButton(kind="option", **kw),
    )

CH_REF = ConversationRef(provider="discord", workspace_id="100", conversation_id="200")

def make_adapter(**kw):
    ch = FakeChannel()
    client = FakeClient(channels={200: ch})
    defaults = dict(guild_id=None, self_id="9", defer_delay=0.02, sdk=make_fake_sdk())
    defaults.update(kw)
    return DiscordAdapter(client, **defaults), client, ch


async def main():
    # --- ABC satisfaction / structural completeness nets -----------------
    adapter, client, ch = make_adapter()
    check("DiscordAdapter instantiates (all 26 abstract methods implemented)",
          isinstance(adapter, ChatAdapter))
    abstract = sorted(ChatAdapter.__abstractmethods__)
    check("ABC still pins 26 methods", len(abstract) == 26, f"got {len(abstract)}")
    check("subscribe is an async generator function",
          inspect.isasyncgenfunction(DiscordAdapter.subscribe))
    for name in abstract:
        check(f"signature pinned vs ABC: {name}",
              inspect.signature(getattr(DiscordAdapter, name)) ==
              inspect.signature(getattr(ChatAdapter, name)))
    src = inspect.getsource(sys.modules["chat.discord_adapter"])
    check("no hollow stubs (NotImplementedError absent from adapter source)",
          "NotImplementedError" not in src)

    # --- messaging through fakes ------------------------------------------
    msg = await adapter.send_message(CH_REF, "hello")
    check("send_message: text lands on channel.send", ch.send_calls[0][0] == "hello")
    check("send_message: returns normalized Message", msg.ref.message_id == "777")

    components = [ActionRow(components=[Button(custom_id="b", label="B")])]
    await adapter.send_message(CH_REF, "with view", components=components)
    view = ch.send_calls[1][1]["view"]
    check("send_message: components → built view with our button",
          isinstance(view, FakeView) and view.items[0].custom_id == "b")

    reply_ref = MessageRef(conversation=CH_REF, message_id="500")
    await adapter.send_message(CH_REF, "reply", reply_to=reply_ref)
    ref_obj = ch.send_calls[2][1]["reference"]
    check("send_message: reply_to → message reference (ids preserved)",
          ref_obj.message_id == 500 and ref_obj.channel_id == 200)

    sends_before = len(ch.send_calls)
    try:
        await adapter.send_message(CH_REF, "with files",
                                   attachments=[Attachment(id="1", filename="a.txt")])
        check("send_message: attachments rejected loudly (no silent partial send)", False)
    except ChatError as exc:
        check("send_message: attachments rejected loudly (no silent partial send)",
              type(exc) is ChatError and "upload_attachment" in str(exc))
    check("send_message: rejected attachments → no send happened (spy)",
          len(ch.send_calls) == sends_before)

    edited = await adapter.edit_message(reply_ref, "new text")
    check("edit_message: returns edited=True", edited.edited is True and edited.text == "new text")

    hist = await adapter.fetch_history(
        CH_REF,
        before=MessageRef(conversation=CH_REF, message_id="50"),
        after=MessageRef(conversation=CH_REF, message_id="10"),
        limit=7,
    )
    check("fetch_history: pagination args forwarded (limit/before/after ids)",
          ch.history_kwargs["limit"] == 7
          and ch.history_kwargs["before"].id == 50 and ch.history_kwargs["after"].id == 10)
    check("fetch_history: chronological order", [m.ref.message_id for m in hist] == ["1", "2"])

    # --- threads: both parent kinds -----------------------------------------
    t1 = await adapter.create_conversation(ConversationKind.THREAD, parent=reply_ref, name="from-msg")
    check("create_conversation THREAD from MessageRef → message thread",
          t1.kind is ConversationKind.THREAD and t1.ref.thread_id == "301")
    t2 = await adapter.create_conversation(ConversationKind.THREAD, parent=CH_REF, name="standalone")
    check("create_conversation THREAD from channel ref → standalone thread",
          t2.ref.thread_id == "302" and adapter.capabilities().supports_standalone_threads)
    try:
        await adapter.create_conversation(ConversationKind.THREAD)
        check("THREAD without parent raises ValueError", False)
    except ValueError:
        check("THREAD without parent raises ValueError", True)

    # --- ephemeral fallback chain -------------------------------------------
    # Native path: live interaction from the same actor+conversation.
    native_i = fake_native_interaction("component", {"component_type": 2, "custom_id": "x"}, iid=901)
    followup_sent = []
    async def followup_send(text, **kw):
        followup_sent.append((text, kw)); return fake_message(mid=910, content=text)
    native_i.followup = SimpleNamespace(send=followup_send)
    native_i.response = SimpleNamespace(defer=None)
    adapter._on_interaction(native_i)
    receipt = await adapter.send_ephemeral(CH_REF, Actor(id="8", type=ActorType.USER), "secret")
    check("ephemeral native path: followup ephemeral=True",
          receipt.path is EphemeralPath.NATIVE and followup_sent[0][1]["ephemeral"] is True)
    adapter._live.clear()

    # DM path: no live interaction → DM the actor.
    dm_sent = []
    async def dm_send(text, **kw):
        dm_sent.append(text); return fake_message(mid=920, channel=dm, content=text)
    client.users[8] = SimpleNamespace(id=8, name="ada", send=dm_send)
    receipt = await adapter.send_ephemeral(CH_REF, Actor(id="8", type=ActorType.USER), "psst")
    check("ephemeral DM fallback", receipt.path is EphemeralPath.DM and dm_sent == ["psst"])

    # Exhausted path: DM closed → DeliveryFailed, and NOTHING public.
    async def closed_dm(text, **kw): raise Forbidden("dm closed")
    client.users[8] = SimpleNamespace(id=8, name="ada", send=closed_dm)
    public_before = len(ch.send_calls)
    try:
        await adapter.send_ephemeral(CH_REF, Actor(id="8", type=ActorType.USER), "psst")
        check("ephemeral exhausted → DeliveryFailed", False)
    except DeliveryFailed:
        check("ephemeral exhausted → DeliveryFailed", True)
    check("ephemeral exhausted: no public post (construction spy)",
          len(ch.send_calls) == public_before)

    # --- files: upload/download round-trip + oversize pre-check --------------
    att = await adapter.upload_attachment(CH_REF, "a.txt", b"abc", mime_type="text/plain")
    check("upload: file posted with filename + bytes",
          ch.send_calls[-1][1]["file"].filename == "a.txt"
          and ch.send_calls[-1][1]["file"].fp.getvalue() == b"abc")
    check("upload: normalized Attachment (filename/size/url, mime preserved)",
          att.filename == "a.txt" and att.size == 3 and att.url == "http://cdn/up"
          and att.mime_type == "text/plain")

    class FakeResp:
        status = 200
        async def read(self): return b"abc"
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
    class FakeSession:
        def get(self, url): return FakeResp()
    client.http.session = FakeSession()
    data = await adapter.download_attachment(att)
    check("download: bytes round-trip through client session", data == b"abc")

    calls_before = len(ch.send_calls)
    big = b"x" * (adapter.capabilities().max_attachment_bytes + 1)
    try:
        await adapter.upload_attachment(CH_REF, "big.bin", big)
        check("oversize upload → AttachmentTooLarge", False)
    except AttachmentTooLarge:
        check("oversize upload → AttachmentTooLarge", True)
    check("oversize rejected BEFORE any send (construction spy)",
          len(ch.send_calls) == calls_before)

    # --- register_commands: guild vs global sync shape ------------------------
    specs = [SlashCommand(name="task", description="d")]
    await adapter.register_commands(specs)
    check("register_commands global: bulk upsert with app id",
          client.http.global_cmds == (4242, commands_to_payload(specs)))
    g_adapter, g_client, _ = make_adapter(guild_id="100")
    await g_adapter.register_commands(specs)
    check("register_commands guild-scoped: bulk upsert to guild",
          g_client.http.guild_cmds == (4242, 100, commands_to_payload(specs)))

    # --- error translation through REAL call sites ----------------------------
    nf_client = FakeClient(fetch_channel_exc=NotFound("gone"))
    nf_adapter = DiscordAdapter(nf_client, self_id="9", sdk=make_fake_sdk())
    try:
        await nf_adapter.fetch_conversation(CH_REF)
        check("channel resolve NotFound → ConversationNotFound", False)
    except ConversationNotFound:
        check("channel resolve NotFound → ConversationNotFound", True)

    mch = FakeChannel(fetch_message_exc=NotFound("msg gone"))
    m_adapter = DiscordAdapter(FakeClient(channels={200: mch}), self_id="9", sdk=make_fake_sdk())
    try:
        await m_adapter.fetch_message(MessageRef(conversation=CH_REF, message_id="1"))
        check("message fetch NotFound (channel OK) → base ChatError", False)
    except ChatError as exc:
        check("message fetch NotFound (channel OK) → base ChatError",
              type(exc) is ChatError, f"got {type(exc).__name__}")

    u_client = FakeClient(fetch_user_exc=NotFound("who"))
    u_adapter = DiscordAdapter(u_client, self_id="9", sdk=make_fake_sdk())
    try:
        await u_adapter.fetch_user("31337")
        check("user fetch NotFound → UserNotFound", False)
    except UserNotFound:
        check("user fetch NotFound → UserNotFound", True)

    perm_ch = FakeChannel(send_exc=Forbidden("no perms"))
    p_adapter = DiscordAdapter(FakeClient(channels={200: perm_ch}), self_id="9", sdk=make_fake_sdk())
    try:
        await p_adapter.send_message(CH_REF, "hi")
        check("send Forbidden → PermissionDenied", False)
    except PermissionDenied:
        check("send Forbidden → PermissionDenied", True)

    # --- identity through fakes ------------------------------------------------
    guild_live = SimpleNamespace(
        id=100, owner_id=7,
        get_member=lambda uid: member if uid == 8 else None,
    )
    id_ch = FakeChannel(); id_ch.guild = guild_live
    id_adapter = DiscordAdapter(FakeClient(channels={200: id_ch}), self_id="9", sdk=make_fake_sdk())
    claims = await id_adapter.fetch_identity_claims(CH_REF, "8")
    check("identity claims: roles + channel membership via permissions_for",
          claims.roles[0].name == "admins" and claims.is_channel_member is True)

    # --- reconciliation ---------------------------------------------------------
    rx_ch = FakeChannel()
    rx_ch._messages[42] = fake_message(mid=42, channel=rx_ch,
                                       reactions=[SimpleNamespace(emoji="✅", count=3, me=True)])
    rx_adapter = DiscordAdapter(FakeClient(channels={200: rx_ch}), self_id="9", sdk=make_fake_sdk())
    rx = await rx_adapter.fetch_reactions(MessageRef(conversation=CH_REF, message_id="42"))
    check("fetch_reactions: current set with honest count + me in metadata",
          rx[0].emoji == "✅" and rx[0].count == 3 and rx[0].metadata["me"] is True)

    # --- permalinks through the adapter (guild + DM) ------------------------------
    check("get_permalink message ref",
          await adapter.get_permalink(reply_ref) == "https://discord.com/channels/100/200/500")
    dm_ref = ConversationRef(provider="discord", workspace_id="@me", conversation_id="400")
    check("get_permalink DM ref uses @me",
          await adapter.get_permalink(dm_ref) == "https://discord.com/channels/@me/400")

    # --- subscription hub contract -------------------------------------------------
    sub_adapter, _, _ = make_adapter()

    async def collect(agen, n):
        out = []
        for _ in range(n):
            out.append(await asyncio.wait_for(agen.__anext__(), 1))
        return out

    a1 = sub_adapter.subscribe()
    a2 = sub_adapter.subscribe()
    t1_task = asyncio.create_task(collect(a1, 1))
    t2_task = asyncio.create_task(collect(a2, 1))
    await asyncio.sleep(0)  # let both subscribers register
    sub_adapter._publish("message", native_msg)
    r1, r2 = await t1_task, await t2_task
    check("hub: two concurrent subscribers each receive the event (independent streams)",
          r1[0].payload["message"].ref.message_id == "500"
          and r2[0].payload["message"].ref.message_id == "500")

    other_ref = ConversationRef(provider="discord", workspace_id="100", conversation_id="999")
    af = sub_adapter.subscribe(conversations=[other_ref])
    tf = asyncio.create_task(collect(af, 1))
    await asyncio.sleep(0)
    sub_adapter._publish("message", native_msg)          # channel 200 — filtered out
    other_msg = fake_message(mid=43, channel=SimpleNamespace(
        id=999, guild=guild, name="o", topic=None, parent_id=None))
    sub_adapter._publish("message", other_msg)           # channel 999 — matches
    got = await tf
    check("hub: conversation filtering at enqueue time",
          got[0].payload["message"].ref.message_id == "43")
    await af.aclose()

    a_since = sub_adapter.subscribe(since=now.timestamp() + 100)
    ts_task = asyncio.create_task(collect(a_since, 1))
    await asyncio.sleep(0)
    sub_adapter._publish("message", native_msg)          # timestamp == now → too old
    late = fake_message(mid=44, created_at=datetime(2026, 7, 5, 13, 0, tzinfo=timezone.utc))
    sub_adapter._publish("message", late)
    got = await ts_task
    check("hub: since filters older events", got[0].payload["message"].ref.message_id == "44")
    await a_since.aclose()

    ag = sub_adapter.subscribe()
    tg = asyncio.create_task(collect(ag, 1))
    await asyncio.sleep(0)
    n_subs = len(sub_adapter._hub._subscribers)
    tg.cancel()
    try: await tg
    except asyncio.CancelledError: pass
    await ag.aclose()
    check("hub: generator close deregisters the subscriber",
          len(sub_adapter._hub._subscribers) == n_subs - 1)

    # Overflow: slow subscriber is disconnected (sentinel, never a silent
    # drop); fast subscriber is unaffected. Hub-level for determinism —
    # publishes are synchronous, so a stalled consumer is just an undrained
    # bounded queue.
    hub = sub_adapter._hub
    # The hub lives in the shared chat._subscription module (t1074_3):
    # _Subscriber reads the bound from ITS module globals, so the
    # monkeypatch must target that module, not the da re-export.
    import chat._subscription as subs
    subs.SUBSCRIBER_QUEUE_MAXSIZE = 2
    slow_sub = da._Subscriber(None, None)     # bounded at 2
    subs.SUBSCRIBER_QUEUE_MAXSIZE = 1024
    fast_sub = da._Subscriber(None, None)
    hub.add(slow_sub)
    hub.add(fast_sub)
    for i in range(4):
        sub_adapter._publish("message", fake_message(mid=50 + i))
    check("hub overflow: fast subscriber unaffected (all 4 delivered)",
          fast_sub in hub._subscribers and fast_sub.queue.qsize() == 4)
    check("hub overflow: slow subscriber removed from hub", slow_sub not in hub._subscribers)
    check("hub overflow: slow queue drained + ends with the disconnect sentinel",
          slow_sub.queue.qsize() == 1 and slow_sub.queue.get_nowait() is da._DISCONNECT)
    hub.remove(fast_sub)

    ad = sub_adapter.subscribe()
    td = asyncio.create_task(collect(ad, 1))
    await asyncio.sleep(0)
    sub_adapter._hub.disconnect_all()
    ended = []
    try:
        ended = await td
        check("hub disconnect: stream ends with no replay", False)
    except (StopAsyncIteration, asyncio.TimeoutError):
        check("hub disconnect: stream ends with no replay", True)
    check("hub disconnect: all subscribers cleared", len(sub_adapter._hub._subscribers) == 0)

    # --- delayed-defer scheme (owned ack) --------------------------------------------
    d_adapter, _, _ = make_adapter(defer_delay=0.03)

    def live_interaction(iid):
        n = fake_native_interaction("component", {"component_type": 2, "custom_id": "x"}, iid=iid)
        state = SimpleNamespace(deferred=False, modal=None, initial=None)
        async def defer(): state.deferred = True
        async def send_message(text, **kw): state.initial = (text, kw)
        async def send_modal(m): state.modal = m
        n.response = SimpleNamespace(defer=defer, send_message=send_message, send_modal=send_modal)
        async def fu_send(text, **kw): return fake_message(mid=930, content=text)
        n.followup = SimpleNamespace(send=fu_send)
        return n, state

    n1, s1 = live_interaction(950)
    # Regression (post-review): the INTERACTION_RECEIVED event must carry the
    # SAME ack-owned Interaction object — not a re-normalized _acked=False copy.
    evt_sub = da._Subscriber(None, None)
    d_adapter._hub.add(evt_sub)
    dom1 = d_adapter._on_interaction(n1)
    evt = evt_sub.queue.get_nowait()
    check("interaction yielded _acked=True (adapter owns the deadline)", dom1._acked is True)
    check("published INTERACTION_RECEIVED carries the identical ack-owned object",
          evt.type is EventType.INTERACTION_RECEIVED
          and evt.payload["interaction"] is dom1
          and evt.payload["interaction"]._acked is True)
    d_adapter._hub.remove(evt_sub)
    await d_adapter.open_modal(dom1, Modal(custom_id="m", title="T", fields=[]))
    check("open_modal before defer: modal sent as initial response", s1.modal is not None)
    await asyncio.sleep(0.06)
    check("open_modal cancelled the scheduled defer (never fired)", s1.deferred is False)

    n2, s2 = live_interaction(951)
    dom2 = d_adapter._on_interaction(n2)
    await asyncio.sleep(0.06)   # let the scheduled defer fire
    check("scheduled defer fired within the window", s2.deferred is True)
    try:
        await d_adapter.open_modal(dom2, Modal(custom_id="m", title="T", fields=[]))
        check("open_modal after defer → InteractionExpired (window closed)", False)
    except InteractionExpired:
        check("open_modal after defer → InteractionExpired (window closed)", True)
    got = await d_adapter.respond(dom2, "late but fine")
    check("respond after defer: follow-up webhook path returns Message",
          got is not None and got.text == "late but fine")

    n3, s3 = live_interaction(952)
    dom3 = d_adapter._on_interaction(n3)
    r = await d_adapter.respond(dom3, "fast", ephemeral=True)
    check("respond before defer: initial response with ephemeral flag",
          s3.initial == ("fast", {"ephemeral": True}))
    await asyncio.sleep(0.06)
    check("consumer response cancelled the scheduled defer", s3.deferred is False)

    await d_adapter.ack(dom3)
    await d_adapter.ack(dom3)
    check("ack idempotent no-op", dom3._acked is True)

    try:
        await d_adapter.respond(Interaction(
            id="unknown", type=InteractionType.BUTTON,
            actor=Actor(id="8", type=ActorType.USER), conversation=CH_REF), "x")
        check("respond on unknown/expired interaction → InteractionExpired", False)
    except InteractionExpired:
        check("respond on unknown/expired interaction → InteractionExpired", True)

    # ================================================================= #
    # t1149_5 — close() / connect() teardown / fetch_bot_permissions
    # ================================================================= #

    # --- close(): duck-typed teardown --------------------------------- #
    class ClosableClient(FakeClient):
        def __init__(self, **kw):
            super().__init__(**kw)
            self.closed = 0
        async def close(self):
            self.closed += 1

    cc = ClosableClient()
    c_adapter = DiscordAdapter(cc, self_id="9", sdk=make_fake_sdk())
    await c_adapter.close()
    check("close() awaits the client's async close", cc.closed == 1)

    plain_adapter, _pc, _ = make_adapter()
    await plain_adapter.close()   # FakeClient has no close — must not raise
    check("close() is a no-op on a client without close", True)

    cc2 = ClosableClient()
    g_adapter = DiscordAdapter(cc2, self_id="9", sdk=make_fake_sdk())
    async def _late_gateway_error():
        raise RuntimeError("late gateway error")
    g_adapter._gateway_task = asyncio.get_running_loop().create_task(
        _late_gateway_error())
    await asyncio.sleep(0)  # let the task finish
    await g_adapter.close()
    check("close() consumes the gateway task outcome",
          g_adapter._gateway_task is None)

    # --- connect(): failure-path teardown via a fake discord module --- #
    class FakeGatewayClient:
        next_config = {}
        last = None
        def __init__(self, intents=None):
            cfg = dict(FakeGatewayClient.next_config)
            self.intents = intents
            self.login_exc = cfg.get("login_exc")
            self.gateway_mode = cfg.get("gateway_mode", "run")
            self.gateway_exc = cfg.get("gateway_exc")
            self.close_hang_s = cfg.get("close_hang_s", 0)
            self.closed = 0
            self.user = SimpleNamespace(id=99)
            self._ready = asyncio.Event()
            if cfg.get("ready"):
                self._ready.set()
            self._stop = asyncio.Event()
            FakeGatewayClient.last = self
        def event(self, fn):
            return fn
        async def login(self, token):
            if self.login_exc:
                raise self.login_exc
        async def connect(self, reconnect=True):
            if self.gateway_mode == "raise":
                raise self.gateway_exc
            if self.gateway_mode == "return":
                return
            await self._stop.wait()
        async def wait_until_ready(self):
            await self._ready.wait()
        async def close(self):
            self.closed += 1
            if self.close_hang_s:
                await asyncio.sleep(self.close_hang_s)
            self._stop.set()

    class LoginFailure(Exception): pass
    class PrivilegedIntentsRequired(Exception): pass

    fake_discord = SimpleNamespace(
        Intents=SimpleNamespace(
            default=lambda: SimpleNamespace(
                members=False, message_content=False)),
        Client=FakeGatewayClient,
        LoginFailure=LoginFailure,
        PrivilegedIntentsRequired=PrivilegedIntentsRequired,
    )
    sys.modules["discord"] = fake_discord
    saved_cleanup_timeout = da.CONNECT_CLEANUP_TIMEOUT_S
    try:
        def pending_tasks():
            return {t for t in asyncio.all_tasks()
                    if t is not asyncio.current_task() and not t.done()}

        # login failure → client closed, exception surfaced
        before = pending_tasks()
        FakeGatewayClient.next_config = {"login_exc": LoginFailure("bad")}
        try:
            await DiscordAdapter.connect("tok")
            check("connect(): login failure raises", False)
        except LoginFailure:
            check("connect(): login failure raises", True)
        check("connect(): login failure closes the client",
              FakeGatewayClient.last.closed == 1)
        check("connect(): login failure leaves no pending tasks",
              pending_tasks() == before)

        # gateway task fails pre-ready → surfaced (no hang), client closed
        FakeGatewayClient.next_config = {
            "gateway_mode": "raise",
            "gateway_exc": PrivilegedIntentsRequired("intents"),
        }
        try:
            await asyncio.wait_for(DiscordAdapter.connect("tok"), 5)
            check("connect(): gateway failure pre-ready surfaces", False)
        except PrivilegedIntentsRequired:
            check("connect(): gateway failure pre-ready surfaces", True)
        check("connect(): gateway failure closes the client",
              FakeGatewayClient.last.closed == 1)
        check("connect(): gateway failure leaves no pending tasks",
              pending_tasks() == before)

        # gateway task returns CLEANLY pre-ready → deterministic fallback
        FakeGatewayClient.next_config = {"gateway_mode": "return"}
        try:
            await asyncio.wait_for(DiscordAdapter.connect("tok"), 5)
            check("connect(): clean gateway exit pre-ready raises fallback",
                  False)
        except RuntimeError as exc:
            check("connect(): clean gateway exit pre-ready raises fallback",
                  "gateway closed before becoming ready" in str(exc))
        check("connect(): clean-exit path leaves no pending tasks",
              pending_tasks() == before)

        # hanging client.close() cannot stall the cleanup past the bound
        da.CONNECT_CLEANUP_TIMEOUT_S = 0.05
        FakeGatewayClient.next_config = {
            "login_exc": LoginFailure("bad"), "close_hang_s": 30}
        t0 = asyncio.get_running_loop().time()
        try:
            await DiscordAdapter.connect("tok")
        except LoginFailure:
            pass
        elapsed = asyncio.get_running_loop().time() - t0
        check("connect(): hanging close is bounded by the cleanup timeout",
              elapsed < 2, f"elapsed={elapsed:.2f}s")
        da.CONNECT_CLEANUP_TIMEOUT_S = saved_cleanup_timeout

        # success path: ready fires, adapter returned, close() consumes all
        FakeGatewayClient.next_config = {"ready": True}
        live_adapter = await asyncio.wait_for(DiscordAdapter.connect("tok"), 5)
        check("connect(): success returns a ready adapter with self_id",
              live_adapter._self_id == "99")
        check("connect(): success stores the gateway task",
              live_adapter._gateway_task is not None
              and not live_adapter._gateway_task.done())
        await live_adapter.close()
        check("connect()+close(): gateway task consumed, no pending tasks",
              live_adapter._gateway_task is None
              and pending_tasks() == before)
        check("connect()+close(): client closed once",
              FakeGatewayClient.last.closed == 1)

        # cancellation-RESISTANT gateway task: the failure-path awaits are
        # bounded too, so a caller-side wait_for deadline is enforced even
        # when the gateway task refuses to die promptly. (Last in this
        # section: the abandoned resistant task drains on its own below.)
        class ResistantClient(FakeGatewayClient):
            async def connect(self, reconnect=True):
                try:
                    await self._stop.wait()
                except asyncio.CancelledError:
                    await asyncio.sleep(0.5)   # resist prompt cancellation
                    raise
        fake_discord.Client = ResistantClient
        # __init__ reads the BASE class attribute — reset it there.
        FakeGatewayClient.next_config = {}     # never ready, gateway runs
        da.CONNECT_CLEANUP_TIMEOUT_S = 0.05
        t0 = asyncio.get_running_loop().time()
        try:
            await asyncio.wait_for(DiscordAdapter.connect("tok"), 0.1)
            check("connect(): resistant gateway still times out", False)
        except asyncio.TimeoutError:
            check("connect(): resistant gateway still times out", True)
        elapsed = asyncio.get_running_loop().time() - t0
        check("connect(): resistant-gateway cleanup is bounded",
              elapsed < 1.0, f"elapsed={elapsed:.2f}s")
        check("connect(): resistant-gateway path still closes the client",
              ResistantClient.last.closed == 1)
        await asyncio.sleep(0.6)               # drain the abandoned task
    finally:
        da.CONNECT_CLEANUP_TIMEOUT_S = saved_cleanup_timeout
        del sys.modules["discord"]

    # --- fetch_bot_permissions ---------------------------------------- #
    def perm_guild(member=None, fetch_member_result=None, fetch_exc=None):
        async def fetch_member(uid):
            if fetch_exc:
                raise fetch_exc
            if fetch_member_result is not None:
                return fetch_member_result
            raise NotFound("no member")
        return SimpleNamespace(id=100, get_member=lambda uid: member,
                               fetch_member=fetch_member)

    class PermCheckChannel(FakeChannel):
        def __init__(self, perms, **kw):
            super().__init__(**kw)
            self._bot_perms = perms
            self.perm_member = None
        def permissions_for(self, member):
            self.perm_member = member
            return self._bot_perms

    bot_member = SimpleNamespace(id=9, roles=[])
    perms_ns = SimpleNamespace(view_channel=True, send_messages=True,
                               manage_messages=False)
    p_ch = PermCheckChannel(perms_ns,
                            guild_obj=perm_guild(member=bot_member))
    p_adapter2 = DiscordAdapter(FakeClient(channels={200: p_ch}),
                                self_id="9", sdk=make_fake_sdk())
    got = await p_adapter2.fetch_bot_permissions(
        CH_REF, ("view_channel", "send_messages", "manage_messages",
                 "not_a_real_perm"))
    check("fetch_bot_permissions reports the requested names",
          got == {"view_channel": True, "send_messages": True,
                  "manage_messages": False, "not_a_real_perm": False})
    check("fetch_bot_permissions used the cached bot member",
          p_ch.perm_member is bot_member)

    # cache miss → fetch_member fallback
    p_ch2 = PermCheckChannel(
        perms_ns, guild_obj=perm_guild(member=None,
                                       fetch_member_result=bot_member))
    p_adapter3 = DiscordAdapter(FakeClient(channels={200: p_ch2}),
                                self_id="9", sdk=make_fake_sdk())
    got2 = await p_adapter3.fetch_bot_permissions(CH_REF, ("view_channel",))
    check("fetch_bot_permissions falls back to fetch_member",
          got2 == {"view_channel": True}
          and p_ch2.perm_member is bot_member)

    # both member paths fail → distinct mapped user error (not a perm map)
    p_ch3 = PermCheckChannel(
        perms_ns, guild_obj=perm_guild(member=None,
                                       fetch_exc=NotFound("who")))
    p_adapter4 = DiscordAdapter(FakeClient(channels={200: p_ch3}),
                                self_id="9", sdk=make_fake_sdk())
    try:
        await p_adapter4.fetch_bot_permissions(CH_REF, ("view_channel",))
        check("fetch_bot_permissions member failure → UserNotFound", False)
    except UserNotFound:
        check("fetch_bot_permissions member failure → UserNotFound", True)

    # DM channel (no guild) → {} (no guild permission model)
    dm_ch = FakeChannel(guild_obj=None)
    dm_adapter2 = DiscordAdapter(FakeClient(channels={200: dm_ch}),
                                 self_id="9", sdk=make_fake_sdk())
    check("fetch_bot_permissions on a DM returns {}",
          await dm_adapter2.fetch_bot_permissions(
              CH_REF, ("view_channel",)) == {})

    # channel without permissions_for → deliberate ChatError, not an
    # AttributeError-shaped surprise
    class NoPermsChannel(FakeChannel):
        permissions_for = None
    np_ch = NoPermsChannel(guild_obj=perm_guild(member=bot_member))
    np_adapter = DiscordAdapter(FakeClient(channels={200: np_ch}),
                                self_id="9", sdk=make_fake_sdk())
    try:
        await np_adapter.fetch_bot_permissions(CH_REF, ("view_channel",))
        check("fetch_bot_permissions without permissions_for → ChatError",
              False)
    except ChatError as exc:
        check("fetch_bot_permissions without permissions_for → ChatError",
              "cannot inspect bot permissions" in str(exc))


asyncio.run(main())
assert "discord" not in sys.modules, "no test path may import the SDK"
print(f"\nPASS: {PASS} checks")
PYEOF
