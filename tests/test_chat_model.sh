#!/usr/bin/env bash
# test_chat_model.sh — unit tests for the chat domain model (t1074_1).
#
# Constructs every public entity, round-trips ConversationRef (incl. THREAD),
# and checks full enum coverage. Dependency-free (stdlib only).
# Run: bash tests/test_chat_model.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# shellcheck source=../.aitask-scripts/lib/python_resolve.sh
source "$PROJECT_DIR/.aitask-scripts/lib/python_resolve.sh"

PYTHON="$(require_ait_python)"

"$PYTHON" - "$PROJECT_DIR" <<'PYEOF'
import sys
from pathlib import Path

root = Path(sys.argv[1])
sys.path.insert(0, str(root / ".aitask-scripts"))

from chat import (
    ActionRow, Actor, ActorType, Attachment, Button, CommandOption,
    Conversation, ConversationKind, ConversationRef, EphemeralPath,
    EphemeralReceipt, Event, EventType, Form, FormField, IdentityClaims,
    Interaction, InteractionType, Mention, Message, MessageRef, Modal,
    Permission, Reaction, Role, SelectMenu, SelectOption, SlashCommand,
    User, Workspace,
)

PASS = 0
def check(label, cond):
    global PASS
    assert cond, f"FAIL: {label}"
    PASS += 1
    print(f"ok - {label}")

# --- entity construction -------------------------------------------------
ws = Workspace(id="W1", name="w", provider="mock")
ref = ConversationRef(provider="mock", workspace_id="W1", conversation_id="C1")
conv = Conversation(ref=ref, kind=ConversationKind.CHANNEL, name="general")
actor = Actor(id="U1", type=ActorType.USER, display_name="dev")
bot = Actor(id="B1", type=ActorType.BOT, is_self=True)
system = Actor(id="S1", type=ActorType.SYSTEM)
user = User(id="U1", display_name="dev")
mref = MessageRef(conversation=ref, message_id="m1")
att = Attachment(id="f1", filename="a.txt")
mention = Mention(user_id="U1")
reaction = Reaction(emoji="ok", count=1, user_ids=["U1"])
msg = Message(ref=mref, author=actor, text="hi", timestamp=1.0,
              attachments=[att], mentions=[mention], reactions=[reaction])
role = Role(id="r1", name="admins", kind="discord_role")
claims = IdentityClaims(user_id="U1", roles=[role], is_workspace_admin=True)
event = Event(id="e1", type=EventType.MESSAGE_CREATED, timestamp=1.0,
              actor=actor, conversation=ref, payload={"message": msg})
perm = Permission(name="post")
receipt = EphemeralReceipt(path=EphemeralPath.NATIVE, message=msg)
btn = Button(custom_id="b1", label="Approve")
sel = SelectMenu(custom_id="s1", options=[SelectOption(value="v", label="V")])
row = ActionRow(components=[btn, sel])
modal = Modal(custom_id="mo1", title="T", fields=[FormField(custom_id="f", label="F")])
cmd = SlashCommand(name="task", description="d",
                   options=[CommandOption(name="id", description="d2")])
inter = Interaction(id="i1", type=InteractionType.BUTTON, actor=actor,
                    conversation=ref, message=mref, custom_id="b1")
check("all entities constructible",
      all(x is not None for x in (ws, conv, user, msg, claims, event, perm,
                                  receipt, row, modal, cmd, inter)))

# --- Actor semantics ------------------------------------------------------
check("Actor.is_bot false for USER", actor.is_bot is False)
check("Actor.is_bot true for BOT", bot.is_bot is True)
check("Actor.is_bot true for SYSTEM", system.is_bot is True)
check("Interaction arrives unacked by default", inter._acked is False)
check("Form is an alias of Modal", Form is Modal)

# --- ConversationRef round-trip (incl. THREAD) ----------------------------
tref = ConversationRef(provider="mock", workspace_id="W1",
                       conversation_id="C1", thread_id="t42",
                       metadata={"slack_thread_ts": "123.456"})
rt = ConversationRef.from_dict(tref.to_dict())
check("THREAD ref round-trips equal", rt == tref)
check("round-trip preserves thread_id", rt.thread_id == "t42")
check("round-trip preserves metadata", rt.metadata == {"slack_thread_ts": "123.456"})
check("metadata excluded from equality",
      ConversationRef(provider="mock", workspace_id="W1", conversation_id="C1",
                      thread_id="t42", metadata={"other": 1}) == tref)
check("thread_id participates in equality", ref != tref)
check("MessageRef metadata excluded from equality",
      MessageRef(conversation=ref, message_id="m1", metadata={"x": 1}) == mref)

# --- enum coverage ---------------------------------------------------------
check("ConversationKind members",
      {k.name for k in ConversationKind}
      == {"CHANNEL", "THREAD", "DIRECT", "PRIVATE", "TEMPORARY"})
check("EventType members (14)",
      {e.name for e in EventType}
      == {"MESSAGE_CREATED", "MESSAGE_EDITED", "MESSAGE_DELETED",
          "REACTION_ADDED", "REACTION_REMOVED", "APP_MENTION",
          "THREAD_CREATED", "THREAD_DELETED", "FILE_UPLOADED",
          "USER_JOINED", "USER_LEFT", "CHANNEL_CREATED",
          "INTERACTION_RECEIVED", "UNKNOWN"})
check("InteractionType members",
      {i.name for i in InteractionType}
      == {"BUTTON", "SELECT", "MODAL_SUBMIT", "COMMAND"})
check("ActorType members", {a.name for a in ActorType} == {"USER", "BOT", "SYSTEM"})
check("EphemeralPath members", {p.name for p in EphemeralPath} == {"NATIVE", "DM"})

print(f"\nPASS: {PASS} checks")
PYEOF
