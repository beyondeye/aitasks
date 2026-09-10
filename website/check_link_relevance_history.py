#!/usr/bin/env python3
"""Replay the link-relevance detector over the history of `website/content`.

`check_link_relevance.py` sweeps one content tree. A precision question -- does a
refinement ever explain away a link the corpus later fixed? -- cannot be answered
from one sweep, because one sweep cannot tell a false positive from a true one.
The corpus's own history can: a reported link that a later commit repointed, or
whose target page later documented its subject, was a true positive, and those
edits were made by people who never saw this report. This script turns the
history into that evidence base.

It prints the distinct `(source, token, url, scope)` records seen across every
commit in the range, each with the number of sweeps it appeared in and the
subject-of-page label where the detector assigns one.

**Replay goes through `scan()`, never through `main()` or `--report`.** The CLI
runs the corpus self-controls, which key on pages a past tree does not contain;
roughly half the swept history predates them, and a replay that treated those
sweeps as unusable would silently drop every record that exists only there. So:

* the ENGINE controls (synthetic probes, valid on any tree) run once, against the
  module in use, and fail the run if any fails -- the replay is only as sound as
  the machinery it runs;
* the CORPUS controls are reported as not applicable, by name, on every run.
  Skipped is not passed, and is never printed as success.

**HEAD self-control.** `scan()` of the archived `HEAD` must equal `scan()` of the
working tree's `website/content`. Both sides use the same `scan()`, so this checks
what is specific to replay -- the archive path, the extraction, content-root
discovery. It only means something when the working tree matches `HEAD`, so it is
gated on `git status --porcelain -- website/content` being empty (not on `git
diff`, which does not see untracked files). Otherwise it is skipped, loudly, with
the differing paths named.

**A commit that cannot be replayed fails the run; it is never a skip.** Only a
commit whose tree genuinely has no `website/content` is skipped and counted --
decided by `git ls-tree`, before archiving. When the directory exists, any
`git archive` or extraction failure (a missing object in a partial or corrupt
clone, say) raises `ReplayError`: counting it as a skip would silently truncate
the aggregation this script exists to make trustworthy.

Exit status: 0 with records reported; 1 when an ENGINE control fails, the HEAD
self-control finds a mismatch, or a commit cannot be replayed; 2 on a usage
error. Never wired to CI.

Usage:
    python3 check_link_relevance_history.py                  # every commit to HEAD
    python3 check_link_relevance_history.py --range A..B     # a rev-range
    python3 check_link_relevance_history.py --repo <path>    # another repository
"""

from __future__ import annotations

import argparse
import io
import subprocess
import sys
import tarfile
import tempfile
import time
from pathlib import Path
from typing import Dict, List, NamedTuple, Optional, Tuple

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import check_link_relevance as clr  # noqa: E402

CONTENT = "website/content"

Key = Tuple[str, str, str, str]          # (source, token, url, scope)


class ReplayError(RuntimeError):
    """A commit whose content exists could not be replayed -- never a skip."""


class Row(NamedTuple):
    sweeps: int
    newest: str      # newest commit the record appears in (short sha)
    oldest: str
    subject: bool


class Replay(NamedTuple):
    rows: Dict[Key, Row]
    swept: int
    skipped: int     # commits in range whose tree had no website/content


def _git(repo: Path, *args: str, binary: bool = False) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=repo, capture_output=True,
                          text=not binary)


def _extract(repo: Path, rev: str, dest: Path) -> Optional[Path]:
    """Materialize `rev`'s website/content under `dest`.

    Returns None **only** when `rev`'s tree has no website/content -- an ordinary
    commit to skip and count. Absence is decided by `git ls-tree` *before*
    archiving, because a non-zero `git archive` cannot tell "no such path" from
    "an object it needs is missing". Once the directory is known to exist, every
    failure raises `ReplayError`.
    """
    probe = _git(repo, "ls-tree", rev, "--", CONTENT)
    if probe.returncode != 0:
        raise ReplayError(f"{rev}: git ls-tree failed: {probe.stderr.strip()}")
    if not probe.stdout.strip():
        return None
    proc = _git(repo, "archive", rev, CONTENT, binary=True)
    if proc.returncode != 0:
        detail = proc.stderr.decode(errors="replace").strip()
        raise ReplayError(f"{rev}: git archive failed although {CONTENT} "
                          f"exists: {detail}")
    try:
        with tarfile.open(fileobj=io.BytesIO(proc.stdout)) as tar:
            try:
                tar.extractall(dest, filter="data")
            except TypeError:                   # Python without extraction filters
                tar.extractall(dest)
    except (tarfile.TarError, OSError) as exc:
        raise ReplayError(f"{rev}: could not extract {CONTENT}: {exc}") from exc
    root = dest / CONTENT
    if not root.is_dir():
        raise ReplayError(f"{rev}: {CONTENT} exists but did not extract as a "
                          "directory")
    return root


