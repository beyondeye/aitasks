#!/usr/bin/env bash
# test_chat_slack.sh — SlackAdapter tests (t1074_3).
#
# Two tiers, both no-network and SDK-free (`slack_sdk`/`slack_bolt` are NEVER
# imported — everything runs against plain-dict payloads and async fakes):
#   Tier 1: pure normalization functions (platform→domain, domain→payload,
#           permalinks, the map_slack_error string×target matrix).
#   Tier 2: adapter-level behavior — ABC satisfaction/signature pinning,
#           method behavior through a fake Web API client (incl. cursor
#           pagination, the fetch_message exact-ts guard, the ephemeral
#           DM-fallback matrix and thread_ts upload propagation), the
#           instant-ack interaction scheme, and the shared subscription hub.
# Run: bash tests/test_chat_slack.sh

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
from pathlib import Path
from types import SimpleNamespace

root = Path(sys.argv[1])
sys.path.insert(0, str(root / ".aitask-scripts"))

# Guard: this suite must run on the stock venv — no SDK anywhere.
assert "slack_sdk" not in sys.modules and "slack_bolt" not in sys.modules

import chat
from chat.adapter import ChatAdapter
from chat.errors import (
    AttachmentTooLarge, ChatError, ConversationNotFound, DeliveryFailed,
    InteractionExpired, PermissionDenied, RateLimited, UserNotFound,
)
from chat.interactions import (
    ActionRow, Button, FormField, Interaction, InteractionType, Modal,
    SelectMenu, SelectOption, SlashCommand,
)
from chat.model import (
    Actor, ActorType, ConversationKind, ConversationRef,
    EphemeralPath, EventType, MessageRef,
)
import chat.slack_adapter as sa
from chat.slack_adapter import (
    SlackAdapter, build_permalink, channel_to_conversation, channel_to_ref,
    components_to_payload, conversation_kind, event_to_domain,
    interaction_to_domain, map_slack_error, member_to_claims,
    message_to_domain, modal_to_payload, thread_ref, user_to_domain,
)

assert "slack_sdk" not in sys.modules and "slack_bolt" not in sys.modules, \
    "importing slack_adapter must not import the SDKs"

PASS = 0
def check(label, cond, detail=""):
    global PASS
    assert cond, f"FAIL: {label} {detail}"
    PASS += 1
    print(f"ok - {label}")


# ===================================================================== #
# Tier 1 — pure normalization
# ===================================================================== #

# --- permalink (conversation-level deep link) ---
check("permalink app_redirect form",
      build_permalink("T1", "C1") == "https://slack.com/app_redirect?team=T1&channel=C1")

# --- conversation kinds ---
check("kind: public channel", conversation_kind({"id": "C1"}) is ConversationKind.CHANNEL)
check("kind: im → DIRECT", conversation_kind({"id": "D1", "is_im": True}) is ConversationKind.DIRECT)
check("kind: mpim → PRIVATE", conversation_kind({"id": "G1", "is_mpim": True}) is ConversationKind.PRIVATE)
check("kind: private channel → PRIVATE",
      conversation_kind({"id": "G2", "is_private": True}) is ConversationKind.PRIVATE)
check("kind: legacy group → PRIVATE",
      conversation_kind({"id": "G3", "is_group": True}) is ConversationKind.PRIVATE)

cref = channel_to_ref({"id": "C1"}, team_id="T1")
check("channel ref: provider/workspace/id",
      cref.provider == "slack" and cref.workspace_id == "T1" and cref.conversation_id == "C1")
tref = thread_ref("C1", "111.222", team_id="T1")
check("thread ref: channel as conversation_id, thread_ts as thread_id",
      tref.conversation_id == "C1" and tref.thread_id == "111.222")

conv = channel_to_conversation(
    {"id": "C1", "name": "general", "topic": {"value": "t"}, "is_archived": False}, team_id="T1")
check("conversation: name/topic/kind", conv.name == "general" and conv.topic == "t"
      and conv.kind is ConversationKind.CHANNEL)

# --- users / actors / claims ---
u = user_to_domain({"id": "U1", "name": "ada", "is_bot": False,
                    "profile": {"display_name": "Ada", "email": "a@x.io", "image_512": "http://av"}})
check("user_to_domain basics", u.id == "U1" and u.display_name == "Ada"
      and u.username == "ada" and u.email == "a@x.io" and not u.is_bot)
u2 = user_to_domain({"id": "U2", "name": "b", "profile": {}})
check("user email stays None when platform omits it", u2.email is None)

claims = member_to_claims(
    {"id": "U1", "is_admin": True, "is_owner": False},
    [{"id": "S1", "name": "devs"}], is_channel_member=True)
check("claims: admin flag + usergroup role kind",
      claims.is_workspace_admin and not claims.is_owner and claims.is_channel_member
      and claims.roles[0].kind == "slack_usergroup" and claims.roles[0].name == "devs")
check("claims: absent knowledge stays empty/False",
      member_to_claims({"id": "U9"}, []).roles == []
      and not member_to_claims({"id": "U9"}, []).is_workspace_admin)

# --- messages ---
m = message_to_domain(
    {"ts": "1000.1", "user": "U1", "text": "hi <@U9> and <@U8|bob>",
     "edited": {"user": "U1"}, "files": [{"id": "F1", "name": "a.txt", "mimetype": "text/plain",
                                          "size": 3, "url_private": "http://f"}],
     "reactions": [{"name": "tada", "count": 2, "users": ["U1", "U9"]}]},
    channel="C1", team_id="T1", self_id="UBOT")
check("message: ts float + ts-as-id", m.timestamp == 1000.1 and m.ref.message_id == "1000.1")
check("message: mentions parsed from <@U…> tokens",
      [x.user_id for x in m.mentions] == ["U9", "U8"])
check("message: edited flag", m.edited is True)
check("message: files → attachments (url_private)",
      m.attachments[0].filename == "a.txt" and m.attachments[0].url == "http://f")
check("message: reactions honest user_ids", m.reactions[0].user_ids == ["U1", "U9"]
      and m.reactions[0].emoji == "tada")
check("message: channel-level ref (no thread)", m.ref.conversation.thread_id is None)

mt = message_to_domain({"ts": "1000.2", "thread_ts": "1000.1", "user": "U1", "text": "reply"},
                       channel="C1", team_id="T1")
check("thread message: ref carries thread_id + reply_to parent",
      mt.ref.conversation.thread_id == "1000.1"
      and mt.reply_to is not None and mt.reply_to.message_id == "1000.1")
mp = message_to_domain({"ts": "1000.1", "thread_ts": "1000.1", "user": "U1", "text": "parent"},
                       channel="C1", team_id="T1")
