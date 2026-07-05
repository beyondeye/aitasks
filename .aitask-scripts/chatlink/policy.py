"""Authorization policy above the chat layer's ``IdentityClaims`` (t1120_2).

The named policy API of pinned contract 9: ``decide(claims, config)`` for
intake authorization and ``may_answer(...)`` — the initiating-user-only
answer-gating **primitive** (never re-derived ad hoc in the daemon).

**Deny-by-default**: absent config, absent/empty claims, unknown user, role
mismatch each deny with a distinct machine-readable reason. Claims semantics
follow ``chat/model.py`` ``IdentityClaims``: absent knowledge is ``False`` /
empty — this layer never invents privileges the platform did not assert.
Role matching is on ``Role.id`` (platform-honest: Discord role ids and Slack
usergroup ids both arrive as ``Role.kind``-tagged claims).

Import-light: ``IdentityClaims`` is referenced for typing only; ``decide``
uses attribute access, so the module imports no ``chat`` code at runtime.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # typing only — no runtime chat/ import
    from chat.model import IdentityClaims

    from .config import ChatlinkConfig

# Machine-readable decision reasons (complete enum — t1120_3 branches on
# these; tests pin one negative control per deny reason).
REASON_NO_CONFIG = "no_config"
REASON_NO_CLAIMS = "no_claims"
REASON_NOT_CHANNEL_MEMBER = "not_channel_member"
REASON_USER_NOT_ALLOWED = "user_not_allowed"
REASON_ROLE_NOT_ALLOWED = "role_not_allowed"
REASON_NOT_INITIATOR = "not_initiator"
REASON_OK_USER = "ok_user"
REASON_OK_ROLE = "ok_role"
REASON_OK_INITIATOR = "ok_initiator"


@dataclass
class Decision:
    """An authorization outcome: ``allow`` plus its machine-readable reason."""

    allow: bool
    reason: str


def decide(claims: "IdentityClaims | None", config: "ChatlinkConfig | None") -> Decision:
    """May this user initiate a bug-report intake? Deny-by-default.

    Order: config present → claims present → channel membership → user
    allowlist → role allowlist → deny (``role_not_allowed`` when roles were
    configured, else ``user_not_allowed`` — covers the both-lists-empty case).
    """
    if config is None:
        return Decision(False, REASON_NO_CONFIG)
    if claims is None or not getattr(claims, "user_id", ""):
        return Decision(False, REASON_NO_CLAIMS)
    if not claims.is_channel_member:
        return Decision(False, REASON_NOT_CHANNEL_MEMBER)
    if claims.user_id in config.allowed_user_ids:
        return Decision(True, REASON_OK_USER)
    if any(role.id in config.allowed_role_ids for role in claims.roles):
        return Decision(True, REASON_OK_ROLE)
    if config.allowed_role_ids:
        return Decision(False, REASON_ROLE_NOT_ALLOWED)
    return Decision(False, REASON_USER_NOT_ALLOWED)


def may_answer(session_initiator_id: str | None, actor_id: str | None) -> Decision:
    """The initiating-user-only answer-gating primitive (pinned contract 9).

    Allow only when both ids are non-empty and equal; any mismatch or
    missing/empty id denies (fail-closed).
    """
    if session_initiator_id and actor_id and session_initiator_id == actor_id:
        return Decision(True, REASON_OK_INITIATOR)
    return Decision(False, REASON_NOT_INITIATOR)
