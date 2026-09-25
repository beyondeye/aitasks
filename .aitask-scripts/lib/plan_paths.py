"""Single source of truth for plan-file path extraction + classification (t1569_1).

Given an implementation plan, pull out every token that looks like a repo-relative
source path, and classify each against `git ls-files`. Two independent consumers
need this and must not drift apart:

  * ``lib/trail_gather.py`` (Python) -- emits ``INFLIGHT_PATH:`` records under
    ``--with-inflight``. Imports this module directly.
  * t1569_3's parallel-admission checker, also by import.

``aitask_remote_drift_check.sh`` was the first consumer of this grammar; since
t1877 it uses the reference search below instead (see THE SECOND ENTRY POINT). Since
t1688 both importers also read task DESCRIPTIONS, for a task that has no plan
yet (``task_body_text`` / ``cut_task_framework_sections``) -- the same grammar
and classifier over a different document, never a second extractor. The
extraction previously lived inline in the drift check as a one-line
``grep -oE ... | sed | sort -u`` pipeline; forking it would guarantee divergence
on the edges recorded in
``aidocs/framework/plan_path_reference_extraction_findings.md``.

NOT THE ONLY EXTRACTOR IN THE REPO, AND DELIBERATELY SO. ``aitask_change_surface.sh``
carries its own, broader one (t1263): no extension allowlist, a token class that
admits a leading dot, and validation against the FILESYSTEM rather than
``git ls-files``. It answers a different question -- "which files did this task
change?" -- with different correctness requirements, so the two are not merged.
This module owns the extension-allowlisted grammar shared by the gatherer and
the admission checker; ``tests/test_plan_paths_seam.sh`` guards that scope and pins the
other one so it cannot quietly drift into a copy.

GRAMMAR -- deliberately unchanged from the pipeline this replaces, so the move is
behaviour-preserving. There is NO allowlist of directory roots (t1275 removed it:
OVERLAP is an exact full-line intersection, so a root filter can only remove TRUE
positives). The *extension* list is a KNOWN remaining narrowing, deliberately kept:
a plan referencing ``internal/pkg/server.go`` yields zero tokens, so in a
Go/Rust/JS project the path evidence is empty BY CONSTRUCTION. Consumers must
surface that as its own state and never as "scanned, nothing to worry about".

COLLATION -- ``sorted()``, i.e. codepoint order. The replaced pipeline used
``sort -u``, which is locale-collated: under ``en_US.UTF-8`` it yields
``a-b.md a_b.md ab.md aB.md`` where codepoint order yields
``a-b.md aB.md a_b.md ab.md``, and it sorts a leading-dot path among the letters
instead of before them. Codepoint order is the canonical one here, and the
``--references`` CLI emits its hits in the same order. No consumer verdict
depends on the order.

MALFORMED TOKENS -- the charset admits a leading ``-``, and the live corpus
produces three (``-claude.md``, ``-agy-/SKILL.md``, ``-codex-/SKILL.md``), split
out of golden filenames like ``SKILL-${p}-claude.md`` where ``$``/``{`` break the
token. These are extraction garbage, not paths the plan meant, and they are
classified ``malformed`` FIRST so they can never reach ``planned_new`` -- the
class a consumer reads as new-file-collision evidence. The class is named for
provenance rather than danger because every consumer is required to pass ``--``
and ``:(literal)``, under which a leading hyphen is in fact safe. It is open to
grow, but only within what the grammar can produce: a colon or newline can never
appear in a token (``:(glob)a.md`` extracts as ``a.md``), so widening it beyond
absolute paths and parent traversal requires widening ``_TOKEN`` first.

THE SECOND ENTRY POINT: REFERENCE DETECTION (t1873). ``find_references()`` asks
the inverted question: given paths git already reported as CHANGED, which of
them does this text reference? The candidate set is whatever git names, byte for
byte, so there is no filename grammar and no extension list: a Go, Rust or
TypeScript source, an extensionless ``Makefile`` and a backtick-quoted spaced
path are all found. It implements the delimitation rule, the Unicode
normalization and the undecodable-byte handling specified in
``aidocs/framework/plan_path_reference_extraction_findings.md`` sections 3-5.
``find_suffix_references()`` is its weaker companion for module-relative
mentions (a sub-project plan naming ``internal/x/main.go`` for
``goengines/internal/x/main.go``), and ``find_dir_references()`` matches
explicit ``<dir>/`` mentions. ``reference_kinds()`` tiers their hits
(full / bare / suffix) for a consumer that must grade its verdict.

Consumers that have a changed-path set in hand use this search: the shadow's
scope-evidence helper (``shadow_scope.py``) and, since t1877, the remote drift
check, which tests ``git diff <base>...origin/<base>`` against the plan through
``plan_paths.py --references`` (bridge: ``plan_paths_references``). Consumers
that need candidates FROM the plan -- the gatherer and parallel admission, which
have no changed-path set for an in-flight task -- keep the extension grammar
above, unchanged. That decision and its measurements are recorded in the
findings doc, section 7.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys

# Extraction grammar. Kept byte-identical in meaning to the pipeline it replaces:
#   grep -oE '[A-Za-z0-9_./-]+\.(sh|py|md|yaml|yml|json|toml)'
_EXTENSIONS = ("sh", "py", "md", "yaml", "yml", "json", "toml")
_TOKEN = re.compile(
    r"[A-Za-z0-9_./-]+\.(?:" + "|".join(_EXTENSIONS) + r")")

# Classification vocabulary, in evaluation order. `malformed` is FIRST by
# contract -- see the module docstring.
CLASSES = ("malformed", "tracked", "planned_new", "phantom")


def extract(text: str) -> list[str]:
    """Every distinct path token in `text`, `./`-stripped, codepoint-sorted."""
    return sorted({_strip_dot_slash(m) for m in _TOKEN.findall(text)})


def cut_task_framework_sections(body: str) -> str:
    """Truncate a task body at the first framework-appended section.

    `## Inbox` (note framework) is inserted BEFORE `## Gate Runs`
    (aitask_note.sh), so cutting only at Gate Runs would leave other agents'
    note prose -- arbitrary paths from other tasks -- in a task-declared
    surface. Note bodies cannot fake either header: every body line is prefixed
    `> | `, so an anchored match on the bare header is exact.
    """
    import gate_ledger   # lazy: keeps the plan_paths_sh.sh bridge's load path unchanged
    import note_inbox
    headers = (note_inbox.SECTION_HEADER, gate_ledger.SECTION_HEADER)
    pattern = re.compile(
        r"^(?:%s)[ \t]*$" % "|".join(re.escape(h) for h in headers), re.MULTILINE)
    match = pattern.search(body)
    return body if match is None else body[:match.start()]


def task_body_text(raw: str) -> str:
    """A task file's declared text: frontmatter stripped, framework sections cut.

    The frontmatter shape is `parallel_admission_collect.strip_frontmatter`'s:
    a leading `---` block closed by the next `\\n---`.
    """
    if raw.startswith("---"):
        end = raw.find("\n---", 3)
        if end != -1:
            raw = raw[end + 4:]
    return cut_task_framework_sections(raw)


def extract_file(path) -> list[str]:
    """`extract()` over a file's text. Raises OSError/UnicodeDecodeError up to
    the caller: "could not read it" is a distinct state from "read it and it had
    nothing", and swallowing it here would file an I/O failure as a corpus fact.
    """
    with open(path, "r", encoding="utf-8") as handle:
        return extract(handle.read())


def _strip_dot_slash(token: str) -> str:
    return token[2:] if token.startswith("./") else token


def is_malformed(token: str) -> bool:
    """Extraction garbage rather than a path the plan meant.

    Currently: a leading `-`. Kept as a predicate (not an inline test) so the
    guard test can assert on this symbol, and so growing the class is one edit.
    """
    return token.startswith("-")


def classify(token: str, tracked: "set[str]", tracked_dirs: "set[str]") -> str:
    """One token -> one member of `CLASSES`. Order is part of the contract."""
    if is_malformed(token):
        return "malformed"
    if token in tracked:
        return "tracked"
    parent = os.path.dirname(token)
    # `planned_new` REQUIRES a non-empty parent. A bare filename's parent is the
    # repo root, which is trivially tracked -- and 428 of the 1059 tokens in the
    # live corpus are bare filenames from prose ("see adapter.py"), which would
    # flood `planned_new` from 75 to 503 and drown the signal a consumer gates
    # on. The cost is a real false negative, recorded in the plan: a GENUINE
    # planned new top-level file (`pyproject.toml` at the root) classifies
    # `phantom`. Stated, not discovered.
    if parent and parent in tracked_dirs:
        return "planned_new"
    return "phantom"


# Bound for the single `git ls-files` call. It is not optional: a wedged
# `.git/index.lock` or a hung NFS mount would otherwise block a caller that has
# promised never to fail its own operation, and no outer budget can rescue it
# because the call is synchronous.
LS_FILES_TIMEOUT_S = 5


def tracked_sets(repo_root=None, timeout=LS_FILES_TIMEOUT_S) -> "tuple[set[str], set[str]]":
    """`git ls-files` once, plus the set of tracked directory prefixes.

    ONE subprocess for the whole classification pass -- never one per path and
    never one per task. A single live plan contributes 45 paths.

    Returns `(tracked_files, tracked_dirs)`. Raises `subprocess.CalledProcessError`,
    `subprocess.TimeoutExpired` or `OSError` when git cannot answer; callers
    decide what that means rather than receiving an empty set that reads as
    "nothing is tracked". A caller that swallows this turns an infrastructure
    failure into a measured result: every path would classify `phantom`, and a
    consumer would read a complete-looking all-clear derived from zero evidence.
    """
    cmd = ["git"]
    if repo_root is not None:
        cmd += ["-C", str(repo_root)]
    cmd += ["ls-files", "-z"]
    out = subprocess.run(cmd, capture_output=True, check=True,
                         timeout=timeout).stdout
    # -z: NUL-delimited, so a path containing a newline cannot split a record.
    tracked = {p.decode("utf-8", "surrogateescape")
               for p in out.split(b"\0") if p}
    dirs: set[str] = set()
    for path in tracked:
        parts = path.split("/")
        for i in range(1, len(parts)):
            dirs.add("/".join(parts[:i]))
    return tracked, dirs


def classify_all(tokens, tracked: "set[str]",
                 tracked_dirs: "set[str]") -> "list[tuple[str, str]]":
    """`[(class, token), ...]` in the input's order."""
    return [(classify(t, tracked, tracked_dirs), t) for t in tokens]


