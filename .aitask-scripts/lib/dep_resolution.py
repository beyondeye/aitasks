#!/usr/bin/env python3
"""The single decision core for LOCAL ``depends:`` resolution (t1527).

Three surfaces used to answer "is this task blocked by its ``depends``?"
independently, with three different policies — ``ait ls``
(``is_task_uncompleted``), the minimonitor task picker
(``TaskInfoCache.blocking_dependencies``) and the board
(``TaskManager.unresolved_local_deps``) — so they could disagree about the same
task in two independent ways: an unresolvable id was silently satisfied on two
of the three, and the t635_3 gate-release rule ("an active upstream whose
required gates all pass unblocks its dependents before archival") was missing
from the minimonitor entirely. This module is the one place that decides, and
every surface now consumes it.

Policy — **fail-closed, tri-state**, the standard the cross-repo (``xdeps``)
half already sets by rendering an explicit ``(UNREACHABLE)`` rather than passing
an id nobody can resolve:

    facts is None   -> UNRESOLVABLE   (blocks, AND renders as `(UNRESOLVED)`)
    status == Done  -> SATISFIED
    gate_released   -> SATISFIED      (t635_3)
    otherwise       -> BLOCKING

*satisfied* / *blocking* / *unresolvable* are three outcomes, not two: an id
that cannot be resolved is a data error and must read as one, never as ordinary
upstream work.

**Resolution scope: loose files only.** Active ``aitasks/`` plus loose
``aitasks/archived/``. Numbered bundles (``archived/_b<N>/old<M>.tar.zst``) are
never extracted — the documented non-goal — so an id that lives only in a bundle
is ``UNRESOLVABLE`` and says so. ``lib/archive_iter.find_archived_markdown_by_id``
*can* read bundles; it is deliberately not used here, because a surface that
resolved more than the others would break the parity this module exists to
provide.

Stdlib + ``task_yaml`` + ``gate_ledger`` only. Base-layer module: it imports
nothing from a TUI directory (``tests/test_no_lib_to_tui_import.sh``).

CLI:
    dep_resolution.py scan <tasks-dir> [registry.yaml]
        One line per task file with >=1 non-satisfied dep:
            <path>\\t<display-csv>
        followed by a terminal ``SCAN_OK`` line. The trailer is load-bearing:
        empty output alone cannot distinguish "nothing is blocked" from "the
        scan never ran", and a consumer that guessed the former would fail OPEN
        — the exact defect class this module removes.
"""
from __future__ import annotations

import os
import re
import sys
from dataclasses import dataclass

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import gate_ledger  # noqa: E402  (shared gate-ledger core; the t635_3 rule)
from task_yaml import parse_frontmatter  # noqa: E402

# --- Verdicts -------------------------------------------------------------

SATISFIED = "SATISFIED"
BLOCKING = "BLOCKING"
UNRESOLVABLE = "UNRESOLVABLE"

#: Rendered suffix for an UNRESOLVABLE dep. Deliberately parallel to the
#: cross-repo ``(UNREACHABLE)`` marker, and deliberately different from it: the
#: cross-repo one means "a sibling repo could not be reached", this one means
#: "no task file with this id exists in this repo".
UNRESOLVED_MARKER = "(UNRESOLVED)"

#: The canonical accepted forms of a `depends:` entry. t1528 (write-time
#: validation) enforces exactly these; anything else canonicalizes to None and
#: is therefore UNRESOLVABLE rather than silently dropped.
_CANONICAL_RE = re.compile(r"^t?(\d+)(?:_(\d+))?$")

_TERMINAL = "SCAN_OK"


