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
import sitrep_refresh
import sitrep_todo as st
from sitrep_corpus import EXCERPT_HEADER, REVIEW_TITLE_PREFIX

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


#: Width of the list's "Checked" cell (COLUMNS[1]); every age_cell fits it.
AGE_CELL_W = 8


def age_cell(checked_at: str, now: _dt.datetime) -> str:
    """The list's "Checked" cell: ``age_text`` compacted to AGE_CELL_W cells,
    so the "What to do" column never shifts off the header (``1042d ago`` is
    nine cells: it becomes ``2y ago``). The details keep the full
    ``age_text``. Never raises."""
    text = age_text(checked_at, now)
    if text == "never":
        return "—"
    if text.endswith("(invalid date)"):
        return "invalid"
    if text == "in the future":
        return "future"
    if len(text) <= AGE_CELL_W:
        return text
    m = re.match(r"^([0-9]+)d ago\Z", text)
    if m:
        years = f"{int(m.group(1)) // 365}y ago"
        if len(years) <= AGE_CELL_W:
            return years
    return "long ago"


# --- what to do (t2211_8) ----------------------------------------------------
#
# The store classifies an item by kind/state; those are internal words. The
# user sees what to do about the item and how. NEXT_STEPS is the ONE table of
# that mapping: t2211_3 / t2211_4 edit the "how" texts here when their keys
# land, never a copy elsewhere.

@dataclass(frozen=True)
class NextStep:
    key: str    # the NEXT_STEPS row (internal; stable)
    what: str   # the "What to do" cell and details line (one line)
    how: str    # the details "How" line


#: classification key -> ("What to do" template, "How" template). Templates
#: are filled with ``str.format(**fields)``: store text is only ever a format
#: ARGUMENT, so braces in a title stay literal.
NEXT_STEPS = {
    "triage": (
        "Triage {task}'s wrap-up: decide which closing notes become actions or watches",
        "In the sitrep agent pane (beside this one) type  >t  — it triages every "
        "open wrap-up, this one included."),
    "review": (
        "Review unparsed agent output{rest}",
        "In the sitrep agent pane type  >t  — open reviews are handled with the triage."),
    "decide": (
        "Decide: {title}",
        "Ask the sitrep agent: type  >q {cid} <your question or decision>  in its pane."),
    "pick": (
        "Pick {ref}{status}: {rest}",
        "Run  /aitask-pick {pick_id}  in a code-agent window (or open it with  ait board)."),
    "pick_xref": (
        "Pick {ref}{status}: {rest}",
        "It lives in project {project}: run  /aitask-pick {pick_id}  there."),
    "pick_noref": (
        "Pick: {title}{status}",
        "The title names the task; pick it with  /aitask-pick <id>."),
    "push": (
        "Do: {title}",
        "Push branch {branch} (commit {sha}) yourself; refresh marks this done once "
        "the commit is on the remote. Shown only — the TUI never runs it."),
    "do": (
        "Do: {title}",
        "Do it yourself; when it is done or no longer needed, dismiss it (in the "
        "agent pane:  >x {cid} <reason>)."),
    "watch": (
        "Waiting on: {title} — nothing to do now{outcome}",
        "A refresh re-checks its trail (in the agent pane:  >r ); the outcome "
        "shows what changed."),
    "watch_manual": (
        "Waiting on: {title} — nothing to do now{outcome}",
        "Refresh does not check this one (it has no trail to follow). To see where "
        "it stands, ask the sitrep agent:  >q {cid} <question>  — it reads the "
        "item's sources."),
    "done": ("Done: {title}{outcome}", "Nothing to do."),
    "dismissed": ("Dismissed: {title}{outcome}", "Nothing to do."),
    "unknown": (
        "Unknown — needs a re-check: {title}",
        "Refresh re-checks it: in the agent pane type  >r ."),
    "unknown_manual": (
        "Unknown — needs a re-check: {title}",
        "Refresh has no automatic check for this item. Ask the sitrep agent to look "
        "at its sources ( >q {cid} <question> ), or dismiss it ( >x {cid} <reason> )."),
    "raw": (
        "{kind} / {state}: {title}",
        "No guidance for this kind of item — read its context below."),
}

_TRIAGE_PREFIX = "Triage wrap-up of "
_TRIAGE_RE = re.compile(r"^Triage wrap-up of (t[0-9]+(?:_[0-9]+)?)\b")
_LOCAL_REF_RE = re.compile(r"^t([0-9]+(?:_[0-9]+)?)\Z")
_XREF_RE = re.compile(r"^([^#\s]+)#([0-9]+(?:_[0-9]+)?)\Z")


