"""sitrep_tui_model.py - the sitrep TUI's read model (t2211_1). No Textual.

Everything the TUI shows is computed here, so it is unit-testable without an App:

* **Snapshots.** ``load_snapshot`` reads ``todo.md`` and ``qa.md`` once, hashes
  the bytes, and parses **those same bytes** -- never a second read that could
  see a newer generation than the one hashed. An unchanged digest returns
  ``None`` without parsing (the auto-reload's no-op path). A read or parse
  failure is an error string, never an exception.
* **Rows and ages.** ``age_text`` and ``resolve_now`` never raise: the store
  grammar accepts timestamps that are no calendar date (``2026-02-31T…``), and
  the clock seam ``AITASK_SITREP_NOW`` is checked for syntax only.
* **Pointers.** ``follow_pointer`` resolves one context source READ-ONLY and
  never raises. Store text is agent-written, so every pointer is re-validated
  here: repo-relative paths must stay inside the repository after symlinks are
  resolved, store passages inside the store, and a handle that reaches a CLI
  must not start with ``-``. Every subprocess is an argv list with a timeout.

The store is ``<canonical root>/.aitask-sitrep`` -- what every read-side consumer
uses (``sitrep_cli``, ``monitor/sitrep_close.py``, harvest, refresh); only the
writer honours ``AITASK_SITREP_DIR``.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

import sitrep_cli
import sitrep_todo as st

SCRIPTS_DIR = Path(__file__).resolve().parent.parent

#: Largest file / command output shown in the pointer viewer.
MAX_VIEW_BYTES = 256 * 1024
#: Wall-clock budget of one pointer subprocess (artifact get may fetch).
POINTER_TIMEOUT = 20.0

_TS_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
_FRAG_RE = re.compile(r"^L([1-9][0-9]*)(?:-L([1-9][0-9]*))?\Z")
_CLOSED_SLOTS = ("done", "dismissed")


# --- snapshots ---------------------------------------------------------------

@dataclass
class Snapshot:
    digest: tuple
    store: "st.TodoStore | None"
    qa: "st.QaLog | None"
    todo_error: str = ""
    qa_error: str = ""


def _read_file(path: str) -> tuple:
    """``(state, sha256, bytes)``; state is ``ok`` / ``missing`` / ``error:<msg>``."""
    try:
        with open(path, "rb") as fh:
            data = fh.read()
    except FileNotFoundError:
        return ("missing", "", None)
    except OSError as e:
        return (f"error:{e.strerror or e}", "", None)
    return ("ok", hashlib.sha256(data).hexdigest(), data)


def _parse(read: tuple, path: str, parse, load_for_read, store_dir: str):
    """``(value, error)`` for one store file, from the bytes in ``read``."""
    state, _, data = read
    try:
        if state == "ok":
            return parse(data.decode("utf-8"), path), ""
        if state == "missing":
            # Never initialized (empty) vs. missing from an established store
            # (damage): the writer's own read-side rule.
            return load_for_read(store_dir), ""
        return None, f"{os.path.basename(path)}: cannot read: {state[6:]}"
    except UnicodeDecodeError:
        return None, f"{os.path.basename(path)}: not valid UTF-8"
    except Exception as e:  # noqa: BLE001 - FormatError and anything else
        return None, str(e)


def load_snapshot(store_dir: str, prev_digest=None) -> "Snapshot | None":
    """The store as it is now, or ``None`` when its bytes equal ``prev_digest``."""
    todo_path = os.path.join(store_dir, "todo.md")
    qa_path = os.path.join(store_dir, "qa.md")
    todo = _read_file(todo_path)
    qa = _read_file(qa_path)
    digest = (todo[0], todo[1], qa[0], qa[1])
    if prev_digest is not None and digest == prev_digest:
        return None
    store, todo_error = _parse(todo, todo_path, lambda t, p: st.parse_todo(t, p),
                               st.load_todo_for_read, store_dir)
    log, qa_error = _parse(qa, qa_path, lambda t, p: st.parse_qa(t, p),
                           st.load_qa_for_read, store_dir)
    return Snapshot(digest, store, log, todo_error, qa_error)


# --- rows --------------------------------------------------------------------

def group_items(store: "st.TodoStore", show_closed: bool) -> list:
    """``[(slot, heading, [Item])]`` in the store's own section order."""
    out = []
    for slot, heading in st.SLOTS:
        if slot in _CLOSED_SLOTS and not show_closed:
            continue
        items = [store.items[n] for n in sorted(store.items)
                 if st._slot_of(store.items[n]) == slot]
        out.append((slot, heading.lstrip("# "), items))
    return out


