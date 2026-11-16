"""One isolated tmux session running a real TUI on a sample project.

This is the set of primitives an agent drives a screenshot with: start a
session, prepare data, launch the TUI, read the screen, send keys, wait for
text, find text, stop. It decides nothing about *what* to show.

Isolation rules (see ``aiplans/p2278_docs_tui_screenshot_generator.md``):

* Every tmux call goes through ``TmuxClient`` on a private socket
  ``ait_shots_<id>``. The client adds ``-u`` and decodes UTF-8 (tmux gateway
  policy 5). No tmux argv is built by hand here.
* The server comes into existence in :func:`start_server` only, with
  ``-f /dev/null`` and after checking the socket has no server, so the user's
  tmux configuration is never loaded.
* The pane environment is pinned at spawn: a scratch ``HOME`` and
  ``XDG_CONFIG_HOME`` (the user's project registry, key overrides and themes
  cannot reach the screen), ``AITASKS_TMUX_SOCKET`` (the TUI's own tmux calls
  stay on the private server), ``AIT_PYTHON``, ``COLORTERM``.
* The server kills itself after :data:`TTL_SECONDS`, so a forgotten session
  cannot outlive that.

Every action is journaled. A recipe is written from the journal of a clean
discovery session (``recipe.from_session``).
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path

from . import sample_project

REPO_ROOT = Path(__file__).resolve().parents[2]
_LIB = REPO_ROOT / ".aitask-scripts" / "lib"
if str(_LIB) not in sys.path:
    sys.path.insert(0, str(_LIB))

from tmux_exec import TmuxClient  # noqa: E402

SOCKET_PREFIX = "ait_shots_"
TTL_SECONDS = 3600
DEFAULT_SIZE = (160, 48)
DEFAULT_TIMEOUT = 30.0
SETUP_TIMEOUT = 120.0
POLL_INTERVAL = 0.2
TMUX_SESSION = "shots"
ORIGINS = ("discovery", "replay")


class SessionError(Exception):
    """A primitive was refused or tmux did not do what was asked."""


class WaitTimeout(SessionError):
    """A bounded wait ran out. ``screen`` is the last screen text."""

    def __init__(self, message: str, screen: str):
        super().__init__(message)
        self.screen = screen


class SetupFailed(SessionError):
    """A setup command exited non-zero (or timed out)."""


@dataclass
class Session:
    id: str
    socket: str
    pane: str
    tmp: str
    project: str
    home: str
    python: str
    dataset: str
    size: tuple[int, int]
    origin: str
    launched: bool = False
    batch: str = ""
    socket_path: str = ""
    journal: list[dict] = field(default_factory=list)
    staging: str = ""

    @property
    def client(self) -> TmuxClient:
        return TmuxClient(socket_args=["-L", self.socket])

    @property
    def state_dir(self) -> Path:
        return sessions_dir(Path(self.staging)) / self.id

    def save(self) -> None:
        self.state_dir.mkdir(parents=True, exist_ok=True)
        data = asdict(self)
        tmp = self.state_dir / "session.json.tmp"
        tmp.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        os.replace(tmp, self.state_dir / "session.json")

    def log(self, kind: str, ok: bool = True, **fields) -> None:
        self.journal.append({"kind": kind, "ok": ok, **fields})
        self.save()


def sessions_dir(staging: Path) -> Path:
    return Path(staging) / "sessions"


def resolve_python() -> str:
    """The interpreter the TUIs in the pane must use.

    The pane gets a scratch ``HOME``, so the framework's own lookup of
    ``~/.aitask/venv`` would miss. This process already runs on the
    interpreter ``require_ait_python`` chose (``website/screenshots.sh``), or
    on one a caller picked explicitly with ``AIT_PYTHON``.
    """
    return os.environ.get("AIT_PYTHON") or sys.executable


def pane_environment(socket: str, home: Path, python: str) -> dict[str, str]:
    """What is pinned in the pane, and for setup commands."""
    return {
        "AITASKS_TMUX_SOCKET": socket,
        "AIT_PYTHON": python,
        "COLORTERM": "truecolor",
        "HOME": str(home),
        "XDG_CONFIG_HOME": str(home / ".config"),
        "TERM": "tmux-256color",
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
    }


def start_server(client: TmuxClient, new_session_args: list[str]) -> str:
    """Start the tmux server. The ONLY place a server comes into existence.

    Refuses when the socket already has a server: a server someone else
    started may have loaded a configuration. Returns the first pane's id.
    """
    probe = client.run_checked(["list-sessions"])
    if probe.outcome == "no_tmux":
        raise SessionError("tmux is not installed")
    if probe.outcome != "no_server":
        raise SessionError(
            f"the private socket {client.socket_args} already has a tmux server "
            f"(or it could not be ruled out: {probe.outcome}); refusing to reuse it")
    result = client.run_checked(["-f", os.devnull, *new_session_args])
    if result.outcome != "ok":
        raise SessionError(f"tmux new-session failed: {result.stderr.strip() or result.outcome}")
    return result.stdout.strip()


def start(staging: Path, *, size: tuple[int, int] = DEFAULT_SIZE, dataset: str = "base",
          origin: str = "discovery") -> Session:
    """Build the sample project, start the isolated server, open a shell pane."""
    if origin not in ORIGINS:
        raise SessionError(f"unknown origin {origin!r}")
    width, height = size
    if not (20 <= width <= 400 and 5 <= height <= 200):
        raise SessionError(f"size {width}x{height} is out of range")
    if dataset not in sample_project.DATASETS:
        # Refuse before anything is created.
        known = ", ".join(sorted(sample_project.DATASETS))
        raise SessionError(f"unknown dataset {dataset!r}; known datasets: {known}")

    session_id = uuid.uuid4().hex[:8]
    socket = SOCKET_PREFIX + session_id
    tmp = Path(tempfile.mkdtemp(prefix="ait_shots_"))
    client = TmuxClient(socket_args=["-L", socket])
    try:
        project = sample_project.build(tmp / sample_project.PROJECT_NAME, dataset)
        home = tmp / "home"
        (home / ".config").mkdir(parents=True)
        (home / ".gitconfig").write_text(
            f"[user]\n\tname = {sample_project.PERSON_NAME}\n"
            f"\temail = {sample_project.PERSON_EMAIL}\n", encoding="utf-8")
        python = resolve_python()
        env = pane_environment(socket, home, python)
        args = ["new-session", "-d", "-s", TMUX_SESSION, "-x", str(width), "-y", str(height),
                "-c", str(project), "-P", "-F", "#{pane_id}"]
        for key, value in env.items():
            args += ["-e", f"{key}={value}"]
        # Rich prefers COLUMNS / LINES over the real pty size.
        args += ["env", "-u", "COLUMNS", "-u", "LINES", "bash", "--noprofile", "--norc"]
        pane = start_server(client, args)
        # From here a server exists: any failure below must kill it.
        try:
            for option in (["set-option", "-g", "status", "off"],
                           ["set-option", "-g", "default-terminal", "tmux-256color"],
                           ["run-shell", "-b", "-d", str(TTL_SECONDS), "-C", "kill-server"]):
                rc, _ = client.run(option)
                if rc != 0:
                    raise SessionError(f"tmux {' '.join(option[:3])} failed")
            rc, out = client.run(["display-message", "-p", "-t", pane,
                                  "#{pane_width}x#{pane_height}"])
            if rc != 0 or out.strip() != f"{width}x{height}":
                raise SessionError(f"pane is {out.strip() or '?'}, asked for {width}x{height}")
            rc, socket_path = client.run(["display-message", "-p", "-t", pane, "#{socket_path}"])
            socket_path = socket_path.strip() if rc == 0 else ""
        except BaseException:
            client.run(["kill-server"])
            raise
    except BaseException:
        shutil.rmtree(tmp, ignore_errors=True)
        raise

    session = Session(id=session_id, socket=socket, pane=pane, tmp=str(tmp),
                      project=str(project), home=str(home), python=python, dataset=dataset,
                      size=(width, height), origin=origin, staging=str(staging),
                      socket_path=socket_path)
    session.save()
    return session


def load(staging: Path, session_id: str) -> Session:
    path = sessions_dir(staging) / session_id / "session.json"
    if not re.fullmatch(r"[0-9a-f]{8}", session_id) or not path.is_file():
        raise SessionError(f"no such session: {session_id}")
    data = json.loads(path.read_text(encoding="utf-8"))
    data["size"] = tuple(data["size"])
    data["staging"] = str(staging)
    return Session(**data)


def list_sessions(staging: Path) -> list[Session]:
    root = sessions_dir(staging)
    if not root.is_dir():
        return []
    return [load(staging, p.name) for p in sorted(root.iterdir())
            if (p / "session.json").is_file()]


def is_alive(session: Session) -> bool:
    return session.client.run_checked(["list-sessions"]).outcome == "ok"


def _require_alive(session: Session) -> None:
    if not is_alive(session):
        raise SessionError(
            f"session {session.id} has no tmux server any more (stopped, or its "
            f"{TTL_SECONDS // 60}-minute time-to-live ran out); stop it and start a new one")


def setup(session: Session, command: str, *, timeout: float = SETUP_TIMEOUT) -> str:
    """Run a data-preparation command in the project, before the TUI starts.

    It runs with the pane's pinned environment and the project as its working
    directory, and is journaled, so a replay repeats it. Returns its output.
    """
    if session.launched:
        raise SessionError("setup is refused after `run`: the TUI is already launched. "
                           "Start a fresh session and run the setup commands first.")
    if not command.strip():
        raise SessionError("empty setup command")
    env = {k: v for k, v in os.environ.items()
           if k not in ("TMUX", "TMUX_PANE", "COLUMNS", "LINES")}
    env.update(pane_environment(session.socket, Path(session.home), session.python))
    try:
        proc = subprocess.run(["bash", "--noprofile", "--norc", "-c", command],
                              cwd=session.project, env=env, capture_output=True, text=True,
                              timeout=timeout, stdin=subprocess.DEVNULL)
    except subprocess.TimeoutExpired:
        session.log("setup", ok=False, command=command)
        raise SetupFailed(f"setup command timed out after {timeout:g}s: {command}") from None
    output = (proc.stdout or "") + (proc.stderr or "")
    session.log("setup", ok=proc.returncode == 0, command=command)
    if proc.returncode != 0:
        raise SetupFailed(f"setup command exited {proc.returncode}: {command}\n{output.rstrip()}")
    return output


def run(session: Session, command: str) -> None:
    """Launch the TUI: type ``command`` into the pane's shell. Once per session."""
    if session.launched:
        raise SessionError("`run` was already called in this session; start a fresh one")
    if not command.strip() or "\n" in command:
        raise SessionError("the launch command must be one non-empty line")
    _require_alive(session)
    client = session.client
    if client.run(["send-keys", "-t", session.pane, "-l", command])[0] != 0 \
            or client.run(["send-keys", "-t", session.pane, "Enter"])[0] != 0:
        raise SessionError("tmux send-keys failed")
    session.launched = True
    session.log("launch", command=command)


