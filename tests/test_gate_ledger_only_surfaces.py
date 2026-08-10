"""Drift guard: the RATIFIED ledger-only gate surfaces (t1416).

t1409 left four surfaces reading archival readiness from the ledger alone, while
two enforcing surfaces re-validated a human gate's code-bound signature. t1416
decided that split per surface: three now re-validate, and two are ratified
ledger-only for reasons that are **contractual, not merely cost**:

* ``gate_ledger.archive_status_from_text`` — a pure-text function (no filesystem,
  no registry, no task id), whose verdict ``trail_gather.task_record`` hashes into
  the trail's ``input_digest``. Making it code-state-dependent would flip every
  trail's staleness result on unrelated commits.
* ``monitor_core.GateSummaryCache.summary_for`` — calls ``read_task_gate_state``
  with **no registry**, so it cannot classify a human gate at all. Its cache is
  keyed on the *task file*'s ``(st_mtime_ns, st_size)``; a code change does not
  touch that file, so a digest-sensitive verdict would need the digest in the
  cache key, recomputed every 3 s tick — undoing t1111_1's per-tick-clear removal.

A split that lives only in prose grows silently. This guard makes each ledger-only
consumer a **registered, reasoned** entry, so adding one is a conscious edit.

**A guard must not contain the hole it is guarding.** Two ways a consumer could
otherwise slip past a naive scanner, both closed here:

* **Aliasing.** ``f = archive_status_from_text; f(text)`` matches no call name.
  So any *re-binding* of a watched name (aliased import, assignment, or use in a
  non-``Call.func`` position such as ``map(...)`` / ``partial(...)``) is itself a
  finding, and ``getattr`` against the gate modules is flagged.
* **A falsy registry.** ``read_task_gate_state(path, None)`` supplies an
  argument but not a registry: the callee does
  ``read_registry(registry_file) if registry_file else {}``, so an empty registry
  classifies no human gate and the call is ledger-only. An arity-only check
  ("two args ⇒ re-validates") let exactly that bypass the guard. Falsy literals
  (``None``, ``""``, ``{}``) are therefore findings, and a **bare name** — which
  could hold ``None`` — is reported as undecidable rather than assumed good.

Scope boundary, stated rather than implied: ``tests/`` is not scanned; a watched
function fetched from a runtime data structure is not statically decidable; and a
*computed* registry expression (``str(PATH)``, an f-string) is accepted as
supplying one, which is where static analysis stops being sound. That residual is
why the paired production convention — "call these directly, never aliased, and
pass a real registry path" — is documented in the functions' own docstrings and
in ``aidocs/gates/gate-guarded-archival.md``.

Run: bash tests/run_all_python_tests.sh
  or: python3 -m unittest tests.test_gate_ledger_only_surfaces -v
"""

from __future__ import annotations

import ast
import sys
import textwrap
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / ".aitask-scripts"

#: Watched in EVERY call position — these are ledger-only by construction.
WATCHED_ALWAYS = frozenset({"archive_status_from_text", "_archive_status_from_state"})

#: Watched only when called WITHOUT a registry: with one, the function
#: re-validates the signature and is not a ledger-only consumer at all.
WATCHED_WITHOUT_REGISTRY = frozenset({"read_task_gate_state"})

WATCHED = WATCHED_ALWAYS | WATCHED_WITHOUT_REGISTRY

#: Module aliases that are conventional and therefore not findings.
CONVENTIONAL_MODULE_ALIASES = frozenset({"gate_ledger", "gl"})

