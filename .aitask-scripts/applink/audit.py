"""Security audit logging for the ait applink server (t985).

A single ``applink.audit`` logger records security-relevant events — auth
failures, permission denials, pairing outcomes, and DoS-limit rejections — to
``applink_audit.log`` in the (owner-only) runtime dir, for observability and
incident response. Deliberately minimal: stdlib ``logging`` only, no rotation
(the framework keeps no other long-running log; size is bounded by the LAN
threat model), and **secrets are never logged in full** — call sites pass a
short bearer prefix and the device name, never the token bytes.

Configuration is idempotent and lazy: the first :func:`get_logger` call wires a
``FileHandler`` (falling back to ``NullHandler`` if the dir is unwritable, so a
logging failure never takes the listener down). Router unit tests construct a
``FrameRouter`` with their own captured logger, so importing this module has no
side effect until ``get_logger`` runs.
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

# Self-sufficient import of the sibling ``paths`` module (mirrors sessions.py).
sys.path.insert(0, str(Path(__file__).resolve().parent))
from paths import ensure_secure_dir  # noqa: E402

LOGGER_NAME = "applink.audit"
AUDIT_FILENAME = "applink_audit.log"

_configured = False


def get_logger(sessions_dir: Path) -> logging.Logger:
    """Return the configured ``applink.audit`` logger (idempotent).

    Wires a ``FileHandler`` at ``<sessions_dir>/applink_audit.log`` on first
    call; a ``NullHandler`` fallback keeps the logger usable if the file cannot
    be opened. Safe to call from both the TUI and headless startup paths.
    """
    global _configured
    log = logging.getLogger(LOGGER_NAME)
    if not _configured:
        _configured = True
        try:
            ensure_secure_dir(sessions_dir)
            handler = logging.FileHandler(sessions_dir / AUDIT_FILENAME)
            handler.setFormatter(
                logging.Formatter("%(asctime)s %(levelname)s %(message)s")
            )
            log.addHandler(handler)
            log.setLevel(logging.INFO)
            log.propagate = False
        except OSError:
            log.addHandler(logging.NullHandler())
    return log


def bearer_tag(bearer: str | None) -> str:
    """A short, non-reversible tag for a bearer (first 8 chars) for log lines.

    Never log the full 256-bit bearer — a truncated prefix is enough to
    correlate events without putting a usable secret in the log.
    """
    if not bearer:
        return "<none>"
    return f"{bearer[:8]}…"