# --- Reference detection (the inverted search) -------------------------------
#
# Delimiters, per findings doc section 3: whitespace plus prose punctuation,
# `#` included. Everything else -- `@ + ~ %`, alphanumerics, `/ . - _`,
# non-ASCII -- continues a path, so `src/app.py@v2` does NOT reference
# `src/app.py` and `src/a` is not referenced by `src/a+b.py`.
_REF_DELIMS = "\t\n\v\f\r []\"'`(){}<>,;:!?|=*#"
_D = re.escape(_REF_DELIMS)
# "Preceded by a delimiter or the start of the text" / "followed by one or the
# end", written as negated classes so no alternation with ^/$ is needed.
_BEFORE = r"(?<![^" + _D + r"])"
_AFTER = r"(?![^" + _D + r"])"

_HEADING = re.compile(r"^\s{0,3}(#{1,6})\s+(.*?)\s*#*\s*$")
# A line that is nothing but a bold label, optionally a list item:
# `**Critical files:**`, `- **Files to modify**:`.
_BOLD_LABEL = re.compile(r"^\s*(?:[-*+]\s+)?\*\*([^*]+?)\*\*\s*:?\s*$")


def _nfc(text: str) -> str:
    import unicodedata
    return unicodedata.normalize("NFC", text)


def _heading_contexts(text: str) -> "list[tuple[int, str, str]]":
    """`[(line_no, heading, line), ...]` for every line of `text`, 1-based.

    `heading` is the nearest enclosing markdown heading or bold-label line
    (without its markup), or "" before the first one. A markdown heading
    replaces any bold label; a bold label replaces the previous bold label.
    """
    rows = []
    heading = ""
    for no, line in enumerate(text.split("\n"), start=1):
        m = _HEADING.match(line)
        if m:
            heading = m.group(2).strip()
        else:
            b = _BOLD_LABEL.match(line)
            if b:
                heading = b.group(1).strip().rstrip(":").strip()
        rows.append((no, heading, line))
    return rows