def _parse_ts(value: str) -> _dt.datetime:
    return _dt.datetime.strptime(value, _TS_FORMAT).replace(tzinfo=_dt.timezone.utc)


def resolve_now() -> _dt.datetime:
    """Now, honouring the ``AITASK_SITREP_NOW`` seam. Never raises: a seam that
    is malformed, or well-formed but no calendar date, falls back to the clock."""
    try:
        return _parse_ts(st.now_ts())
    except Exception:  # noqa: BLE001 - RequestError (syntax) or ValueError (date)
        return _dt.datetime.now(_dt.timezone.utc)


def age_text(checked_at: str, now: _dt.datetime) -> str:
    """``never`` / ``just now`` / ``5m ago`` / ``3h ago`` / ``2d ago``.

    Never raises -- it runs at render time. The store grammar is syntax only, so
    ``2026-02-31T12:00:00Z`` is a valid stored value; it is shown verbatim."""
    if not checked_at or checked_at == "never":
        return "never"
    try:
        then = _parse_ts(checked_at)
    except (ValueError, TypeError):
        return f"at {checked_at} (invalid date)"
    secs = (now - then).total_seconds()
    if secs < -60:
        return "in the future"
    if secs < 60:
        return "just now"
    if secs < 3600:
        return f"{int(secs // 60)}m ago"
    if secs < 86400:
        return f"{int(secs // 3600)}h ago"
    return f"{int(secs // 86400)}d ago"


def row_text(item: "st.Item", now: _dt.datetime) -> str:
    """One list row. The age sits BEFORE the title: rows are cut to one line
    with an ellipsis, so only the free text at the end may be lost."""
    outcome = f" — {item.outcome}" if item.outcome else ""
    return (f"{item.cid:<5} {item.kind:<8} {item.state:<9} "
            f"{age_text(item.checked_at, now):<10} {item.title}{outcome}")


def qa_newest_first(log: "st.QaLog | None") -> list:
    """``[(index, QaEntry)]``, newest first (ties: later in the file first)."""
    if log is None:
        return []
    pairs = list(enumerate(log.entries))
    return sorted(pairs, key=lambda p: (p[1].ts, p[0]), reverse=True)


def qa_backlinks(log: "st.QaLog | None", num: int) -> list:
    return [(i, e) for i, e in qa_newest_first(log) if num in e.items]


def referenced_by(store: "st.TodoStore", num: int) -> list:
    return sorted(n for n, ctx in store.contexts.items()
                  if n != num and num in ctx.related and n in store.items)


def qa_first_line(entry: "st.QaEntry", limit: int = 80) -> str:
    line = next((ln.strip() for ln in entry.body if ln.strip()), "")
    return line if len(line) <= limit else line[:limit - 1] + "…"


# --- pointers ----------------------------------------------------------------

class PointerRefused(Exception):
    """A pointer that is not followed (invalid, outside its root, missing)."""


@dataclass
class PointerView:
    title: str
    text: str = ""
    error: str = ""
    note: str = ""
    first_line: int = 1
    focus_line: "int | None" = None


def _inside(root_real: str, path_real: str) -> bool:
    """Is ``path_real`` the root itself or below it (both already realpath'd)?"""
    return path_real == root_real or path_real.startswith(root_real.rstrip(os.sep) + os.sep)


def _has_control(value: str) -> bool:
    return any(ord(c) < 0x20 or ord(c) == 0x7f for c in value)


def safe_repo_path(root: str, ptr: str) -> tuple:
    """``(absolute path, line a, line b)`` for a repo-relative ``task:`` /
    ``plan:`` / ``file:`` pointer, or PointerRefused.

    Re-applies the writer's rules (no absolute path, no ``~``, no ``\\``, no
    ``..`` segment) because the file may not have come through the writer, and
    adds the one the writer cannot check: after symlinks are resolved the path
    must still be inside the repository."""
    if not ptr or _has_control(ptr):
        raise PointerRefused("empty pointer or control characters")
    rel, _, frag = ptr.partition("#")
    if not rel:
        raise PointerRefused("empty path")
    if rel.startswith(("/", "~")) or "\\" in rel:
        raise PointerRefused(f"{rel!r} must be a repo-relative path")
    if ".." in rel.split("/"):
        raise PointerRefused(f"{rel!r} must not contain '..'")
    a = b = None
    m = _FRAG_RE.match(frag) if frag else None
    if m:
        a = int(m.group(1))
        b = int(m.group(2) or a)
    root_real = os.path.realpath(root)
    full = os.path.realpath(os.path.join(root_real, rel))
    if not _inside(root_real, full):
        raise PointerRefused(f"{rel!r} points outside the repository")
    if not os.path.isfile(full):
        raise PointerRefused(f"{rel!r} is not a file in the repository")
    return full, a, b


