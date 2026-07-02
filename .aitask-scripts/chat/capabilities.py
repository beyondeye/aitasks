"""capabilities — feature-discovery surface of the chat abstraction layer.

Slice of the layer: what each platform can and cannot do, stated as data.
Normalizes the platforms' uneven feature sets (Slack has native ephemerals
and message search; Discord has standalone threads and voice) into one
introspectable struct ("abstract concepts, not APIs").

Purpose: higher layers *adapt* to the platform instead of hard-coding
platform assumptions — check the flag, then choose the strategy (e.g. no
modals → fall back to a message-based form flow).
"""
from __future__ import annotations

from dataclasses import dataclass, field

__all__ = ["Capabilities"]


@dataclass
class Capabilities:
    """Static feature flags and limits for one adapter.

    What it abstracts: the feature matrix of Slack vs Discord — e.g.
    ``supports_ephemeral`` (Slack ``chat.postEphemeral`` yes / Discord only
    as interaction responses), ``supports_standalone_threads`` (Discord
    channel-threads yes / Slack no), ``supports_message_search`` (Slack
    ``search.messages`` yes / Discord no bot API), ``max_message_length``
    (Slack ~40000 / Discord 2000), ``max_attachment_bytes`` (varies by plan
    / boost tier).

    Purpose: returned by ``ChatAdapter.capabilities()`` so higher layers
    branch on capability, never on platform name. Contract: values are
    static for the adapter instance's context; ``False``/small is the
    honest default when a platform's support is conditional.
    """

    supports_buttons: bool = True
    supports_selects: bool = True
    supports_modals: bool = True
    supports_slash_commands: bool = True
    supports_reactions: bool = True
    supports_files: bool = True
    supports_ephemeral: bool = True
    supports_dm: bool = True
    supports_voice: bool = False
    supports_editing: bool = True
    supports_thread_creation: bool = True
    supports_standalone_threads: bool = False
    supports_message_search: bool = False
    max_message_length: int = 2000
    max_attachment_bytes: int = 8 * 1024 * 1024
    metadata: dict = field(default_factory=dict)
