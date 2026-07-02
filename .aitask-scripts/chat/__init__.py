"""chat — platform-agnostic chat (Slack/Discord) abstraction layer.

The bottom layer of the planned stack (``… → Messaging Runtime →
Slack/Discord Adapter``): a self-contained, dependency-free, asyncio
package that freezes the platform-agnostic contract concrete adapters
implement. Guiding principle: **abstract concepts, not APIs** — nothing
above this boundary may know whether it is talking to Slack or Discord.

Modules: ``model`` (domain nouns), ``errors`` (failure taxonomy),
``interactions`` (components/modals/commands), ``capabilities`` (feature
discovery), ``adapter`` (the frozen ``ChatAdapter`` ABC), ``mock``
(deterministic in-memory implementation for tests).

Contract: imports ONLY from within ``chat/`` and the stdlib — no aitasks
framework module (guard-tested by ``tests/test_chat_no_aitasks_import.sh``);
``__all__`` is exact and pinned by ``tests/test_chat_contract.sh``.
"""
from __future__ import annotations

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
    CommandOption,
    Form,
    FormField,
    Interaction,
    InteractionType,
    Modal,
    SelectMenu,
    SelectOption,
    SlashCommand,
)
from .mock import MockChatAdapter
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
    Permission,
    Reaction,
    Role,
    User,
    Workspace,
)

__all__ = [
    # model
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
    # interactions
    "Button",
    "SelectMenu",
    "SelectOption",
    "ActionRow",
    "FormField",
    "Modal",
    "Form",
    "SlashCommand",
    "CommandOption",
    "InteractionType",
    "Interaction",
    # capabilities
    "Capabilities",
    # adapter + mock
    "ChatAdapter",
    "MockChatAdapter",
    # errors
    "ChatError",
    "ConversationNotFound",
    "PermissionDenied",
    "RateLimited",
    "AttachmentTooLarge",
    "UserNotFound",
    "DeliveryFailed",
    "InteractionExpired",
]