def _reference_scan(text: str, stems: "dict[str, list[str]]",
                    tail: str) -> "dict[str, list[tuple[int, str]]]":
    """Shared matcher. `stems` maps an NFC stem to the originals it stands for."""
    found: "dict[str, list[tuple[int, str]]]" = {}
    if not stems:
        return found
    # Longest first: at one position the longer path wins, which is what keeps
    # `src/my` from being reported for `` `src/my file.py` `` when both changed.
    alternation = "|".join(re.escape(s) for s in sorted(stems, key=len, reverse=True))
    pattern = re.compile(_BEFORE + r"(?:\./)?(" + alternation + r")" + tail)
    for no, heading, line in _heading_contexts(_nfc(text)):
        for m in pattern.finditer(line):
            for original in stems[m.group(1)]:
                refs = found.setdefault(original, [])
                if (no, heading) not in refs:
                    refs.append((no, heading))
    return found


def find_references(text: str, candidates) -> "dict[str, list[tuple[int, str]]]":
    """Which `candidates` (paths git reported) does `text` reference, and where.

    Returns `{original_candidate: [(line_no, heading), ...]}` for the referenced
    ones only. `heading` is the enclosing section (see `_heading_contexts`), so a
    caller can tell a file-list mention from a context citation without
    requiring any particular heading to exist.

    A reference is `<path>` bounded by delimiters, optionally `./`-prefixed, and
    optionally followed by one sentence-final `.` (findings doc section 3). Both
    sides are NFC-normalized, and the result is keyed by the ORIGINAL candidate
    string, so an NFD path git reports is returned as git named it; candidates
    that collide under NFC are all reported (section 4). Strings decoded with
    `surrogateescape` pass through unchanged (section 5). Never raises on
    content.
    """
    stems: "dict[str, list[str]]" = {}
    for c in candidates:
        if c:
            stems.setdefault(_nfc(c), []).append(c)
    return _reference_scan(text, stems, r"(?:" + _AFTER + r"|\." + _AFTER + r")")