def capture(session: Session, *, ansi: bool = False) -> str:
    """The pane's visible content. ``-N`` keeps trailing cells, so a row's
    background reaches the right edge."""
    args = ["capture-pane", "-p", "-N", "-t", session.pane]
    if ansi:
        args.insert(1, "-e")
    rc, out = session.client.run(args)
    if rc != 0:
        _require_alive(session)
        raise SessionError("tmux capture-pane failed")
    return out


def screen_rows(session: Session) -> list[str]:
    height = session.size[1]
    rows = capture(session).split("\n")[:height]
    return [row.rstrip() for row in rows] + [""] * (height - len(rows))


def screen_text(session: Session) -> str:
    return "\n".join(screen_rows(session))


def pane_command(session: Session) -> str:
    rc, out = session.client.run(["display-message", "-p", "-t", session.pane,
                                  "#{pane_current_command}"])
    return out.strip() if rc == 0 else "?"


def keys(session: Session, key_names: list[str]) -> None:
    """Send keys by tmux key name (``x``, ``Enter``, ``Escape``, ``C-p``, ``Down``)."""
    if not key_names:
        raise SessionError("no keys given")
    _require_alive(session)
    for key in key_names:
        # One key per call: tmux looks each argument up as a key name, and a
        # failed lookup must not send the others.
        if session.client.run(["send-keys", "-t", session.pane, key])[0] != 0:
            session.log("keys", ok=False, keys=list(key_names))
            raise SessionError(f"tmux send-keys failed for {key!r}")
    session.log("keys", keys=list(key_names))


