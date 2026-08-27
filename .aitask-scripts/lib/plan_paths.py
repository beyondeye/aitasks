"""Single source of truth for plan-file path extraction + classification (t1569_1).

Given an implementation plan, pull out every token that looks like a repo-relative
source path, and classify each against `git ls-files`. Two independent consumers
need this and must not drift apart:

  * ``aitask_remote_drift_check.sh`` (shell) -- intersects plan paths with
    remote-changed files to decide OVERLAP. Consumes this module through the
    lazy bridge ``plan_paths_sh.sh``.
  * ``lib/trail_gather.py`` (Python) -- emits ``INFLIGHT_PATH:`` records under
    ``--with-inflight``. Imports this module directly.

t1569_3's parallel-admission checker is a third consumer, also by import. The
extraction previously lived inline in the drift check as a one-line
``grep -oE ... | sed | sort -u`` pipeline; forking it would guarantee divergence
on the edges recorded in
``aidocs/framework/plan_path_reference_extraction_findings.md``.

NOT THE ONLY EXTRACTOR IN THE REPO, AND DELIBERATELY SO. ``aitask_change_surface.sh``
carries its own, broader one (t1263): no extension allowlist, a token class that
admits a leading dot, and validation against the FILESYSTEM rather than
``git ls-files``. It answers a different question -- "which files did this task
change?" -- with different correctness requirements, so the two are not merged.
This module owns the extension-allowlisted grammar shared by the drift check and
the gatherer; ``tests/test_plan_paths_seam.sh`` guards that scope and pins the
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
instead of before them. Codepoint order is the canonical one here and the shell
bridge sorts under ``LC_ALL=C`` to match. This changes the drift check's emitted
path ORDER but no verdict: its intersect is ``grep -Fxf``, which is
order-independent.

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


def main(argv) -> int:
    args = list(argv[1:])
    validate = False
    if args and args[0] == "--validate-tracked":
        validate = True
        args = args[1:]
    # `--` ends option parsing: the plan path itself may begin with a hyphen.
    if args and args[0] == "--":
        args = args[1:]
    if len(args) != 1:
        sys.stderr.write(
            "usage: plan_paths.py [--validate-tracked] <plan-file>\n")
        return 2
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
