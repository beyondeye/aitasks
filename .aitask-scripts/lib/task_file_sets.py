#!/usr/bin/env python3
"""Batch task->file-set derivation over one `git log` pass (t1569_2).

Pure bucketer for `aitask_revert_analyze.sh --batch-map`. Deliberately side
effect free: no writes, no git, no subprocess. The driver owns every `git`
invocation, so the parsing and bucketing rules can be unit-tested without a
repository -- the same split `lib/followup_backfill_classify.py` uses.

The products reproduce `--task-files` (which stays the oracle) for every task
id, at whole-corpus cost instead of per-id cost. Four properties are
load-bearing and each one is a silent-wrong-answer bug if dropped:

1. **Framing is NUL-only, and the parse fails closed.** A `\\x1e`/`\\x1f`
   framing is not collision-safe: a git path may contain any byte but NUL and
   `/`, and a commit message may contain arbitrary control bytes. NUL is the
   one byte a path can never hold, and a path is never empty -- so an empty
   token is an unambiguous record marker. The hash and timestamp are validated
   on every record; a violation raises `FramingError` rather than yielding a
   plausible-looking corrupt map.

2. **Only the FIRST path token of a record carries a leading newline** (git
   emits it between the format output and the name list). Strip exactly that
   one byte from that one token -- a blanket ``.strip()`` would corrupt a path
   that legitimately begins or ends with a newline.

3. **Matching is the literal substring `(t<id>)` anywhere in the FULL commit
   message**, because the oracle greps with `--fixed-strings --grep` over the
   whole message. `%s` would silently diverge for a body-only reference, and a
   looser regex would match `(t100, t101)`, which the oracle matches for
   neither id.

4. **Parent->children expansion is disk-derived**, mirroring
   `aitask_query_files.sh all-children` (active + `archived/t<N>/` only, never
   the deep-archive tarballs). Deriving children from the commit map instead
   diverges on ~100 parents whose child task files are no longer on disk; those
   must resolve to `UNKNOWN_HISTORY`, never to a silently richer file set. The
   commit-derived expansion is still available via `children_from_commits`, but
   only ever as the separately-named, opt-in `RECOVERED_*` product.
"""

import glob
import os
import re
import sys

# Literal `(t<id>)` -- the exact form `--fixed-strings --grep="(t<id>)"` matches.
TASK_ID_RE = re.compile(rb"\(t(\d+(?:_\d+)?)\)")

_HASH_RE = re.compile(rb"^[0-9a-f]{40}$")
_CT_RE = re.compile(rb"^[0-9]+$")

#: The three-valued history status. `UNKNOWN_HISTORY` means "unrecognized by
#: the oracle's disk-derived expansion" -- NOT "no commit exists anywhere".
FILES = "FILES"
NO_FILES = "NO_FILES"
UNKNOWN_HISTORY = "UNKNOWN_HISTORY"


class FramingError(Exception):
    """The NUL framing assumption broke; no map may be emitted.

    Carries the offending token index so the driver can report
    ``FRAMING_ERROR:<token_index>`` and exit non-zero. A corrupt map that looks
    plausible is the failure this guards against, so this is never recoverable
    by guessing -- callers must abort.
    """

    def __init__(self, token_index, detail):
        super().__init__("framing violation at token %d: %s" % (token_index, detail))
        self.token_index = token_index
        self.detail = detail


class CommitRecord:
    """One commit from the batch walk: hash, commit timestamp, ids, paths."""

    __slots__ = ("sha", "committed_at", "task_ids", "paths")

    def __init__(self, sha, committed_at, task_ids, paths):
        self.sha = sha
        self.committed_at = committed_at
        self.task_ids = task_ids
        self.paths = paths


def _decode(raw_bytes):
    """Bytes -> str, preserving undecodable bytes rather than failing."""
    return raw_bytes.decode("utf-8", "surrogateescape")