def _keys(result: clr.Result) -> List[Tuple[Key, bool]]:
    # `subject` is read with a default so the harness runs against a detector
    # that does not label, too -- e.g. to freeze a baseline before a rule exists.
    return [((m.source, m.token, m.url, m.scope), bool(getattr(m, "subject", False)))
            for m in result.misses]


def replay(repo: Path, rev_range: str) -> Replay:
    proc = _git(repo, "rev-list", rev_range, "--", CONTENT)
    if proc.returncode != 0:
        raise ValueError(proc.stderr.strip() or f"bad rev-range: {rev_range}")
    rows: Dict[Key, Row] = {}
    swept = skipped = 0
    for sha in proc.stdout.split():             # newest first
        short = sha[:9]
        with tempfile.TemporaryDirectory() as tmp:
            root = _extract(repo, sha, Path(tmp))
            if root is None:
                skipped += 1
                continue
            swept += 1
            for key, subject in _keys(clr.scan(root)):
                row = rows.get(key)
                rows[key] = (Row(1, short, short, subject) if row is None else
                             row._replace(sweeps=row.sweeps + 1, oldest=short))
    return Replay(rows, swept, skipped)


def engine_controls() -> Dict[str, bool]:
    # ENGINE controls are synthetic probes: the result they are handed is unused.
    empty = clr.Result([], 0, [], {}, [])
    return clr.evaluate_controls(empty, clr.ENGINE_CONTROLS)


def head_control(repo: Path) -> Tuple[str, str]:
    """`('passed'|'skipped'|'failed', detail)` for the HEAD self-control."""
    status = _git(repo, "status", "--porcelain", "--", CONTENT)
    if status.returncode != 0:
        return "skipped", "git status failed: " + status.stderr.strip()
    dirty = [line[3:] for line in status.stdout.splitlines() if line.strip()]
    if dirty:
        return "skipped", ("website/content differs from HEAD, so the replay "
                           "path is unverified this run: " + ", ".join(dirty))
    live_root = repo / CONTENT
    if not live_root.is_dir():
        return "skipped", "HEAD has no website/content"
    with tempfile.TemporaryDirectory() as tmp:
        try:
            root = _extract(repo, "HEAD", Path(tmp))
        except ReplayError as exc:
            return "failed", str(exc)
        if root is None:
            return "failed", "git archive HEAD produced no website/content"
        archived, live = clr.scan(root), clr.scan(live_root)
        if (sorted(archived.records) == sorted(live.records)
                and sorted(archived.misses) == sorted(live.misses)):
            return "passed", f"{len(live.records)} records agree"
        return "failed", (f"archived HEAD has {len(archived.records)} records / "
                          f"{len(archived.misses)} misses, working tree has "
                          f"{len(live.records)} / {len(live.misses)}")


def _tip(repo: Path, rev_range: str) -> str:
    tip = rev_range.split("..")[-1] or "HEAD"
    proc = _git(repo, "rev-parse", "--short=9", tip)
    return proc.stdout.strip() if proc.returncode == 0 else tip


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--repo", default=str(HERE.parent),
                        help="repository to replay (default: this one)")
    parser.add_argument("--range", default="HEAD", dest="rev_range",
                        help="git rev-range to sweep (default: HEAD, i.e. all)")
    args = parser.parse_args(argv)

    repo = Path(args.repo)
    if _git(repo, "rev-parse", "--git-dir").returncode != 0:
        print(f"error: not a git repository: {repo}", file=sys.stderr)
        return 2

    started = time.monotonic()
    try:
        result = replay(repo, args.rev_range)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except ReplayError as exc:
        print(f"REPLAY FAILED -- the aggregation would be incomplete: {exc}",
              file=sys.stderr)
        return 1
    elapsed = time.monotonic() - started

    for (source, token, url, scope), row in sorted(result.rows.items()):
        label = "  [subject-of-page]" if row.subject else ""
        print(f"{row.sweeps:5}  {source}  `{token}`  ->  {url} [{scope}]{label}"
              f"   ({row.newest}..{row.oldest})")

    print(f"\nrange         : {args.rev_range}  (tip {_tip(repo, args.rev_range)})")
    print(f"commits       : {result.swept} swept, {result.skipped} skipped "
          "(no website/content)")
    print(f"distinct      : {len(result.rows)}")
    print(f"elapsed       : {elapsed:.1f}s")

    failed = False
    for name, ok in engine_controls().items():
        print(f"engine ctl    : {name}: {ok}")
        failed |= not ok
    names = ", ".join(name for name, _ in clr.CORPUS_CONTROLS)
    print(f"corpus ctl    : NOT APPLICABLE to historical trees (not run): {names}")

    verdict, detail = head_control(repo)
    print(f"head ctl      : {verdict.upper()} -- {detail}")
    failed |= verdict == "failed"

    if failed:
        print("\nFAILED CONTROL(S) -- this replay proves nothing about the history.",
              file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