#: FROZEN registry of ledger-only consumers: (file, qualified caller) -> reason.
#: An entry here is a decision that this surface does NOT re-validate a
#: code-bound human-gate signature. Adding one without a reason is the drift this
#: guard exists to surface.
LEDGER_ONLY_CONSUMERS: dict[tuple[str, str], str] = {
    # --- gate_ledger's own internal composition (the canonical definitions).
    ("lib/gate_ledger.py", "archive_status"): (
        "The ENFORCING guard. Uses the ledger-only base decision, then overlays "
        "stale_signed_gates() itself — it needs the stale list merged into a "
        "declared-ORDER blocked list, not a filtered state map."),
    ("lib/gate_ledger.py", "archive_status_from_text"): (
        "The ratified pure-text twin itself. Ledger-only by contract: no "
        "filesystem/registry/task-id, and its verdict is hashed into the trail's "
        "input_digest (trail_gather.task_record)."),
    ("lib/gate_ledger.py", "read_task_gate_state"): (
        "Composes the ledger-only primitive over an ALREADY-DEMOTED state map "
        "(demote_stale_signed runs just above), so the verdict does re-validate."),

    # --- ratified external consumers.
    ("lib/stats_data.py", "collect_inflight"): (
        "Analytics scan over (filename, content) pairs; holds no path or "
        "registry. Counts 'implementation-complete but gate-blocked' from file "
        "content alone, deterministically."),
    ("lib/trail_gather.py", "_gates_pending"): (
        "Feeds task_record()['gates_pending'], which is HASHED into the trail's "
        "input_digest staleness key. A code-state-dependent verdict would flip "
        "every trail's staleness result on unrelated commits."),
    ("monitor/monitor_core.py", "GateSummaryCache.summary_for"): (
        "Passes no registry, so it cannot classify a human gate. Its cache is "
        "keyed on the TASK FILE's (st_mtime_ns, st_size); a code change does not "
        "touch that file, so re-validating would require the digest in the cache "
        "key on every 3s tick, undoing t1111_1."),
}


# --- scanner ---------------------------------------------------------------


def _qualname(stack: list[str]) -> str:
    return ".".join(stack)


def _call_name(node: ast.Call) -> str | None:
    fn = node.func
    if isinstance(fn, ast.Attribute):
        return fn.attr
    if isinstance(fn, ast.Name):
        return fn.id
    return None


def _registry_arg(node: ast.Call) -> ast.expr | None:
    """The `registry_file` argument expression, or None if not supplied."""
    if len(node.args) >= 2:
        return node.args[1]
    for k in node.keywords:
        if k.arg == "registry_file":
            return k.value
    return None


def _registry_arg_kind(node: ast.Call) -> str:
    """Classify the registry argument: absent | falsy | undecidable | supplied.

    **A supplied argument is not the same as a registry.** The callee reads
    ``read_registry(registry_file) if registry_file else {}`` — so a FALSY value
    (`None`, `""`, `{}`) produces an empty registry, which cannot classify a
    human gate, which makes the call ledger-only. Counting "arity >= 2" as
    re-validating let `read_task_gate_state(path, None)` bypass this guard
    entirely, which is the exact split-growth the guard exists to prevent.

    ``undecidable`` is a bare name whose value is invisible here (it could hold
    ``None``); it is reported on its own channel rather than as a ratified
    consumer, because "we cannot tell" is not the same answer as "ledger-only by
    design". Computed expressions (``str(PATH)``, an f-string, an attribute) are
    accepted as supplying a registry — the normal way a path is passed, and the
    line past which static analysis stops being sound.
    """
    arg = _registry_arg(node)
    if arg is None:
        return "absent"
    if isinstance(arg, ast.Constant):
        return "supplied" if arg.value else "falsy"
    if isinstance(arg, (ast.Dict, ast.List, ast.Tuple, ast.Set)):
        # An empty literal container is falsy; a non-empty one is not a path
        # either, but it is at least a deliberate value.
        return "falsy" if not getattr(arg, "elts", getattr(arg, "keys", [])) else "supplied"
    if isinstance(arg, ast.Name):
        return "undecidable"
    return "supplied"