check("thread parent: channel-level ref, no reply_to",
      mp.ref.conversation.thread_id is None and mp.reply_to is None)

# --- events ---
e = event_to_domain({"type": "message", "channel": "C1", "user": "U1",
                     "text": "hello", "ts": "1.0", "event_ts": "1.0"}, team_id="T1", self_id="UBOT")
check("event: plain message → MESSAGE_CREATED", e.type is EventType.MESSAGE_CREATED
      and e.payload["message"].text == "hello")
e = event_to_domain({"type": "message", "channel": "C1", "user": "U1",
                     "text": "yo <@UBOT>", "ts": "1.1"}, team_id="T1", self_id="UBOT")
check("event: self-mention in message → APP_MENTION", e.type is EventType.APP_MENTION)
e = event_to_domain({"type": "app_mention", "channel": "C1", "user": "U1",
                     "text": "yo <@UBOT>", "ts": "1.1"}, team_id="T1", self_id="UBOT")
check("event: app_mention envelope also normalizes to APP_MENTION (pure fn completeness)",
      e.type is EventType.APP_MENTION)
e = event_to_domain({"type": "message", "subtype": "message_changed", "channel": "C1",
                     "message": {"ts": "2.0", "user": "U1", "text": "new"}, "event_ts": "2.5"},
                    team_id="T1")
check("event: message_changed → MESSAGE_EDITED with edited=True",
      e.type is EventType.MESSAGE_EDITED and e.payload["message"].edited is True)
e = event_to_domain({"type": "message", "subtype": "message_deleted", "channel": "C1",
                     "deleted_ts": "3.0", "event_ts": "3.5"}, team_id="T1")
check("event: message_deleted → MESSAGE_DELETED with message_ref",
      e.type is EventType.MESSAGE_DELETED and e.payload["message_ref"].message_id == "3.0")
e = event_to_domain({"type": "reaction_added", "user": "U1", "reaction": "eyes",
                     "item": {"type": "message", "channel": "C1", "ts": "4.0"},
                     "event_ts": "4.5"}, team_id="T1")
check("event: reaction_added payload contract",
      e.type is EventType.REACTION_ADDED and e.payload["emoji"] == "eyes"
      and e.payload["message_ref"].message_id == "4.0" and e.actor.id == "U1")
e = event_to_domain({"type": "reaction_removed", "user": "U1", "reaction": "eyes",
                     "item": {"channel": "C1", "ts": "4.0"}}, team_id="T1")
check("event: reaction_removed", e.type is EventType.REACTION_REMOVED)
e = event_to_domain({"type": "member_joined_channel", "user": "U5", "channel": "C1",
                     "event_ts": "5.0"}, team_id="T1")
check("event: member_joined → USER_JOINED with User payload",
      e.type is EventType.USER_JOINED and e.payload["user"].id == "U5")
e = event_to_domain({"type": "member_left_channel", "user": "U5", "channel": "C1"}, team_id="T1")
check("event: member_left → USER_LEFT", e.type is EventType.USER_LEFT)
e = event_to_domain({"type": "channel_created",
                     "channel": {"id": "C9", "name": "new"}, "event_ts": "6.0"}, team_id="T1")
check("event: channel_created → CHANNEL_CREATED with Conversation",
      e.type is EventType.CHANNEL_CREATED and e.payload["conversation"].name == "new")
e = event_to_domain({"type": "file_shared", "file_id": "F7", "user_id": "U1",
                     "channel_id": "C1", "event_ts": "7.0"}, team_id="T1")
check("event: file_shared → FILE_UPLOADED (honest minimal attachment)",
      e.type is EventType.FILE_UPLOADED and e.payload["attachment"].id == "F7"
      and e.payload["message_ref"] is None)
e = event_to_domain({"type": "team_join", "user": {"id": "U1"}}, team_id="T1")
check("event: unmapped type → UNKNOWN with raw payload",
      e.type is EventType.UNKNOWN and e.payload["raw"]["type"] == "team_join")
e = event_to_domain({"type": "message", "subtype": "channel_join", "channel": "C1"}, team_id="T1")
check("event: unmapped message subtype → UNKNOWN", e.type is EventType.UNKNOWN)

# --- interactions ---
btn = interaction_to_domain(
    {"type": "block_actions", "trigger_id": "tr1", "user": {"id": "U1", "name": "ada"},
     "team": {"id": "T1"}, "channel": {"id": "C1"},
     "container": {"message_ts": "8.0"},
     "actions": [{"type": "button", "action_id": "approve", "action_ts": "8.1"}],
     "response_url": "http://ru"})
check("interaction: button (custom_id=action_id, id=trigger_id)",
      btn.type is InteractionType.BUTTON and btn.custom_id == "approve" and btn.id == "tr1"
      and btn.message is not None and btn.message.message_id == "8.0")
sel = interaction_to_domain(
    {"type": "block_actions", "trigger_id": "tr2", "user": {"id": "U1"},
     "team": {"id": "T1"}, "channel": {"id": "C1"},
     "actions": [{"type": "static_select", "action_id": "pick",
                  "selected_option": {"value": "v1"}}]})
check("interaction: single select values", sel.type is InteractionType.SELECT
      and sel.values == {"values": ["v1"]})
msel = interaction_to_domain(
    {"type": "block_actions", "trigger_id": "tr3", "user": {"id": "U1"},
     "channel": {"id": "C1"},
     "actions": [{"type": "multi_static_select", "action_id": "pickN",
                  "selected_options": [{"value": "a"}, {"value": "b"}]}]})
check("interaction: multi select values", msel.values == {"values": ["a", "b"]})
vs = interaction_to_domain(
    {"type": "view_submission", "trigger_id": "tr4", "user": {"id": "U1"},
     "team": {"id": "T1"},
     "view": {"callback_id": "myform",
              "state": {"values": {
                  "blk1": {"field_a": {"type": "plain_text_input", "value": "hello"}},
                  "blk2": {"field_b": {"type": "static_select",
                                       "selected_option": {"value": "x"}}}}}}})
check("interaction: view_submission flattens state to {custom_id: value}",
      vs.type is InteractionType.MODAL_SUBMIT and vs.custom_id == "myform"
      and vs.values == {"field_a": "hello", "field_b": "x"})
cmd = interaction_to_domain(
    {"command": "/deploy", "text": "prod now", "trigger_id": "tr5",
     "user_id": "U1", "channel_id": "C1", "team_id": "T1",
     "response_url": "http://ru2"})
check("interaction: slash command (name stripped, text in values)",
      cmd.type is InteractionType.COMMAND and cmd.custom_id == "deploy"
      and cmd.values == {"text": "prod now"} and cmd.conversation.conversation_id == "C1")