def refresh_checks(store: "st.TodoStore | None") -> dict:
    """``{item num: check}`` for the items refresh re-checks (task / push /
    trail), from ``sitrep_refresh.select_targets`` -- the refresh's OWN rule,
    so the guidance never promises a check refresh does not make. A failure is
    ``{}``: every watch / unknown item then gets the manual guidance."""
    if store is None:
        return {}
    try:
        return {t.num: t.check for t in sitrep_refresh.select_targets(store)}
    except Exception:  # noqa: BLE001 - guidance is decoration
        return {}


def classify(item: "st.Item", refresh_check: "str | None" = None) -> str:
    """The NEXT_STEPS key for ``item``. ``refresh_check`` is the item's entry
    in ``refresh_checks`` (None: refresh does not check it)."""
    if item.state in ("done", "dismissed"):
        return item.state
    if item.state == "unknown":
        return "unknown" if refresh_check else "unknown_manual"
    if item.state != "open":
        return "raw"
    if item.kind == "question":
        if item.title.startswith(REVIEW_TITLE_PREFIX):
            return "review"
        if sitrep_cli.is_triage(item) and item.title.startswith(_TRIAGE_PREFIX):
            return "triage"
        return "decide"
    if item.kind == "task":
        if _LOCAL_REF_RE.match(item.ref or ""):
            return "pick"
        if _XREF_RE.match(item.ref or ""):
            return "pick_xref"
        return "pick_noref"
    if item.kind == "action":
        return "push" if st.parse_push_ref(item.ref) else "do"
    if item.kind == "watch":
        return "watch" if refresh_check == "trail" else "watch_manual"
    return "raw"


def _fields(item: "st.Item") -> dict:
    title, ref, outcome = item.title, item.ref or "", item.outcome or ""
    m = _TRIAGE_RE.match(title)
    rest = title
    if title.startswith(REVIEW_TITLE_PREFIX):
        rest = title[len(REVIEW_TITLE_PREFIX):]
    elif ref and title.startswith(ref + " "):
        rest = title[len(ref) + 1:]
    pick_id = project = ""
    lm, xm = _LOCAL_REF_RE.match(ref), _XREF_RE.match(ref)
    if lm:
        pick_id = lm.group(1)
    elif xm:
        project, pick_id = xm.group(1), xm.group(2)
    push = st.parse_push_ref(ref)
    if outcome.startswith("status:"):
        status = f" ({outcome})"          # the task's live status, verbatim
    else:
        status = f" — {outcome}" if outcome else ""
    return {
        "title": title, "cid": item.cid, "kind": item.kind, "state": item.state,
        "task": m.group(1) if m else "this run", "rest": rest, "ref": ref,
        "pick_id": pick_id, "project": project, "status": status,
        "outcome": f" — {outcome}" if outcome else "",
        "branch": push[0] if push else "", "sha": push[1][:12] if push else "",
    }


def next_step(item: "st.Item", refresh_check: "str | None" = None) -> NextStep:
    """What to do about ``item`` and how. Never raises (render time): any
    failure falls back to the raw row."""
    try:
        key = classify(item, refresh_check)
        what, how = NEXT_STEPS[key]
        fields = _fields(item)
        return NextStep(key, what.format(**fields), how.format(**fields))
    except Exception:  # noqa: BLE001
        what, how = NEXT_STEPS["raw"]
        fields = {"kind": getattr(item, "kind", "?"), "state": getattr(item, "state", "?"),
                  "title": getattr(item, "title", "")}
        return NextStep("raw", what.format(**fields), how)


# --- the list's columns --------------------------------------------------------

#: (heading, width) of the main list's columns; the last one takes the rest.
#: header_text and row_text both build from it, so they align by construction.
COLUMNS = (("Item", 5), ("Checked", AGE_CELL_W), ("What to do", 0))


def cid_width(store: "st.TodoStore | None") -> int:
    if store is None or not store.items:
        return COLUMNS[0][1]
    return max(COLUMNS[0][1], max(len(f"c{n}") for n in store.items))


def header_text(cid_w: int = COLUMNS[0][1]) -> str:
    return f"{COLUMNS[0][0]:<{cid_w}} {COLUMNS[1][0]:<{COLUMNS[1][1]}} {COLUMNS[2][0]}"


def row_text(item: "st.Item", now: _dt.datetime, cid_w: int = COLUMNS[0][1],
             refresh_check: "str | None" = None) -> str:
    """One list row: item id, checked age, what to do. Rows are cut to one line
    with an ellipsis, so the free text sits last."""
    return (f"{item.cid:<{cid_w}} {age_cell(item.checked_at, now):<{COLUMNS[1][1]}} "
            f"{next_step(item, refresh_check).what}")


# --- plain-language labels -------------------------------------------------------

#: An origin key -> its details label (an unknown key is shown as itself).
ORIGIN_LABELS = {"agent": "Agent", "task": "Task", "commit": "Commit",
                 "date": "Date", "skill": "Skill", "pane": "Pane"}