def _decode(data: bytes) -> str:
    return data.decode("utf-8", errors="replace").replace("\0", "␀")


def _read_text(path: str, limit: int = MAX_VIEW_BYTES) -> tuple:
    """``(text, total size or None when not truncated)``."""
    with open(path, "rb") as fh:
        data = fh.read(limit + 1)
    if len(data) > limit:
        return _decode(data[:limit]), os.path.getsize(path)
    return _decode(data), None


def _truncated_note(size) -> str:
    return f"showing the first {MAX_VIEW_BYTES // 1024} KiB of {size} bytes" if size else ""


def _run(argv: list, cwd: str, timeout: float) -> tuple:
    """``(rc, stdout, stderr)``; a timeout or a missing command is refused."""
    try:
        proc = subprocess.run(argv, cwd=cwd, stdin=subprocess.DEVNULL,
                              capture_output=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        raise PointerRefused(f"{os.path.basename(argv[0])} timed out after "
                             f"{timeout:g}s") from None
    except OSError as e:
        raise PointerRefused(f"cannot run {os.path.basename(argv[0])}: "
                             f"{e.strerror or e}") from None
    out = proc.stdout[:MAX_VIEW_BYTES]
    return proc.returncode, _decode(out), _decode(proc.stderr[-4000:])


def _tail(text: str, lines: int = 6) -> str:
    return "\n".join(text.strip().splitlines()[-lines:]) or "(no output)"


def _check_handle(stype: str, ptr: str) -> None:
    if not ptr or _has_control(ptr) or any(c.isspace() for c in ptr):
        raise PointerRefused(f"{stype} pointer must be one word without control characters")
    if ptr.startswith("-"):
        raise PointerRefused(f"{stype} pointer {ptr!r} must not start with '-'")


def capture_label(store_dir: str, ptr: str) -> str:
    """CAPTURE / BANNER / KEY / CASE / ANALYSIS / REVIEW for a ``capture:``
    pointer -- ``sitrep_cli``'s labels, so a case counts only with its trusted
    ``cases/`` twin. ``?`` for a pointer that is not a capture pointer."""
    if not st.CAPTURE_RE.match(ptr or ""):
        return "?"
    try:
        kind = sitrep_cli.capture_kind(store_dir, ptr)
    except Exception:  # noqa: BLE001 - a label is decoration
        return "?"
    return sitrep_cli.KIND_LABEL.get(kind, kind.upper())


def _follow_path(root: str, stype: str, ptr: str) -> PointerView:
    full, a, _b = safe_repo_path(root, ptr)
    text, size = _read_text(full)
    return PointerView(f"{stype}: {ptr}", text, note=_truncated_note(size),
                       focus_line=a)


def _follow_capture(store_dir: str, ptr: str) -> PointerView:
    m = st.CAPTURE_RE.match(ptr or "")
    if not m:
        raise PointerRefused(f"{ptr!r} is not sources/<16 hex>.txt#L<a>[-L<b>]")
    hexname, a = m.group(1), int(m.group(2))
    b = int(m.group(3) or a)
    path = os.path.join(store_dir, "sources", f"{hexname}.txt")
    if os.path.islink(path) or not os.path.isfile(path):
        raise PointerRefused(f"no retained file sources/{hexname}.txt in the store")
    if not _inside(os.path.realpath(store_dir), os.path.realpath(path)):
        raise PointerRefused(f"sources/{hexname}.txt points outside the store")
    text, _size = _read_text(path)
    lines = text.split("\n")
    if text.endswith("\n"):
        lines = lines[:-1]
    note = ""
    if b > len(lines):
        note = f"the range ends past the retained file ({len(lines)} lines)"
    return PointerView(f"capture [{capture_label(store_dir, ptr)}]: {ptr}",
                       "\n".join(lines[a - 1:b]), note=note, first_line=a)


def _follow_commit(root: str, ptr: str, timeout: float) -> PointerView:
    if not st.COMMIT_RE.match(ptr or ""):
        raise PointerRefused(f"{ptr!r} is not a 7-40 char hex sha")
    rc, out, err = _run(["git", "-C", root, "show", "--stat", "--no-color",
                         "--format=fuller", ptr, "--"], root, timeout)
    if rc != 0:
        raise PointerRefused(f"git show failed (exit {rc}): {_tail(err)}")
    return PointerView(f"commit: {ptr}", out)


def _artifact_get(root: str, handle: str, scripts_dir: Path, timeout: float) -> tuple:
    rc, out, err = _run([str(scripts_dir / "aitask_artifact.sh"), "get", handle],
                        root, timeout)
    if rc != 0:
        return "", f"artifact get failed (exit {rc}): {_tail(err)}"
    return out, ""


def _follow_trail(root: str, ptr: str, scripts_dir: Path, timeout: float) -> PointerView:
    _check_handle("trail", ptr)
    if ptr.startswith("art:"):
        drift_arg = ptr
        content, error = _artifact_get(root, ptr, scripts_dir, timeout)
    else:
        # Anything that is not a handle reaches trail_gather as a PATH, so it
        # gets the repo-relative path rules first.
        full, _a, _b = safe_repo_path(root, ptr)
        drift_arg = ptr.partition("#")[0]
        content, size = _read_text(full)
        error = ""
        if size:
            content += f"\n({_truncated_note(size)})"
    rc, out, err = _run([str(scripts_dir / "aitask_trail_gather.sh"), "drift",
                         "--trail", drift_arg], root, timeout)
    drift = out.strip() or f"(drift check exit {rc}: {_tail(err)})"
    text = f"Drift check:\n{drift}\n\nTrail:\n{content or '(not available)'}"
    return PointerView(f"trail: {ptr}", text, error=error)


def _follow_artifact(root: str, ptr: str, scripts_dir: Path, timeout: float) -> PointerView:
    _check_handle("artifact", ptr)
    content, error = _artifact_get(root, ptr, scripts_dir, timeout)
    if error:
        raise PointerRefused(error)
    return PointerView(f"artifact: {ptr}", content)


def follow_pointer(root: str, store_dir: str, stype: str, ptr: str,
                   timeout: float = POINTER_TIMEOUT,
                   scripts_dir: Path = SCRIPTS_DIR) -> PointerView:
    """Resolve one context source READ-ONLY. Never raises."""
    title = f"{stype}: {ptr}"
    try:
        if stype in ("task", "plan", "file"):
            return _follow_path(root, stype, ptr)
        if stype == "capture":
            return _follow_capture(store_dir, ptr)
        if stype == "commit":
            return _follow_commit(root, ptr, timeout)
        if stype == "trail":
            return _follow_trail(root, ptr, scripts_dir, timeout)
        if stype == "artifact":
            return _follow_artifact(root, ptr, scripts_dir, timeout)
        if stype == "url":
            return PointerView(title, ptr,
                               note="An external link: shown here, never opened.")
        return PointerView(title, error=f"unknown source type {stype!r}")
    except PointerRefused as e:
        return PointerView(title, error=f"Not followed: {e}")
    except Exception as e:  # noqa: BLE001 - the viewer shows it, the TUI lives
        return PointerView(title, error=f"Could not follow the pointer: {e}")


# --- review cases (t2175_6) --------------------------------------------------

def case_extras(store_dir: str, ptr: str):
    """``(raw rel path, sha256)`` when ``ptr`` is a TRUSTED case origin, else
    None. Does not hash the raw input (it can be 64 MiB): ``follow_raw`` does,
    off the event loop."""
    m = st.CAPTURE_RE.match(ptr or "")
    if not m or capture_label(store_dir, ptr) != "CASE":
        return None
    try:
        return st.case_origin_input(store_dir, m.group(1))
    except Exception:  # noqa: BLE001
        return None


def follow_raw(store_dir: str, rel: str, sha: str) -> PointerView:
    """The head of a review case's verbatim raw input, after its sha256 check."""
    title = f"raw input: {rel}"
    try:
        if not st.RAW_RE.match(rel or ""):
            raise PointerRefused(f"{rel!r} is not raw/<16 hex>.txt")
        if not st.raw_input_ok(store_dir, rel, sha):
            raise PointerRefused("the raw input is missing, not a regular file, or "
                                 "its sha256 differs from the case origin")
        text, size = _read_text(os.path.join(store_dir, rel))
        return PointerView(title, text, note=_truncated_note(size))
    except PointerRefused as e:
        return PointerView(title, error=f"Not followed: {e}")
    except Exception as e:  # noqa: BLE001
        return PointerView(title, error=f"Could not read the raw input: {e}")


def review_line(store_dir: str, ctx: "st.ContextEntry | None") -> str:
    """The "review case" line of an "Analyze unparsed agent output" item, or ''."""
    if ctx is None:
        return ""
    captures = [p for t, p in ctx.sources if t == "capture"]
    try:
        found = sitrep_cli.review_case(store_dir, captures[1:])
    except Exception:  # noqa: BLE001
        return ""
    if not found:
        return ""
    hexname, _, codes = found.partition("|")
    return (f"Review case {hexname} ({codes}) — read it with "
            f"`ait sitrep case show {hexname}`")