thr_i = interaction_to_domain(
    {"type": "block_actions", "trigger_id": "tr6", "user": {"id": "U1"},
     "team": {"id": "T1"}, "channel": {"id": "C1"},
     "container": {"message_ts": "9.0", "thread_ts": "8.5"},
     "actions": [{"action_id": "x"}]})
check("interaction: container thread_ts → thread-scoped conversation ref",
      thr_i.conversation.thread_id == "8.5")

# --- domain → payload ---
blocks = components_to_payload([ActionRow(components=[
    Button(custom_id="ok", label="OK", style="primary"),
    Button(custom_id="meh", label="Meh", style="secondary"),
    SelectMenu(custom_id="pick", options=[SelectOption(value="v", label="V", description="d")],
               placeholder="choose"),
    SelectMenu(custom_id="pickN", options=[SelectOption(value="v", label="V")], max_values=3),
])])
els = blocks[0]["elements"]
check("blocks: actions block with button style mapping",
      blocks[0]["type"] == "actions" and els[0]["style"] == "primary" and "style" not in els[1])
check("blocks: static_select with placeholder + option description",
      els[2]["type"] == "static_select" and els[2]["placeholder"]["text"] == "choose"
      and els[2]["options"][0]["description"]["text"] == "d")
check("blocks: max_values>1 → multi_static_select", els[3]["type"] == "multi_static_select")

view = modal_to_payload(Modal(custom_id="f", title="Form", fields=[
    FormField(custom_id="a", label="A"),
    FormField(custom_id="b", label="B", kind="multiline", required=False, placeholder="…"),
]))
check("modal: view shape (callback_id/title/submit)",
      view["type"] == "modal" and view["callback_id"] == "f"
      and view["title"]["text"] == "Form" and view["submit"]["text"] == "Submit")
check("modal: input blocks (action_id, multiline, optional)",
      view["blocks"][0]["element"]["action_id"] == "a"
      and view["blocks"][0]["element"]["multiline"] is False
      and view["blocks"][1]["element"]["multiline"] is True
      and view["blocks"][1]["optional"] is True)

# --- map_slack_error matrix ---
def api_err(error=None, status=None):
    exc = SimpleNamespace  # noqa: F841 (readability)
    class SlackApiError(Exception):
        pass
    e = SlackApiError(error or "boom")
    if error is not None:
        e.response = {"error": error}
    if status is not None:
        e.status = status
    return e

cases = [
    ("channel_not_found", "conversation", ConversationNotFound),
    ("channel_not_found", "message", ChatError),
    ("thread_not_found", "conversation", ConversationNotFound),
    ("is_archived", "conversation", ConversationNotFound),
    ("user_not_found", "user", UserNotFound),
    ("users_not_found", "conversation", UserNotFound),   # string self-describes
    ("message_not_found", "message", ChatError),
    ("ratelimited", "conversation", RateLimited),
    ("missing_scope", "user", PermissionDenied),
    ("not_in_channel", "conversation", PermissionDenied),
    ("user_not_in_channel", "conversation", PermissionDenied),
    ("no_permission", "conversation", PermissionDenied),
    ("cant_delete_message", "message", PermissionDenied),
    ("expired_trigger_id", "message", InteractionExpired),
    ("file_uploads_exceed_max_size", "attachment", AttachmentTooLarge),
    ("some_novel_error", "conversation", ChatError),
]
for error, target, expected in cases:
    got = map_slack_error(api_err(error=error), target=target)
    exact = type(got) is expected if expected in (ChatError,) else isinstance(got, expected)
    check(f"map_slack_error: {error} × {target} → {expected.__name__}", exact, f"got {type(got).__name__}")
check("map_slack_error: HTTP 429 → RateLimited",
      isinstance(map_slack_error(api_err(status=429), target="message"), RateLimited))
check("map_slack_error: HTTP 413 → AttachmentTooLarge",
      isinstance(map_slack_error(api_err(status=413), target="attachment"), AttachmentTooLarge))
check("map_slack_error: bare 404 × conversation → ConversationNotFound",
      isinstance(map_slack_error(api_err(status=404), target="conversation"), ConversationNotFound))
check("map_slack_error: bare 404 × user → UserNotFound",
      isinstance(map_slack_error(api_err(status=404), target="user"), UserNotFound))
check("map_slack_error: bare 404 × message → base ChatError",
      type(map_slack_error(api_err(status=404), target="message")) is ChatError)


# ===================================================================== #
# Tier 2 — adapter-level, no-network
# ===================================================================== #

class ApiError(Exception):
    """SlackApiError-shaped: .response dict with the error string."""
    def __init__(self, error):
        super().__init__(error)
        self.response = {"error": error}


def ok(**kw):
    d = {"ok": True}
    d.update(kw)
    return d


class FakeWeb:
    """Duck-typed AsyncWebClient: records calls, returns scripted dicts."""

    def __init__(self):
        self.calls = []            # (method, kwargs) in order
        self.responses = {}        # method -> dict | list[dict] (paged) | Exception
        self.token = "xoxb-test"
        self._page_state = {}

    def _record(self, method, kwargs):
        self.calls.append((method, kwargs))

    def calls_for(self, method):
        return [kw for (m, kw) in self.calls if m == method]

    async def _dispatch(self, method, **kwargs):
        self._record(method, kwargs)
        scripted = self.responses.get(method)
        if isinstance(scripted, Exception):
            raise scripted
        if isinstance(scripted, list):   # paged: consume one page per call
            idx = self._page_state.get(method, 0)
            self._page_state[method] = idx + 1
            return scripted[min(idx, len(scripted) - 1)]
        if scripted is not None:
            return scripted
        return ok()

    def __getattr__(self, name):
        if name.startswith("_"):
            raise AttributeError(name)
        async def method(**kwargs):
            return await self._dispatch(name, **kwargs)
        return method


CH_REF = ConversationRef(provider="slack", workspace_id="T1", conversation_id="C1")
TH_REF = ConversationRef(provider="slack", workspace_id="T1", conversation_id="C1", thread_id="100.5")
ACTOR = Actor(id="U1", type=ActorType.USER)


def make_adapter(**kw):
    web = FakeWeb()
    web.responses["conversations_info"] = ok(channel={"id": "C1", "name": "general"})
    defaults = dict(team_id="T1", self_id="UBOT")
    defaults.update(kw)
    return SlackAdapter(web, **defaults), web


async def collect(agen, n):
    out = []
    for _ in range(n):
        out.append(await asyncio.wait_for(agen.__anext__(), 1))
    return out