def parse_log_stream(raw):
    """Parse the batch walk's stdout into `CommitRecord`s.

    Expects the output of::

        git log --all --no-renames -z --name-only \\
                --format='%x00%H%x00%ct%x00%B'

    Tokens are NUL-separated. An empty token marks a record; the next three
    tokens are positionally the hash, the commit timestamp and the full
    message (consumed positionally so an *empty* message cannot be mistaken
    for the next record marker); every token up to the following empty one is
    a path.

    Raises `FramingError` if the hash or timestamp does not validate, or if a
    non-empty token appears where a record marker is required.
    """
    if not isinstance(raw, (bytes, bytearray)):
        raise TypeError("parse_log_stream expects bytes, got %s" % type(raw).__name__)

    # Every token git emits is NUL-terminated, so a non-empty final token means
    # the stream was cut mid-token. Reject it here rather than silently keeping
    # a truncated path: a short map that looks complete is exactly the failure
    # the fail-closed contract exists to prevent.
    if raw and not bytes(raw).endswith(b"\x00"):
        raise FramingError(len(raw), "stream does not end on a NUL: truncated record")

    tokens = raw.split(b"\x00")
    total = len(tokens)
    records = []
    i = 0

    while i < total:
        if tokens[i] != b"":
            # Only reachable at the head of the stream: the paths loop below
            # always stops on an empty token or the end. A non-empty token here
            # means the stream is not the format we were promised.
            raise FramingError(i, "expected a record marker, got a non-empty token")
        # A record marker owes three header tokens PLUS the NUL that terminates
        # the format output -- so a well-formed record always leaves at least
        # four tokens after its marker, even when the message is empty and the
        # commit touched nothing (`\0sha\0ct\0\0` -> 4). Three means the
        # terminator is missing, i.e. the header was cut short; returning the
        # records parsed so far would emit a partial map that exits 0, which is
        # the "valid prefix plus truncation" case.
        #
        # Exactly zero remaining is the ONE legitimate end: the final
        # terminating NUL makes `split` yield a last empty element.
        remaining = total - i - 1
        if remaining == 0:
            break
        if remaining < 4:
            raise FramingError(
                i + 1, "incomplete record header: %d tokens after the marker" % remaining
            )

        sha, committed_at, message = tokens[i + 1], tokens[i + 2], tokens[i + 3]
        if not _HASH_RE.match(sha):
            raise FramingError(i + 1, "not a 40-hex commit hash")
        if not _CT_RE.match(committed_at):
            raise FramingError(i + 2, "not an integer commit timestamp")
        i += 4

        paths = []
        is_first_path = True
        while i < total and tokens[i] != b"":
            token = tokens[i]
            if is_first_path and token.startswith(b"\n"):
                # Exactly one byte, from exactly this token: git puts a newline
                # between the format output and the name list. Stripping more
                # (or stripping every token) would corrupt a path that
                # legitimately begins or ends with a newline.
                token = token[1:]
                is_first_path = False
            if token:
                paths.append(_decode(token))
            i += 1

        records.append(
            CommitRecord(
                sha=_decode(sha),
                committed_at=int(committed_at),
                task_ids=sorted({_decode(m) for m in TASK_ID_RE.findall(message)}),
                paths=paths,
            )
        )

    return records


def bucket_own_paths(records):
    """`task_id -> set(paths)` for each id's OWN commits (no child expansion)."""
    own = {}
    for rec in records:
        for tid in rec.task_ids:
            own.setdefault(tid, set()).update(rec.paths)
    return own


def matched_ids(records):
    """The set of ids that matched at least one commit (however empty)."""
    seen = set()
    for rec in records:
        seen.update(rec.task_ids)
    return seen


def commit_index(records):
    """`path -> [(sha, committed_at, [task_ids])]`, newest-walk order preserved.

    `committed_at` is carried from the single pass on purpose: the premise-drift
    consumer needs commit timestamps, and re-deriving them per path would
    reintroduce exactly the per-id git cost this module exists to remove.
    """
    index = {}
    for rec in records:
        for path in rec.paths:
            index.setdefault(path, []).append((rec.sha, rec.committed_at, rec.task_ids))
    return index


_CHILD_STEM_RE = re.compile(r"^t(\d+)_(\d+)_")


def children_from_disk(root, task_dir="aitasks", archived_dir=None):
    """`parent -> set(child_id)` from the SAME two globs `all-children` uses.

    Mirrors `aitask_query_files.sh cmd_all_children`: active `<task_dir>/t<N>/`
    and archived `<archived_dir>/t<N>/` only. The deep-archive tarballs are
    deliberately not consulted -- the oracle does not consult them either, and
    matching it exactly is what keeps the batch byte-equal.

    Built in one filesystem pass for the whole corpus rather than per parent;
    the per-parent shell-out is the cost this replaces.
    """
    if archived_dir is None:
        archived_dir = os.path.join(task_dir, "archived")

    kids = {}
    for base in (task_dir, archived_dir):
        pattern = os.path.join(root, base, "t*", "t*_*_*.md")
        for path in glob.glob(pattern):
            parent_dir = os.path.basename(os.path.dirname(path))
            if not parent_dir.startswith("t"):
                continue
            parent = parent_dir[1:]
            match = _CHILD_STEM_RE.match(os.path.basename(path))
            # The child file must actually belong to the directory it sits in;
            # a stray t99_1_*.md under t42/ is not one of t42's children.
            if match and match.group(1) == parent:
                kids.setdefault(parent, set()).add(
                    "%s_%s" % (match.group(1), match.group(2))
                )
    return kids


def children_from_commits(own):
    """`parent -> set(child_id)` implied by the commit map alone.

    Recovers parents whose child task files are gone from disk. This is the
    RECOVERED product only -- never the default one, and never a substitute for
    `children_from_disk`.
    """
    kids = {}
    for tid in own:
        if "_" in tid:
            kids.setdefault(tid.split("_", 1)[0], set()).add(tid)
    return kids


