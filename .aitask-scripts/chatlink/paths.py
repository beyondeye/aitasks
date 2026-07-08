"""Filesystem locations for the chatlink gateway (t1120_2).

Resolves project-relative paths for the gitignored, per-PC runtime state (the
bot-token file + relay spool dirs under ``aitasks/metadata/chatlink_sessions/``)
and the shared, checked-in gateway config
(``aitasks/metadata/chatlink_config.yaml``). Kept in one place so every
chatlink module agrees on where these live; in separate-``aitask-data``-branch
mode the ``aitasks`` symlink resolves both under ``.aitask-data/``.

Gateway-side (imported by the daemon / config layer, never by the agent-side
``relay`` / ``relay_ask`` — the import-purity guard in
``tests/test_chatlink_relay.sh`` stays unaffected).

Import contract: importing any ``chatlink.*`` module requires only
``.aitask-scripts`` on ``sys.path`` (the ``PYTHONPATH`` the
``aitask_relay_ask.sh`` wrapper already sets). The ``config_utils`` dependency
below bootstraps ``lib/`` itself when needed.

No environment variables are defined by chatlink v1: the token file is the
only token source, and relay dirs are passed by argv (t1120_1). Recorded here
per pinned contract 10 ("no env-var names invented outside t1120_2").
"""
from __future__ import annotations

import sys
from pathlib import Path

try:
    from config_utils import resolve_config_path
except ImportError:  # entrypoint did not pre-insert .aitask-scripts/lib
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))
    from config_utils import resolve_config_path

#: Repo-root-relative location of the shared gateway config (pinned
#: contract 10); also the ``default_rel`` behind the ``chatlink.config``
#: project_config.yaml override key.
CONFIG_DEFAULT_REL = "aitasks/metadata/chatlink_config.yaml"


def project_root() -> Path:
    """Repo root — three levels up from ``.aitask-scripts/chatlink/paths.py``."""
    return Path(__file__).resolve().parent.parent.parent


def ensure_secure_dir(path: Path) -> Path:
    """``mkdir -p`` the dir and best-effort ``chmod 0o700`` (owner-only).

    Owner-only mode on the gitignored runtime dir is the *structural* guard
    for the secrets it holds (bot token, relay spools): even if a file inside
    is created world-readable by a lax umask, another local user cannot
    traverse in to read it. Best-effort — silently tolerated on filesystems
    without POSIX modes (mirrors applink ``paths.ensure_secure_dir``).
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
    """Gitignored, per-PC runtime dir: bot token + relay spools."""
    return metadata_dir() / "chatlink_sessions"


def token_file() -> Path:
    """The per-PC bot-token file (0600, gitignored — pinned contract 10)."""
    return sessions_dir() / "bot_token"


def relay_root() -> Path:
    """Parent dir of per-session relay spools (``relay.create_session_dir`` arg)."""
    return sessions_dir() / "relay"


def workspaces_root_beside(relay_root_path: Path) -> Path:
    """Workspace-copy root for a given relay root (``…/relay`` →
    ``…/workspaces``). Single derivation point so injected test relay roots
    and production agree on where per-session workspace copies live."""
    return Path(relay_root_path).parent / "workspaces"


def workspaces_root() -> Path:
    """Parent dir of per-session disposable workspace copies (t1120_5)."""
    return workspaces_root_beside(relay_root())


def write_token(token: str) -> Path:
    """Write the bot token with owner-only permissions (dir 0700, file 0600).

    The chmod is best-effort like :func:`ensure_secure_dir`, but the 0700 dir
    is the structural guard even where file modes are unsupported.
    """
    path = token_file()
    ensure_secure_dir(path.parent)
    path.write_text(token, encoding="utf-8")
    try:
        path.chmod(0o600)
    except OSError:
        pass
    return path


def read_token() -> str | None:
    """Read the bot token; ``None`` when missing/unreadable (never raises)."""
    try:
        token = token_file().read_text(encoding="utf-8").strip()
    except OSError:
        return None
    return token or None


def config_file() -> Path | None:
    """Absolute path to the gateway config, or ``None`` when absent.

    Reuses the canonical ``resolve_config_path`` seam (``chatlink.config``
    key in ``project_config.yaml``, seeded default ``CONFIG_DEFAULT_REL``).
    The resolver returns a repo-root-relative string, so it is absolutized
    against :func:`project_root` here — the daemon may run from any cwd.
    ``None`` means no readable config exists ⇒ callers fail closed.
    """
    rel = resolve_config_path(
        "chatlink.config",
        default_rel=CONFIG_DEFAULT_REL,
        root=project_root(),
    )
    if rel is None:
        return None
    return project_root() / rel