def canonical_dep_id(raw) -> str | None:
    """``"t423_6"`` / ``"423_6"`` / ``"423"`` / ``423`` -> ``"423_6"`` / ``"423"``.

    Returns ``None`` for anything outside the accepted forms — an empty entry, a
    glob, a stray word. ``None`` means UNRESOLVABLE, never "skip": an id nobody
    can parse is exactly the data error this module renders honestly.

    Note ``depends:`` is read through ``task_yaml.parse_frontmatter``, whose
    ``_TaskSafeLoader`` already keeps ``423_6`` a *string* — PyYAML's YAML-1.1
    underscore digit-separator would otherwise coerce it to the integer 4236 and
    the intent would be unrecoverable.
    """
    if raw is None or isinstance(raw, bool):
        return None
    m = _CANONICAL_RE.match(str(raw).strip())
    if not m:
        return None
    return f"{m.group(1)}_{m.group(2)}" if m.group(2) else m.group(1)


@dataclass(frozen=True)
class DepFacts:
    """What resolution found about one dependency."""
    status: str
    gate_released: bool
    path: str


@dataclass(frozen=True)
class DepVerdict:
    """One dependency's verdict, carrying enough to render it honestly.

    ``raw`` is the token **as written** in ``depends:``, kept so each surface can
    display it in its own established convention (``ait ls`` shows a bare parent
    number, the TUIs prefix ``t``) without this module having to pick one and
    change three outputs. ``canonical`` is the resolution key.
    """
    raw: str
    canonical: str | None
    verdict: str

    @property
    def blocking(self) -> bool:
        """True for BOTH non-satisfied outcomes — unresolvable blocks too."""
        return self.verdict != SATISFIED

    @property
    def unresolvable(self) -> bool:
        return self.verdict == UNRESOLVABLE

    def display(self, *, prefix: str = "") -> str:
        """Render for a user-facing surface, e.g. ``t2 (UNRESOLVED)``.

        ``prefix`` is the surface's id convention (``"t"`` for the board and the
        minimonitor, ``""`` for ``ait ls``, which prints ids as its parser
        normalized them). The marker itself is single-sourced here so the three
        surfaces cannot drift into three spellings of the same state.
        """
        if self.canonical is None and not _looks_like_an_id(self.raw):
            # The malformed-field token is not an id: prefixing it would render
            # `t<malformed depends>`, which reads as a task that does not exist
            # rather than as a field that cannot be read.
            return f"{self.raw} {UNRESOLVED_MARKER}"
        shown = self.raw if not prefix else f"{prefix}{str(self.raw).lstrip('t')}"
        return f"{shown} {UNRESOLVED_MARKER}" if self.unresolvable else shown


#: Rendered stand-in for a `depends:` field that is not a list at all. It is a
#: token, not an id: there is nothing to resolve, and the *field* is what is
#: wrong.
MALFORMED_TOKEN = "<malformed depends>"

#: Conservative pre-filter for :meth:`LocalDepResolver.classify_text`. It only
#: ever answers "this file definitely has no dependency"; anything it is not
#: certain about goes to the authoritative parse, so it can never become a
#: second, disagreeing reader of the field.
_DEPENDS_LINE_RE = re.compile(r"^depends:[ \t]*(.*)$", re.M)
#: An explicit inline empty list — the ONLY same-line value that proves the field
#: carries nothing. A bare key is a block-list head, not an empty field.
_INLINE_EMPTY_RE = re.compile(r"^\[\s*\]$")


def may_have_depends(text: str) -> bool:
    """Whether ``text``'s frontmatter could carry a dependency.

    `parse_frontmatter` costs ~0.55 ms/file (PyYAML), and many tasks carry
    `depends: []`. Measured on this repo: 453 task files, of which **244 (54%)**
    are skipped here. Same shape as `gate_ledger.has_gate_markers`, and the same
    rule: **it may only return ``False`` for a certainty.**

    Exactly two shapes are certain: no ``depends:`` key at all, and an explicit
    INLINE empty list. Everything else — including a **bare** ``depends:`` key,
    which is the head of a valid YAML block list ::

        depends:
          - 999

    — goes to the authoritative parse. Treating a bare key as dep-free (because
    nothing follows the colon on that line) skipped a task that really does have
    dependencies, so `ait ls` showed it Ready while the board and the minimonitor
    blocked it: the exact three-surface disagreement this module exists to
    remove, reintroduced by its own optimisation. A key with a trailing comment
    (``depends:  # none``) is likewise not a certainty and is parsed.
    """
    head = text.split("\n---", 1)[0] if text.startswith("---") else text
    m = _DEPENDS_LINE_RE.search(head)
    if m is None:
        return False                       # no field at all
    return _INLINE_EMPTY_RE.match(m.group(1).strip()) is None


