#!/usr/bin/env bash
# test_chat_contract.sh — contract-introspection guard for the frozen chat
# surface (t1074_1).
#
# The ChatAdapter contract is FROZEN: adapter children implement it verbatim
# and higher layers rely on it. This test pins the surface mechanically so
# drift is caught here — exact __all__, exact __abstractmethods__, pinned
# method signatures (names/kinds/defaults), coroutine/async-generator kinds,
# docstring presence (abstraction-documentation rule), dataclass field
# schemas, and the mutable-default (default_factory) guard.
#
# If a change here is intentional, amend the ABC, the Mock, AND the pinned
# tables below in the same commit (see "Notes for sibling tasks" in
# aiplans/p1074/p1074_1_core_domain_model_and_chatadapter.md).
# Run: bash tests/test_chat_contract.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# shellcheck source=../.aitask-scripts/lib/python_resolve.sh
source "$PROJECT_DIR/.aitask-scripts/lib/python_resolve.sh"

PYTHON="$(require_ait_python)"

"$PYTHON" - "$PROJECT_DIR" <<'PYEOF'
import dataclasses
import inspect
import sys
from pathlib import Path

root = Path(sys.argv[1])
sys.path.insert(0, str(root / ".aitask-scripts"))

import chat
from chat import ChatAdapter, MockChatAdapter

PASS = 0
def check(label, cond, detail=""):
    global PASS
    assert cond, f"FAIL: {label}{': ' + detail if detail else ''}"
    PASS += 1
    print(f"ok - {label}")

# --- exact __all__ ----------------------------------------------------------
EXPECTED_ALL = {
    # model
    "Workspace", "ConversationKind", "ConversationRef", "Conversation",
    "MessageRef", "Message", "User", "ActorType", "Actor", "Role",
    "IdentityClaims", "Attachment", "Mention", "Reaction", "EventType",
    "Event", "Permission", "EphemeralPath", "EphemeralReceipt",
    # interactions
    "Button", "SelectMenu", "SelectOption", "ActionRow", "FormField",
    "Modal", "Form", "SlashCommand", "CommandOption", "InteractionType",
    "Interaction",
    # capabilities / adapter / mock
    "Capabilities", "ChatAdapter", "MockChatAdapter",
    # errors
    "ChatError", "ConversationNotFound", "PermissionDenied", "RateLimited",
    "AttachmentTooLarge", "UserNotFound", "DeliveryFailed",
    "InteractionExpired",
}
check("__all__ is exactly the pinned export set",
      set(chat.__all__) == EXPECTED_ALL,
      f"diff={set(chat.__all__) ^ EXPECTED_ALL}")
check("__all__ has no duplicates", len(chat.__all__) == len(set(chat.__all__)))

# --- exact abstract-method set ------------------------------------------------
EXPECTED_ABSTRACT = {
    "send_message", "edit_message", "delete_message", "fetch_message",
    "send_ephemeral", "create_conversation", "archive_conversation",
    "fetch_history", "fetch_participants", "fetch_conversation",
    "list_conversations", "get_permalink", "fetch_user",
    "fetch_identity_claims", "fetch_reactions", "upload_attachment",
    "download_attachment", "add_reaction", "remove_reaction",
    "register_commands", "ack", "respond", "follow_up", "open_modal",
    "subscribe", "capabilities",
}
check("__abstractmethods__ is exactly the pinned method set",
      set(ChatAdapter.__abstractmethods__) == EXPECTED_ABSTRACT,
      f"diff={set(ChatAdapter.__abstractmethods__) ^ EXPECTED_ABSTRACT}")

