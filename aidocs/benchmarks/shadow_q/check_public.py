#!/usr/bin/env python3
"""Refuse to publish private aitasks_go text through the public aitasks repo.

Two rules, applied to every PUBLIC experiment file (by default the staged or
working-tree copies of ``aidocs/benchmarks/shadow_q/**`` and
``tests/test_shadow_q_harness.py``):

1. **Shared lines.** Any whitespace-normalised line of >= 40 characters that
   also occurs in the store's *private-origin* text is a hit.
   - Private origin: fixtures, instructions, notes, judge texts, and the raw
     streams' answers and helper/task outputs.
   - The raw streams are decoded; tool outputs of **skill-file reads** are left
     out, since that text came from public skill files, as recorded by the
     store's own trace.
   - Lines that also occur in a **HEAD-committed** public source (the seed
     instructions, the tracked `.claude/skills/**` / `.agents/skills/**`
     sources) are exempt.
   - Exemptions never come from the files being checked: the candidate
     publication cannot certify its own text.
2. **Leak terms.** Each term in the store's ``leak_terms.txt`` is searched for
   as a whole word (case-sensitive).

Exit 0 when clean, 1 on any hit, 2 on a usage or environment error. Hits are
printed as ``LEAK:<public path>:<line>:<rule>:<detail>``.

    python3 aidocs/benchmarks/shadow_q/check_public.py [--store DIR] [--staged]
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from store import REPO, resolve_store  # noqa: E402

MIN_LEN = 40
DEFAULT_PUBLIC = ("aidocs/benchmarks/shadow_q", "tests/test_shadow_q_harness.py")
# HEAD-committed sources that are public independently of this experiment's files.
KNOWN_PUBLIC_PREFIXES = ("seed/aitasks_agent_instructions.seed.md", ".claude/skills/", ".agents/skills/")
SKILL_PATH_RX = re.compile(r"\.(?:claude|agents)/skills/")
# Store parts that are public-origin or ids only: never part of the private corpus.
NON_PRIVATE_STORE_PARTS = ("skill_listing",)
NON_PRIVATE_STORE_FILES = ("meta.json", "answers.json", "blind_map.json")
_WS = re.compile(r"\s+")


def normalise(line: str) -> str:
    return _WS.sub(" ", line).strip()


def _strings(obj):
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for v in obj.values():
            yield from _strings(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _strings(v)


def text_lines(path: Path) -> list[str]:
    try:
        raw = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return []
    lines: list[str] = []
    if path.suffix in (".jsonl", ".json"):
        for row in raw.splitlines():
            try:
                obj = json.loads(row)
            except ValueError:
                lines.append(row)
                continue
            for s in _strings(obj):
                lines.extend(s.splitlines())
        if path.suffix == ".json":
            try:
                for s in _strings(json.loads(raw)):
                    lines.extend(s.splitlines())
            except ValueError:
                pass
    else:
        lines = raw.splitlines()
    return lines


_KEY_PREFIX = re.compile(r'^"?[\w.-]+"?\s*:\s*')


def identifier_only(n: str) -> bool:
    """A (key: )value line whose value has no whitespace: an id, hash or path, never prose.

    Harness-generated identifiers (trial ids, run ids) legitimately appear in both the
    store and the public numbers-only records. Prose leaks always contain spaces;
    distinctive single-token identifiers are covered by ``leak_terms.txt`` instead.
    """
    rest = _KEY_PREFIX.sub("", n, count=1).strip().rstrip(",").strip('"')
    return " " not in rest


def line_set(paths) -> set[str]:
    out: set[str] = set()
    for p in paths:
        for ln in text_lines(p):
            n = normalise(ln)
            if len(n) >= MIN_LEN and not identifier_only(n):
                out.add(n)
    return out


def load_terms(store: Path) -> list[str]:
    f = store / "leak_terms.txt"
    if not f.is_file():
        return []
    terms = []
    for ln in f.read_text(encoding="utf-8").splitlines():
        ln = ln.split("#", 1)[0].strip() if not ln.lstrip().startswith("#") else ""
        if ln:
            terms.append(ln)
    return terms


def term_regex(term: str) -> re.Pattern:
    # "Whole word": not preceded/followed by a word character.
    return re.compile(r"(?<![\w])" + re.escape(term) + r"(?![\w])")


def public_files(repo: Path, roots, staged: bool) -> dict[str, str]:
    """Map repo-relative path -> text, for the public files under ``roots``."""
    out: dict[str, str] = {}
    if staged:
        names = subprocess.run(
            ["git", "-C", str(repo), "diff", "--cached", "--name-only", "--diff-filter=ACMR", "--", *roots],
            capture_output=True, text=True, check=True,
        ).stdout.split()
        for n in names:
            blob = subprocess.run(
                ["git", "-C", str(repo), "show", f":{n}"], capture_output=True, check=True
            ).stdout
            try:
                out[n] = blob.decode("utf-8")
            except UnicodeDecodeError:
                continue
        return out
    for r in roots:
        p = repo / r
        files = [p] if p.is_file() else sorted(x for x in p.rglob("*") if x.is_file()) if p.is_dir() else []
        for f in files:
            try:
                out[str(f.relative_to(repo))] = f.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
    return out


def known_public_lines(repo: Path) -> set[str]:
    """Lines of HEAD-committed public sources, read from git objects, never the working tree."""
    names = subprocess.run(["git", "-C", str(repo), "ls-tree", "-r", "--name-only", "HEAD"],
                           capture_output=True, text=True, check=True).stdout.splitlines()
    names = [n for n in names if n.startswith(KNOWN_PUBLIC_PREFIXES)]
    out: set[str] = set()
    if not names:
        return out
    batch = subprocess.run(["git", "-C", str(repo), "cat-file", "--batch"],
                           input="".join(f"HEAD:{n}\n" for n in names).encode(), capture_output=True, check=True).stdout
    i = 0
    while i < len(batch):
        nl = batch.index(b"\n", i)
        header = batch[i:nl].split()
        if len(header) < 3 or header[1] != b"blob":
            i = nl + 1
            continue
        size = int(header[2])
        body = batch[nl + 1:nl + 1 + size]
        i = nl + 1 + size + 1
        try:
            text = body.decode("utf-8")
        except UnicodeDecodeError:
            continue
        for ln in text.splitlines():
            n = normalise(ln)
            if len(n) >= MIN_LEN and not identifier_only(n):
                out.add(n)
    return out


def _stream_private_lines(path: Path) -> list[str]:
    """A raw CLI stream, decoded generically (every string counts: fail-safe), minus the text
    the subject received from **skill-file reads**: that text is public by origin, as the
    store's own trace shows. Unknown event shapes therefore stay private."""
    import validate as V
    agent = "claude" if ("-claude-" in str(path) or ".claude." in path.name) else "codex"
    events = V.parse(agent, path.read_text(encoding="utf-8", errors="replace"))
    public_origin: set[str] = set()
    for e in events:
        if e.kind != "tool":
            continue
        target = e.command or str(e.input.get("file_path", ""))
        if SKILL_PATH_RX.search(target) and not re.search(r"aitask_shadow_(capture|context)", target):
            for ln in (e.output or "").splitlines():
                public_origin.add(normalise(re.sub(r"^\s*\d+\t", "", ln)))
    out = []
    for ln in text_lines(path):
        n = normalise(re.sub(r"^\s*\d+\t", "", ln))
        if n not in public_origin:
            out.append(ln)
    return out