def find_suffix_references(text: str, candidates,
                           min_components: int = 2) -> "dict[str, list[tuple[int, str]]]":
    """Candidates referenced only by a TRAILING SUB-PATH of at least
    `min_components` components -- the module-relative form a plan for a
    sub-project uses (`internal/tools/x/main.go` for the repo path
    `goengines/internal/tools/x/main.go`).

    Weaker than `find_references`: a short suffix (`cmd/main.go`) can match
    several modules, so a caller must keep the two kinds apart. A candidate the
    text references IN FULL is not reported here, and the left boundary still
    applies, so the full path's own occurrence never doubles as a suffix hit.
    """
    full = find_references(text, candidates)
    stems: "dict[str, list[str]]" = {}
    for c in candidates:
        if not c or c in full:
            continue
        parts = c.split("/")
        for start in range(1, len(parts) - min_components + 1):
            stems.setdefault(_nfc("/".join(parts[start:])), []).append(c)
    return _reference_scan(text, stems, r"(?:" + _AFTER + r"|\." + _AFTER + r")")


def find_dir_references(text: str, dirs) -> "dict[str, list[tuple[int, str]]]":
    """`find_references` for EXPLICIT directory mentions: `<dir>/` bounded on
    both sides exactly like a file reference ("the new goengines/ tree").

    A file path does not count as a mention of its directories: were
    `lib/x.sh` to reference `lib`, one cited file would lend every sibling in
    `lib/` the same evidence, and the signal would be noise. Keys are the
    directories as given, without the slash.
    """
    stems: "dict[str, list[str]]" = {}
    for d in dirs:
        d = d.rstrip("/")
        if d:
            stems.setdefault(_nfc(d) + "/", []).append(d)
    return _reference_scan(text, stems, r"(?:" + _AFTER + r"|\." + _AFTER + r")")