# --- pinned signatures (param names, kinds, defaults) ---------------------------
# Format: method -> list of (name, kind, default) after `self`.
P = inspect.Parameter
POS = P.POSITIONAL_OR_KEYWORD
KW = P.KEYWORD_ONLY
E = P.empty
EXPECTED_SIGNATURES = {
    "send_message": [("conversation", POS, E), ("text", POS, E),
                     ("attachments", KW, None), ("components", KW, None),
                     ("reply_to", KW, None)],
    "edit_message": [("message", POS, E), ("text", POS, E), ("components", KW, None)],
    "delete_message": [("message", POS, E)],
    "fetch_message": [("message", POS, E)],
    "send_ephemeral": [("conversation", POS, E), ("actor", POS, E),
                       ("text", POS, E), ("components", KW, None)],
    "create_conversation": [("kind", POS, E), ("parent", KW, None),
                            ("name", KW, None), ("participants", KW, None)],
    "archive_conversation": [("conversation", POS, E)],
    "fetch_history": [("conversation", POS, E), ("before", KW, None),
                      ("after", KW, None), ("limit", KW, 100)],
    "fetch_participants": [("conversation", POS, E)],
    "fetch_conversation": [("ref", POS, E)],
    "list_conversations": [("kinds", KW, None)],
    "get_permalink": [("ref", POS, E)],
    "fetch_user": [("user_id", POS, E)],
    "fetch_identity_claims": [("conversation", POS, E), ("user_id", POS, E)],
    "fetch_reactions": [("message", POS, E)],
    "upload_attachment": [("conversation", POS, E), ("filename", POS, E),
                          ("content", POS, E), ("mime_type", KW, None)],
    "download_attachment": [("attachment", POS, E)],
    "add_reaction": [("message", POS, E), ("emoji", POS, E)],
    "remove_reaction": [("message", POS, E), ("emoji", POS, E)],
    "register_commands": [("specs", POS, E)],
    "ack": [("interaction", POS, E)],
    "respond": [("interaction", POS, E), ("text", POS, E),
                ("components", KW, None), ("ephemeral", KW, False)],
    "follow_up": [("interaction", POS, E), ("text", POS, E),
                  ("components", KW, None), ("ephemeral", KW, False)],
    "open_modal": [("interaction", POS, E), ("modal", POS, E)],
    "subscribe": [("conversations", KW, None), ("since", KW, None)],
    "capabilities": [],
}
for name, expected in sorted(EXPECTED_SIGNATURES.items()):
    sig = inspect.signature(getattr(ChatAdapter, name))
    got = [(p.name, p.kind, p.default)
           for p in sig.parameters.values() if p.name != "self"]
    check(f"signature pinned: {name}", got == expected, f"got={got}")

# --- method kinds: coroutine vs async generator vs plain --------------------------
for cls in (ChatAdapter, MockChatAdapter):
    label = cls.__name__
    for name in sorted(EXPECTED_ABSTRACT - {"subscribe", "capabilities"}):
        check(f"{label}.{name} is a coroutine function",
              inspect.iscoroutinefunction(getattr(cls, name)))
    check(f"{label}.subscribe is an async generator function",
          inspect.isasyncgenfunction(getattr(cls, "subscribe")))
    check(f"{label}.capabilities is a plain (sync) function",
          not inspect.iscoroutinefunction(getattr(cls, "capabilities"))
          and not inspect.isasyncgenfunction(getattr(cls, "capabilities")))

# --- docstrings: ABC methods + every public class (abstraction-documentation rule) --
for name in sorted(EXPECTED_ABSTRACT):
    doc = inspect.getdoc(getattr(ChatAdapter, name))
    check(f"ChatAdapter.{name} has a docstring", bool(doc and doc.strip()))
missing_docs = [n for n in sorted(chat.__all__)
                if inspect.isclass(getattr(chat, n))
                and not (getattr(chat, n).__doc__ or "").strip()]
check("every public class has a docstring", not missing_docs, f"missing={missing_docs}")

