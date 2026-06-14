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


def metadata_dir() -> Path:
    return project_root() / "aitasks" / "metadata"


def sessions_dir() -> Path:
    """Gitignored, per-PC runtime dir: TLS cert/key + ``sessions.json``."""
    return metadata_dir() / "applink_sessions"


def profiles_dir() -> Path:
    """Checked-in, shared permission-profile YAMLs."""
    return metadata_dir() / "applink_profiles"
