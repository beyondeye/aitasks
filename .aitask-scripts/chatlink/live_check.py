"""live_check — optional live Discord validation for the config wizard.

Connects to Discord with the entered token and affirmatively verifies, at
config time, the failure modes the docs troubleshooting table can only
diagnose after the fact: token validity, privileged intents (Message
Content / Server Members), intake-channel visibility, and the bot's
permission set. Discord-only (the wizard gates the step on
``provider == "discord"``).

Contracts (t1149_5):

- **Textual-free and discord-import-free at module level.** The real SDK
  is reached only through the lazy default ``connector``
  (``DiscordAdapter.connect``); tests inject an async fake connector and
  never import ``discord``.
- **Never raises, never hangs.** Every failure becomes a specific
  :class:`~chatlink.preflight.CheckResult` row; the whole run is bounded
  by a wall-clock deadline shared across stages; the connection is torn
  down on all paths (success, failure, timeout) via a bounded ``close()``.
- **Token hygiene.** Row messages are fixed templates carrying at most an
  exception *class name* — never ``str(exc)``/``repr(exc)``, which can
  embed the token (HTTP layers, SDK reprs, fakes).
"""
from __future__ import annotations

import asyncio
import contextlib
import time

from chat.model import ConversationRef

from .preflight import FAIL, PASS, TRANSPORT, WARN, CheckResult

#: Overall wall-clock cap for one live-check run (all stages share it).
LIVE_CHECK_TIMEOUT_S = 30.0
#: Bound on the teardown close awaited in the finally path.
CLOSE_TIMEOUT_S = 5.0

# Bot permissions the current bug-report intake / explore-relay flow needs
# on the intake channel, as discord.py Permissions attribute names.
# Canonical list: aidocs/chat/discord_bot_setup.md step 5 (the invite-URL
# permission set) — update the two together.
REQUIRED_BOT_PERMISSIONS = (
    "view_channel",
    "send_messages",
    "send_messages_in_threads",
    "create_public_threads",
    "create_private_threads",
    "manage_threads",
    "read_message_history",
    "attach_files",
    "embed_links",
    "add_reactions",
)
#: Documented as "drop if not needed" — absence is a warn, not a fail.
OPTIONAL_BOT_PERMISSIONS = ("manage_messages",)

_CHECK_IDS = ("live_login", "live_intents", "live_channel_visible",
              "live_permissions")

_FIX_TOKEN = ("reset the bot token in the Discord developer portal "
              "(Bot page) and re-enter it in the wizard")
_FIX_INTENTS = ("enable BOTH privileged intents — Message Content and "
                "Server Members — on the portal Bot page, then restart")
_FIX_VISIBILITY = ("check server/channel ids and invite the bot to the "
                   "server with channel access "
                   "(aidocs/chat/discord_bot_setup.md)")
_FIX_PERMISSIONS = ("re-invite the bot with the documented permission set "
                    "(aidocs/chat/discord_bot_setup.md, invite URL step)")


def _row(check_id: str, severity: str, message: str,
         fix_hint: str = "") -> CheckResult:
    return CheckResult(id=check_id, category=TRANSPORT, severity=severity,
                       message=message, fix_hint=fix_hint)


def _not_checked(check_id: str, reason: str) -> CheckResult:
    return _row(check_id, WARN, f"not checked — {reason}")


def _fill_not_checked(results: list[CheckResult], reason: str) -> None:
    """Append WARN rows for every stage not reached, keeping row order."""
    have = {res.id for res in results}
    for check_id in _CHECK_IDS:
        if check_id not in have:
            results.append(_not_checked(check_id, reason))


def _exc_names(exc: BaseException) -> set[str]:
    """Class names across the MRO — SDK-import-free matching (same idiom
    as chat.discord_adapter.map_discord_error)."""
    return {cls.__name__ for cls in type(exc).__mro__}


def run_live_checks(token: str, workspace_id: str, conversation_id: str,
                    thread_id: str | None = None, *,
                    timeout: float = LIVE_CHECK_TIMEOUT_S,
                    connector=None) -> list[CheckResult]:
    """Run the live Discord checks; always returns exactly four rows.

    Sync (thread-worker friendly): runs its own fresh asyncio loop.
    ``connector`` defaults lazily to ``DiscordAdapter.connect``; tests
    inject an async fake returning a fake adapter.
    """
    return asyncio.run(_run_async(token, workspace_id, conversation_id,
                                  thread_id, timeout, connector))