def paths_for(task_id, own, kids):
    """The oracle's answer for one id: its own paths, union its children's."""
    paths = set(own.get(task_id, ()))
    for child in kids.get(task_id, ()):
        paths |= own.get(child, set())
    return paths


def status_for(task_id, own, kids, seen):
    """`FILES` / `NO_FILES` / `UNKNOWN_HISTORY` for one queried id.

    `UNKNOWN_HISTORY` is emitted when neither the id nor any of its expanded
    children matched a commit -- i.e. *unrecognized by this expansion*, which
    is not the same claim as "no commit exists anywhere". Emitted for every
    queried id so no consumer ever has to infer state from an absent entry.
    """
    expansion = [task_id] + sorted(kids.get(task_id, ()))
    if not any(tid in seen for tid in expansion):
        return UNKNOWN_HISTORY
    return FILES if paths_for(task_id, own, kids) else NO_FILES


def discovered_ids(own, kids):
    """Every id this map can answer for: matched ids plus their parents."""
    ids = set(own)
    ids.update(kids)
    for tid in list(own):
        if "_" in tid:
            ids.add(tid.split("_", 1)[0])
    return ids


# --- CLI -------------------------------------------------------------------
#
# The driver (`aitask_revert_analyze.sh --batch-map`) owns every git call and
# pipes the walk in on stdin, so this stays free of subprocesses. Output is
# buffered and written only after the parse succeeds: a framing violation must
# emit no map at all, not a truncated one.


def _emit(records, tracked, kids_disk, queried, with_recovered):
    """Build the protocol lines. Returns a list of strings (no trailing \\n)."""
    own = bucket_own_paths(records)
    seen = matched_ids(records)
    ids = sorted(queried) if queried is not None else sorted(discovered_ids(own, kids_disk))

    out = []
    for tid in ids:
        for path in sorted(paths_for(tid, own, kids_disk)):
            out.append("TASKFILES:%s|%s" % (tid, path))
    for path, entries in sorted(commit_index(records).items()):
        for sha, committed_at, task_ids in entries:
            out.append("COMMIT:%s|%s|%d|%s" % (path, sha, committed_at, ",".join(task_ids)))
    for path in sorted(tracked):
        out.append("TRACKED:%s" % path)
    for tid in ids:
        out.append("STATUS:%s|%s" % (tid, status_for(tid, own, kids_disk, seen)))

    if with_recovered:
        # Separately named, opt-in, and never a substitute for the lines above.
        kids_rec = children_from_commits(own)
        for tid in ids:
            rec_paths = paths_for(tid, own, kids_rec)
            for path in sorted(rec_paths):
                out.append("RECOVERED_TASKFILES:%s|%s" % (tid, path))
        for tid in ids:
            out.append("RECOVERED_STATUS:%s|%s" % (tid, status_for(tid, own, kids_rec, seen)))
        for tid in ids:
            extra = paths_for(tid, own, kids_rec) - paths_for(tid, own, kids_disk)
            out.append("RECOVERED_DIVERGES:%s|%d" % (tid, len(extra)))
    return out


def _read_nul_file(path):
    if not path:
        return []
    with open(path, "rb") as handle:
        return [_decode(t) for t in handle.read().split(b"\x00") if t]


def _read_ids_file(path):
    if not path:
        return None
    with open(path, "r", encoding="utf-8") as handle:
        return {line.strip() for line in handle if line.strip()}


def main(argv):
    import argparse

    parser = argparse.ArgumentParser(
        prog="task_file_sets.py",
        description="Bucket one `git log` walk into the batch task->file-set map.",
    )
    parser.add_argument("--root", default=".", help="repo root for the children glob")
    parser.add_argument("--task-dir", default="aitasks")
    parser.add_argument("--archived-dir", default=None)
    parser.add_argument("--tracked-file", default=None, help="NUL-separated `git ls-files -z` output")
    parser.add_argument("--ids-file", default=None, help="newline-separated ids to report STATUS for")
    parser.add_argument("--with-recovered", action="store_true")
    args = parser.parse_args(argv)

    raw = sys.stdin.buffer.read()
    try:
        records = parse_log_stream(raw)
    except FramingError as exc:
        # No map, non-zero exit: a plausible-looking corrupt map is the failure
        # this guards against, so there is nothing safe to emit here.
        sys.stderr.write("FRAMING_ERROR:%d %s\n" % (exc.token_index, exc.detail))
        return 2

    lines = _emit(
        records,
        _read_nul_file(args.tracked_file),
        children_from_disk(args.root, args.task_dir, args.archived_dir),
        _read_ids_file(args.ids_file),
        args.with_recovered,
    )
    sys.stdout.write("".join(line + "\n" for line in lines))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