# --- dataclass field schemas ------------------------------------------------------
EXPECTED_FIELDS = {
    "Workspace": ["id", "name", "provider", "metadata"],
    "ConversationRef": ["provider", "workspace_id", "conversation_id",
                        "thread_id", "metadata"],
    "Conversation": ["ref", "kind", "name", "topic", "is_archived", "metadata"],
    "MessageRef": ["conversation", "message_id", "metadata"],
    "Message": ["ref", "author", "text", "timestamp", "attachments",
                "mentions", "reactions", "reply_to", "edited", "metadata"],
    "User": ["id", "display_name", "username", "email", "avatar_url",
             "is_bot", "metadata"],
    "Actor": ["id", "type", "display_name", "is_self", "metadata"],
    "Role": ["id", "name", "kind", "metadata"],
    "IdentityClaims": ["user_id", "roles", "is_workspace_admin", "is_owner",
                       "is_channel_member", "metadata"],
    "Attachment": ["id", "filename", "mime_type", "size", "url", "uploader",
                   "metadata"],
    "Mention": ["user_id", "display_name", "metadata"],
    "Reaction": ["emoji", "count", "user_ids", "metadata"],
    "Event": ["id", "type", "timestamp", "actor", "conversation", "payload",
              "metadata"],
    "Permission": ["name", "metadata"],
    "EphemeralReceipt": ["path", "message", "metadata"],
    "Button": ["custom_id", "label", "style", "disabled", "metadata"],
    "SelectOption": ["value", "label", "description", "metadata"],
    "SelectMenu": ["custom_id", "options", "placeholder", "min_values",
                   "max_values", "metadata"],
    "ActionRow": ["components", "metadata"],
    "FormField": ["custom_id", "label", "kind", "required", "placeholder",
                  "metadata"],
    "Modal": ["custom_id", "title", "fields", "metadata"],
    "CommandOption": ["name", "description", "kind", "required", "metadata"],
    "SlashCommand": ["name", "description", "options", "metadata"],
    "Interaction": ["id", "type", "actor", "conversation", "message",
                    "custom_id", "values", "metadata", "_acked"],
    "Capabilities": ["supports_buttons", "supports_selects", "supports_modals",
                     "supports_slash_commands", "supports_reactions",
                     "supports_files", "supports_ephemeral", "supports_dm",
                     "supports_voice", "supports_editing",
                     "supports_thread_creation", "supports_standalone_threads",
                     "supports_message_search", "max_message_length",
                     "max_attachment_bytes", "metadata"],
}
for name, expected in sorted(EXPECTED_FIELDS.items()):
    cls = getattr(chat, name)
    got = [f.name for f in dataclasses.fields(cls)]
    check(f"fields pinned: {name}", got == expected, f"got={got}")

# ConversationRef / MessageRef / Interaction._acked compare-exclusions.
def compare_of(cls, fname):
    return next(f.compare for f in dataclasses.fields(cls) if f.name == fname)
check("ConversationRef.metadata excluded from equality",
      compare_of(chat.ConversationRef, "metadata") is False)
check("MessageRef.metadata excluded from equality",
      compare_of(chat.MessageRef, "metadata") is False)
check("Interaction._acked excluded from equality",
      compare_of(chat.Interaction, "_acked") is False)

# --- mutable-default guard: default-constructed instances share nothing --------------
def fresh(cls):
    """Construct with minimal positional args (defaults for the rest)."""
    kwargs = {}
    for f in dataclasses.fields(cls):
        if f.default is dataclasses.MISSING and f.default_factory is dataclasses.MISSING:
            kwargs[f.name] = None  # placeholder for required fields
    return cls(**kwargs)

shared = []
for name in sorted(EXPECTED_FIELDS):
    cls = getattr(chat, name)
    a, b = fresh(cls), fresh(cls)
    for f in dataclasses.fields(cls):
        va, vb = getattr(a, f.name), getattr(b, f.name)
        if isinstance(va, (list, dict)) and va is vb:
            shared.append(f"{name}.{f.name}")
check("no shared mutable defaults across instances (default_factory guard)",
      not shared, f"shared={shared}")

# --- errors taxonomy shape ----------------------------------------------------------
for err in ("ConversationNotFound", "PermissionDenied", "RateLimited",
            "AttachmentTooLarge", "UserNotFound", "DeliveryFailed",
            "InteractionExpired"):
    check(f"{err} subclasses ChatError", issubclass(getattr(chat, err), chat.ChatError))
check("ChatError subclasses Exception", issubclass(chat.ChatError, Exception))

# --- Mock adds no public methods beyond the ABC + documented test seams --------------
ALLOWED_MOCK_EXTRAS = {
    # documented test-helper seams (mock-only, never on real adapters)
    "register_user", "set_identity_claims", "add_participant",
    "inject_message", "inject_interaction", "inject_reaction",
    "set_window_closed", "simulate_disconnect",
}
mock_public = {n for n, v in vars(MockChatAdapter).items()
               if callable(v) and not n.startswith("_")}
extras = mock_public - EXPECTED_ABSTRACT - ALLOWED_MOCK_EXTRAS
check("MockChatAdapter public surface = ABC + documented seams",
      not extras, f"extras={extras}")

print(f"\nPASS: {PASS} checks")
PYEOF