_CAPTURE_LABELS = {
    "banner": "Workflow result",
    "passage": "Closing message",
    "case": "Review case: origin record",
    "analysis": "Review case: parser analysis",
    "review": "Review case: review record",
}
_TASK_FILE_RE = re.compile(r"^t([0-9]+(?:_[0-9]+)?)_")
_PLAN_FILE_RE = re.compile(r"^p([0-9]+(?:_[0-9]+)?)_")


def about_text(ref: str) -> str:
    """The item's ``ref`` -- the one thing it is about -- in words; '' if none."""
    if not ref:
        return ""
    push = st.parse_push_ref(ref)
    if push:
        return f"push of branch {push[0]} (commit {push[1][:12]})"
    xm = _XREF_RE.match(ref)
    if xm:
        return f"task {xm.group(2)} in project {xm.group(1)}"
    return ref


def _range_text(frag: str, single: str = "line") -> str:
    m = _FRAG_RE.match(frag or "")
    if not m:
        return ""
    if m.group(2) and m.group(2) != m.group(1):
        return f", lines {m.group(1)}–{m.group(2)}"
    return f", {single} {m.group(1)}"


def _first_line(store_dir: str, ptr: str) -> str:
    try:
        with open(os.path.join(store_dir, ptr.split("#", 1)[0]),
                  encoding="utf-8", errors="replace") as fh:
            return fh.readline().rstrip("\n")
    except OSError:
        return ""


def _file_label(kind: str, regex, ptr: str) -> str:
    path = ptr.partition("#")[0]
    m = regex.match(os.path.basename(path))
    if not m:
        return f"{kind} file {path}"
    noun = "Task" if kind == "Task" else "Plan of"
    archived = " (archived)" if "/archived/" in f"/{path}" else ""
    return f"{noun} t{m.group(1)}{archived}"


def source_label(store_dir: str, stype: str, ptr: str) -> "str | None":
    """A context source in plain words, or None when the TUI hides it (KEY
    receipts: dedupe / consumed-proof bookkeeping the store keeps). No store
    handles (hex names) in a label. Never raises."""
    try:
        if stype == "capture":
            kind = "?"
            if st.CAPTURE_RE.match(ptr or ""):
                try:
                    kind = sitrep_cli.capture_kind(store_dir, ptr)
                except Exception:  # noqa: BLE001
                    kind = "?"
            if kind == "key":
                return None
            label = _CAPTURE_LABELS.get(kind, "Retained text")
            # The producer (sitrep_corpus.excerpt_bytes) writes the header
            # followed by " lines=<a>-<b>".
            first = _first_line(store_dir, ptr)
            if kind == "passage" and (first == EXCERPT_HEADER
                                      or first.startswith(EXCERPT_HEADER + " ")):
                label = "Excerpt of the unparsed output"
            return label + _range_text(ptr.partition("#")[2], "line")
        if stype == "task":
            return _file_label("Task", _TASK_FILE_RE, ptr)
        if stype == "plan":
            return _file_label("Plan", _PLAN_FILE_RE, ptr)
        if stype == "file":
            path, _, frag = ptr.partition("#")
            return f"File {path}{_range_text(frag)}"
        if stype == "commit":
            return f"Commit {ptr[:12]}"
        if stype == "trail":
            return f"Trail {ptr}"
        if stype == "artifact":
            return f"Artifact {ptr}"
        if stype == "url":
            return f"Web link {ptr} (shown, never opened)"
        return f"{stype}: {ptr}"
    except Exception:  # noqa: BLE001 - a label is decoration
        return f"{stype}: {ptr}"


def markdown_source(text: str) -> str:
    """``text`` for the Markdown widget: a leading YAML front matter becomes a
    fenced ``yaml`` block (it would otherwise render as a rule and a run-on
    paragraph). The fence is longer than any backtick run inside it."""
    if not text.startswith("---\n"):
        return text
    end = text.find("\n---\n", 3)
    if end < 0:
        if text.endswith("\n---"):
            end = len(text) - 4
        else:
            return text
    front = text[4:end + 1]
    body = text[end + 5:]
    runs = [len(r) for r in re.findall(r"`+", front)]
    fence = "`" * max(3, max(runs, default=0) + 1)
    return f"{fence}yaml\n{front}{fence}\n\n{body}"


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
    #: Render as Markdown (task / plan files, `.md` file pointers) -- the
    #: viewer still offers the raw text with line numbers.
    markdown: bool = False


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
    markdown = stype in ("task", "plan") or (
        stype == "file" and ptr.partition("#")[0].lower().endswith(".md"))
    return PointerView(f"{stype}: {ptr}", text, note=_truncated_note(size),
                       focus_line=a, markdown=markdown)


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