def scan_source(source: str, relpath: str) -> tuple[dict, list[str]]:
    """Return ``({(relpath, qualname): 'call'}, [alias findings])``.

    Fails CLOSED: a file that cannot be parsed **raises** — a guard that skips
    what it cannot read is a guard that passes on a broken tree — and a call
    whose enclosing scope cannot be resolved is recorded under an
    ``UNANALYSABLE:`` key that can never compare equal to a registry entry.
    """
    tree = ast.parse(source, filename=relpath)
    sites: dict[tuple[str, str], str] = {}
    aliases: list[str] = []
    stack: list[str] = []

    class V(ast.NodeVisitor):
        def visit_ClassDef(self, node):
            stack.append(node.name)
            self.generic_visit(node)
            stack.pop()

        def visit_FunctionDef(self, node):
            stack.append(node.name)
            self.generic_visit(node)
            stack.pop()

        visit_AsyncFunctionDef = visit_FunctionDef

        # -- aliased imports
        def visit_ImportFrom(self, node):
            for a in node.names:
                if a.asname and a.name in WATCHED:
                    aliases.append(
                        f"ALIAS:{relpath}:{node.lineno}:{a.name} as {a.asname}")
            self.generic_visit(node)

        def visit_Import(self, node):
            for a in node.names:
                if (a.name.endswith("gate_ledger") and a.asname
                        and a.asname not in CONVENTIONAL_MODULE_ALIASES):
                    aliases.append(
                        f"ALIAS:{relpath}:{node.lineno}:module gate_ledger "
                        f"as {a.asname}")
            self.generic_visit(node)

        # -- calls
        def visit_Call(self, node):
            name = _call_name(node)
            if name == "getattr" and node.args:
                mod = node.args[0]
                mod_name = (mod.id if isinstance(mod, ast.Name)
                            else getattr(mod, "attr", ""))
                if mod_name in CONVENTIONAL_MODULE_ALIASES:
                    aliases.append(
                        f"ALIAS:{relpath}:{node.lineno}:getattr on {mod_name} "
                        f"(not statically decidable)")
            ledger_only = name in WATCHED_ALWAYS
            if name in WATCHED_WITHOUT_REGISTRY:
                kind = _registry_arg_kind(node)
                if kind in ("absent", "falsy"):
                    ledger_only = True
                elif kind == "undecidable":
                    aliases.append(
                        f"ALIAS:{relpath}:{node.lineno}:{name} registry argument "
                        f"is a bare name (may be None — not statically decidable)")
            if ledger_only:
                key = (relpath, _qualname(stack) or f"UNANALYSABLE:module-level:{node.lineno}")
                sites[key] = "call"
            self.generic_visit(node)

        # -- re-bindings: a watched NAME used anywhere other than as Call.func
        def visit_Name(self, node):
            if node.id in WATCHED and isinstance(node.ctx, ast.Load):
                parent = getattr(node, "_guard_parent", None)
                if not (isinstance(parent, ast.Call) and parent.func is node):
                    aliases.append(
                        f"ALIAS:{relpath}:{node.lineno}:{node.id} used outside a "
                        f"direct call")
            self.generic_visit(node)

        def visit_Attribute(self, node):
            if node.attr in WATCHED and isinstance(node.ctx, ast.Load):
                parent = getattr(node, "_guard_parent", None)
                if not (isinstance(parent, ast.Call) and parent.func is node):
                    aliases.append(
                        f"ALIAS:{relpath}:{node.lineno}:{node.attr} used outside a "
                        f"direct call")
            self.generic_visit(node)

    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            child._guard_parent = parent            # type: ignore[attr-defined]

    V().visit(tree)
    return sites, aliases


def scan_tree(root: Path) -> tuple[dict, list[str]]:
    sites: dict[tuple[str, str], str] = {}
    aliases: list[str] = []
    for path in sorted(root.rglob("*.py")):
        rel = path.relative_to(root).as_posix()
        s, a = scan_source(path.read_text(encoding="utf-8"), rel)
        sites.update(s)
        aliases.extend(a)
    return sites, aliases