def wait(session: Session, *, text: str | None = None, gone: str | None = None,
         timeout: float = DEFAULT_TIMEOUT, journal: bool = True) -> str:
    """Poll the screen until ``text`` is on it (or ``gone`` is not).

    A timeout is a failure: it is journaled with ``ok: false`` and raises
    :class:`WaitTimeout` carrying the last screen. Returns the screen text.
    """
    if (text is None) == (gone is None):
        raise SessionError("give exactly one of text / gone")
    needle = text if text is not None else gone
    if not needle:
        raise SessionError("empty wait text")
    kind = "wait" if text is not None else "wait_gone"
    deadline = time.monotonic() + timeout
    current = ""
    while True:
        current = screen_text(session)
        present = needle in current
        if present == (text is not None):
            if journal:
                session.log(kind, text=needle, timeout=timeout)
            return current
        if time.monotonic() >= deadline:
            break
        time.sleep(POLL_INTERVAL)
    if journal:
        session.log(kind, ok=False, text=needle, timeout=timeout)
    what = "never appeared" if text is not None else "never went away"
    raise WaitTimeout(f"{needle!r} {what} within {timeout:g}s", current)


def find(session: Session, text: str) -> list[tuple[int, int]]:
    """Every ``(column, row)`` cell where ``text`` starts on screen."""
    return find_in_rows(screen_rows(session), text)


