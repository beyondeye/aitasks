"""status_paths - where the monitor status servers live on disk (stdlib only).

The runtime directory, the per-(tmux server, VERSION) socket stem and its key,
and the listing of the server sockets in that directory. Shared by
``status_server.py`` (which re-exports every name here) and by
``status_restart.py``, the restart procedure — which must stay importable
WITHOUT the framework venv: the ``ait upgrade`` hook runs it at install time,
where ``status_server.py`` (``monitor_core`` -> ``task_yaml`` -> ``yaml``) may
not import. Keep this module stdlib-only.

Specification: ``aidocs/framework/monitor_status_protocol.md`` ("Socket path",
"Restart").
"""
from __future__ import annotations

import hashlib
import os
import re
from dataclasses import dataclass
from pathlib import Path

RUNTIME_SUBDIR = "aitasks"
FALLBACK_RUNTIME_DIR = "~/.aitask/run"

_SLUG_RE = re.compile(r"[A-Za-z0-9._+-]{1,64}")

#: A server socket's file name: ``monitor-<16 hex tmux key>-<version slug>.sock``.
SOCKET_NAME_RE = re.compile(
    r"^monitor-(?P<key>[0-9a-f]{16})-(?P<slug>[A-Za-z0-9._+-]{1,64})\.sock$")


def runtime_dir(environ=None) -> Path:
    """``$XDG_RUNTIME_DIR/aitasks`` when that is an existing directory, else
    ``~/.aitask/run``. Resolution only — ``status_server.ensure_runtime_dir``
    creates and checks it."""
    env = os.environ if environ is None else environ
    xdg = env.get("XDG_RUNTIME_DIR")
    if xdg and os.path.isdir(xdg):
        return Path(xdg) / RUNTIME_SUBDIR
    return Path(os.path.expanduser(FALLBACK_RUNTIME_DIR))


def version_slug(version: str) -> str:
    """``version`` itself when it is filename-safe, else ``v`` + a hash."""
    if _SLUG_RE.fullmatch(version):
        return version
    return "v" + hashlib.sha256(version.encode("utf-8", "surrogatepass")).hexdigest()[:12]


def tmux_key(tmux_socket: str) -> str:
    """The 16-hex key of a tmux server, from its own ``#{socket_path}``."""
    return hashlib.sha256(tmux_socket.encode("utf-8", "surrogateescape")).hexdigest()[:16]


def socket_stem(tmux_socket: str, version: str) -> str:
    return f"monitor-{tmux_key(tmux_socket)}-{version_slug(version)}"


def lock_path_for(socket_path) -> Path:
    socket_path = Path(socket_path)
    return socket_path.with_name(socket_path.stem + ".lock")


@dataclass(frozen=True)
class ServerSocket:
    path: Path
    key: str
    slug: str


def list_server_sockets(directory, *, key: str | None = None,
                        version: str | None = None) -> list[ServerSocket]:
    """The server sockets in ``directory``, sorted by name.

    ``key`` keeps one tmux server's sockets only; ``version`` keeps one
    VERSION's, compared as the exact slug (so ``0.40.1`` never matches
    ``0.40.10``). A missing or unreadable directory lists nothing. Only the
    NAME is matched: whether a file is a live socket is the caller's question.
    """
    want_slug = version_slug(version) if version is not None else None
    try:
        names = sorted(os.listdir(directory))
    except OSError:
        return []
    out = []
    for name in names:
        m = SOCKET_NAME_RE.match(name)
        if m is None:
            continue
        if key is not None and m["key"] != key:
            continue
        if want_slug is not None and m["slug"] != want_slug:
            continue
        out.append(ServerSocket(Path(directory) / name, m["key"], m["slug"]))
    return out