def private_lines(store: Path) -> set[str]:
    out: set[str] = set()
    for p in store.rglob("*"):
        if not p.is_file() or ".git" in p.parts:
            continue
        rel = p.relative_to(store)
        if rel.parts and rel.parts[0] in NON_PRIVATE_STORE_PARTS or p.name in NON_PRIVATE_STORE_FILES:
            continue
        lines = _stream_private_lines(p) if p.name.endswith(".stdout.jsonl") else text_lines(p)
        for ln in lines:
            n = normalise(ln)
            if len(n) >= MIN_LEN and not identifier_only(n):
                out.add(n)
    return out


def scan(public: dict[str, str], store: Path, repo: Path = REPO,
         known_public: set[str] | None = None) -> list[str]:
    private = private_lines(store)
    if known_public is None:
        known_public = known_public_lines(repo)
    private -= known_public
    terms = [(t, term_regex(t)) for t in load_terms(store)]
    hits: list[str] = []
    for rel, text in sorted(public.items()):
        for i, ln in enumerate(text.splitlines(), start=1):
            n = normalise(ln)
            if len(n) >= MIN_LEN and n in private:
                hits.append(f"LEAK:{rel}:{i}:shared_line:{n[:60]}")
            for t, rx in terms:
                if rx.search(ln):
                    hits.append(f"LEAK:{rel}:{i}:leak_term:{t}")
    return hits


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--store", help="private store root (default: resolve aitasks_go)")
    ap.add_argument("--staged", action="store_true", help="scan the git index instead of the working tree")
    ap.add_argument("paths", nargs="*", help="public roots (default: the experiment dir + its test)")
    args = ap.parse_args(argv)
    try:
        store = resolve_store(args.store)
    except SystemExit as exc:
        print(f"ERROR:{exc}", file=sys.stderr)
        return 2
    if not store.is_dir():
        print(f"ERROR:store not found: {store}", file=sys.stderr)
        return 2
    public = public_files(REPO, args.paths or DEFAULT_PUBLIC, args.staged)
    hits = scan(public, store)
    for h in hits:
        print(h)
    print(f"SCANNED:{len(public)} public file(s); {len(hits)} hit(s)")
    return 1 if hits else 0


if __name__ == "__main__":
    raise SystemExit(main())
