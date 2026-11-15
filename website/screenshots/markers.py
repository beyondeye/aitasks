"""The one screenshot-placeholder grammar used in ``website/content/``.

A doc author marks the place a screenshot belongs with one single-line HTML
comment::

    <!-- screenshot: scene=board_child_tasks file=aitasks_board_child_tasks.svg alt="Board with a parent task expanded to show its child tasks" caption="An expanded parent task with its child tasks." -->

Required keys are ``scene``, ``file`` and ``alt``; ``caption`` and ``class`` are
optional. ``scene`` names ``website/screenshots/scenes/<scene>.yaml``; ``file``
is a path relative to ``website/static/imgs/``.

No value may contain a character sequence from ``FORBIDDEN_IN_VALUE``:

* ``"`` would end the shortcode parameter the value is rendered into;
* ``--`` would end the HTML comment the marker lives in;
* ``\\`` is an escape inside a quoted Hugo shortcode parameter, so a value
  ending in a backslash leaves the parameter unterminated and breaks the page.
  Rejecting it here means every accepted value can be inserted verbatim into a
  shortcode by ``render_static_img`` -- no escaping layer whose rules could
  differ between Hugo versions.

This module is stdlib-only so the check can run in the Hugo CI job. It also
owns the reader for the two lines of a scene spec the checker needs (``id:`` and
``output:``), and the YAML scene loader is required to agree with it -- see
``read_spec_owner``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

REQUIRED = ("scene", "file", "alt")
OPTIONAL = ("caption", "class")
KEYS = REQUIRED + OPTIONAL

FORBIDDEN_IN_VALUE = ('"', "--", "\\")

SCENE_RE = re.compile(r"^[a-z0-9_]+$")

#: One segment of an image path: RFC 3986 unreserved characters minus ``~``,
#: so the path needs no percent-encoding and holds no URL delimiter.
PATH_SEGMENT_RE = re.compile(r"^[A-Za-z0-9._-]+$")

#: A whole line holding one marker: up to three leading spaces (beyond that
#: CommonMark makes it an indented code block), the ``screenshot:`` tag, the
#: key=value pairs, the comment close, optional trailing whitespace.
MARKER_RE = re.compile(r"^ {0,3}<!--\s*screenshot:(?P<body>.*?)-->\s*$")

#: One key=value pair. A value is a bare token or a double-quoted string; the
#: quoted form deliberately has no escape syntax.
_PAIR_RE = re.compile(r'\s*(?P<key>[A-Za-z_]+)=(?:"(?P<q>[^"]*)"|(?P<bare>[A-Za-z0-9_./-]+))')

#: An opening code fence. CommonMark: a backtick fence's info string may not
#: contain a backtick -- such a line is a paragraph, not a fence (Goldmark in
#: Hugo agrees: it renders it as text and keeps a following comment).
_FENCE_OPEN_RE = re.compile(r"^ {0,3}(?P<fence>`{3,}|~{3,})(?P<info>.*)$")
_BLOCK_COMMENT_RE = re.compile(r"^ {0,3}<!--")

_MENTION = "screenshot"


@dataclass(frozen=True)
class Marker:
    path: str
    line: int
    text: str
    scene: str
    file: str
    alt: str
    caption: str | None = None
    cls: str | None = None


@dataclass(frozen=True)
class Unparseable:
    path: str
    line: int
    text: str
    reason: str


def path_problem(path: str) -> str | None:
    """Why ``path`` is not a canonical image path relative to ``static/imgs/``.

    Canonical means: relative, ``/``-separated, and every segment non-empty and
    neither ``.`` nor ``..``. So ``x.svg`` and ``home/x.svg`` are canonical,
    while ``./x.svg``, ``/x.svg``, ``a//x.svg``, ``home/`` and ``../x.svg`` are
    not. One spelling per file is what lets ownership and duplicate checks
    compare paths as plain strings.

    Each segment is also limited to ``PATH_SEGMENT_RE`` (letters, digits,
    ``.``, ``_``, ``-``). The path becomes the image URL verbatim, so a ``#``
    or ``?`` would make the browser request a different file, and a space or
    ``%`` would depend on percent-encoding. With this set the filesystem name,
    the URL and the requested path are the same string.
    """
    if path.startswith("/"):
        return "must be relative to static/imgs/, not absolute"
    for seg in path.split("/"):
        if seg in ("", ".", ".."):
            return "must be a canonical path (no empty, '.' or '..' segment)"
        if not PATH_SEGMENT_RE.match(seg):
            return f"segment {seg!r} may only use letters, digits, '.', '_' and '-' (it becomes the image URL)"
    return None


def value_problem(value: str) -> str | None:
    """The reason ``value`` may not appear in a marker, or None when it may."""
    if value == "":
        return "empty value"
    for seq in FORBIDDEN_IN_VALUE:
        if seq in value:
            return f"value contains forbidden {seq!r}"
    return None


def parse_marker(text: str, path: str = "", line: int = 0) -> Marker | str:
    """Parse one marker line; return a ``Marker`` or the rejection reason."""
    m = MARKER_RE.match(text)
    if not m:
        return "not a '<!-- screenshot: ... -->' line"
    body = m.group("body")
    pairs: dict[str, str] = {}
    pos = 0
    while True:
        rest = body[pos:]
        if not rest.strip():
            break
        pm = _PAIR_RE.match(body, pos)
        if not pm:
            return f"cannot parse near {rest.strip()[:30]!r}"
        key = pm.group("key")
        value = pm.group("q") if pm.group("q") is not None else pm.group("bare")
        pos = pm.end()
        # A pair must be followed by whitespace or the end of the body, so
        # `alt="x"y` is not read as alt="x" plus junk silently.
        if pos < len(body) and not body[pos].isspace():
            return f"cannot parse near {body[pm.start():].strip()[:30]!r}"
        if key not in KEYS:
            return f"unknown key {key!r}"
        if key in pairs:
            return f"duplicate key {key!r}"
        problem = value_problem(value)
        if problem:
            return f"{key}: {problem}"
        pairs[key] = value
    for key in REQUIRED:
        if key not in pairs:
            return f"missing required key {key!r}"
    if not SCENE_RE.match(pairs["scene"]):
        return "scene must match [a-z0-9_]+"
    f = pairs["file"]
    problem = path_problem(f)
    if problem:
        return f"file {problem}"
    return Marker(
        path=path, line=line, text=text.rstrip("\n"),
        scene=pairs["scene"], file=f, alt=pairs["alt"],
        caption=pairs.get("caption"), cls=pairs.get("class"),
    )


def scan(content_root: Path) -> tuple[list[Marker], list[Unparseable]]:
    """Find every marker and every screenshot comment that does not parse.

    Lexical rules, modeled on CommonMark:

    * fenced code blocks are skipped (an opening fence of three or more
      backticks or tildes, closed by the same character, at least as long);
    * a block comment starts on a line beginning (after up to three spaces)
      with ``<!--`` and ends on the first line containing ``-->``. One that
      mentions ``screenshot`` is a marker when it is a single line and parses,
      otherwise unparseable;
    * any other line holding both ``<!--`` and ``screenshot`` is reported as an
      inline comment -- markers must stand on their own line.

    A ``<!--`` written mid-line (for example inside inline code) never opens a
    block, so it cannot swallow the lines after it.
    """
    markers: list[Marker] = []
    bad: list[Unparseable] = []
    root = Path(content_root)
    for page in sorted(root.rglob("*.md")):
        rel = page.relative_to(root).as_posix()
        lines = page.read_text(encoding="utf-8").splitlines()
        fence: str | None = None
        i = 0
        while i < len(lines):
            ln = lines[i]
            if fence is not None:
                stripped = ln.lstrip(" ")
                if (len(ln) - len(stripped) <= 3 and stripped.startswith(fence[0] * len(fence))
                        and stripped.rstrip() == fence[0] * (len(stripped.rstrip()))):
                    fence = None
                i += 1
                continue
            fm = _FENCE_OPEN_RE.match(ln)
            if fm and not (fm.group("fence")[0] == "`" and "`" in fm.group("info")):
                fence = fm.group("fence")
                i += 1
                continue
            if _BLOCK_COMMENT_RE.match(ln):
                start = i
                end = i
                after_open = ln.index("<!--") + 4
                if "-->" not in ln[after_open:]:
                    end = i + 1
                    while end < len(lines) and "-->" not in lines[end]:
                        end += 1
                    end = min(end, len(lines) - 1)
                block = lines[start:end + 1]
                if _MENTION in "\n".join(block).lower():
                    if end != start:
                        bad.append(Unparseable(rel, start + 1, "\n".join(block), "multi-line"))
                    else:
                        res = parse_marker(ln, rel, start + 1)
                        if isinstance(res, Marker):
                            markers.append(res)
                        else:
                            bad.append(Unparseable(rel, start + 1, ln, res))
                i = end + 1
                continue
            if "<!--" in ln and _MENTION in ln.lower():
                bad.append(Unparseable(rel, i + 1, ln, "inline comment"))
            i += 1
    return markers, bad


def render_static_img(marker: Marker) -> str:
    """The ``static-img`` shortcode that replaces ``marker`` once captured.

    Raises ``ValueError`` on a value ``parse_marker`` would have rejected, so a
    hand-built ``Marker`` cannot produce a broken shortcode either.
    """
    params = [("src", f"imgs/{marker.file}"), ("alt", marker.alt)]
    if marker.caption is not None:
        params.append(("caption", marker.caption))
    if marker.cls is not None:
        params.append(("class", marker.cls))
    for key, value in params:
        problem = value_problem(value)
        if problem:
            raise ValueError(f"{key}: {problem}")
    body = " ".join(f'{k}="{v}"' for k, v in params)
    return "{{< static-img " + body + " >}}"


# --- image shortcode sources -------------------------------------------------

#: Shortcode name -> the parameter that names an image under static/.
IMAGE_SHORTCODES = {"static-img": "src", "split-hero": "image", "tour-tile": "src"}

_SC_OPEN_RE = re.compile(r"\{\{(?P<d>[<%])")
_SC_NAME_RE = re.compile(r"\s*(?P<name>/?[A-Za-z0-9_][A-Za-z0-9_./-]*)")
_SC_KEY_RE = re.compile(r"(?P<key>[A-Za-z0-9_-]+)\s*=\s*")


def _parse_shortcode(text: str, pos: int, delim: str):
    """Tokenize one shortcode call whose ``{{<`` / ``{{%`` ends at ``pos``.

    Follows Hugo's argument lexer as probed on Hugo 0.169: a value is
    ``"double quoted"`` (``\\"`` is an escaped quote), `` `raw` `` (no escapes)
    or a bare token ending at whitespace or the closing delimiter; ``key = value``
    may have spaces around ``=``; a closing delimiter inside a quoted value does
    not end the call. Returns ``(name, params, end)``; ``params`` maps a key to
    its decoded value. Returns None when the call is malformed or unterminated
    (Hugo fails such a build on its own).
    """
    close = delim + "}}"
    nm = _SC_NAME_RE.match(text, pos)
    if not nm:
        return None
    name = nm.group("name")
    i = nm.end()
    params: dict[str, str] = {}
    n = len(text)
    while True:
        while i < n and text[i].isspace():
            i += 1
        if i >= n:
            return None
        if text.startswith(close, i):
            return name, params, i + len(close)
        if text.startswith("/" + close, i):
            return name, params, i + 1 + len(close)
        km = _SC_KEY_RE.match(text, i)
        key = None
        if km:
            key = km.group("key")
            i = km.end()
        if i >= n:
            return None
        ch = text[i]
        if ch == '"':
            j = i + 1
            buf = []
            while j < n and text[j] != '"':
                if text[j] == "\\" and j + 1 < n and text[j + 1] == '"':
                    buf.append('"')
                    j += 2
                    continue
                buf.append(text[j])
                j += 1
            if j >= n:
                return None
            value, i = "".join(buf), j + 1
        elif ch == "`":
            j = text.find("`", i + 1)
            if j < 0:
                return None
            value, i = text[i + 1:j], j + 1
        else:
            j = i
            while j < n and not text[j].isspace() and not text.startswith(close, j):
                j += 1
            if j == i:
                return None
            value, i = text[i:j], j
        if key is not None:
            params[key] = value


def scan_image_sources(content_root: Path) -> list[tuple[str, int, str, str | None]]:
    """``(page, line, shortcode, src)`` for every image shortcode call.

    ``src`` is None when the call carries no image parameter. The escaped
    ``{{</* ... */>}}`` form is skipped, matching Hugo, which prints it as text.
    """
    out = []
    root = Path(content_root)
    for page in sorted(root.rglob("*.md")):
        rel = page.relative_to(root).as_posix()
        text = page.read_text(encoding="utf-8")
        pos = 0
        while True:
            m = _SC_OPEN_RE.search(text, pos)
            if not m:
                break
            delim = ">" if m.group("d") == "<" else "%"
            if text.startswith("/*", m.end()):
                end = text.find("*/" + delim + "}}", m.end())
                pos = len(text) if end < 0 else end + 4
                continue
            parsed = _parse_shortcode(text, m.end(), delim)
            if parsed is None:
                pos = m.end()
                continue
            name, params, pos = parsed
            if name in IMAGE_SHORTCODES:
                line = text.count("\n", 0, m.start()) + 1
                out.append((rel, line, name, params.get(IMAGE_SHORTCODES[name])))
    return out


# --- scene spec owner reader -------------------------------------------------

#: One top-level ``id:`` / ``output:`` line. A value is a bare token, a
#: double-quoted string without ``"`` or ``\`` (so it has no escapes), or a
#: single-quoted string without ``'`` (so it has no ``''`` doubling). A comment
#: needs at least one space before ``#``. Separators are spaces only: PyYAML
#: refuses a tab after the colon, before a comment, and as trailing whitespace.
SPEC_SCALAR_RE = re.compile(
    r"""^(?P<key>id|output): +(?P<val>"[^"\\]*"|'[^']*'|[A-Za-z0-9_./-]+)(?: +#.*)? *$"""
)

#: A bare value is accepted only when every YAML resolver loads it as a string:
#: it starts with a letter (ruling out ints, floats, dates, sexagesimals,
#: ``.inf`` / ``.nan``) ...
BARE_STRING_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_./-]*$")
#: ... and is not a YAML 1.1 bool/null word in any case. PyYAML loads ``y`` and
#: ``n`` as strings, but YAML 1.1 lists them as booleans; kept conservatively.
YAML_KEYWORDS = frozenset({"yes", "no", "true", "false", "on", "off", "null", "y", "n"})

SPEC_KEYS = ("id", "output")


@dataclass
class SpecOwner:
    id: str | None = None
    output: str | None = None
    problems: list[str] = field(default_factory=list)


def read_spec_scalar(line: str) -> tuple[str, str | None, str | None]:
    """Read one ``id:`` / ``output:`` line: ``(key, value, problem)``.

    Exactly one of ``value`` and ``problem`` is set. The contract with the YAML
    scene loader: whenever ``value`` is set, ``yaml.safe_load(line)[key]`` is
    that same ``str``.
    """
    key = line.split(":", 1)[0]
    m = SPEC_SCALAR_RE.match(line)
    if not m:
        return key, None, f"{key}: is not a supported single-line scalar"
    val = m.group("val")
    if val[0] in "\"'":
        return key, val[1:-1], None
    if not BARE_STRING_RE.match(val) or val.lower() in YAML_KEYWORDS:
        return key, None, f"{key}: bare value {val!r} may not load as a string in YAML; quote it"
    return key, val, None


def read_spec_owner(path: Path) -> SpecOwner:
    """Read the ``id:`` and ``output:`` of a scene spec without a YAML parser.

    Only lines starting ``id:`` / ``output:`` at column 0 count (top-level
    keys). An unsupported form is a named problem, never read as an absent key.
    ``output`` must also be canonical (``path_problem``); a non-canonical
    spelling such as ``./x.svg`` is a problem and leaves ``output`` unset, so
    duplicate and ownership checks only ever compare canonical strings.
    """
    owner = SpecOwner()
    seen: dict[str, int] = {}
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        for key in SPEC_KEYS:
            if line.startswith(key + ":"):
                seen[key] = seen.get(key, 0) + 1
                if seen[key] > 1:
                    owner.problems.append(f"{key}: duplicated")
                    setattr(owner, key, None)
                    continue
                _, value, problem = read_spec_scalar(line)
                if problem is None and key == "output":
                    pp = path_problem(value)
                    if pp:
                        problem = f"output {value!r} {pp}"
                if problem:
                    owner.problems.append(problem)
                else:
                    setattr(owner, key, value)
    for key in SPEC_KEYS:
        if key not in seen:
            owner.problems.append(f"{key}: missing")
    return owner