async def main():
    # --- ABC satisfaction / structural completeness nets -----------------
    adapter, web = make_adapter()
    check("SlackAdapter instantiates (all 26 abstract methods implemented)",
          isinstance(adapter, ChatAdapter))
    abstract = sorted(ChatAdapter.__abstractmethods__)
    check("ABC still pins 26 methods", len(abstract) == 26, f"got {len(abstract)}")
    check("subscribe is an async generator function",
          inspect.isasyncgenfunction(SlackAdapter.subscribe))
    for name in abstract:
        check(f"signature pinned vs ABC: {name}",
              inspect.signature(getattr(SlackAdapter, name)) ==
              inspect.signature(getattr(ChatAdapter, name)))
    src = inspect.getsource(sys.modules["chat.slack_adapter"])
    check("no hollow stubs (NotImplementedError absent from adapter source)",
          "NotImplementedError" not in src)

    # --- messaging through fakes ------------------------------------------
    web.responses["chat_postMessage"] = ok(ts="10.1", message={"ts": "10.1", "user": "UBOT", "text": "hello"})
    msg = await adapter.send_message(CH_REF, "hello")
    sent = web.calls_for("chat_postMessage")[0]
    check("send_message: channel+text on chat.postMessage, no thread_ts for channel ref",
          sent["channel"] == "C1" and sent["text"] == "hello" and "thread_ts" not in sent)
    check("send_message: returns normalized Message", msg.ref.message_id == "10.1")

    await adapter.send_message(TH_REF, "in thread")
    check("send_message: thread ref → thread_ts",
          web.calls_for("chat_postMessage")[1]["thread_ts"] == "100.5")
    await adapter.send_message(CH_REF, "reply",
                               reply_to=MessageRef(conversation=CH_REF, message_id="9.9"))
    check("send_message: reply_to → thread_ts (Slack threading IS reply)",
          web.calls_for("chat_postMessage")[2]["thread_ts"] == "9.9")
    components = [ActionRow(components=[Button(custom_id="b", label="B")])]
    await adapter.send_message(CH_REF, "with blocks", components=components)
    check("send_message: components → blocks payload",
          web.calls_for("chat_postMessage")[3]["blocks"][0]["type"] == "actions")

    n_posts = len(web.calls_for("chat_postMessage"))
    try:
        await adapter.send_message(CH_REF, "with files",
                                   attachments=[sa.Attachment(id="F1", filename="a.txt")])
        check("send_message: attachments rejected loudly (no silent partial send)", False)
    except ChatError as exc:
        check("send_message: attachments rejected loudly (no silent partial send)",
              type(exc) is ChatError and "upload_attachment" in str(exc))
    check("send_message: rejected attachments → no post happened (spy)",
          len(web.calls_for("chat_postMessage")) == n_posts)

    web.responses["chat_update"] = ok(ts="10.1", text="new", message={"ts": "10.1", "text": "new", "user": "UBOT"})
    edited = await adapter.edit_message(MessageRef(conversation=CH_REF, message_id="10.1"), "new")
    check("edit_message: chat.update call + edited=True",
          web.calls_for("chat_update")[0]["ts"] == "10.1" and edited.edited is True)

    await adapter.delete_message(MessageRef(conversation=CH_REF, message_id="10.1"))
    check("delete_message: chat.delete with channel+ts",
          web.calls_for("chat_delete")[0] == {"channel": "C1", "ts": "10.1"})

    # --- fetch_message exact-ts guard ---------------------------------------
    web.responses["conversations_history"] = ok(messages=[{"ts": "10.1", "user": "U1", "text": "exact"}])
    got = await adapter.fetch_message(MessageRef(conversation=CH_REF, message_id="10.1"))
    check("fetch_message: exact ts match returned", got.text == "exact")
    hkw = web.calls_for("conversations_history")[-1]
    check("fetch_message: bounded point lookup (latest/inclusive/limit=1)",
          hkw["latest"] == "10.1" and hkw["inclusive"] is True and hkw["limit"] == 1)
    # Deleted-target shape: Slack returns the NEAREST older message.
    web.responses["conversations_history"] = ok(messages=[{"ts": "9.7", "user": "U1", "text": "neighbor"}])
    try:
        await adapter.fetch_message(MessageRef(conversation=CH_REF, message_id="10.1"))
        check("fetch_message: neighbor message → ChatError (never the wrong message)", False)
    except ChatError as exc:
        check("fetch_message: neighbor message → ChatError (never the wrong message)",
              not isinstance(exc, (ConversationNotFound, UserNotFound)))
    web.responses["conversations_replies"] = ok(messages=[{"ts": "100.7", "thread_ts": "100.5", "user": "U1", "text": "t"}])
    got = await adapter.fetch_message(MessageRef(conversation=TH_REF, message_id="100.7"))
    check("fetch_message: thread ref uses conversations.replies with ts anchor",
          web.calls_for("conversations_replies")[-1]["ts"] == "100.5" and got.text == "t")

    # --- fetch_history: args + cursor pagination -----------------------------
    web2 = adapter._web
    web2.responses["conversations_history"] = [
        ok(messages=[{"ts": "2.0", "user": "U1", "text": "b"}],
           has_more=True, response_metadata={"next_cursor": "CUR1"}),
        ok(messages=[{"ts": "1.0", "user": "U1", "text": "a"}],
           response_metadata={"next_cursor": ""}),
    ]
    web2._page_state.pop("conversations_history", None)
    hist = await adapter.fetch_history(
        CH_REF,
        before=MessageRef(conversation=CH_REF, message_id="5.0"),
        after=MessageRef(conversation=CH_REF, message_id="0.5"),
        limit=10,
    )
    calls = web2.calls_for("conversations_history")[-2:]
    check("fetch_history: latest/oldest forwarded (before/after)",
          calls[0]["latest"] == "5.0" and calls[0]["oldest"] == "0.5")
    check("fetch_history: page 2 carries the cursor", calls[1].get("cursor") == "CUR1")
    check("fetch_history: multi-page concatenation, chronological",
          [m.text for m in hist] == ["a", "b"])
    web2.responses["conversations_history"] = [
        ok(messages=[{"ts": "3.0", "user": "U1", "text": "x"},
                     {"ts": "4.0", "user": "U1", "text": "y"}],
           response_metadata={"next_cursor": "CUR9"}),
        ok(messages=[{"ts": "5.0", "user": "U1", "text": "z"}],
           response_metadata={"next_cursor": ""}),
    ]
    web2._page_state.pop("conversations_history", None)
    hist = await adapter.fetch_history(CH_REF, limit=2)
    check("fetch_history: limit stops the cursor loop mid-pagination",
          len(hist) == 2 and len(web2.calls_for("conversations_history")) >= 3)

    web2.responses["conversations_replies"] = ok(
        messages=[{"ts": "100.5", "user": "U1", "text": "parent"},
                  {"ts": "100.7", "thread_ts": "100.5", "user": "U1", "text": "reply"}])
    hist = await adapter.fetch_history(TH_REF, limit=10)
    check("fetch_history: thread ref pages conversations.replies",
          web2.calls_for("conversations_replies")[-1]["ts"] == "100.5" and len(hist) == 2)

    # --- ephemeral: native → DM → DeliveryFailed (matrix) --------------------
    for err in ("user_not_in_channel", "not_in_channel", "channel_not_found", "no_permission"):
        a2, w2 = make_adapter()
        w2.responses["chat_postEphemeral"] = ApiError(err)
        w2.responses["conversations_open"] = ok(channel={"id": "D9"})
        w2.responses["chat_postMessage"] = ok(ts="20.1", message={"ts": "20.1", "user": "UBOT", "text": "psst"})
        receipt = await a2.send_ephemeral(CH_REF, ACTOR, "psst")
        dm_posts = w2.calls_for("chat_postMessage")
        check(f"ephemeral fallback matrix: {err} → DM path (never an error)",
              receipt.path is EphemeralPath.DM and receipt.message is not None
              and dm_posts and dm_posts[0]["channel"] == "D9")
        check(f"ephemeral fallback matrix: {err} → nothing public (spy)",
              all(c["channel"] == "D9" for c in dm_posts))

    a2, w2 = make_adapter()
    w2.responses["chat_postEphemeral"] = ok(message_ts="21.0")
    receipt = await a2.send_ephemeral(TH_REF, ACTOR, "private", components=components)
    eph = w2.calls_for("chat_postEphemeral")[0]
    check("ephemeral native: per-user post with thread_ts + blocks",
          receipt.path is EphemeralPath.NATIVE and receipt.message is None
          and eph["user"] == "U1" and eph["thread_ts"] == "100.5" and "blocks" in eph)

    a2, w2 = make_adapter()
    w2.responses["chat_postEphemeral"] = ApiError("user_not_in_channel")
    w2.responses["conversations_open"] = ApiError("user_not_found")
    try:
        await a2.send_ephemeral(CH_REF, ACTOR, "x")
        check("ephemeral exhausted: DeliveryFailed", False)
    except DeliveryFailed:
        check("ephemeral exhausted: DeliveryFailed", True)
    check("ephemeral exhausted: no public post (construction spy)",
          not w2.calls_for("chat_postMessage"))

    # --- conversations / threads ---------------------------------------------
    a3, w3 = make_adapter()
    sub_events = []
    hub_sub = sa._Subscriber(None, None)
    a3._hub.add(hub_sub)
    t1 = await a3.create_conversation(
        ConversationKind.THREAD, parent=MessageRef(conversation=CH_REF, message_id="30.0"), name="thr")
    check("create THREAD from MessageRef: implicit thread ref (no create API)",
          t1.kind is ConversationKind.THREAD and t1.ref.thread_id == "30.0"
          and t1.ref.conversation_id == "C1")
    check("create THREAD: parent channel probed (existence check)",
          w3.calls_for("conversations_info"))
    evt = hub_sub.queue.get_nowait()
    check("create THREAD: synthetic THREAD_CREATED published",
          evt.type is EventType.THREAD_CREATED and evt.payload["conversation"].ref.thread_id == "30.0")
    a3._hub.remove(hub_sub)
    try:
        await a3.create_conversation(ConversationKind.THREAD, parent=CH_REF)
        check("create THREAD from channel ref → PermissionDenied (no standalone threads)", False)
    except PermissionDenied:
        check("create THREAD from channel ref → PermissionDenied (no standalone threads)", True)
    try:
        await a3.create_conversation(ConversationKind.THREAD)
        check("create THREAD without parent → ValueError", False)
    except ValueError:
        check("create THREAD without parent → ValueError", True)
    try:
        await a3.create_conversation(ConversationKind.DIRECT)
        check("create DIRECT without participants → ValueError", False)
    except ValueError:
        check("create DIRECT without participants → ValueError", True)

    w3.responses["conversations_open"] = ok(channel={"id": "D1", "is_im": True})
    dm = await a3.create_conversation(ConversationKind.DIRECT, participants=["U1"])
    check("create DIRECT: conversations.open with users",
          dm.kind is ConversationKind.DIRECT
          and w3.calls_for("conversations_open")[0]["users"] == "U1")

    w3.responses["conversations_create"] = ok(channel={"id": "C7", "name": "new"})
    c = await a3.create_conversation(ConversationKind.CHANNEL, name="new")
    check("create CHANNEL: conversations.create", c.ref.conversation_id == "C7")
    p = await a3.create_conversation(ConversationKind.PRIVATE, name="secret")
    check("create PRIVATE: is_private=True",
          w3.calls_for("conversations_create")[1]["is_private"] is True
          and p.ref.conversation_id == "C7")
    try:
        await a3.create_conversation(ConversationKind.TEMPORARY)
        check("create TEMPORARY → PermissionDenied", False)
    except PermissionDenied:
        check("create TEMPORARY → PermissionDenied", True)

    await a3.archive_conversation(CH_REF)
    check("archive_conversation: conversations.archive",
          w3.calls_for("conversations_archive")[0]["channel"] == "C1")
    try:
        await a3.archive_conversation(TH_REF)
        check("archive thread ref → ChatError (platform gap)", False)
    except ChatError as exc:
        check("archive thread ref → ChatError (platform gap)",
              not isinstance(exc, (ConversationNotFound, PermissionDenied)))

    # --- discovery: list/participants pagination ------------------------------
    a4, w4 = make_adapter()
    w4.responses["conversations_list"] = [
        ok(channels=[{"id": "C1", "name": "one"}],
           response_metadata={"next_cursor": "CURL"}),
        ok(channels=[{"id": "D1", "name": None, "is_im": True}],
           response_metadata={"next_cursor": ""}),
    ]
    convs = await a4.list_conversations()
    check("list_conversations: assembles across the cursor boundary",
          [c.ref.conversation_id for c in convs] == ["C1", "D1"]
          and w4.calls_for("conversations_list")[1]["cursor"] == "CURL")
    w4._page_state.pop("conversations_list", None)
    only_dm = await a4.list_conversations(kinds=[ConversationKind.DIRECT])
    check("list_conversations: kind filter", [c.ref.conversation_id for c in only_dm] == ["D1"])

    w4.responses["conversations_members"] = [
        ok(members=["U1"], response_metadata={"next_cursor": "CURM"}),
        ok(members=["U2"], response_metadata={"next_cursor": ""}),
    ]
    w4.responses["users_info"] = ok(user={"id": "U1", "name": "ada", "profile": {}})
    users = await a4.fetch_participants(CH_REF)
    check("fetch_participants: members paginated + hydrated via users.info",
          len(users) == 2 and w4.calls_for("conversations_members")[1]["cursor"] == "CURM"
          and len(w4.calls_for("users_info")) == 2)

    conv = await a4.fetch_conversation(CH_REF)
    check("fetch_conversation: conversations.info → Conversation", conv.name == "general")
    a_missing, w_missing = make_adapter()
    w_missing.responses["conversations_info"] = ApiError("channel_not_found")
    try:
        await a_missing.fetch_conversation(CH_REF)
        check("fetch_conversation: gone → ConversationNotFound", False)
    except ConversationNotFound:
        check("fetch_conversation: gone → ConversationNotFound", True)

    w4.responses["chat_getPermalink"] = ok(permalink="https://ws.slack.com/archives/C1/p101")
    link = await a4.get_permalink(MessageRef(conversation=CH_REF, message_id="10.1"))
    check("get_permalink: MessageRef via chat.getPermalink",
          link.endswith("/p101") and w4.calls_for("chat_getPermalink")[0]["message_ts"] == "10.1")
    link = await a4.get_permalink(CH_REF)
    check("get_permalink: ConversationRef via app_redirect deep link",
          link == "https://slack.com/app_redirect?team=T1&channel=C1")

    # --- identity --------------------------------------------------------------
    a5, w5 = make_adapter()
    w5.responses["users_info"] = ok(user={"id": "U1", "name": "ada", "is_admin": True,
                                          "is_owner": False, "profile": {}})
    u = await a5.fetch_user("U1")
    check("fetch_user: users.info → User", u.id == "U1" and u.username == "ada")
    w_gone = make_adapter()[1]
    a_gone = SlackAdapter(w_gone, team_id="T1")
    w_gone.responses["users_info"] = ApiError("user_not_found")
    try:
        await a_gone.fetch_user("U404")
        check("fetch_user: unknown id → UserNotFound", False)
    except UserNotFound:
        check("fetch_user: unknown id → UserNotFound", True)

    w5.responses["conversations_members"] = ok(members=["U1", "U2"],
                                               response_metadata={"next_cursor": ""})
    w5.responses["usergroups_list"] = ok(usergroups=[{"id": "S1", "name": "devs"},
                                                     {"id": "S2", "name": "ops"}])
    w5.responses["usergroups_users_list"] = [
        ok(users=["U1", "U9"]),   # S1 contains U1
        ok(users=["U9"]),         # S2 does not
    ]
    claims = await a5.fetch_identity_claims(CH_REF, "U1")
    check("claims: admin/owner flags + membership + usergroup scan",
          claims.is_workspace_admin and claims.is_channel_member
          and [r.name for r in claims.roles] == ["devs"]
          and claims.roles[0].kind == "slack_usergroup")
    a6, w6 = make_adapter()
    w6.responses["users_info"] = ok(user={"id": "U1", "profile": {}})
    w6.responses["conversations_members"] = ok(members=["U1"],
                                               response_metadata={"next_cursor": ""})
    w6.responses["usergroups_list"] = ApiError("missing_scope")
    claims = await a6.fetch_identity_claims(CH_REF, "U1")
    check("claims: usergroup scan degradation (missing scope → empty roles + metadata note)",
          claims.roles == [] and "usergroups_degraded" in claims.metadata
          and claims.is_channel_member)

    # --- reconciliation ---------------------------------------------------------
    a7, w7 = make_adapter()
    w7.responses["reactions_get"] = ok(message={"reactions": [
        {"name": "eyes", "count": 2, "users": ["U1", "U2"]}]})
    rx = await a7.fetch_reactions(MessageRef(conversation=CH_REF, message_id="10.1"))
    check("fetch_reactions: reactions.get → normalized list",
          rx[0].emoji == "eyes" and rx[0].count == 2 and rx[0].user_ids == ["U1", "U2"])

    # --- files -------------------------------------------------------------------
    a8, w8 = make_adapter()
    w8.responses["files_upload_v2"] = ok(file={"id": "F1", "name": "a.txt",
                                               "mimetype": "text/plain", "size": 3,
                                               "url_private": "http://files/a"})
    att = await a8.upload_attachment(CH_REF, "a.txt", b"abc")
    up = w8.calls_for("files_upload_v2")[0]
    check("upload: files_upload_v2 channel/filename/content, no thread_ts for channel ref",
          up["channel"] == "C1" and up["filename"] == "a.txt" and "thread_ts" not in up)
    check("upload: normalized Attachment", att.id == "F1" and att.url == "http://files/a")
    await a8.upload_attachment(TH_REF, "b.txt", b"xyz")
    check("upload: thread ref propagates thread_ts (lands IN the thread)",
          w8.calls_for("files_upload_v2")[1]["thread_ts"] == "100.5")
    try:
        big = b"x" * (a8.capabilities().max_attachment_bytes + 1)
        await a8.upload_attachment(CH_REF, "big.bin", big)
        check("upload: oversize → AttachmentTooLarge BEFORE any web call", False)
    except AttachmentTooLarge:
        check("upload: oversize → AttachmentTooLarge BEFORE any web call",
              len(w8.calls_for("files_upload_v2")) == 2)  # no third call happened

    fetched = {}
    async def fake_http_get(url, headers):
        fetched["url"] = url
        fetched["headers"] = headers
        return b"bytes!"
    a9, w9 = make_adapter(http_get=fake_http_get)
    data = await a9.download_attachment(att)
    check("download: authed GET through the seam (bearer header)",
          data == b"bytes!" and fetched["url"] == "http://files/a"
          and fetched["headers"]["Authorization"] == "Bearer xoxb-test")
    try:
        await a9.download_attachment(sa.Attachment(id="F2", filename="no-url"))
        check("download: no URL → ChatError", False)
    except ChatError:
        check("download: no URL → ChatError", True)

    # --- reactions ------------------------------------------------------------------
    a10, w10 = make_adapter()
    await a10.add_reaction(MessageRef(conversation=CH_REF, message_id="10.1"), ":tada:")
    check("add_reaction: colon-stripped name",
          w10.calls_for("reactions_add")[0]["name"] == "tada")
    w10.responses["reactions_add"] = ApiError("already_reacted")
    await a10.add_reaction(MessageRef(conversation=CH_REF, message_id="10.1"), "tada")
    check("add_reaction: already_reacted → no-op (contract)", True)
    w10.responses["reactions_remove"] = ApiError("no_reaction")
    await a10.remove_reaction(MessageRef(conversation=CH_REF, message_id="10.1"), "tada")
    check("remove_reaction: no_reaction → no-op (contract)", True)
    w10.responses["reactions_remove"] = ApiError("cant_delete_message")
    try:
        await a10.remove_reaction(MessageRef(conversation=CH_REF, message_id="10.1"), "tada")
        check("reaction op: real errors still raise", False)
    except PermissionDenied:
        check("reaction op: real errors still raise", True)

    # --- error translation through REAL call sites --------------------------------
    a11, w11 = make_adapter()
    w11.responses["conversations_info"] = ApiError("channel_not_found")
    try:
        await a11.delete_message(MessageRef(conversation=CH_REF, message_id="1.0"))
        check("call-site targets: gone channel on message op → ConversationNotFound (resolve step)", False)
    except ConversationNotFound:
        check("call-site targets: gone channel on message op → ConversationNotFound (resolve step)", True)
    a12, w12 = make_adapter()
    w12.responses["conversations_history"] = ok(messages=[])
    try:
        await a12.fetch_message(MessageRef(conversation=CH_REF, message_id="1.0"))
        check("call-site targets: resolvable channel, missing message → base ChatError", False)
    except ChatError as exc:
        check("call-site targets: resolvable channel, missing message → base ChatError",
              type(exc) is ChatError)

    # --- register_commands: validate + no-op ----------------------------------------
    a13, w13 = make_adapter()
    await a13.register_commands([SlashCommand(name="/deploy", description="d"),
                                 SlashCommand(name="status", description="s")])
    check("register_commands: valid specs → no-op (no web calls)",
          not [c for c in w13.calls if c[0] != "conversations_info"])
    try:
        await a13.register_commands([SlashCommand(name="Bad Name!", description="d")])
        check("register_commands: invalid name → ValueError", False)
    except ValueError:
        check("register_commands: invalid name → ValueError", True)

    # --- interactions: instant ack, respond/follow_up, open_modal -------------------
    a14, w14 = make_adapter()
    order = []
    async def fake_ack():
        order.append("ack")
    evt_sub = sa._Subscriber(None, None)
    a14._hub.add(evt_sub)
    payload = {"type": "block_actions", "trigger_id": "TRIG1",
               "user": {"id": "U1"}, "team": {"id": "T1"}, "channel": {"id": "C1"},
               "actions": [{"type": "button", "action_id": "go"}],
               "response_url": "http://hooks/resp1"}
    dom = await a14._on_interaction(payload, fake_ack)
    order.append("published" if not evt_sub.queue.empty() else "not-published")
    check("interaction: ack called BEFORE publish (instant-ack)",
          order == ["ack", "published"])
    check("interaction yielded _acked=True (ack already performed)", dom._acked is True)
    evt = evt_sub.queue.get_nowait()
    check("published INTERACTION_RECEIVED carries the identical ack-owned object",
          evt.type is EventType.INTERACTION_RECEIVED
          and evt.payload["interaction"] is dom
          and evt.payload["interaction"]._acked is True)
    a14._hub.remove(evt_sub)

    webhook_posts = []
    class FakeWebhookClient:
        def __init__(self, url): self.url = url
        async def send_dict(self, payload):
            webhook_posts.append((self.url, payload))
            return SimpleNamespace(status_code=200)
    fake_sdk = SimpleNamespace(webhook=SimpleNamespace(
        async_client=SimpleNamespace(AsyncWebhookClient=FakeWebhookClient)))
    a14._sdk_override = fake_sdk

    got = await a14.respond(dom, "done", ephemeral=True)
    check("respond: response_url post (ephemeral response_type), returns None",
          got is None and webhook_posts[0][0] == "http://hooks/resp1"
          and webhook_posts[0][1]["response_type"] == "ephemeral"
          and webhook_posts[0][1]["text"] == "done")
    got = await a14.follow_up(dom, "more", components=components)
    check("follow_up: in_channel + blocks through the same webhook",
          got is None and webhook_posts[1][1]["response_type"] == "in_channel"
          and webhook_posts[1][1]["blocks"][0]["type"] == "actions")

    class FailingWebhookClient:
        def __init__(self, url): self.url = url
        async def send_dict(self, payload):
            return SimpleNamespace(status_code=404)
    a14._sdk_override = SimpleNamespace(webhook=SimpleNamespace(
        async_client=SimpleNamespace(AsyncWebhookClient=FailingWebhookClient)))
    try:
        await a14.respond(dom, "late")
        check("respond: non-200 webhook → InteractionExpired", False)
    except InteractionExpired:
        check("respond: non-200 webhook → InteractionExpired", True)
    try:
        await a14.respond(Interaction(id="unknown", type=InteractionType.BUTTON,
                                      actor=ACTOR, conversation=CH_REF), "x")
        check("respond on unknown/expired interaction → InteractionExpired", False)
    except InteractionExpired:
        check("respond on unknown/expired interaction → InteractionExpired", True)

    await a14.ack(dom)
    await a14.ack(dom)
    check("ack idempotent no-op", dom._acked is True)

    modal = Modal(custom_id="m", title="T", fields=[FormField(custom_id="f", label="F")])
    await a14.open_modal(dom, modal)
    vo = w14.calls_for("views_open")[0]
    check("open_modal: views.open with trigger_id + view payload",
          vo["trigger_id"] == "TRIG1" and vo["view"]["callback_id"] == "m")
    w14.responses["views_open"] = ApiError("expired_trigger_id")
    try:
        await a14.open_modal(dom, modal)
        check("open_modal: expired trigger → InteractionExpired", False)
    except InteractionExpired:
        check("open_modal: expired trigger → InteractionExpired", True)
    sub_payload = {"type": "view_submission", "trigger_id": "TRIG2",
                   "user": {"id": "U1"}, "team": {"id": "T1"},
                   "view": {"callback_id": "m", "state": {"values": {}}}}
    dom_sub = await a14._on_interaction(sub_payload, fake_ack)
    try:
        await a14.open_modal(dom_sub, modal)
        check("open_modal: MODAL_SUBMIT cannot open another modal", False)
    except InteractionExpired:
        check("open_modal: MODAL_SUBMIT cannot open another modal", True)

    # --- subscription (through SlackAdapter + the shared hub) ------------------------
    a15, _ = make_adapter()
    ag1 = a15.subscribe()
    ag2 = a15.subscribe(conversations=[CH_REF])
    t_all = asyncio.create_task(collect(ag1, 2))
    t_filtered = asyncio.create_task(collect(ag2, 1))
    await asyncio.sleep(0)
    a15._publish_event({"type": "message", "channel": "C1", "user": "U1", "text": "one", "ts": "1.0"})
    a15._publish_event({"type": "message", "channel": "C2", "user": "U1", "text": "two", "ts": "2.0"})
    got_all = await t_all
    got_filtered = await t_filtered
    check("subscribe: two concurrent subscribers, independent streams",
          [e.payload["message"].text for e in got_all] == ["one", "two"])
    check("subscribe: conversation filter", [e.payload["message"].text for e in got_filtered] == ["one"])

    ag3 = a15.subscribe(since=5.0)
    t3 = asyncio.create_task(collect(ag3, 1))
    await asyncio.sleep(0)
    a15._publish_event({"type": "message", "channel": "C1", "user": "U1", "text": "old", "ts": "1.0"})
    a15._publish_event({"type": "message", "channel": "C1", "user": "U1", "text": "new", "ts": "9.0"})
    got3 = await t3
    check("subscribe: since filters older events", [e.payload["message"].text for e in got3] == ["new"])

    ag4 = a15.subscribe()
    t4 = asyncio.create_task(collect(ag4, 1))
    await asyncio.sleep(0)
    n_subs = len(a15._hub._subscribers)
    t4.cancel()
    try: await t4
    except asyncio.CancelledError: pass
    await ag4.aclose()
    check("subscribe: generator close deregisters", len(a15._hub._subscribers) == n_subs - 1)

    import chat._subscription as subs
    subs.SUBSCRIBER_QUEUE_MAXSIZE = 2
    slow = sa._Subscriber(None, None)
    subs.SUBSCRIBER_QUEUE_MAXSIZE = 1024
    fast = sa._Subscriber(None, None)
    a15._hub.add(slow); a15._hub.add(fast)
    for i in range(4):
        a15._publish_event({"type": "message", "channel": "C1", "user": "U1",
                            "text": f"m{i}", "ts": f"{10+i}.0"})
    check("hub overflow: slow subscriber sentinel-disconnected, fast unaffected",
          slow not in a15._hub._subscribers and fast.queue.qsize() == 4)
    while not slow.queue.empty():
        last = slow.queue.get_nowait()
    check("hub overflow: sentinel is the terminal item", last is sa._DISCONNECT)
    a15._hub.remove(fast)

    ag5 = a15.subscribe()
    t5 = asyncio.create_task(collect(ag5, 1))
    await asyncio.sleep(0)
    a15._hub.disconnect_all()
    try:
        await t5
        check("disconnect ends all streams (no replay)", False)
    except (StopAsyncIteration, asyncio.TimeoutError):
        check("disconnect ends all streams (no replay)", True)
    check("disconnect: subscribers cleared", len(a15._hub._subscribers) == 0)

    # Full-queue disconnect: a subscriber whose bounded queue is EXACTLY
    # full must still receive the sentinel (put_nowait would raise QueueFull
    # out of the transport's disconnect listener) — sentinel-safe drain.
    subs.SUBSCRIBER_QUEUE_MAXSIZE = 2
    full_sub = sa._Subscriber(None, None)
    subs.SUBSCRIBER_QUEUE_MAXSIZE = 1024
    healthy_sub = sa._Subscriber(None, None)
    a15._hub.add(full_sub); a15._hub.add(healthy_sub)
    for i in range(2):  # fill exactly — no overflow branch fires
        a15._publish_event({"type": "message", "channel": "C1", "user": "U1",
                            "text": f"f{i}", "ts": f"{20+i}.0"})
    a15._hub.disconnect_all()   # must not raise
    drained = []
    while not full_sub.queue.empty():
        drained.append(full_sub.queue.get_nowait())
    check("disconnect on a FULL queue: no raise, sentinel is terminal",
          drained and drained[-1] is sa._DISCONNECT)
    h_drained = []
    while not healthy_sub.queue.empty():
        h_drained.append(healthy_sub.queue.get_nowait())
    check("disconnect on a FULL queue: every stream ended (later subscriber too)",
          h_drained and h_drained[-1] is sa._DISCONNECT
          and len(a15._hub._subscribers) == 0)

    # --- capabilities ------------------------------------------------------------------
    caps = a15.capabilities()
    check("capabilities: Slack matrix (ephemeral/search/threads honest)",
          caps.supports_ephemeral and not caps.supports_standalone_threads
          and caps.supports_thread_creation and not caps.supports_voice)
    check("capability honesty: supports_message_search is False (user-token-only API)",
          caps.supports_message_search is False
          and "message_search_note" in caps.metadata)
    check("capabilities: Slack limits", caps.max_message_length == 40000
          and caps.max_attachment_bytes == 1024 ** 3)


