"""errors — normalized error taxonomy for the chat abstraction layer.

Slice of the layer: adapters translate raw platform failures (Slack API
``error`` strings, Discord HTTP/Gateway exceptions) into this small, closed
set of exceptions so higher layers can handle failures without knowing which
platform produced them ("abstract concepts, not APIs").

Purpose: a frozen, platform-agnostic failure vocabulary. Adapters MUST map
platform errors onto these classes and MUST NOT let SDK exception types
escape above the adapter boundary.
"""
from __future__ import annotations

__all__ = [
    "ChatError",
    "ConversationNotFound",
    "PermissionDenied",
    "RateLimited",
    "AttachmentTooLarge",
    "UserNotFound",
    "DeliveryFailed",
    "InteractionExpired",
]


class ChatError(Exception):
    """Base class for every error raised by the chat abstraction layer.

    What it abstracts: the union of Slack API error responses and Discord
    HTTP/Gateway exceptions, re-rooted under one framework-owned base.

    Purpose: lets higher layers write ``except ChatError`` without importing
    any platform SDK. Contract: every exception an adapter raises for a chat
    operation is an instance of this class (or a subclass below); platform
    detail may be attached to ``args`` / ``__cause__`` but never as the
    exception type itself.
    """


class ConversationNotFound(ChatError):
    """A conversation reference could not be resolved.

    What it abstracts: Slack ``channel_not_found`` / ``thread_not_found``;
    Discord Unknown Channel / Unknown Thread (HTTP 404, code 10003).

    Purpose: existence signal for reconnect/recovery — higher layers probe a
    stored ``ConversationRef`` via ``fetch_conversation`` and use this error
    to detect a deleted/archived-beyond-reach conversation. Contract: raised
    by any operation whose target conversation (or thread) does not exist.
    """


class PermissionDenied(ChatError):
    """The bot lacks permission for the attempted operation.

    What it abstracts: Slack ``missing_scope`` / ``not_in_channel`` /
    ``restricted_action``; Discord Missing Permissions / Missing Access
    (HTTP 403, code 50013/50001). Also raised for operations the platform
    cannot express at all (e.g. standalone threads on Slack — see
    ``ChatAdapter.create_conversation``).

    Purpose: distinguishes "not allowed / not supported here" from "does not
    exist", so higher layers can surface actionable permission errors.
    """


class RateLimited(ChatError):
    """The platform throttled the request.

    What it abstracts: Slack ``ratelimited`` (HTTP 429 + ``Retry-After``);
    Discord rate-limit buckets (HTTP 429).

    Purpose: gives higher layers a single retry/backoff trigger. Contract:
    adapters raise it only after exhausting their own transparent retry
    budget (if any); the retry-after hint, when known, goes in ``args``.
    """


class AttachmentTooLarge(ChatError):
    """An uploaded attachment exceeds the platform's size limit.

    What it abstracts: Slack file-size limits; Discord upload limits (which
    vary by guild boost tier).

    Purpose: pairs with ``Capabilities.max_attachment_bytes`` — higher
    layers can pre-check the advertised limit, and this error is the
    authoritative backstop when the platform still refuses the upload.
    """


class UserNotFound(ChatError):
    """A user id could not be resolved to a platform user.

    What it abstracts: Slack ``user_not_found``; Discord Unknown User /
    Unknown Member (HTTP 404, code 10013).

    Purpose: identity lookups (``fetch_user`` / ``fetch_identity_claims``)
    fail loudly instead of returning half-empty records, so authorization
    layers never act on a phantom identity.
    """


class DeliveryFailed(ChatError):
    """A private (ephemeral/DM) message could not be delivered privately.

    What it abstracts: the terminal state of the private-only ephemeral
    fallback chain — Slack ``chat.postEphemeral`` unavailable and DM failed
    (e.g. ``cannot_dm_bot`` / DMs disabled); Discord ephemeral flag not
    applicable outside an interaction and the user's DMs are closed
    (HTTP 403, code 50007).

    Purpose: the safety valve of the never-post-publicly contract
    (``ChatAdapter.send_ephemeral``): when no private path exists the
    adapter raises this instead of leaking the content to a public channel;
    the higher layer decides what (if anything) to post publicly.
    """


class InteractionExpired(ChatError):
    """A response was attempted after the interaction's follow-up window.

    What it abstracts: Discord's interaction token expiry (15 min after the
    3 s ack window); Slack's ``response_url`` validity window (30 min).

    Purpose: since adapters auto-ack interactions before yielding them
    (see ``ChatAdapter.ack``), the only deadline left for consumers is the
    follow-up window — this error is how they learn they missed it and must
    re-prompt through a fresh message instead.
    """