REMEDIES = textwrap.dedent("""
    Remedies, in order of preference:
      1. Pass a NON-FALSY registry AND a digest so the surface RE-VALIDATES the
         signature (read_task_gate_state(path, registry_path, digest_provider))
         — then it is not a ledger-only consumer and needs no entry here.
         `registry_file=None` / "" is NOT a registry: the callee turns it into an
         empty dict, which classifies no human gate.
      2. If it must stay ledger-only, add it to LEDGER_ONLY_CONSUMERS with a
         reason saying WHY re-validation is wrong for this surface (contract, not
         convenience).
      3. If the finding is an ALIAS: call the function directly. These functions
         are documented as call-directly-never-aliased precisely because this
         guard is syntactic and an indirection defeats it.
      4. If the finding says the registry argument is a BARE NAME: the guard
         cannot see whether it holds None. Pass the path expression inline (or a
         literal) so the call is decidable — do NOT register it, because
         "undecidable" is not the same answer as "ledger-only by design".
    """).strip()


class LedgerOnlyConsumerRegistryTest(unittest.TestCase):
    def test_registered_consumers_match_the_source_tree(self):
        sites, _ = scan_tree(SCRIPTS_DIR)
        self.assertTrue(sites, "no call sites found — the scan would pass vacuously")
        self.assertEqual(
            set(sites), set(LEDGER_ONLY_CONSUMERS),
            "ledger-only gate consumers drifted from the registry.\n" + REMEDIES)

    def test_every_registry_entry_carries_a_reason(self):
        for key, reason in LEDGER_ONLY_CONSUMERS.items():
            self.assertGreater(len(reason), 40,
                               f"{key} needs a real reason, not a placeholder")

    def test_no_aliases_in_the_source_tree(self):
        _, aliases = scan_tree(SCRIPTS_DIR)
        self.assertEqual(aliases, [],
                         "watched gate functions must be called directly.\n" + REMEDIES)


