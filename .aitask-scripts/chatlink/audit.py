"""Audit logging for the chatlink gateway (t1120_3).

A single ``chatlink.audit`` logger records security- and lifecycle-relevant
events — intake denials, ceiling rejections, session state transitions,
reconciliation outcomes — to ``chatlink_audit.log`` in the owner-only runtime
dir. Mirrors ``applink/audit.py`` deliberately: stdlib ``logging`` only, no
rotation, lazy idempotent configuration, and a ``NullHandler`` fallback so a
logging failure never takes the daemon down. **Secrets and raw platform ids
are never logged in full** — call sites pass truncated tags.
"""
from __future__ import annotations

import logging
from pathlib import Path

LOGGER_NAME = "chatlink.audit"
AUDIT_FILENAME = "chatlink_audit.log"

_configured = False


def get_logger(sessions_dir: Path) -> logging.Logger:
    """Return the configured ``chatlink.audit`` logger (idempotent).

    Wires a ``FileHandler`` at ``<sessions_dir>/chatlink_audit.log`` on
    first call; falls back to ``NullHandler`` if the dir is unwritable.
    """
    global _configured
    log = logging.getLogger(LOGGER_NAME)
    if not _configured:
        _configured = True
        try:
            sessions_dir.mkdir(parents=True, exist_ok=True)
            try:
                sessions_dir.chmod(0o700)
            except OSError:
                pass
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