# --- rectangles on a screen (pure: rows of plain text) --------------------------
#
# Columns are terminal cells, not characters: a wide glyph counts as two, the
# same measure (``rich.cells.cell_len``) the SVG export places text by. These
# work on rows of plain text, so the CLI runs them on the very frame it
# exports, and tests run them without tmux.

VERTICAL = set("│┃║╎╏┆┇┊┋▏▕")
TOP_LEFT = set("┌┏╔╭┍┎╒╓")
TOP_RIGHT = set("┐┓╗╮┑┒╕╖")
BOTTOM_LEFT = set("└┗╚╰┕┖╘╙")
BOTTOM_RIGHT = set("┘┛╝╯┙┚╛╜")
HORIZONTAL = set("─━═╌╍┄┅┈┉")


def cell_grid(line: str) -> list[str]:
    """``line`` as one entry per cell. A wide grapheme fills its first cell
    and leaves ``""`` in the second.

    Cells come from Rich's own grapheme spans (``rich.cells.split_graphemes``),
    the measure the exporter places text by and ``find_in_rows`` counts
    prefixes with: ``🏷`` + VS16 and a ZWJ sequence such as ``👩‍💻`` are one
    grapheme of two cells each. A zero-width span joins the cell before it.
    """
    from rich.cells import split_graphemes

    cells: list[str] = []
    spans, _ = split_graphemes(line)
    for start, end, width in spans:
        cluster = line[start:end]
        if width == 0:
            if cells:
                cells[-1 if cells[-1] else -2] += cluster
            else:
                cells.append(cluster)
            continue
        cells += [cluster] + [""] * (width - 1)
    return cells