class ScannerDiscriminationTest(unittest.TestCase):
    """Negative controls — each over a synthetic source, never the live tree."""

    def test_a_new_ledger_only_consumer_is_caught(self):
        src = textwrap.dedent("""
            from gate_ledger import archive_status_from_text

            def some_new_report(text):
                return archive_status_from_text(text)[0]
        """)
        sites, aliases = scan_source(src, "lib/newthing.py")
        self.assertEqual(set(sites), {("lib/newthing.py", "some_new_report")})
        self.assertEqual(aliases, [])
        self.assertNotIn(("lib/newthing.py", "some_new_report"), LEDGER_ONLY_CONSUMERS)

    def test_an_aliased_consumer_is_caught(self):
        """The control that proves the alias hole is closed, not documented away."""
        src = textwrap.dedent("""
            from gate_ledger import archive_status_from_text

            def sneaky(text):
                f = archive_status_from_text
                return f(text)[0]
        """)
        sites, aliases = scan_source(src, "lib/sneaky.py")
        self.assertEqual(sites, {}, "the call-name pass alone cannot see this")
        self.assertEqual(len(aliases), 1, f"alias pass missed the re-binding: {aliases}")
        self.assertIn("used outside a direct call", aliases[0])

    def test_an_aliased_import_is_caught(self):
        src = "from gate_ledger import archive_status_from_text as _asft\n"
        _, aliases = scan_source(src, "lib/x.py")
        self.assertEqual(len(aliases), 1)
        self.assertIn("as _asft", aliases[0])

    def test_a_functional_use_is_caught(self):
        src = textwrap.dedent("""
            from gate_ledger import archive_status_from_text

            def bulk(texts):
                return list(map(archive_status_from_text, texts))
        """)
        _, aliases = scan_source(src, "lib/bulk.py")
        self.assertEqual(len(aliases), 1)

    def test_getattr_indirection_is_flagged(self):
        src = textwrap.dedent("""
            import gate_ledger as gl

            def dynamic(name, text):
                return getattr(gl, name)(text)
        """)
        _, aliases = scan_source(src, "lib/dyn.py")
        self.assertEqual(len(aliases), 1)
        self.assertIn("not statically decidable", aliases[0])

    def test_a_registry_bearing_call_is_NOT_a_finding(self):
        """The discriminating case: re-validating callers must not be flagged.

        A *decidably non-falsy* registry argument. A bare name is deliberately
        NOT used here — that is the undecidable case with its own test below,
        and letting it stand for "supplied" is what the arity-only check got
        wrong.
        """
        src = textwrap.dedent("""
            import gate_ledger

            def board_like(path, provider):
                return gate_ledger.read_task_gate_state(
                    path, "aitasks/metadata/gates.yaml", provider)
        """)
        sites, aliases = scan_source(src, "board/x.py")
        self.assertEqual(sites, {})
        self.assertEqual(aliases, [])

    def test_a_registryless_call_IS_a_finding(self):
        src = textwrap.dedent("""
            import gate_ledger

            def monitor_like(path):
                return gate_ledger.read_task_gate_state(path)
        """)
        sites, _ = scan_source(src, "monitor/x.py")
        self.assertEqual(set(sites), {("monitor/x.py", "monitor_like")})

    def test_positional_None_registry_IS_a_finding(self):
        """`read_task_gate_state(path, None)` is ledger-only, not re-validating.

        The callee does `read_registry(registry_file) if registry_file else {}`,
        so a falsy argument yields an EMPTY registry — no human gate can be
        classified and no signature re-validated. An arity-only check counted
        this as re-validating and let a new consumer bypass the guard entirely.
        """
        src = textwrap.dedent("""
            import gate_ledger

            def sneaky(path):
                return gate_ledger.read_task_gate_state(path, None)
        """)
        sites, _ = scan_source(src, "lib/sneaky.py")
        self.assertEqual(set(sites), {("lib/sneaky.py", "sneaky")})

    def test_keyword_None_registry_IS_a_finding(self):
        src = textwrap.dedent("""
            import gate_ledger

            def sneaky_kw(path):
                return gate_ledger.read_task_gate_state(path, registry_file=None)
        """)
        sites, _ = scan_source(src, "lib/sneaky_kw.py")
        self.assertEqual(set(sites), {("lib/sneaky_kw.py", "sneaky_kw")})

    def test_empty_string_registry_IS_a_finding(self):
        src = textwrap.dedent("""
            import gate_ledger

            def empty_str(path):
                return gate_ledger.read_task_gate_state(path, "")
        """)
        sites, _ = scan_source(src, "lib/empty.py")
        self.assertEqual(set(sites), {("lib/empty.py", "empty_str")})

    def test_a_bare_name_registry_is_undecidable_not_silently_accepted(self):
        """`reg` could hold None, so "supplied" cannot be concluded.

        Reported on the undecidable channel rather than registered as a ratified
        consumer: "we cannot tell" is a different answer from "ledger-only by
        design", and conflating them would let a real hole be waved through with
        a plausible-looking registry entry.
        """
        src = textwrap.dedent("""
            import gate_ledger

            def maybe(path, reg):
                return gate_ledger.read_task_gate_state(path, reg)
        """)
        sites, aliases = scan_source(src, "lib/maybe.py")
        self.assertEqual(sites, {})
        self.assertEqual(len(aliases), 1)
        self.assertIn("not statically decidable", aliases[0])

    def test_a_computed_registry_path_is_accepted(self):
        """The board's real shape: `str(GATES_REGISTRY_FILE)` must not be flagged."""
        src = textwrap.dedent("""
            import gate_ledger

            def board_like(path, provider):
                return gate_ledger.read_task_gate_state(
                    path, str(GATES_REGISTRY_FILE), provider)
        """)
        sites, aliases = scan_source(src, "board/x.py")
        self.assertEqual(sites, {})
        self.assertEqual(aliases, [])

    def test_an_unparsable_file_raises_rather_than_skipping(self):
        with self.assertRaises(SyntaxError):
            scan_source("def broken(:\n", "lib/broken.py")

    def test_module_level_call_is_unanalysable_not_silently_dropped(self):
        sites, _ = scan_source("from gate_ledger import archive_status_from_text\n"
                               "archive_status_from_text('x')\n", "lib/top.py")
        key = next(iter(sites))
        self.assertTrue(key[1].startswith("UNANALYSABLE:"),
                        "a call outside any function must not vanish from the scan")


if __name__ == "__main__":
    unittest.main()
