"""_subscription — shared per-subscriber broadcast hub for platform adapters.

Slice of the layer: the fan-out plumbing behind every adapter's
``subscribe()``. Platform transports (Discord Gateway, Slack Socket Mode)
deliver each dispatch to a single callback; the ``ChatAdapter`` contract
requires *independent* per-subscriber streams. This module is the one
implementation of that bridge — platform-free (domain ``Event`` /
``ConversationRef`` + asyncio only), extracted verbatim from the Discord
adapter in t1074_3 so the Slack adapter reuses it instead of cloning it
(mirrors ``mock.py``'s proven ``_Subscriber`` + sentinel design).

Module-private: not exported from ``chat/__init__`` (the package surface is
pinned stdlib-only and adapters re-import from here).
"""
from __future__ import annotations

import asyncio

from .model import ConversationRef, Event

# Per-subscriber queue bound. On overflow the hub disconnects THAT subscriber
# (sentinel push) instead of dropping events silently — "at-least-once while
# connected" stays honest.
SUBSCRIBER_QUEUE_MAXSIZE = 1024

# Sentinel pushed into subscriber queues to end a subscribe() stream
# (transport drop or per-subscriber overflow). Mirrors mock.py's design.
_DISCONNECT = object()


def _ref_key(ref: ConversationRef) -> str:
    """Filter key for a ref: the most specific id (thread over channel)."""
    return ref.thread_id or ref.conversation_id


class _Subscriber:
    """One active subscribe() stream: bounded queue + optional filters."""

    def __init__(self, keys: set[str] | None, since: float | None) -> None:
        self.keys = keys                      # None = all conversations
        self.since = since
        self.queue: asyncio.Queue = asyncio.Queue(maxsize=SUBSCRIBER_QUEUE_MAXSIZE)


class _SubscriptionHub:
    """Broadcast fan-out from the single transport callback to N subscribers.

    Contract fidelity (mirrors ``MockChatAdapter``): each subscriber owns
    its queue (independent streams, no competition); filtering happens at
    enqueue time; a full queue disconnects only that subscriber (sentinel
    push after draining — never a silent drop); a transport disconnect ends
    every stream with no replay.
    """

    def __init__(self) -> None:
        self._subscribers: list[_Subscriber] = []

    def add(self, sub: _Subscriber) -> None:
        self._subscribers.append(sub)

    def remove(self, sub: _Subscriber) -> None:
        if sub in self._subscribers:
            self._subscribers.remove(sub)

    def publish(self, event: Event) -> None:
        for sub in list(self._subscribers):
            if sub.since is not None and event.timestamp < sub.since:
                continue
            if sub.keys is not None and event.conversation is not None:
                if _ref_key(event.conversation) not in sub.keys:
                    continue
            # Events without a conversation are delivered to all (contract).
            try:
                sub.queue.put_nowait(event)
            except asyncio.QueueFull:
                # Overflow = this subscriber is too slow: disconnect IT (and
                # only it). Drain so the sentinel always lands.
                while not sub.queue.empty():
                    try:
                        sub.queue.get_nowait()
                    except asyncio.QueueEmpty:  # pragma: no cover - race-safe
                        break
                sub.queue.put_nowait(_DISCONNECT)
                self.remove(sub)

    def disconnect_all(self) -> None:
        """Transport drop: end every active stream (no replay).

        Sentinel-safe like the overflow path: a subscriber whose bounded
        queue is exactly full would make a bare ``put_nowait`` raise
        ``QueueFull`` out of the transport's disconnect listener, leaving
        the remaining streams never ended — drain first in that case.
        """
        for sub in list(self._subscribers):
            try:
                sub.queue.put_nowait(_DISCONNECT)
            except asyncio.QueueFull:
                while not sub.queue.empty():
                    try:
                        sub.queue.get_nowait()
                    except asyncio.QueueEmpty:  # pragma: no cover - race-safe
                        break
                sub.queue.put_nowait(_DISCONNECT)
        self._subscribers.clear()