async def _run_async(token: str, workspace_id: str, conversation_id: str,
                     thread_id: str | None, timeout: float,
                     connector) -> list[CheckResult]:
    if connector is None:
        # Lazy: needs the chat tier + SDK (pattern: chatlink/daemon.py).
        from chat.discord_adapter import DiscordAdapter
        connector = DiscordAdapter.connect

    deadline = time.monotonic() + timeout

    def remaining() -> float:
        return max(0.001, deadline - time.monotonic())

    results: list[CheckResult] = []

    # ---- stage 1+2: connect (login + privileged intents) -------------- #
    try:
        adapter = await asyncio.wait_for(connector(token), remaining())
    except asyncio.TimeoutError:
        results.append(_row(
            "live_login", FAIL,
            f"connection timed out after {timeout:.0f}s", _FIX_TOKEN))
        _fill_not_checked(results, "connection timed out")
        return results
    except BaseException as exc:  # noqa: BLE001 - contract: never raises
        names = _exc_names(exc)
        if "LoginFailure" in names:
            results.append(_row(
                "live_login", FAIL, "token rejected by Discord",
                _FIX_TOKEN))
            _fill_not_checked(results, "login failed")
        elif "PrivilegedIntentsRequired" in names:
            results.append(_row("live_login", PASS, "token accepted"))
            results.append(_row(
                "live_intents", FAIL,
                "privileged intents not enabled for this bot",
                _FIX_INTENTS))
            _fill_not_checked(results, "intents not granted")
        else:
            # Sanitized: class name only — exception text may embed the
            # token (pinned hygiene contract).
            results.append(_row(
                "live_login", FAIL,
                f"connection failed ({type(exc).__name__})", _FIX_TOKEN))
            _fill_not_checked(results, "connection failed")
        return results

    try:
        # Reaching ready means the Gateway accepted the requested intents.
        results.append(_row("live_login", PASS, "token accepted"))
        results.append(_row(
            "live_intents", PASS,
            "privileged intents granted (Message Content, Server Members)"))

        target_ref = ConversationRef(
            provider="discord", workspace_id=workspace_id,
            conversation_id=conversation_id, thread_id=thread_id or None)

        # ---- stage 3: visibility of the configured intake target ------ #
        thread_note = " (thread)" if thread_id else ""
        try:
            await asyncio.wait_for(
                adapter.fetch_conversation(target_ref), remaining())
        except asyncio.TimeoutError:
            results.append(_row(
                "live_channel_visible", FAIL,
                f"channel lookup timed out after {timeout:.0f}s",
                _FIX_VISIBILITY))
            _fill_not_checked(results, "channel lookup timed out")
            return results
        except BaseException as exc:  # noqa: BLE001
            names = _exc_names(exc)
            if "ConversationNotFound" in names:
                message = (f"intake channel{thread_note} not found or "
                           "not visible to the bot")
            elif "PermissionDenied" in names:
                message = (f"bot lacks access to the intake "
                           f"channel{thread_note}")
            else:
                message = (f"channel lookup failed "
                           f"({type(exc).__name__})")
            results.append(_row("live_channel_visible", FAIL, message,
                                _FIX_VISIBILITY))
            _fill_not_checked(results, "channel not visible")
            return results
        results.append(_row(
            "live_channel_visible", PASS,
            f"intake channel{thread_note} visible to the bot"))

        # ---- stage 4: bot permission set (ALWAYS the parent channel —
        # create/manage-thread capabilities live on the parent; seeing an
        # existing thread proves nothing about them) -------------------- #
        parent_ref = ConversationRef(
            provider="discord", workspace_id=workspace_id,
            conversation_id=conversation_id, thread_id=None)
        try:
            perms = await asyncio.wait_for(
                adapter.fetch_bot_permissions(
                    parent_ref,
                    REQUIRED_BOT_PERMISSIONS + OPTIONAL_BOT_PERMISSIONS),
                remaining())
        except asyncio.TimeoutError:
            results.append(_row(
                "live_permissions", FAIL,
                f"permission lookup timed out after {timeout:.0f}s",
                _FIX_PERMISSIONS))
            return results
        except BaseException as exc:  # noqa: BLE001
            names = _exc_names(exc)
            if "UserNotFound" in names:
                message = ("could not resolve the bot's own member in "
                           "the server")
            else:
                message = (f"permission lookup failed "
                           f"({type(exc).__name__})")
            results.append(_row("live_permissions", FAIL, message,
                                _FIX_PERMISSIONS))
            return results
        if not perms:
            results.append(_row(
                "live_permissions", PASS,
                "n/a (DM channel — no guild permission model)"))
            return results
        missing_required = [name for name in REQUIRED_BOT_PERMISSIONS
                            if not perms.get(name)]
        missing_optional = [name for name in OPTIONAL_BOT_PERMISSIONS
                            if not perms.get(name)]
        if missing_required:
            results.append(_row(
                "live_permissions", FAIL,
                "missing required channel permission(s): "
                + ", ".join(missing_required), _FIX_PERMISSIONS))
        elif missing_optional:
            results.append(_row(
                "live_permissions", WARN,
                "missing optional permission(s): "
                + ", ".join(missing_optional)
                + " (documented as drop-if-not-needed)"))
        else:
            results.append(_row(
                "live_permissions", PASS,
                "required channel permissions present"))
        return results
    finally:
        # Guaranteed teardown on every path, itself bounded so a stuck
        # close can never hang the wizard.
        with contextlib.suppress(BaseException):
            await asyncio.wait_for(adapter.close(), CLOSE_TIMEOUT_S)
