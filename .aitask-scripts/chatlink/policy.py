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

**Per-dimension authorization modes** (t1186_1): the user and role
dimensions each run in ``allowlist`` or ``denylist`` mode
(``ChatlinkConfig.user_authorization_mode`` / ``role_authorization_mode``,
both default ``allowlist`` — the pinned deny-by-default posture). Each
dimension consults only its mode's active list; the other list is ignored.
Composition precedence is pinned: **explicit deny > explicit allow >
default** — the default allows (``ok_not_denied``) only when BOTH
dimensions are denylist, else it denies. An empty allowlist dimension
therefore keeps meaning "nobody" (fail-closed), and the degenerate
deny-all combinations are classified by :func:`effective_posture`.

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
REASON_USER_DENIED = "user_denied"
REASON_ROLE_DENIED = "role_denied"
REASON_NOT_INITIATOR = "not_initiator"
REASON_OK_USER = "ok_user"
REASON_OK_ROLE = "ok_role"
REASON_OK_NOT_DENIED = "ok_not_denied"
REASON_OK_INITIATOR = "ok_initiator"


@dataclass
class Decision:
    """An authorization outcome: ``allow`` plus its machine-readable reason."""

    allow: bool
    reason: str


def decide(claims: "IdentityClaims | None", config: "ChatlinkConfig | None") -> Decision:
    """May this user initiate a bug-report intake? Deny-by-default.

    Order: config present → claims present → channel membership → explicit
    denies (each dimension's denylist, when that dimension is in denylist
    mode) → explicit allows (each dimension's allowlist, when in allowlist
    mode) → default: allow ``ok_not_denied`` only when BOTH dimensions are
    denylist, else deny (``role_not_allowed`` when the role dimension is an
    allowlist with entries, else ``user_not_allowed`` — covers the
    both-allowlists-empty case).
    """
    if config is None:
        return Decision(False, REASON_NO_CONFIG)
    if claims is None or not getattr(claims, "user_id", ""):
        return Decision(False, REASON_NO_CLAIMS)
    if not claims.is_channel_member:
        return Decision(False, REASON_NOT_CHANNEL_MEMBER)
    user_denylist = config.user_authorization_mode == "denylist"
    role_denylist = config.role_authorization_mode == "denylist"
    if user_denylist and claims.user_id in config.denied_user_ids:
        return Decision(False, REASON_USER_DENIED)
    if role_denylist and any(
            role.id in config.denied_role_ids for role in claims.roles):
        return Decision(False, REASON_ROLE_DENIED)
    if not user_denylist and claims.user_id in config.allowed_user_ids:
        return Decision(True, REASON_OK_USER)
    if not role_denylist and any(
            role.id in config.allowed_role_ids for role in claims.roles):
        return Decision(True, REASON_OK_ROLE)
    if user_denylist and role_denylist:
        return Decision(True, REASON_OK_NOT_DENIED)
    if not role_denylist and config.allowed_role_ids:
        return Decision(False, REASON_ROLE_NOT_ALLOWED)
    return Decision(False, REASON_USER_NOT_ALLOWED)


@dataclass(frozen=True)
class Posture:
    """Classified authorization posture of a config (t1186_1).

    ``kind`` is the coarse class; ``degenerate_dimensions`` names the
    dimension(s) (``"users"`` / ``"roles"``) whose **empty active
    allowlist** caused a ``deny_all`` — empty otherwise. Single source of
    the cause: consumers (preflight, the wizard) render copy from these
    facts and never re-derive which combination is degenerate.
    """

    kind: str  #: "deny_all" | "open_members" | "restricted"
    degenerate_dimensions: tuple[str, ...] = ()


def effective_posture(config: "ChatlinkConfig") -> Posture:
    """Classify a config's posture ONCE for preflight / wizard / tests.

    - ``deny_all`` — no allow path exists: every allowlist-mode dimension
      has an empty list, so the restrictive default denies everyone (the
      fail-closed degenerate postures, loudly warned but never silent).
    - ``open_members`` — both dimensions denylist with both denied lists
      empty: any channel member is allowed.
    - ``restricted`` — anything else.
    """
    user_denylist = config.user_authorization_mode == "denylist"
    role_denylist = config.role_authorization_mode == "denylist"
    empty_dims = tuple(
        dim for dim, denylist, allowed in (
            ("users", user_denylist, config.allowed_user_ids),
            ("roles", role_denylist, config.allowed_role_ids),
        ) if not denylist and not allowed
    )
    # An allow path exists iff some allowlist dimension has entries, or
    # both dimensions are denylist (default allows). Otherwise deny-all.
    if not (user_denylist and role_denylist) and len(empty_dims) == (
            (not user_denylist) + (not role_denylist)):
        return Posture("deny_all", empty_dims)
    if (user_denylist and role_denylist
            and not config.denied_user_ids and not config.denied_role_ids):
        return Posture("open_members")
    return Posture("restricted")


def may_answer(session_initiator_id: str | None, actor_id: str | None) -> Decision:
    """The initiating-user-only answer-gating primitive (pinned contract 9).

    Allow only when both ids are non-empty and equal; any mismatch or
    missing/empty id denies (fail-closed).
    """
    if session_initiator_id and actor_id and session_initiator_id == actor_id:
        return Decision(True, REASON_OK_INITIATOR)
    return Decision(False, REASON_NOT_INITIATOR)
