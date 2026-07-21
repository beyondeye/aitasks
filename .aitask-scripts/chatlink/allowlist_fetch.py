"""allowlist_fetch — live Discord member/role fetch for the config wizard.

Data source for the wizard's allowlist picker (step "who may open a bug
report"): fetches the intake channel's visible members and the guild's
roles so the operator selects from lists instead of hand-typing snowflake
IDs. Discord-only (the wizard gates the picker on ``provider ==
"discord"``). Also home of the headless ID-validation helpers the manual
entry path uses.

Contracts (mirrors ``live_check`` — t1149_5):

- **Textual-free and discord-import-free at module level.** The real SDK
  is reached only through the lazy default ``connector``
  (``DiscordAdapter.connect``); tests inject an async fake connector and
  never import ``discord``.
- **Never raises, never hangs.** Every failure becomes a sanitized
  per-stage error string on :class:`AllowlistFetchResult`; the whole run
  is bounded by a wall-clock deadline shared across stages; the
  connection is torn down on all paths via a bounded ``close()``.
- **Token hygiene.** Error strings are fixed templates carrying at most
  an exception *class name* — never ``str(exc)``/``repr(exc)``, which
  can embed the token.
- **Partial results.** Members and roles are independent stages: one
  failing does not blank the other.
"""
from __future__ import annotations

import asyncio
import contextlib
import re
import time
from dataclasses import dataclass, field

from chat.model import ConversationRef

from .live_check import CLOSE_TIMEOUT_S, _exc_names

#: Overall wall-clock cap for one fetch run (both stages share it).
FETCH_TIMEOUT_S = 30.0
#: Cap on returned members — guilds can be huge; the picker is searchable
#: but must stay bounded.
MAX_MEMBERS = 500

#: Discord snowflakes are 15-21 decimal digits (same envelope the docs
#: and the wizard's manual-entry validation use).
_SNOWFLAKE_RE = re.compile(r"^\d{15,21}$")


@dataclass
class AllowlistFetchResult:
    """Outcome of one member/role fetch run (always returned, never raised).

    ``members`` is ``(id, display_name)`` pairs with bot accounts filtered
    out (intake drops bot actors anyway); ``roles`` is ``(id, name)``
    pairs. ``members_error`` / ``roles_error`` are per-stage sanitized
    error strings (``None`` = stage succeeded); ``members_truncated`` is
    set when the member list was cut at :data:`MAX_MEMBERS`.
    """

    members: list[tuple[str, str]] = field(default_factory=list)
    roles: list[tuple[str, str]] = field(default_factory=list)
    members_error: str | None = None
    roles_error: str | None = None
    members_truncated: bool = False


def dedupe_ids(ids) -> list[str]:
    """Order-preserving dedupe of an iterable of ID strings."""
    seen: set[str] = set()
    out: list[str] = []
    for i in ids:
        if i not in seen:
            seen.add(i)
            out.append(i)
    return out


def invalid_snowflakes(ids) -> list[str]:
    """The entries that are not snowflake-shaped (15-21 decimal digits)."""
    return [i for i in ids if not _SNOWFLAKE_RE.match(i)]


def run_allowlist_fetch(token: str, workspace_id: str, conversation_id: str,
                        thread_id: str | None = None, *,
                        timeout: float = FETCH_TIMEOUT_S,
                        connector=None) -> AllowlistFetchResult:
    """Fetch pickable members and roles for the intake channel.

    Sync (thread-worker friendly): runs its own fresh asyncio loop.
    ``connector`` defaults lazily to ``DiscordAdapter.connect``; tests
    inject an async fake returning a fake adapter.
    """
    return asyncio.run(_run_async(token, workspace_id, conversation_id,
                                  thread_id, timeout, connector))


async def _run_async(token: str, workspace_id: str, conversation_id: str,
                     thread_id: str | None, timeout: float,
                     connector) -> AllowlistFetchResult:
    if connector is None:
        # Lazy: needs the chat tier + SDK (pattern: chatlink/live_check.py).
        from chat.discord_adapter import DiscordAdapter
        connector = DiscordAdapter.connect

    deadline = time.monotonic() + timeout

    def remaining() -> float:
        return max(0.001, deadline - time.monotonic())

    result = AllowlistFetchResult()

    try:
        adapter = await asyncio.wait_for(connector(token), remaining())
    except asyncio.TimeoutError:
        result.members_error = f"connection timed out after {timeout:.0f}s"
        result.roles_error = result.members_error
        return result
    except BaseException as exc:  # noqa: BLE001 - contract: never raises
        # Sanitized: class name only — exception text may embed the token
        # (pinned hygiene contract).
        msg = f"connection failed ({type(exc).__name__})"
        if "LoginFailure" in _exc_names(exc):
            msg = "token rejected by Discord"
        result.members_error = msg
        result.roles_error = msg
        return result

    try:
        # Both stages target the PARENT channel: an allowlist governs the
        # intake channel, and roles/member enumeration live on its guild
        # (same thread→parent scoping as live_check stage 4).
        parent_ref = ConversationRef(
            provider="discord", workspace_id=workspace_id,
            conversation_id=conversation_id, thread_id=None)

        # ---- stage 1: channel members ------------------------------- #
        try:
            fetched = await asyncio.wait_for(
                adapter.fetch_channel_members(parent_ref), remaining())
        except asyncio.TimeoutError:
            result.members_error = (
                f"member fetch timed out after {timeout:.0f}s")
        except BaseException as exc:  # noqa: BLE001
            result.members_error = (
                f"member fetch failed ({type(exc).__name__})")
        else:
            humans = [u for u in fetched if not getattr(u, "is_bot", False)]
            if len(humans) > MAX_MEMBERS:
                humans = humans[:MAX_MEMBERS]
                result.members_truncated = True
            result.members = [(u.id, u.display_name) for u in humans]

        # ---- stage 2: guild roles ----------------------------------- #
        try:
            roles = await asyncio.wait_for(
                adapter.fetch_roles(parent_ref), remaining())
        except asyncio.TimeoutError:
            result.roles_error = (
                f"role fetch timed out after {timeout:.0f}s")
        except BaseException as exc:  # noqa: BLE001
            result.roles_error = (
                f"role fetch failed ({type(exc).__name__})")
        else:
            result.roles = [(r.id, r.name) for r in roles]

        return result
    finally:
        # Guaranteed teardown on every path, itself bounded so a stuck
        # close can never hang the wizard.
        with contextlib.suppress(BaseException):
            await asyncio.wait_for(adapter.close(), CLOSE_TIMEOUT_S)