def read_depends(raw) -> tuple[list, bool]:
    """``(tokens, malformed)`` for a raw ``depends:`` frontmatter value.

    ``task_yaml._normalize_task_ids`` deliberately passes a non-list value
    through untouched ("malformed input stays malformed and type-honest, and
    consumers can detect it") — this is the consumer that detects it, once, for
    every surface.

    A **scalar** field (`depends: 999`, `depends: "999"`) or a mapping is
    ``malformed``: the frontmatter contract says `depends` is a list, and a
    consumer that guessed would be guessing which of two incompatible readings
    the author meant. It must not degrade to "no dependencies" — that is
    fail-open on a task nobody can verify. It also must not be *iterated*: the
    int raises ``TypeError`` and the string yields ``['9', '9', '9']``, which is
    exactly the trap ``_normalize_task_ids`` documents.

    An absent, ``None``, empty-list or blank field is genuinely "no
    dependencies" and is NOT malformed. (t1528 stops malformed values being
    written; this keeps them visible until then, and afterwards for
    hand-edited files.)
    """
    if raw is None:
        return [], False
    if isinstance(raw, (list, tuple)):
        return list(raw), False
    if isinstance(raw, str) and not raw.strip():
        return [], False                   # a blank field, not a broken one
    return [], True


def _looks_like_an_id(raw) -> bool:
    """Whether ``raw`` is at least *shaped* like a task-id token.

    Distinguishes an id we could not resolve (`4242`, `t9_9` — render it as an
    id) from the malformed-field stand-in (render it verbatim).
    """
    return bool(re.match(r"^t?\d", str(raw)))


def classify_facts(facts: DepFacts | None) -> str:
    """The whole policy, in one function. See the module docstring."""
    if facts is None:
        return UNRESOLVABLE
    if facts.status == "Done":
        return SATISFIED
    if facts.gate_released:
        return SATISFIED
    return BLOCKING


# --- Resolver -------------------------------------------------------------

def _canonical_from_path(path: str) -> str:
    """Canonical id from a task filename — the key the gate ledger stamps runs
    with. Falls back to the basename so a odd name still produces a stable id,
    matching ``gate_ledger.task_id_from_file``."""
    name = os.path.basename(path)
    m = re.match(r"^t(\d+)(?:_(\d+))?_", name)
    if not m:
        return name
    return f"{m.group(1)}_{m.group(2)}" if m.group(2) else m.group(1)


def _dir_identity(path: str) -> tuple[int, int] | None:
    """``(st_mtime_ns, st_ino)`` for a directory, or ``None`` if absent.

    A directory's mtime changes when an entry is added, removed or renamed —
    which is exactly the set of events that can change *which file* an id
    resolves to. Keying the id->path index on it is what makes a cached miss and
    a cached archived-hit self-correcting.
    """
    try:
        st = os.stat(path)
    except OSError:
        return None
    return (st.st_mtime_ns, st.st_ino)


def _file_identity(path: str) -> tuple[int, int] | None:
    """``(st_mtime_ns, st_size)`` — the identity key ``TaskInfoCache`` and
    ``GateSummaryCache`` already use, so two caches over one file cannot
    disagree about whether it changed. An *edit* leaves the parent directory's
    mtime alone, so this is the level that catches it."""
    try:
        st = os.stat(path)
    except OSError:
        return None
    return (st.st_mtime_ns, st.st_size)


