"""Resumable draft of in-progress config-wizard state (t1190).

Written by the wizard driver on every step transition to the gitignored,
0700 per-PC sessions dir (``paths.sessions_dir()``); deleted on a fully
successful summary-step save or an explicit "Start fresh". The next
wizard launch offers resume / start-fresh when a draft exists.

Token hygiene (pinned): a draft NEVER contains the bot token. Only the
keys in :data:`DRAFT_STATE_KEYS` are serialized — a fail-closed explicit
allowlist mirroring ``wizard.build_edits`` (never ``**state``), so
``token`` and transient ``_``-prefixed working entries are excluded by
construction. ``token_entered`` records only the secret's *existence*
(the wizard caps resume at the token step when set). Loads filter
through the same allowlist and validate every value against the
``chatlink.config`` ranges/enums, rejecting the whole draft on any
anomaly (the fail-closed corrupt-record stance of ``sessions_store`` /
``reconcile`` — a tampered or stale draft must not inject values past
the screens that would normally validate them).

Textual-free (guard-tested) so the headless wizard suite covers it.
All writes are atomic (pid-suffixed ``*.tmp`` + ``os.replace``, the
``sessions_store`` discipline; best-effort 0600).
"""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from . import config, paths

DRAFT_FILENAME = "wizard_draft.json"
DRAFT_VERSION = 1

#: Every non-secret key of ``wizard.initial_state`` — the ONLY keys a
#: draft may carry. ``token`` is deliberately absent; a drift-guard test
#: pins ``set(DRAFT_STATE_KEYS) == set(initial_state(...)) - {"token"}``.
DRAFT_STATE_KEYS = (
    "provider", "workspace_id", "conversation_id", "thread_id",
    "allowed_user_ids", "allowed_role_ids",
    "denied_user_ids", "denied_role_ids",
    "user_authorization_mode", "role_authorization_mode",
    "deny_message_mode", "repo_name",
    "max_concurrent_sandboxes", "intake_rate_per_user_per_hour",
    "sandbox_memory", "sandbox_cpus", "sandbox_pids",
    "sandbox_wall_clock_s",
)

_STR_KEYS = ("provider", "workspace_id", "conversation_id", "thread_id",
             "repo_name")
_ID_LIST_KEYS = ("allowed_user_ids", "allowed_role_ids",
                 "denied_user_ids", "denied_role_ids")
_RANGE_KEYS = {
    "max_concurrent_sandboxes": config.RANGE_MAX_CONCURRENT_SANDBOXES,
    "intake_rate_per_user_per_hour":
        config.RANGE_INTAKE_RATE_PER_USER_PER_HOUR,
    "sandbox_cpus": config.RANGE_SANDBOX_CPUS,
    "sandbox_pids": config.RANGE_SANDBOX_PIDS,
    "sandbox_wall_clock_s": config.RANGE_SANDBOX_WALL_CLOCK_S,
}


def draft_path() -> Path:
    return paths.sessions_dir() / DRAFT_FILENAME


def config_fingerprint(config_path: Path) -> str | None:
    """sha256 of the saved config's bytes; ``None`` if missing/unreadable.

    Recorded at draft time so a later resume can warn when the config
    changed underneath the draft (staleness is surfaced, never silently
    resolved)."""
    try:
        return hashlib.sha256(Path(config_path).read_bytes()).hexdigest()
    except OSError:
        return None


def save_draft(step_name: str, state: dict, fingerprint: str | None, *,
               path: Path | None = None) -> None:
    """Atomically persist the allowlisted state + resume metadata."""
    path = path or draft_path()
    paths.ensure_secure_dir(path.parent)
    payload = {
        "version": DRAFT_VERSION,
        "saved_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "step_name": step_name,
        "token_entered": bool(state.get("token")),
        "config_fingerprint": fingerprint,
        "state": {k: state[k] for k in DRAFT_STATE_KEYS if k in state},
    }
    tmp = path.with_name(path.name + f".{os.getpid()}.tmp")
    tmp.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    try:
        tmp.chmod(0o600)
    except OSError:
        pass
    os.replace(tmp, path)


def _valid_value(key: str, val) -> bool:
    if key in _STR_KEYS:
        return isinstance(val, str)
    if key in _ID_LIST_KEYS:
        return (isinstance(val, list)
                and all(isinstance(v, str) for v in val))
    if key in ("user_authorization_mode", "role_authorization_mode"):
        return val in config.AUTHORIZATION_MODES
    if key == "deny_message_mode":
        return val in config.DENY_MESSAGE_MODES
    if key in _RANGE_KEYS:
        lo, hi = _RANGE_KEYS[key]
        return (isinstance(val, int) and not isinstance(val, bool)
                and lo <= val <= hi)
    if key == "sandbox_memory":
        return isinstance(val, str) and bool(config.SANDBOX_MEMORY_RE.match(val))
    return False


def load_draft(*, path: Path | None = None) -> dict | None:
    """Load and validate the draft; ``None`` means "no usable draft".

    Fail-closed: any parse error, version mismatch, malformed envelope,
    or invalid state value rejects the WHOLE draft. A key absent from
    ``state`` is fine (the wizard falls back to its ``initial_state``
    prefill for it); a present-but-invalid value is not."""
    path = path or draft_path()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(raw, dict) or raw.get("version") != DRAFT_VERSION:
        return None
    step_name = raw.get("step_name")
    state = raw.get("state")
    if not isinstance(step_name, str) or not isinstance(state, dict):
        return None
    filtered = {k: v for k, v in state.items() if k in DRAFT_STATE_KEYS}
    if not all(_valid_value(k, v) for k, v in filtered.items()):
        return None
    fingerprint = raw.get("config_fingerprint")
    return {
        "saved_at": raw.get("saved_at"),
        "step_name": step_name,
        "token_entered": bool(raw.get("token_entered")),
        "config_fingerprint":
            fingerprint if isinstance(fingerprint, str) else None,
        "state": filtered,
    }


def clear_draft(*, path: Path | None = None) -> None:
    (path or draft_path()).unlink(missing_ok=True)