asyncio.run(main())
assert "slack_sdk" not in sys.modules and "slack_bolt" not in sys.modules, \
    "no test path may import the SDKs"
print(f"\nPASS: {PASS} checks")
PYEOF

# ---------------------------------------------------------------------------
# Live-seam check (separate process — the block above must stay SDK-free).
# Runs only when slack_sdk is installed (ait setup --with-chat); verifies the
# webhook-client resolution against the REAL SDK: `import slack_sdk` does not
# bind .webhook.async_client, so both the default path and the
# connect()-style module override must resolve via a genuine submodule
# import (regression: AttributeError → every live respond() died as
# InteractionExpired while nested-shape fakes passed).
"$PYTHON" - "$PROJECT_DIR" <<'PYEOF'
import importlib.util
import sys
from pathlib import Path

root = Path(sys.argv[1])
sys.path.insert(0, str(root / ".aitask-scripts"))

if importlib.util.find_spec("slack_sdk") is None:
    print("SKIP - slack_sdk not installed (live webhook-seam check needs the opt-in chat tier)")
    sys.exit(0)

import slack_sdk  # bare import — deliberately BEFORE any submodule import

from chat.slack_adapter import SlackAdapter

checks = 0

# connect()-style override FIRST, while webhook.async_client is (possibly)
# unbound on the bare module — the regression was an AttributeError here.
adapter = SlackAdapter(object(), team_id="T1", sdk=slack_sdk)
override_client = adapter._webhook_client("https://hooks.slack.com/x")
checks += 1
print("ok - live seam: bare real-module override resolves (no AttributeError)")

from slack_sdk.webhook.async_client import AsyncWebhookClient as RealClient

assert isinstance(override_client, RealClient), \
    f"module-override seam resolved {type(override_client)}"
checks += 1
print("ok - live seam: override path yielded the real AsyncWebhookClient")

# Default path: no override → real submodule import.
adapter = SlackAdapter(object(), team_id="T1")
client = adapter._webhook_client("https://hooks.slack.com/x")
assert isinstance(client, RealClient), f"default seam resolved {type(client)}"
checks += 1
print("ok - live seam: default path resolves the real AsyncWebhookClient")

print(f"\nPASS: {checks} live-seam checks")
PYEOF