class LocalDepResolver:
    """Resolve ``depends:`` ids against ONE tasks tree, loose files only.

    **Caching is two-level, and each level self-invalidates on the event that
    can change its answer.** Keying only by resolved-file identity is not
    enough, and both gaps are silent:

    * a *miss* has no path to stat, so a long-lived minimonitor would keep
      reporting ``UNRESOLVED`` after the task was created;
    * an archived hit keeps its identity when an *active* copy appears, so the
      archived ``Done`` copy would stay authoritative forever.

    Both are **directory** events, hence level 1 below. Level 2 catches the one
    thing a directory mtime does not see: an edit to a file already indexed.

    **Cycles.** ``gate_released`` is derived through a
    :class:`gate_ledger.DependentsEvaluator`, which memoizes the gate registry
    and the repo code digest. Those are re-validation inputs, so an evaluator is
    scoped to ONE scan/refresh cycle — see its docstring, and
    ``TaskManager.clear_gate_cache``'s t1416 note. :meth:`begin_cycle` installs a
    fresh one and bumps a generation counter; cached facts carry their
    generation, so ``gate_released`` is recomputed on the first touch of each new
    cycle while the (evaluator-independent) directory index survives.

    Accepted residual: a create-and-delete pair landing inside one mtime tick
    leaves the index stale — the same residual the ``(mtime_ns, size)`` key
    already accepts elsewhere. :meth:`invalidate_all` is the forced immediate
    re-resolve for it.
    """

    def __init__(self, tasks_dir, registry_file: str | None = None) -> None:
        self.tasks_dir = str(tasks_dir)
        self.archived_dir = os.path.join(self.tasks_dir, "archived")
        self.registry_file = registry_file
        self._dir_index: dict[str, tuple[tuple[int, int] | None, dict[str, str]]] = {}
        self._facts: dict[str, tuple[tuple[int, int] | None, int, DepFacts | None]] = {}
        self._generation = 0
        self._evaluator: gate_ledger.DependentsEvaluator | None = None

    # -- cycle management --------------------------------------------------

    def begin_cycle(self, *, digest_provider=None) -> None:
        """Start a new scan/refresh cycle: fresh evaluator, bumped generation.

        Call this once per refresh — never once per process for a long-running
        TUI. ``digest_provider`` lets a caller thread its own once-per-refresh
        code-digest memo (the board's ``code_digest_for_refresh``); omitted, the
        evaluator computes at most one itself, lazily.
        """
        self._generation += 1
        self._evaluator = gate_ledger.DependentsEvaluator(
            self.registry_file,
            digest_provider if digest_provider is not None
            else gate_ledger._COMPUTE_DIGEST,
        )

    def invalidate_all(self) -> None:
        """Drop every cached answer and start a new cycle.

        The forced immediate re-resolve: it is what the minimonitor's
        ``refresh=True`` means, and the escape hatch for the same-mtime-tick
        residual documented on the class.
        """
        self._dir_index.clear()
        self._facts.clear()
        self.begin_cycle()

    def _evaluator_for_cycle(self) -> gate_ledger.DependentsEvaluator:
        if self._evaluator is None:
            self.begin_cycle()
        assert self._evaluator is not None
        return self._evaluator

    # -- resolution --------------------------------------------------------

    def _index_for(self, directory: str, child_prefix: str | None) -> dict[str, str]:
        """``{canonical_id: path}`` for one directory, rebuilt when it changes.

        ``child_prefix`` is the parent number when ``directory`` is a child dir
        (``aitasks/t635/``), ``None`` for a top-level one. A directory that does
        not exist caches as an empty index keyed on ``None`` identity, and is
        re-checked the moment it appears.
        """
        identity = _dir_identity(directory)
        cached = self._dir_index.get(directory)
        if cached is not None and cached[0] == identity:
            return cached[1]
        index: dict[str, str] = {}
        if identity is not None:
            try:
                entries = os.listdir(directory)
            except OSError:
                entries = []
            for name in sorted(entries):
                if not name.endswith(".md"):
                    continue
                m = re.match(r"^t(\d+)(?:_(\d+))?_", name)
                if not m:
                    continue
                if child_prefix is not None:
                    # Child dir: only t<parent>_<child>_* belongs to it.
                    if m.group(2) is None or m.group(1) != child_prefix:
                        continue
                    key = f"{m.group(1)}_{m.group(2)}"
                else:
                    # Top level: t<N>_<M>_* files are children that were filed
                    # flat; a parent id must not prefix-match one (the t1026
                    # rule the board's find_task_by_id states).
                    key = f"{m.group(1)}_{m.group(2)}" if m.group(2) else m.group(1)
                index.setdefault(key, os.path.join(directory, name))
        self._dir_index[directory] = (identity, index)
        return index

    def _path_for(self, canonical: str) -> str | None:
        """Active location wins over archived — the precedence every surface
        already intends. Bundles are never consulted (see module docstring)."""
        if "_" in canonical:
            parent = canonical.split("_", 1)[0]
            candidates = (
                (os.path.join(self.tasks_dir, f"t{parent}"), parent),
                (os.path.join(self.archived_dir, f"t{parent}"), parent),
            )
        else:
            candidates = (
                (self.tasks_dir, None),
                (self.archived_dir, None),
            )
        for directory, child_prefix in candidates:
            hit = self._index_for(directory, child_prefix).get(canonical)
            if hit:
                return hit
        return None

    def facts(self, canonical: str | None) -> DepFacts | None:
        """Resolved facts for one canonical id, or ``None`` if unresolvable."""
        if not canonical:
            return None
        path = self._path_for(canonical)
        if path is None:
            return None
        identity = _file_identity(path)
        generation = self._generation or 1
        cached = self._facts.get(path)
        if (cached is not None and cached[0] == identity
                and cached[1] == generation and identity is not None):
            return cached[2]
        facts = self._read_facts(path, canonical)
        self._facts[path] = (identity, generation, facts)
        return facts

    def prime(self, path: str, canonical: str, text: str) -> None:
        """Seed the facts cache for a file the caller has ALREADY read.

        Without this the whole-tree scan parses each active task twice — once as
        a scan input (for its own `depends:`) and again as some other task's
        dependency. Measured on this repo, the second pass was ~250 redundant
        `parse_frontmatter` calls at ~0.55 ms each.
        """
        identity = _file_identity(path)
        if identity is None:
            return
        self._facts[path] = (identity, self._generation or 1,
                             self._facts_from_text(text, path))

    def _read_facts(self, path: str, canonical: str) -> DepFacts | None:
        try:
            with open(path, encoding="utf-8") as fh:
                text = fh.read()
        except OSError:
            return None
        return self._facts_from_text(text, path)

    def _facts_from_text(self, text: str, path: str) -> DepFacts | None:
        canonical = _canonical_from_path(path)
        parsed = parse_frontmatter(text)
        if parsed is None:
            return None
        metadata = parsed[0]
        status = str(metadata.get("status", "") or "").strip()
        decision, _pending = self._evaluator_for_cycle()(text, canonical)
        return DepFacts(status=status,
                        gate_released=(decision == "SATISFIED"),
                        path=path)

    # -- classification ----------------------------------------------------

    def classify(self, depends_raw) -> list[DepVerdict]:
        """One :class:`DepVerdict` per ``depends:`` entry, in declared order.

        Accepts the RAW frontmatter value, so a malformed field is decided here
        rather than by each caller — see :func:`read_depends`.
        """
        tokens, malformed = read_depends(depends_raw)
        return self.classify_tokens(tokens, malformed=malformed)

    def classify_tokens(self, tokens, *, malformed: bool = False
                        ) -> list[DepVerdict]:
        """:meth:`classify` for a caller that already split the field.

        ``malformed`` must carry :func:`read_depends`'s second return value; a
        caller that drops it silently converts an unreadable field into "no
        dependencies", which is the fail-open this module exists to remove.
        """
        if malformed:
            return [DepVerdict(raw=MALFORMED_TOKEN, canonical=None,
                               verdict=UNRESOLVABLE)]
        out: list[DepVerdict] = []
        for raw in tokens or []:
            canonical = canonical_dep_id(raw)
            out.append(DepVerdict(raw=str(raw), canonical=canonical,
                                  verdict=classify_facts(self.facts(canonical))))
        return out

    def classify_text(self, text: str) -> list[DepVerdict]:
        """:meth:`classify` over a task file's raw text.

        Skips the (comparatively expensive) YAML parse for a file whose
        frontmatter cannot carry a dependency — see :func:`may_have_depends`.
        """
        if not may_have_depends(text):
            return []
        parsed = parse_frontmatter(text)
        if parsed is None:
            return []
        return self.classify(parsed[0].get("depends"))


