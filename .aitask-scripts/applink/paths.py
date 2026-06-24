"""Filesystem locations for the ait applink server (t822_7).

Resolves project-relative paths for the gitignored, per-PC runtime state (the
TLS cert/key + session table under ``aitasks/metadata/applink_sessions/``) and
the shared, checked-in permission profiles
(``aitasks/metadata/applink_profiles/``). Kept in one place so every applink
module agrees on where these live; in separate-``aitask-data``-branch mode the
``aitasks`` symlink resolves both under ``.aitask-data/``.
"""
from __future__ import annotations

from pathlib import Path


def project_root() -> Path:
    """Repo root — three levels up from ``.aitask-scripts/applink/paths.py``."""
    return Path(__file__).resolve().parent.parent.parent


def ensure_secure_dir(path: Path) -> Path:
    """``mkdir -p`` the dir and best-effort ``chmod 0o700`` (owner-only).

    Owner-only mode on the gitignored runtime dir is the *structural* guard for
    the secrets it holds (TLS key, ``sessions.json``, audit log): even if a file
    inside is created world-readable by a lax umask, another local user cannot
    traverse in to read it. Best-effort — silently tolerated on filesystems
    without POSIX modes (mirrors the key-file ``chmod`` in ``tls.py``).
    """
    path.mkdir(parents=True, exist_ok=True)
    try:
        path.chmod(0o700)
    except OSError:
        pass
    return path


def metadata_dir() -> Path:
    return project_root() / "aitasks" / "metadata"


def sessions_dir() -> Path:
    """Gitignored, per-PC runtime dir: TLS cert/key + ``sessions.json``."""
    return metadata_dir() / "applink_sessions"


def profiles_dir() -> Path:
    """Checked-in, shared permission-profile YAMLs."""
    return metadata_dir() / "applink_profiles"