def find_in_rows(rows: list[str], text: str) -> list[tuple[int, int]]:
    """Every ``(column, row)`` cell where ``text`` starts."""
    from rich.cells import cell_len

    if not text:
        raise SessionError("empty find text")
    cells = []
    for row, line in enumerate(rows):
        start = line.find(text)
        while start != -1:
            cells.append((cell_len(line[:start]), row))
            start = line.find(text, start + 1)
    return cells


def _only(rows: list[str], text: str) -> tuple[int, int]:
    found = find_in_rows(rows, text)
    if len(found) != 1:
        raise SessionError(f"{text!r} is on the screen {len(found)} times; "
                           "it must occur exactly once")
    return found[0]


def _closed_box(at, left: int, row: int):
    """The box whose left border runs through ``(left, row)``, as
    ``(left, top, right, bottom)``, or None unless all four border runs and
    all four corners are there."""
    top = row
    while at(left, top - 1) in VERTICAL:
        top -= 1
    top -= 1
    bottom = row
    while at(left, bottom + 1) in VERTICAL:
        bottom += 1
    bottom += 1
    if at(left, top) not in TOP_LEFT or at(left, bottom) not in BOTTOM_LEFT:
        return None
    right = left + 1
    while at(right, top) in HORIZONTAL:
        right += 1
    if right == left + 1 or at(right, top) not in TOP_RIGHT \
            or at(right, bottom) not in BOTTOM_RIGHT:
        return None
    if any(at(c, bottom) not in HORIZONTAL for c in range(left + 1, right)):
        return None
    if any(at(right, r) not in VERTICAL for r in range(top + 1, bottom)):
        return None
    return left, top, right, bottom


def box_around(rows: list[str], text: str) -> tuple[int, int, int, int]:
    """``(column, row, width, height)`` of the innermost closed box-drawn
    border around ``text``, border cells included. ``text`` must occur once.

    Every vertical glyph left of the text is tried as a left border, nearest
    first; the first one that closes into a box (all four edges and corners)
    holding the whole text wins. A smaller box beside the text is skipped, so
    an enclosing box further out is still found.
    """
    from rich.cells import cell_len

    col, row = _only(rows, text)
    end = col + cell_len(text)
    grid = [cell_grid(line) for line in rows]

    def at(c: int, r: int) -> str:
        return grid[r][c] if 0 <= r < len(grid) and 0 <= c < len(grid[r]) else ""

    for left in range(col - 1, -1, -1):
        if at(left, row) not in VERTICAL:
            continue
        box = _closed_box(at, left, row)
        if box is not None and box[2] >= end:
            left, top, right, bottom = box
            return left, top, right - left + 1, bottom - top + 1
    raise SessionError(f"no closed box around {text!r}")


def rect_holds(rows: list[str], rect, text: str) -> bool:
    """Whether ``text`` occurs with every one of its cells inside ``rect``."""
    from rich.cells import cell_len

    c, r, w, h = rect
    width = cell_len(text)
    return any(c <= col and col + width <= c + w and r <= row < r + h
               for col, row in find_in_rows(rows, text))


def _remove_dead_socket(session: Session) -> None:
    """tmux leaves the socket file behind when its server is killed. Remove
    ours, and only ours: a file named for this session, that is a socket, with
    no server answering on it."""
    path = Path(session.socket_path) if session.socket_path else None
    if path is None or path.name != session.socket:
        return
    deadline = time.monotonic() + 3.0
    while session.client.run_checked(["list-sessions"]).outcome == "ok":
        if time.monotonic() >= deadline:
            return
        time.sleep(0.05)
    try:
        if path.is_socket():
            path.unlink()
    except OSError:
        pass


def stop(session: Session) -> None:
    """Kill the private server, remove the sample project and the state."""
    session.client.run(["kill-server"])
    _remove_dead_socket(session)
    tmp = Path(session.tmp)
    if tmp.name.startswith("ait_shots_"):
        shutil.rmtree(tmp, ignore_errors=True)
    shutil.rmtree(session.state_dir, ignore_errors=True)