# --- Scan CLI (the bash surface) ------------------------------------------

def _iter_task_files(tasks_dir: str):
    """Every active task file, parents then children — the set ``ait ls``
    enumerates. Archived files are resolution *targets*, never scan inputs."""
    try:
        entries = sorted(os.listdir(tasks_dir))
    except OSError:
        return
    child_dirs = []
    for name in entries:
        full = os.path.join(tasks_dir, name)
        if name.endswith(".md") and re.match(r"^t\d+_", name):
            yield full
        elif re.match(r"^t\d+$", name) and os.path.isdir(full):
            child_dirs.append(full)
    for directory in child_dirs:
        try:
            kids = sorted(os.listdir(directory))
        except OSError:
            continue
        for name in kids:
            if name.endswith(".md") and re.match(r"^t\d+_\d+_", name):
                yield os.path.join(directory, name)


def scan(tasks_dir: str, registry_file: str | None, out) -> int:
    """Write ``<path>\\t<display-csv>`` for every task with a blocking dep.

    One resolver, therefore ONE registry parse and at most one ``code_digest()``
    for the whole scan — the t1472 amortization, preserved. Ends with the
    ``SCAN_OK`` trailer so the consumer can tell a real "nothing is blocked"
    from a scan that died before producing anything.
    """
    resolver = LocalDepResolver(tasks_dir, registry_file)
    resolver.begin_cycle()
    for path in _iter_task_files(tasks_dir):
        try:
            with open(path, encoding="utf-8") as fh:
                text = fh.read()
            # Prime BEFORE classifying: this file is very likely some other
            # task's dependency, and priming turns that lookup into a cache hit.
            # Only for files the pre-filter is about to parse anyway — priming
            # an unparsed one would pay the cost this scan is avoiding.
            if may_have_depends(text):
                resolver.prime(path, _canonical_from_path(path), text)
            verdicts = resolver.classify_text(text)
        except OSError as exc:
            # Per-file totality boundary, same rule as deps-unblock-batch: one
            # unreadable task file must not cost every other decision. It is
            # reported, not silently skipped.
            sys.stderr.write(f"deps-blocking-scan: {path}: {exc}\n")
            continue
        blocking = [v for v in verdicts if v.blocking]
        if not blocking:
            continue
        # Comma-joined WITHOUT a space: this string is what `ait ls` prints
        # verbatim inside `Blocked (by ...)`, and its existing output — including
        # the cross-repo ids it appends after this — uses bare commas.
        out.write("{}\t{}\n".format(
            path, ",".join(v.display() for v in blocking)))
    out.write(_TERMINAL + "\n")
    return 0


def main(argv: list[str]) -> int:
    if not argv or argv[0] != "scan":
        sys.stderr.write("Usage: dep_resolution.py scan <tasks-dir> [registry]\n")
        return 2
    if len(argv) < 2:
        sys.stderr.write("Usage: dep_resolution.py scan <tasks-dir> [registry]\n")
        return 2
    registry = argv[2] if len(argv) > 2 else None
    return scan(argv[1], registry, sys.stdout)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