def reference_kinds(text: str, candidates) -> "dict[str, str]":
    """Referenced `candidates` -> the strength of the reference, for a consumer
    that must tier its verdict (the remote drift check's OVERLAP / WEAK_OVERLAP).

      full    `find_references` hit on a path with a `/`, or a `.` in its name
      bare    `find_references` hit on a single-component name with no `.`
              (`ait`, `Makefile`, `LICENSE`) -- the same word is ordinary prose
              ("run `ait setup`"), so it is evidence, never a strong claim
      suffix  `find_suffix_references` hit -- a module-relative mention, which
              a short suffix makes ambiguous across modules

    Composes the matchers above and adds no grammar of its own. Measured on the
    live corpus in findings doc section 7.
    """
    full = find_references(text, candidates)
    kinds = {c: ("bare" if "/" not in c and "." not in c else "full")
             for c in full}
    for c in find_suffix_references(text, candidates):
        kinds.setdefault(c, "suffix")
    return kinds


def _references_main(plan_file: str) -> int:
    """`--references`: candidates NUL-delimited on stdin -> `<kind>\\t<path>`."""
    try:
        with open(plan_file, "r", encoding="utf-8",
                  errors="surrogateescape") as handle:
            text = handle.read()
    except OSError as exc:
        sys.stderr.write(f"plan_paths: cannot read {plan_file}: {exc}\n")
        return 3
    raw = sys.stdin.buffer.read()
    # A path containing a newline can never match the per-line scan, and would
    # break the line protocol on the way out, so it is not a candidate.
    candidates = [p for p in (b.decode("utf-8", "surrogateescape")
                              for b in raw.split(b"\0")) if p and "\n" not in p]
    kinds = reference_kinds(text, candidates)
    out = "".join(f"{kinds[p]}\t{p}\n" for p in sorted(kinds))
    sys.stdout.buffer.write(out.encode("utf-8", "surrogateescape"))
    return 0


def main(argv) -> int:
    args = list(argv[1:])
    validate = False
    references = False
    if args and args[0] == "--validate-tracked":
        validate = True
        args = args[1:]
    elif args and args[0] == "--references":
        references = True
        args = args[1:]
    # `--` ends option parsing: the plan path itself may begin with a hyphen.
    if args and args[0] == "--":
        args = args[1:]
    if len(args) != 1:
        sys.stderr.write(
            "usage: plan_paths.py [--validate-tracked | --references] <plan-file>\n")
        return 2
    if references:
        return _references_main(args[0])
    try:
        tokens = extract_file(args[0])
    except (OSError, UnicodeDecodeError) as exc:
        sys.stderr.write(f"plan_paths: cannot read {args[0]}: {exc}\n")
        return 3
    if not validate:
        sys.stdout.write("".join(f"{t}\n" for t in tokens))
        return 0
    try:
        tracked, dirs = tracked_sets()
    except (subprocess.CalledProcessError, OSError) as exc:
        sys.stderr.write(f"plan_paths: git ls-files failed: {exc}\n")
        return 3
    sys.stdout.write("".join(
        f"{cls}\t{tok}\n" for cls, tok in classify_all(tokens, tracked, dirs)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
